"""
IPT Scanner Service
Communicates with the IPT scraper microservice
"""
import re
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.movie import Movie
from app.services.ipt_scraper import get_scraper
from app.utils.torrent_parser import TorrentTitleParser

logger = get_logger(__name__)


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching: lowercase, strip punctuation, collapse spaces"""
    t = title.lower().strip()
    t = re.sub(r"[''`]", "", t)          # Remove apostrophes
    t = re.sub(r"[^a-z0-9\s]", " ", t)   # Replace punctuation with space
    t = re.sub(r"\s+", " ", t).strip()    # Collapse whitespace
    return t


class IPTService:
    """Service for interacting with IPT scraper microservice"""

    def __init__(self, db: AsyncSession | None = None):
        """Initialize IPT service"""
        settings = get_settings()
        self.scraper_url = settings.IPT_SCRAPER_URL
        self.timeout = 60.0  # IPT scans can take time
        self.db = db

    async def trigger_scan(self) -> dict[str, Any]:
        """
        Trigger an IPT scan using the in-process scraper.
        """
        logger.info("ipt.scan_triggered")
        scraper = get_scraper()
        try:
            results = await scraper.scan()
        except Exception as e:  # noqa: BLE001
            logger.error("ipt.scan_failed", error=str(e))
            raise

        new_count = sum(1 for r in results if r.get("isNew"))
        logger.info("ipt.scan_completed", total=len(results), new=new_count)
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results": {
                "total": len(results),
                "new": new_count,
                "torrents": results,
            },
        }

    async def _build_library_index(self) -> dict[str, dict[str, Any]]:
        """
        Build a lookup index from the movie database for matching against torrent titles.
        Key: normalized title + year → movie quality info
        """
        if not self.db:
            return {}

        result = await self.db.execute(
            select(
                Movie.title,
                Movie.year,
                Movie.resolution,
                Movie.dv_profile,
                Movie.dv_fel,
                Movie.has_atmos,
                Movie.hdr_type,
                Movie.audio_codec,
            )
        )

        index: dict[str, dict[str, Any]] = {}
        for title, year, resolution, dv_profile, dv_fel, has_atmos, hdr_type, audio_codec in result.fetchall():
            norm = _normalize_title(title)

            # Build quality display string
            quality_parts = []
            if resolution:
                height = int("".join(filter(str.isdigit, resolution)) or "0")
                if height >= 2160:
                    quality_parts.append("4K")
                elif height >= 1080:
                    quality_parts.append("1080p")
                elif height >= 720:
                    quality_parts.append("720p")
                else:
                    quality_parts.append(resolution)

            if dv_fel:
                quality_parts.append("DV P7 FEL")
            elif dv_profile:
                quality_parts.append(f"DV {dv_profile}")
            elif hdr_type and hdr_type.lower() not in ("sdr", ""):
                quality_parts.append(hdr_type.upper())

            if has_atmos:
                quality_parts.append("Atmos")

            quality_str = " / ".join(quality_parts) if quality_parts else "Unknown"

            entry = {
                "in_library": True,
                "library_quality": quality_str,
                "library_resolution": resolution,
                "library_dv_profile": dv_profile,
                "library_dv_fel": dv_fel,
                "library_has_atmos": has_atmos,
            }

            # Store with year key for exact match, and without year for fallback
            if year:
                index[f"{norm}|{year}"] = entry
            # Also store by title only (last match wins, fine for our purposes)
            index[f"{norm}|"] = entry

        return index

    async def _build_radarr_index(self) -> dict[str, bool]:
        """
        Build lookup index from Radarr to know which movies are managed.
        Key: normalized title + year → True
        """
        settings = get_settings()
        if not settings.RADARR_URL or not settings.RADARR_API_KEY:
            return {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{settings.RADARR_URL}/api/v3/movie",
                    headers={"X-Api-Key": settings.RADARR_API_KEY},
                )
                if resp.status_code != 200:
                    return {}
                movies = resp.json()
        except Exception as e:
            logger.warning("ipt.radarr_index_failed", error=str(e))
            return {}

        index: dict[str, bool] = {}
        for m in movies:
            title = m.get("title", "")
            year = m.get("year")
            norm = _normalize_title(title)
            if year:
                index[f"{norm}|{year}"] = True
            index[f"{norm}|"] = True
            # Also index alternate titles
            for alt in m.get("alternateTitles", []):
                alt_title = alt.get("title", "")
                if alt_title:
                    alt_norm = _normalize_title(alt_title)
                    if year:
                        index[f"{alt_norm}|{year}"] = True
                    index[f"{alt_norm}|"] = True

        return index

    def _match_library(
        self,
        metadata: dict[str, Any],
        library_index: dict[str, dict[str, Any]],
        radarr_index: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        """Match a torrent's parsed metadata against the library and radarr indexes"""
        clean_title = metadata.get("clean_title", "")
        year = metadata.get("year")

        if not clean_title:
            return {"in_library": False, "in_radarr": False}

        norm = _normalize_title(clean_title)

        # Check radarr
        in_radarr = False
        if radarr_index:
            if year and f"{norm}|{year}" in radarr_index:
                in_radarr = True
            elif f"{norm}|" in radarr_index:
                in_radarr = True

        # Try exact title + year match first
        if year:
            key = f"{norm}|{year}"
            if key in library_index:
                result = library_index[key].copy()
                result["in_radarr"] = in_radarr
                return result

        # Fallback: title-only match
        key = f"{norm}|"
        if key in library_index:
            result = library_index[key].copy()
            result["in_radarr"] = in_radarr
            return result

        return {"in_library": False, "in_radarr": in_radarr}

    async def get_latest_results(self) -> dict[str, Any]:
        """
        Get latest scan results from the in-process scraper, enriched with
        parsed metadata and matched against the Plex library / Radarr catalogue.
        """
        try:
            raw = await get_scraper().get_latest_results()
        except Exception as e:  # noqa: BLE001
            logger.error("ipt.get_results_failed", error=str(e))
            return {
                "success": False,
                "timestamp": None,
                "results": {"total": 0, "new": 0, "torrents": []},
            }

        torrents = raw.get("torrents", []) or []
        library_index = await self._build_library_index()
        radarr_index  = await self._build_radarr_index()

        enriched = []
        for t in torrents:
            row = self._enrich_torrent(t)
            row["library"] = self._match_library(
                row.get("metadata", {}), library_index, radarr_index
            )
            enriched.append(row)

        return {
            "success": True,
            "timestamp": raw.get("timestamp"),
            "results": {
                "total": len(enriched),
                "new": sum(1 for t in enriched if t.get("isNew")),
                "torrents": enriched,
            },
        }

    def _enrich_torrent(self, torrent: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich torrent with parsed metadata from title

        Args:
            torrent: Raw torrent data from scraper

        Returns:
            dict: Torrent with added 'metadata' field containing parsed data
        """
        title = torrent.get("name") or torrent.get("title", "")
        metadata = TorrentTitleParser.parse(title)
        metadata["quality_score"] = TorrentTitleParser.get_quality_score(metadata)

        # Add metadata to torrent
        enriched = torrent.copy()
        enriched["metadata"] = metadata

        return enriched

    async def get_known_torrents(self) -> list[dict[str, Any]]:
        """
        Get known torrents from in-process cache, enriched + sorted by quality.
        """
        try:
            torrents = await get_scraper().get_known_torrents()
        except Exception as e:  # noqa: BLE001
            logger.error("ipt.get_known_failed", error=str(e))
            return []

        enriched = [self._enrich_torrent(t) for t in torrents]
        enriched.sort(
            key=lambda t: t.get("metadata", {}).get("quality_score", 0),
            reverse=True,
        )
        return enriched

    async def clear_cache(self) -> dict[str, str]:
        """Clear known torrents cache."""
        try:
            await get_scraper().clear_known_torrents()
        except Exception as e:  # noqa: BLE001
            logger.error("ipt.clear_cache_failed", error=str(e))
            raise
        logger.info("ipt.cache_cleared")
        return {"message": "Cache cleared"}

    async def check_health(self) -> dict[str, str]:
        """
        Report scraper health. In-process — always healthy when FlareSolverr
        is configured; reports degraded if not.
        """
        scraper = get_scraper()
        if not scraper.flaresolverr_url:
            return {
                "status": "degraded",
                "message": "IPT scraper running in-process — FLARESOLVERR_URL not set",
            }
        return {
            "status": "healthy",
            "message": "IPT scraper (in-process) ready",
            "uptime": 0,
        }
