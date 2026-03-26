"""
Plex Scanner - Dolby Vision Profile Detection
Core scanning logic for analyzing Plex movies and detecting DV profiles
"""
import asyncio
import re
from typing import Any

import aiohttp
import xmltodict
from plexapi.video import Movie as PlexMovie

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.plex.client import PlexClient

logger = get_logger(__name__)


class PlexScanner:
    """
    Plex library scanner with DV profile detection

    Fetches movie metadata via Plex XML API and analyzes video streams
    to detect Dolby Vision profiles (P4, P5, P7, P8, P9) and FEL.
    """

    # Dolby Vision profile detection patterns
    DV_PROFILE_PATTERNS = {
        "dvhe.04": "P4",
        "dvhe.05": "P5",
        "dvhe.07": "P7",
        "dvhe.08": "P8",
        "dvhe.09": "P9",
        "dvh1.04": "P4",
        "dvh1.05": "P5",
        "dvh1.07": "P7",
        "dvh1.08": "P8",
        "dvh1.09": "P9",
    }

    # FEL (Full Enhancement Layer) indicator
    FEL_PATTERN = re.compile(r"BL\+EL|FEL|dvhe\.07", re.IGNORECASE)

    def __init__(self):
        """Initialize scanner with Plex client"""
        self.settings = get_settings()
        self.client = PlexClient()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.settings.PLEX_TIMEOUT)
            )
        return self._session

    async def close(self):
        """Close aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_movie_xml(self, rating_key: str) -> dict[str, Any] | None:
        """
        Fetch detailed movie metadata from Plex XML API

        Args:
            rating_key: Plex unique identifier

        Returns:
            dict: Parsed XML metadata or None if failed
        """
        url = f"{self.settings.PLEX_URL}/library/metadata/{rating_key}"
        params = {"X-Plex-Token": self.settings.PLEX_TOKEN}

        try:
            session = await self._get_session()
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    xml_text = await response.text()
                    parsed = xmltodict.parse(xml_text)
                    return parsed
                else:
                    logger.warning(
                        "plex.xml_fetch_failed",
                        rating_key=rating_key,
                        status=response.status,
                    )
                    return None

        except Exception as e:
            logger.error("plex.xml_fetch_error", rating_key=rating_key, error=str(e))
            return None

    def detect_dv_profile(self, video_stream: dict[str, Any]) -> tuple[str | None, bool]:
        """
        Detect Dolby Vision profile from video stream metadata

        Args:
            video_stream: Video stream dictionary from Plex XML

        Returns:
            tuple: (profile, has_fel)
                - profile: "P4", "P5", "P7", "P8", "P9", or None
                - has_fel: True if FEL detected (Profile 7)
        """
        profile = None
        has_fel = False

        # Check codec and DOVIProfile attributes
        codec = video_stream.get("@codec", "").lower()
        dovi_profile = video_stream.get("@DOVIProfile", "")
        color_space = video_stream.get("@colorSpace", "").lower()

        # Pattern 1: codec contains dvhe/dvh1
        for pattern, detected_profile in self.DV_PROFILE_PATTERNS.items():
            if pattern in codec:
                profile = detected_profile
                break

        # Pattern 2: DOVIProfile attribute (e.g., "7", "5")
        if dovi_profile:
            profile = f"P{dovi_profile}"

        # Pattern 3: colorSpace contains dolbyvision
        if not profile and "dolbyvision" in color_space:
            # Default to P5 if we can't determine specific profile
            profile = "P5"

        # FEL detection
        if profile == "P7":
            has_fel = True
        else:
            # Check for FEL indicators in codec string
            if self.FEL_PATTERN.search(codec):
                has_fel = True
                # If FEL found and no profile, assume P7
                if not profile:
                    profile = "P7"

        return profile, has_fel

    def detect_atmos(self, audio_streams: list[dict[str, Any]]) -> bool:
        """
        Detect TrueHD Atmos audio track

        Args:
            audio_streams: List of audio stream dictionaries

        Returns:
            bool: True if TrueHD Atmos found
        """
        for stream in audio_streams:
            codec = stream.get("@codec", "").lower()
            profile = stream.get("@profile", "").lower()
            title = stream.get("@title", "").lower()

            # TrueHD codec
            if codec == "truehd":
                # Check for explicit Atmos indicators
                if "atmos" in profile or "atmos" in title:
                    return True

                # Check if displayTitle contains Atmos
                display_title = stream.get("@displayTitle", "").lower()
                if "atmos" in display_title:
                    return True

                # TrueHD with 8 channels is Atmos (7.1 with height channels)
                channels = stream.get("@channels")
                if channels:
                    try:
                        if int(channels) == 8:
                            return True
                    except (ValueError, TypeError):
                        pass

        return False

    def parse_resolution(self, video_stream: dict[str, Any]) -> str | None:
        """
        Parse video resolution

        Args:
            video_stream: Video stream dictionary

        Returns:
            str: Resolution like "2160p", "1080p", or None
        """
        height = video_stream.get("@height")
        if not height:
            return None

        try:
            height = int(height)
            if height >= 2160:
                return "2160p"
            elif height >= 1080:
                return "1080p"
            elif height >= 720:
                return "720p"
            else:
                return f"{height}p"
        except (ValueError, TypeError):
            return None

    async def scan_movie(self, movie: PlexMovie) -> dict[str, Any]:
        """
        Scan a single movie and extract all metadata

        Args:
            movie: PlexMovie object from plexapi

        Returns:
            dict: Comprehensive movie metadata
        """
        rating_key = movie.ratingKey
        movie_data = {
            "rating_key": str(rating_key),
            "title": movie.title,
            "year": movie.year,
            "sort_title": movie.titleSort if hasattr(movie, "titleSort") else None,
            "original_title": movie.originalTitle if hasattr(movie, "originalTitle") else None,
            "resolution": None,
            "video_codec": None,
            "hdr_type": None,
            "dv_profile": None,
            "dv_fel": False,
            "dv_bl_compatible": False,
            "audio_codec": None,
            "has_atmos": False,
            "audio_channels": None,
            "file_path": None,
            "file_size_bytes": None,
            "container": None,
            "version_count": 0,
            "best_version_index": None,
            "extra_data": {},
        }

        try:
            # Fetch detailed XML metadata
            xml_data = await self.fetch_movie_xml(rating_key)
            if not xml_data:
                logger.warning("scanner.no_xml_data", rating_key=rating_key)
                return movie_data

            # Extract Media container
            media_container = xml_data.get("MediaContainer", {})
            video_element = media_container.get("Video", {})

            if not video_element:
                logger.warning("scanner.no_video_element", rating_key=rating_key)
                return movie_data

            # Handle multiple versions
            media_elements = video_element.get("Media", [])
            if isinstance(media_elements, dict):
                media_elements = [media_elements]

            movie_data["version_count"] = len(media_elements)

            # Analyze all versions and find best quality
            best_quality_score = -1
            best_version_data = None

            for idx, media in enumerate(media_elements):
                version_data = await self._analyze_media_version(media)
                version_data["version_index"] = idx

                # Calculate quality score
                quality_score = self._calculate_quality_score(version_data)

                if quality_score > best_quality_score:
                    best_quality_score = quality_score
                    best_version_data = version_data
                    movie_data["best_version_index"] = idx

            # Use best version for top-level fields
            if best_version_data:
                movie_data.update({
                    "resolution": best_version_data.get("resolution"),
                    "video_codec": best_version_data.get("video_codec"),
                    "hdr_type": best_version_data.get("hdr_type"),
                    "dv_profile": best_version_data.get("dv_profile"),
                    "dv_fel": best_version_data.get("dv_fel", False),
                    "dv_bl_compatible": best_version_data.get("dv_bl_compatible", False),
                    "audio_codec": best_version_data.get("audio_codec"),
                    "has_atmos": best_version_data.get("has_atmos", False),
                    "audio_channels": best_version_data.get("audio_channels"),
                    "file_path": best_version_data.get("file_path"),
                    "file_size_bytes": best_version_data.get("file_size_bytes"),
                    "container": best_version_data.get("container"),
                })

                # Store all versions in extra_data
                movie_data["extra_data"]["versions"] = media_elements
                movie_data["extra_data"]["best_quality_score"] = best_quality_score

            logger.debug(
                "scanner.movie_scanned",
                rating_key=rating_key,
                title=movie_data["title"],
                dv_profile=movie_data["dv_profile"],
                has_fel=movie_data["dv_fel"],
                has_atmos=movie_data["has_atmos"],
            )

            return movie_data

        except Exception as e:
            logger.error(
                "scanner.scan_movie_error",
                rating_key=rating_key,
                error=str(e),
                exc_info=True,
            )
            return movie_data

    async def _analyze_media_version(self, media: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a single media version

        Args:
            media: Media element from Plex XML

        Returns:
            dict: Extracted metadata for this version
        """
        version_data = {
            "resolution": None,
            "video_codec": None,
            "hdr_type": None,
            "dv_profile": None,
            "dv_fel": False,
            "dv_bl_compatible": False,
            "audio_codec": None,
            "has_atmos": False,
            "audio_channels": None,
            "file_path": None,
            "file_size_bytes": None,
            "container": None,
        }

        # File information
        part = media.get("Part", {})
        if isinstance(part, list):
            part = part[0]

        version_data["file_path"] = part.get("@file")
        version_data["file_size_bytes"] = int(part.get("@size", 0))
        version_data["container"] = part.get("@container")

        # Video streams
        streams = part.get("Stream", [])
        if isinstance(streams, dict):
            streams = [streams]

        video_streams = [s for s in streams if s.get("@streamType") == "1"]
        audio_streams = [s for s in streams if s.get("@streamType") == "2"]

        # Analyze video
        if video_streams:
            video_stream = video_streams[0]
            version_data["video_codec"] = video_stream.get("@codec")
            version_data["resolution"] = self.parse_resolution(video_stream)

            # DV detection
            dv_profile, has_fel = self.detect_dv_profile(video_stream)
            version_data["dv_profile"] = dv_profile
            version_data["dv_fel"] = has_fel

            # HDR type
            if dv_profile:
                version_data["hdr_type"] = "dolbyvision"
                # Check if BL is HDR10 compatible (profiles 7, 8)
                if dv_profile in ("P7", "P8"):
                    version_data["dv_bl_compatible"] = True
            elif "hdr" in video_stream.get("@colorSpace", "").lower():
                version_data["hdr_type"] = "hdr10"
            else:
                version_data["hdr_type"] = "sdr"

        # Analyze audio
        if audio_streams:
            primary_audio = audio_streams[0]
            version_data["audio_codec"] = primary_audio.get("@codec")
            version_data["audio_channels"] = primary_audio.get("@channels")

            # Atmos detection
            version_data["has_atmos"] = self.detect_atmos(audio_streams)

        return version_data

    def _calculate_quality_score(self, version_data: dict[str, Any]) -> int:
        """
        Calculate quality score for version ranking.

        Delegates to the consolidated quality scoring module.

        Args:
            version_data: Version metadata

        Returns:
            int: Quality score
        """
        from app.utils.quality_scoring import calculate_library_quality_score

        return calculate_library_quality_score({
            "dv_fel": version_data.get("dv_fel"),
            "dv_profile": version_data.get("dv_profile"),
            "resolution": version_data.get("resolution"),
            "has_atmos": version_data.get("has_atmos"),
        })

    async def scan_library(
        self,
        batch_size: int = 50,
        on_progress: callable = None,
    ) -> list[dict[str, Any]]:
        """
        Scan entire Plex library

        Args:
            batch_size: Number of movies to process concurrently
            on_progress: Optional callback for progress updates
                         Called with (message, scanned, total, current_movie)

        Returns:
            list[dict]: All scanned movie data
        """
        logger.info("scanner.library_scan_start")

        if on_progress:
            on_progress("Connecting to Plex...", 0, 0, None)

        # Get all movies
        movies = await self.client.get_all_movies()
        total_count = len(movies)

        logger.info("scanner.library_scan_progress", total=total_count)

        if on_progress:
            on_progress(f"Found {total_count} movies to scan", 0, total_count, None)

        all_movie_data = []
        dv_count = 0
        fel_count = 0
        atmos_count = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = movies[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self.scan_movie(movie) for movie in batch],
                return_exceptions=True,
            )

            # Filter out exceptions and count discoveries
            for result in batch_results:
                if isinstance(result, dict):
                    all_movie_data.append(result)
                    if result.get("dv_profile"):
                        dv_count += 1
                    if result.get("dv_fel"):
                        fel_count += 1
                    if result.get("has_atmos"):
                        atmos_count += 1
                else:
                    logger.error("scanner.batch_error", error=str(result))

            completed = min(i + batch_size, total_count)
            current_movie = batch[-1].title if batch else None

            logger.info(
                "scanner.batch_complete",
                completed=completed,
                total=total_count,
            )

            if on_progress:
                on_progress(
                    f"Scanned {completed}/{total_count} movies (DV: {dv_count}, FEL: {fel_count}, Atmos: {atmos_count})",
                    completed,
                    total_count,
                    current_movie,
                )

        logger.info("scanner.library_scan_complete", scanned=len(all_movie_data))

        if on_progress:
            on_progress(
                f"Scan complete! {len(all_movie_data)} movies scanned",
                len(all_movie_data),
                total_count,
                None,
            )

        return all_movie_data
