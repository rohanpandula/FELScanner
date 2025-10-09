import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

from plexapi.server import PlexServer

log = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _safe_getattr(obj: Any, attr: str, default: Any = None) -> Any:
    """Return attribute value if present, otherwise default."""
    return getattr(obj, attr, default)


class MetadataCache:
    """Simple JSON-backed cache for movie metadata."""

    def __init__(self, cache_path: str):
        self._cache_path = cache_path
        self._lock = threading.RLock()
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self._cache_path):
            return {"_meta": {"last_summary_refresh": None}, "movies": {}}
        try:
            with open(self._cache_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid cache format")
        except Exception as exc:
            log.warning("Failed to load metadata cache %s: %s", self._cache_path, exc)
            return {"_meta": {"last_summary_refresh": None}, "movies": {}}

        payload.setdefault("_meta", {}).setdefault("last_summary_refresh", None)
        payload.setdefault("movies", {})
        return payload

    def _persist(self) -> None:
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        tmp_path = f"{self._cache_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, self._cache_path)

    def get_last_summary_refresh(self) -> Optional[str]:
        with self._lock:
            return self._data.get("_meta", {}).get("last_summary_refresh")

    def set_last_summary_refresh(self, value: str) -> None:
        with self._lock:
            self._data.setdefault("_meta", {})["last_summary_refresh"] = value
            self._persist()

    def get_movie(self, rating_key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            movie = self._data.get("movies", {}).get(str(rating_key))
            if movie:
                return json.loads(json.dumps(movie))
            return None

    def list_movies(self) -> List[Dict[str, Any]]:
        with self._lock:
            movies = self._data.get("movies", {})
            return [json.loads(json.dumps(movie)) for movie in movies.values()]

    def upsert_movie(self, payload: Dict[str, Any]) -> None:
        rating_key = str(payload.get("ratingKey"))
        if not rating_key:
            raise ValueError("Payload missing ratingKey")

        with self._lock:
            movies = self._data.setdefault("movies", {})
            existing = movies.get(rating_key)
            if existing:
                payload = self._merge_movies(existing, payload)
            movies[rating_key] = payload
            self._persist()

    def bulk_upsert(self, movies: List[Dict[str, Any]]) -> None:
        with self._lock:
            store = self._data.setdefault("movies", {})
            for movie in movies:
                key = str(movie.get("ratingKey"))
                if not key:
                    continue
                existing = store.get(key)
                if existing:
                    movie = self._merge_movies(existing, movie)
                store[key] = movie
            self._persist()

    @staticmethod
    def _merge_movies(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        merged = existing.copy()
        merged.update({k: v for k, v in incoming.items() if k != "versions"})

        existing_versions = existing.get("versions", [])
        incoming_versions = incoming.get("versions", [])
        merged["versions"] = MetadataCache._merge_versions(existing_versions, incoming_versions)

        # Preserve detail metadata if the incoming payload does not include a refresh timestamp
        detail_ts = incoming.get("detailRefreshedAt")
        if not detail_ts and existing.get("detailRefreshedAt"):
            merged["detailRefreshedAt"] = existing["detailRefreshedAt"]
        return merged

    @staticmethod
    def _merge_versions(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_id = {str(item.get("id")): item for item in existing if item.get("id") is not None}

        merged_versions: List[Dict[str, Any]] = []
        for version in incoming:
            version_id = str(version.get("id"))
            previous = by_id.get(version_id)
            if previous:
                merged_version = previous.copy()
                merged_version.update({k: v for k, v in version.items() if k != "parts"})
                merged_version["parts"] = MetadataCache._merge_parts(previous.get("parts", []), version.get("parts", []))
            else:
                merged_version = version
            merged_versions.append(merged_version)
        return merged_versions

    @staticmethod
    def _merge_parts(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_id = {str(item.get("id")): item for item in existing if item.get("id") is not None}
        merged_parts: List[Dict[str, Any]] = []
        for part in incoming:
            part_id = str(part.get("id"))
            previous = by_id.get(part_id)
            if previous:
                merged_part = previous.copy()
                merged_part.update(part)
                if previous.get("ffprobe") and not part.get("ffprobe"):
                    merged_part["ffprobe"] = previous["ffprobe"]
                if previous.get("streamSummary") and not part.get("streamSummary"):
                    merged_part["streamSummary"] = previous["streamSummary"]
            else:
                merged_part = part
            merged_parts.append(merged_part)
        return merged_parts


class MetadataService:
    """Fetch and cache metadata for Plex movies, including ffprobe analysis."""

    def __init__(
        self,
        cache_path: str,
        plex_url: Optional[str] = None,
        plex_token: Optional[str] = None,
        library_name: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
        summary_ttl_seconds: int = 3600,
        ffprobe_timeout: int = 30,
    ):
        self._cache = MetadataCache(cache_path)
        self._plex_url = plex_url
        self._plex_token = plex_token
        self._library_name = library_name
        self._ffprobe_path = ffprobe_path or "ffprobe"
        self._summary_ttl_seconds = summary_ttl_seconds
        self._ffprobe_timeout = ffprobe_timeout

        self._plex: Optional[PlexServer] = None
        self._plex_lock = threading.RLock()

    # Configuration management -------------------------------------------------

    def update_config(
        self,
        plex_url: Optional[str],
        plex_token: Optional[str],
        library_name: Optional[str],
        ffprobe_path: Optional[str] = None,
    ) -> None:
        with self._plex_lock:
            config_changed = (plex_url != self._plex_url) or (plex_token != self._plex_token)
            self._plex_url = plex_url
            self._plex_token = plex_token
            self._library_name = library_name
            if ffprobe_path:
                self._ffprobe_path = ffprobe_path
            if config_changed:
                self._plex = None

    def is_configured(self) -> bool:
        return bool(self._plex_url and self._plex_token and self._library_name)

    @property
    def ffprobe_path(self) -> str:
        return self._ffprobe_path

    # Public API ----------------------------------------------------------------

    def list_movies(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Return cached movie summaries, refreshing from Plex when needed."""
        if force_refresh or self._summary_cache_expired():
            try:
                summaries = self._fetch_library_summaries()
                self._cache.bulk_upsert(summaries)
                self._cache.set_last_summary_refresh(_utcnow_iso())
            except Exception as exc:
                log.error("Failed to refresh Plex metadata summaries: %s", exc, exc_info=True)
        return self._cache.list_movies()

    def summary_refreshed_at(self) -> Optional[str]:
        return self._cache.get_last_summary_refresh()

    def get_movie(self, rating_key: str, refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific movie, optionally refreshing."""
        if refresh:
            try:
                movie = self._fetch_movie_detail(rating_key)
                self._cache.upsert_movie(movie)
                return movie
            except Exception as exc:
                log.error("Failed to refresh metadata for ratingKey %s: %s", rating_key, exc, exc_info=True)
                cached = self._cache.get_movie(rating_key) or {}
                cached["detailError"] = str(exc)
                cached["detailRefreshedAt"] = _utcnow_iso()
                self._cache.upsert_movie(cached)
                return cached

        cached_movie = self._cache.get_movie(rating_key)
        if cached_movie:
            return cached_movie

        try:
            movie = self._fetch_movie_detail(rating_key)
            self._cache.upsert_movie(movie)
            return movie
        except Exception as exc:
            log.error("Unable to fetch metadata for ratingKey %s: %s", rating_key, exc, exc_info=True)
            return None

    # Internal helpers ---------------------------------------------------------

    def _summary_cache_expired(self) -> bool:
        ts = self._cache.get_last_summary_refresh()
        if not ts:
            return True
        try:
            last = datetime.fromisoformat(ts)
        except ValueError:
            return True
        delta = datetime.now(timezone.utc) - last
        return delta.total_seconds() > self._summary_ttl_seconds

    def _fetch_library_summaries(self) -> List[Dict[str, Any]]:
        library = self._get_library()
        movies = []
        for movie in library.all():
            try:
                movies.append(self._normalize_movie(movie, include_ffprobe=False))
            except Exception as exc:
                log.warning("Failed to normalize movie %s (%s): %s", getattr(movie, "title", "unknown"), getattr(movie, "ratingKey", "?"), exc)
        return movies

    def _fetch_movie_detail(self, rating_key: str) -> Dict[str, Any]:
        plex = self._get_plex()
        if not plex:
            raise RuntimeError("Plex is not configured")
        item = plex.fetchItem(int(rating_key) if str(rating_key).isdigit() else rating_key)
        return self._normalize_movie(item, include_ffprobe=True)

    def _get_plex(self) -> Optional[PlexServer]:
        if not self._plex_url or not self._plex_token:
            return None
        with self._plex_lock:
            if self._plex is None:
                log.info("Connecting to Plex at %s", self._plex_url)
                self._plex = PlexServer(self._plex_url, self._plex_token)
        return self._plex

    def _get_library(self):
        plex = self._get_plex()
        if not plex:
            raise RuntimeError("Plex is not configured")
        if not self._library_name:
            raise RuntimeError("Plex library name is not configured")
        return plex.library.section(self._library_name)

    def _normalize_movie(self, movie, include_ffprobe: bool) -> Dict[str, Any]:
        stream_lookup: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        if include_ffprobe:
            stream_lookup = self._fetch_streams_map(movie)

        payload: Dict[str, Any] = {
            "ratingKey": _safe_getattr(movie, "ratingKey"),
            "title": _safe_getattr(movie, "title"),
            "year": _safe_getattr(movie, "year"),
            "summary": _safe_getattr(movie, "summary"),
            "thumb": _safe_getattr(movie, "thumb"),
            "art": _safe_getattr(movie, "art"),
            "guid": _safe_getattr(movie, "guid"),
            "studio": _safe_getattr(movie, "studio"),
            "tagline": _safe_getattr(movie, "tagline"),
            "genres": [g.tag for g in _safe_getattr(movie, "genres", []) if getattr(g, "tag", None)],
            "collections": [c.tag for c in _safe_getattr(movie, "collections", []) if getattr(c, "tag", None)],
            "addedAt": self._datetime_to_iso(_safe_getattr(movie, "addedAt")),
            "updatedAt": self._datetime_to_iso(_safe_getattr(movie, "updatedAt")),
            "summaryRefreshedAt": _utcnow_iso(),
        }

        versions = []
        for media in _safe_getattr(movie, "media", []):
            version = {
                "id": _safe_getattr(media, "id"),
                "duration": _safe_getattr(media, "duration"),
                "bitrate": _safe_getattr(media, "bitrate"),
                "container": _safe_getattr(media, "container"),
                "videoResolution": _safe_getattr(media, "videoResolution"),
                "videoCodec": _safe_getattr(media, "videoCodec"),
                "audioCodec": _safe_getattr(media, "audioCodec"),
                "audioChannels": _safe_getattr(media, "audioChannels"),
                "height": _safe_getattr(media, "height"),
                "width": _safe_getattr(media, "width"),
                "aspectRatio": _safe_getattr(media, "aspectRatio"),
                "parts": [],
            }
            media_streams = stream_lookup.get(str(version["id"])) if stream_lookup else None
            for part in _safe_getattr(media, "parts", []):
                version["parts"].append(self._normalize_part(part, include_ffprobe, media_streams))
            versions.append(version)

        for version in versions:
            self._summarize_version_features(version)

        payload["versions"] = versions
        if include_ffprobe:
            payload["detailRefreshedAt"] = _utcnow_iso()
        return payload

    def _normalize_part(
        self,
        part,
        include_ffprobe: bool,
        media_streams: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        normalized = {
            "id": _safe_getattr(part, "id"),
            "file": _safe_getattr(part, "file"),
            "size": _safe_getattr(part, "size"),
            "duration": _safe_getattr(part, "duration"),
            "container": _safe_getattr(part, "container"),
            "accessedAt": self._datetime_to_iso(_safe_getattr(part, "accessedAt")),
            "exists": _safe_getattr(part, "exists"),
            "streamSummary": None,
            "ffprobe": None,
            "ffprobeError": None,
            "plexStreams": [],
        }

        if media_streams:
            part_streams = media_streams.get(str(normalized["id"]))
            if part_streams:
                normalized["plexStreams"] = part_streams

        if include_ffprobe and normalized.get("file"):
            try:
                probe = self._run_ffprobe(normalized["file"])
                normalized["ffprobe"] = probe
                normalized["streamSummary"] = self._summarize_streams(probe)
            except Exception as exc:
                normalized["ffprobeError"] = str(exc)
        return normalized

    def _run_ffprobe(self, file_path: str) -> Dict[str, Any]:
        import subprocess

        cmd = [
            self._ffprobe_path,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            file_path,
        ]
        start = time.time()
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
            timeout=self._ffprobe_timeout,
        )
        duration = time.time() - start
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed ({result.returncode}) after {duration:.1f}s: {result.stderr.strip()}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Unable to parse ffprobe output: {exc}") from exc

    def _summarize_streams(self, probe: Dict[str, Any]) -> Dict[str, Any]:
        streams = probe.get("streams", [])
        format_info = probe.get("format", {})

        video_streams = []
        audio_streams = []
        subtitle_streams = []

        for stream in streams:
            codec_type = stream.get("codec_type")
            base = {
                "id": stream.get("index"),
                "codec": stream.get("codec_name"),
                "codecLong": stream.get("codec_long_name"),
                "language": stream.get("tags", {}).get("language"),
                "title": stream.get("tags", {}).get("title"),
            }
            if codec_type == "video":
                video_streams.append(
                    {
                        **base,
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "profile": stream.get("profile"),
                        "pixFmt": stream.get("pix_fmt"),
                        "colorPrimaries": stream.get("color_primaries"),
                        "colorTransfer": stream.get("color_transfer"),
                        "colorSpace": stream.get("color_space"),
                        "bitDepth": stream.get("bits_per_raw_sample") or stream.get("bits_per_sample"),
                    }
                )
            elif codec_type == "audio":
                audio_streams.append(
                    {
                        **base,
                        "channels": stream.get("channels"),
                        "channelLayout": stream.get("channel_layout"),
                        "sampleRate": stream.get("sample_rate"),
                        "bitRate": stream.get("bit_rate") or format_info.get("bit_rate"),
                    }
                )
            elif codec_type in ("subtitle", "text"):
                subtitle_streams.append(
                    {
                        **base,
                        "hearingImpaired": stream.get("disposition", {}).get("hearing_impaired") == 1,
                        "forced": stream.get("disposition", {}).get("forced") == 1,
                    }
                )

        return {
            "format": {
                "filename": format_info.get("filename"),
                "duration": format_info.get("duration"),
                "size": format_info.get("size"),
                "bitRate": format_info.get("bit_rate"),
                "tags": format_info.get("tags", {}),
            },
            "video": video_streams,
            "audio": audio_streams,
            "subtitles": subtitle_streams,
        }

    @staticmethod
    def _datetime_to_iso(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

    def _fetch_streams_map(self, movie) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        plex = self._get_plex()
        if not plex:
            return {}

        try:
            element = plex._server.query(f"{movie.key}?checkFiles=1&includeAllStreams=1")
        except Exception as exc:
            log.debug("Failed to fetch stream XML for %s: %s", getattr(movie, "ratingKey", "?"), exc)
            return {}

        stream_map: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for video_el in element.iter("Video"):
            for media_el in video_el.findall("Media"):
                media_id = media_el.get("id")
                if not media_id:
                    continue
                part_map: Dict[str, List[Dict[str, Any]]] = {}
                for part_el in media_el.findall("Part"):
                    part_id = part_el.get("id")
                    if not part_id:
                        continue
                    streams = [self._normalize_stream_xml(stream_el) for stream_el in part_el.findall("Stream")]
                    part_map[part_id] = streams
                if part_map:
                    stream_map[media_id] = part_map
        return stream_map

    @staticmethod
    def _normalize_stream_xml(stream_el: ElementTree.Element) -> Dict[str, Any]:
        stream_type_map = {
            "1": "video",
            "2": "audio",
            "3": "subtitle",
            "4": "lyrics",
        }
        stream_type = stream_el.get("streamType")
        data: Dict[str, Any] = {
            "id": stream_el.get("id"),
            "type": stream_type_map.get(stream_type, stream_type),
            "codec": stream_el.get("codec"),
            "profile": stream_el.get("profile"),
            "displayTitle": stream_el.get("displayTitle"),
            "extendedDisplayTitle": stream_el.get("extendedDisplayTitle"),
            "language": stream_el.get("language") or stream_el.get("languageTag"),
            "languageCode": stream_el.get("languageCode"),
            "channels": stream_el.get("channels"),
            "audioChannelLayout": stream_el.get("audioChannelLayout"),
            "bitDepth": stream_el.get("bitDepth"),
            "bitrate": stream_el.get("bitrate"),
            "frameRate": stream_el.get("frameRate"),
            "width": stream_el.get("width"),
            "height": stream_el.get("height"),
            "hdr": stream_el.get("hdr"),
            "colorSpace": stream_el.get("colorSpace"),
            "colorTrc": stream_el.get("colorTrc"),
            "colorPrimaries": stream_el.get("colorPrimaries"),
            "colorRange": stream_el.get("colorRange"),
            "title": stream_el.get("title"),
            "forced": stream_el.get("forced") == "1",
            "hearingImpaired": stream_el.get("hearingImpaired") == "1",
        }

        if stream_type == "1":  # video
            dolby_present = stream_el.get("DOVIPresent") == "1"
            data["dolbyVision"] = {
                "present": dolby_present,
                "profile": stream_el.get("DOVIProfile"),
                "level": stream_el.get("DOVILevel"),
                "version": stream_el.get("DOVIVersion"),
                "rpu": stream_el.get("DOVIRPUPresent") == "1" if stream_el.get("DOVIRPUPresent") else None,
                "bl": stream_el.get("DOVIBLPresent") == "1" if stream_el.get("DOVIBLPresent") else None,
                "el": stream_el.get("DOVIELPresent") == "1" if stream_el.get("DOVIELPresent") else None,
            }
            data["dynamicRange"] = stream_el.get("hdr") or ("Dolby Vision" if dolby_present else None)
        return {k: v for k, v in data.items() if v not in (None, "", [])}

    def _summarize_version_features(self, version: Dict[str, Any]) -> None:
        parts = version.get("parts", [])
        if not any(part.get("plexStreams") for part in parts):
            return

        video_streams: List[Dict[str, Any]] = []
        audio_streams: List[Dict[str, Any]] = []
        subtitle_streams: List[Dict[str, Any]] = []

        for part in parts:
            for stream in part.get("plexStreams", []):
                stream_type = stream.get("type")
                if stream_type == "video":
                    video_streams.append(stream)
                elif stream_type == "audio":
                    audio_streams.append(stream)
                elif stream_type == "subtitle":
                    subtitle_streams.append(stream)

        prefer_video = video_streams[0] if video_streams else {}
        dynamic_range = prefer_video.get("dynamicRange")
        if not dynamic_range and prefer_video.get("dolbyVision", {}).get("present"):
            dynamic_range = "Dolby Vision"
        elif not dynamic_range and prefer_video.get("hdr"):
            dynamic_range = prefer_video.get("hdr")

        resolution_label = None
        resolution_rank = 0
        width = version.get("width") or prefer_video.get("width")
        height = version.get("height") or prefer_video.get("height")
        if version.get("videoResolution"):
            res = str(version["videoResolution"]).lower()
            if res in {"4k", "uhd", "2160", "2160p"}:
                resolution_label = "4K"
                resolution_rank = 3
            elif res in {"1080", "1080p"}:
                resolution_label = "1080p"
                resolution_rank = 2
            elif res in {"720", "720p"}:
                resolution_label = "720p"
                resolution_rank = 1
            else:
                resolution_label = version["videoResolution"]
        if width or height:
            w = int(width or 0)
            h = int(height or 0)
            if w >= 3000 or h >= 1700:
                resolution_label = resolution_label or "4K"
                resolution_rank = max(resolution_rank, 3)
            elif w >= 1700 or h >= 900:
                if not resolution_label or resolution_label == "4K":
                    resolution_label = resolution_label or "1080p"
                resolution_rank = max(resolution_rank, 2)
            elif w >= 1200 or h >= 700:
                if not resolution_label:
                    resolution_label = "720p"
                resolution_rank = max(resolution_rank, 1)

        dolby = prefer_video.get("dolbyVision", {})
        has_dv = bool(dolby.get("present"))
        dv_profile = dolby.get("profile")
        dv_level = dolby.get("level")
        has_dv_fel = bool(dolby.get("el"))

        audio_formats = []
        has_atmos = False
        for stream in audio_streams:
            display = stream.get("extendedDisplayTitle") or stream.get("displayTitle")
            if display:
                audio_formats.append(display)
                if "atmos" in display.lower():
                    has_atmos = True
            title = stream.get("title") or ""
            if "atmos" in title.lower():
                has_atmos = True

        subtitle_languages = list(
            dict.fromkeys(
                [
                    stream.get("language") or stream.get("languageCode")
                    for stream in subtitle_streams
                    if (stream.get("language") or stream.get("languageCode"))
                ]
            )
        )
        subtitle_summary = subtitle_languages[:4]
        subtitle_extra = max(len(subtitle_languages) - len(subtitle_summary), 0)

        features = {
            "hasDolbyVision": has_dv,
            "dolbyVisionProfile": dv_profile,
            "dolbyVisionLevel": dv_level,
            "dolbyVisionIsProfile7": bool(dv_profile) and dv_profile.strip() == "7",
            "dolbyVisionHasFEL": has_dv_fel,
            "dolbyVisionLabel": f"P{dv_profile} · L{dv_level}" if dv_profile and dv_level else None,
            "dynamicRange": dynamic_range,
            "bitDepth": prefer_video.get("bitDepth"),
            "colorSpace": prefer_video.get("colorSpace"),
            "colorTrc": prefer_video.get("colorTrc"),
            "colorPrimaries": prefer_video.get("colorPrimaries"),
            "hasAtmos": has_atmos,
            "audioFormats": audio_formats,
            "subtitleLanguages": subtitle_languages,
            "subtitleSummary": subtitle_summary,
            "subtitleExtraCount": subtitle_extra,
            "resolutionLabel": resolution_label,
            "videoCodec": version.get("videoCodec"),
            "audioCodec": version.get("audioCodec"),
            "resolutionRank": resolution_rank,
        }

        if has_dv:
            if features["dolbyVisionIsProfile7"]:
                if has_dv_fel:
                    features["dolbyVisionSummary"] = "Dolby Vision · Profile 7 FEL"
                else:
                    features["dolbyVisionSummary"] = "Dolby Vision · Profile 7"
            else:
                profile_label = f"Profile {dv_profile}" if dv_profile else None
                features["dolbyVisionSummary"] = "Dolby Vision" + (f" · {profile_label}" if profile_label else "")

        version["features"] = {k: v for k, v in features.items() if v not in (None, "", [])}
        tags = []
        if has_dv:
            if features.get("dolbyVisionIsProfile7"):
                if has_dv_fel:
                    tags.append("DoVi P7 FEL")
                else:
                    tags.append("DoVi P7")
            else:
                tags.append("Dolby Vision")
        elif dynamic_range:
            tags.append(dynamic_range)
        if resolution_label:
            tags.append(resolution_label)
        if has_atmos:
            tags.append("Atmos")
        if version.get("audioChannels"):
            tags.append(f"{version['audioChannels']}ch")
        if subtitle_summary:
            tag_text = ", ".join(subtitle_summary)
            if subtitle_extra:
                tag_text += f" +{subtitle_extra} more"
            tags.append(f"Subs: {tag_text}")
        version["summaryTags"] = tags
