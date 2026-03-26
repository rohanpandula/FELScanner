"""
Analytics Service
Quality reports, storage analytics, duplicate detection, upgrade availability
"""
from typing import Any

from sqlalchemy import case, cast, func, select, text, Float, Integer as SQLInt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.movie import Movie
from app.utils.quality_scoring import calculate_library_quality_score

logger = get_logger(__name__)


class AnalyticsService:
    """Analytics and intelligence layer for library data"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Feature 1: Library Quality Report / Health Score
    # ------------------------------------------------------------------

    async def get_quality_report(self) -> dict[str, Any]:
        """
        Comprehensive library quality breakdown and health score.

        Returns quality distribution, upgrade opportunities, and a
        single 0-100 library health score.
        """
        # Total movies
        total_result = await self.db.execute(select(func.count()).select_from(Movie))
        total = total_result.scalar() or 0

        if total == 0:
            return {
                "health_score": 0,
                "total_movies": 0,
                "quality_tiers": {},
                "hdr_distribution": {},
                "audio_distribution": {},
                "resolution_distribution": {},
                "upgrade_opportunities": [],
                "profile_breakdown": {},
                "quality_summary": {},
            }

        # Resolution distribution
        res_result = await self.db.execute(
            select(
                func.coalesce(Movie.resolution, "Unknown"),
                func.count(Movie.id),
            )
            .group_by(Movie.resolution)
        )
        raw_res = {r: c for r, c in res_result.fetchall()}
        # Bucket into standard tiers
        resolution_dist = {"4K": 0, "1080p": 0, "720p": 0, "SD": 0, "Unknown": 0}
        for res, count in raw_res.items():
            if not res or res == "Unknown":
                resolution_dist["Unknown"] += count
            else:
                # Extract numeric height
                height = int("".join(filter(str.isdigit, res)) or "0")
                if height >= 2160:
                    resolution_dist["4K"] += count
                elif height >= 1080:
                    resolution_dist["1080p"] += count
                elif height >= 720:
                    resolution_dist["720p"] += count
                elif height > 0:
                    resolution_dist["SD"] += count
                else:
                    resolution_dist["Unknown"] += count
        # Remove empty buckets
        resolution_dist = {k: v for k, v in resolution_dist.items() if v > 0}

        # HDR distribution
        hdr_result = await self.db.execute(
            select(
                func.coalesce(Movie.hdr_type, "SDR"),
                func.count(Movie.id),
            )
            .group_by(Movie.hdr_type)
        )
        hdr_dist = {h: c for h, c in hdr_result.fetchall()}

        # DV Profile breakdown
        profile_result = await self.db.execute(
            select(Movie.dv_profile, func.count(Movie.id))
            .where(Movie.dv_profile.isnot(None))
            .group_by(Movie.dv_profile)
        )
        profile_breakdown = {p: c for p, c in profile_result.fetchall()}

        # Audio distribution
        audio_result = await self.db.execute(
            select(
                func.coalesce(Movie.audio_codec, "Unknown"),
                func.count(Movie.id),
            )
            .group_by(Movie.audio_codec)
        )
        audio_dist = {a: c for a, c in audio_result.fetchall()}

        # Atmos count
        atmos_result = await self.db.execute(
            select(func.count()).select_from(Movie).where(Movie.has_atmos == True)
        )
        atmos_count = atmos_result.scalar() or 0

        # FEL count
        fel_result = await self.db.execute(
            select(func.count()).select_from(Movie).where(Movie.dv_fel == True)
        )
        fel_count = fel_result.scalar() or 0

        # DV count
        dv_result = await self.db.execute(
            select(func.count())
            .select_from(Movie)
            .where(Movie.dv_profile.isnot(None))
        )
        dv_count = dv_result.scalar() or 0

        # 4K count
        fourk_result = await self.db.execute(
            select(func.count())
            .select_from(Movie)
            .where(Movie.resolution.in_(["2160p", "4K"]))
        )
        fourk_count = fourk_result.scalar() or 0

        # Quality tiers
        quality_tiers = {
            "reference": 0,    # P7 FEL + Atmos + 4K
            "excellent": 0,    # DV + Atmos + 4K
            "great": 0,        # DV + 4K or FEL
            "good": 0,         # 4K HDR or DV 1080p
            "acceptable": 0,   # 4K SDR or 1080p HDR
            "needs_upgrade": 0, # 1080p SDR or lower
        }

        # Classify each movie into a tier
        movies_result = await self.db.execute(
            select(
                Movie.dv_fel,
                Movie.dv_profile,
                Movie.has_atmos,
                Movie.resolution,
                Movie.hdr_type,
            )
        )
        for dv_fel, dv_profile, has_atmos, resolution, hdr_type in movies_result.fetchall():
            is_4k = resolution in ("2160p", "4K")
            is_dv = dv_profile is not None
            is_hdr = hdr_type and hdr_type.lower() not in ("sdr", "", None)

            if dv_fel and has_atmos and is_4k:
                quality_tiers["reference"] += 1
            elif is_dv and has_atmos and is_4k:
                quality_tiers["excellent"] += 1
            elif (is_dv and is_4k) or dv_fel:
                quality_tiers["great"] += 1
            elif (is_4k and is_hdr) or (is_dv and not is_4k):
                quality_tiers["good"] += 1
            elif is_4k or (resolution == "1080p" and is_hdr):
                quality_tiers["acceptable"] += 1
            else:
                quality_tiers["needs_upgrade"] += 1

        # Health score: weighted average of quality tiers
        tier_weights = {
            "reference": 100,
            "excellent": 90,
            "great": 75,
            "good": 55,
            "acceptable": 35,
            "needs_upgrade": 10,
        }
        weighted_sum = sum(
            quality_tiers[tier] * tier_weights[tier] for tier in quality_tiers
        )
        health_score = round(weighted_sum / total) if total > 0 else 0

        # Quality summary percentages
        quality_summary = {
            "dv_percentage": round((dv_count / total) * 100, 1) if total else 0,
            "fel_percentage": round((fel_count / total) * 100, 1) if total else 0,
            "atmos_percentage": round((atmos_count / total) * 100, 1) if total else 0,
            "fourk_percentage": round((fourk_count / total) * 100, 1) if total else 0,
            "dv_count": dv_count,
            "fel_count": fel_count,
            "atmos_count": atmos_count,
            "fourk_count": fourk_count,
        }

        return {
            "health_score": health_score,
            "total_movies": total,
            "quality_tiers": quality_tiers,
            "hdr_distribution": hdr_dist,
            "audio_distribution": audio_dist,
            "resolution_distribution": resolution_dist,
            "profile_breakdown": profile_breakdown,
            "quality_summary": quality_summary,
        }

    # ------------------------------------------------------------------
    # Feature 2: Upgrade Opportunities
    # ------------------------------------------------------------------

    async def get_upgrade_opportunities(self) -> list[dict[str, Any]]:
        """
        Find movies that could benefit from an upgrade.

        Returns movies sorted by upgrade potential (worst quality first).
        """
        result = await self.db.execute(
            select(Movie)
            .order_by(Movie.dv_fel.asc(), Movie.dv_profile.asc().nullsfirst(), Movie.has_atmos.asc())
            .limit(100)
        )
        movies = result.scalars().all()

        opportunities = []
        for movie in movies:
            score = calculate_library_quality_score({
                "dv_fel": movie.dv_fel,
                "dv_profile": movie.dv_profile,
                "resolution": movie.resolution,
                "has_atmos": movie.has_atmos,
            })

            # Determine what upgrades are possible
            possible_upgrades = []
            if not movie.dv_fel:
                possible_upgrades.append("FEL (P7)")
            if not movie.dv_profile:
                possible_upgrades.append("Dolby Vision")
            if not movie.has_atmos:
                possible_upgrades.append("TrueHD Atmos")
            if movie.resolution not in ("2160p", "4K"):
                possible_upgrades.append("4K")

            if possible_upgrades:
                opportunities.append({
                    "id": movie.id,
                    "title": movie.title,
                    "year": movie.year,
                    "current_quality": movie.display_quality,
                    "quality_score": score,
                    "resolution": movie.resolution,
                    "dv_profile": movie.dv_profile,
                    "dv_fel": movie.dv_fel,
                    "has_atmos": movie.has_atmos,
                    "hdr_type": movie.hdr_type,
                    "possible_upgrades": possible_upgrades,
                    "upgrade_priority": len(possible_upgrades),
                })

        # Sort by most upgrades possible first, then by lowest score
        opportunities.sort(key=lambda x: (-x["upgrade_priority"], x["quality_score"]))
        return opportunities

    # ------------------------------------------------------------------
    # Feature 4: Duplicate Detection
    # ------------------------------------------------------------------

    async def get_duplicates(self) -> list[dict[str, Any]]:
        """
        Find movies with multiple versions in the library.

        Groups by title+year and returns movies with version_count > 1
        or with multiple entries sharing the same title.
        """
        # Movies with multiple versions
        multi_version = await self.db.execute(
            select(Movie)
            .where(Movie.version_count > 1)
            .order_by(Movie.title)
        )
        multi_version_movies = multi_version.scalars().all()

        # Also find distinct titles that appear multiple times
        dup_titles = await self.db.execute(
            select(Movie.title, Movie.year, func.count(Movie.id).label("count"))
            .group_by(Movie.title, Movie.year)
            .having(func.count(Movie.id) > 1)
        )
        duplicate_title_groups = dup_titles.fetchall()

        duplicates = []

        # Handle multi-version movies
        for movie in multi_version_movies:
            versions = movie.extra_data.get("versions", []) if movie.extra_data else []
            file_size = movie.file_size_bytes or 0
            duplicates.append({
                "id": movie.id,
                "title": movie.title,
                "year": movie.year,
                "version_count": movie.version_count,
                "primary_quality": movie.display_quality,
                "quality_score": movie.quality_score,
                "file_size_bytes": file_size,
                "versions": versions,
                "type": "multi_version",
            })

        # Handle duplicate title entries
        for title, year, count in duplicate_title_groups:
            entries_result = await self.db.execute(
                select(Movie)
                .where(Movie.title == title, Movie.year == year)
                .order_by(Movie.dv_fel.desc(), Movie.has_atmos.desc())
            )
            entries = entries_result.scalars().all()

            versions = []
            total_size = 0
            best_score = 0
            for entry in entries:
                score = entry.quality_score
                size = entry.file_size_bytes or 0
                total_size += size
                best_score = max(best_score, score)
                versions.append({
                    "id": entry.id,
                    "quality": entry.display_quality,
                    "quality_score": score,
                    "resolution": entry.resolution,
                    "dv_profile": entry.dv_profile,
                    "dv_fel": entry.dv_fel,
                    "has_atmos": entry.has_atmos,
                    "file_size_bytes": size,
                    "file_path": entry.file_path,
                })

            duplicates.append({
                "title": title,
                "year": year,
                "version_count": count,
                "total_size_bytes": total_size,
                "best_quality_score": best_score,
                "versions": versions,
                "type": "duplicate_entries",
            })

        return duplicates

    # ------------------------------------------------------------------
    # Feature 5: Storage Analytics
    # ------------------------------------------------------------------

    async def get_storage_analytics(self) -> dict[str, Any]:
        """
        Storage breakdown by quality tier, codec, resolution.
        Includes size forecasting based on current library growth.
        """
        # Total storage
        total_size = await self.db.execute(
            select(func.coalesce(func.sum(Movie.file_size_bytes), 0)).select_from(Movie)
        )
        total_bytes = total_size.scalar() or 0

        total_count = await self.db.execute(
            select(func.count()).select_from(Movie)
        )
        movie_count = total_count.scalar() or 0

        # Storage by resolution
        res_storage = await self.db.execute(
            select(
                func.coalesce(Movie.resolution, "Unknown"),
                func.count(Movie.id),
                func.coalesce(func.sum(Movie.file_size_bytes), 0),
                func.coalesce(func.avg(Movie.file_size_bytes), 0),
            )
            .group_by(Movie.resolution)
        )
        # Bucket into standard tiers
        res_buckets: dict[str, dict] = {}
        for res, count, total, avg_size in res_storage.fetchall():
            if not res or res == "Unknown":
                tier = "Unknown"
            else:
                height = int("".join(filter(str.isdigit, res)) or "0")
                if height >= 2160:
                    tier = "4K"
                elif height >= 1080:
                    tier = "1080p"
                elif height >= 720:
                    tier = "720p"
                elif height > 0:
                    tier = "SD"
                else:
                    tier = "Unknown"
            if tier not in res_buckets:
                res_buckets[tier] = {"count": 0, "total_bytes": 0}
            res_buckets[tier]["count"] += count
            res_buckets[tier]["total_bytes"] += int(total)

        by_resolution = []
        for tier in ["4K", "1080p", "720p", "SD", "Unknown"]:
            if tier in res_buckets:
                b = res_buckets[tier]
                by_resolution.append({
                    "resolution": tier,
                    "count": b["count"],
                    "total_bytes": b["total_bytes"],
                    "avg_bytes": b["total_bytes"] // b["count"] if b["count"] else 0,
                })

        # Storage by DV status
        dv_storage = await self.db.execute(
            select(
                case(
                    (Movie.dv_fel == True, "FEL (P7)"),
                    (Movie.dv_profile.isnot(None), "Dolby Vision"),
                    else_="Non-DV",
                ).label("category"),
                func.count(Movie.id),
                func.coalesce(func.sum(Movie.file_size_bytes), 0),
                func.coalesce(func.avg(Movie.file_size_bytes), 0),
            )
            .group_by("category")
        )
        by_dv_status = []
        for cat, count, total, avg_size in dv_storage.fetchall():
            by_dv_status.append({
                "category": cat,
                "count": count,
                "total_bytes": int(total),
                "avg_bytes": int(avg_size),
            })

        # Storage by audio
        audio_storage = await self.db.execute(
            select(
                case(
                    (Movie.has_atmos == True, "TrueHD Atmos"),
                    else_=func.coalesce(Movie.audio_codec, "Unknown"),
                ).label("audio"),
                func.count(Movie.id),
                func.coalesce(func.sum(Movie.file_size_bytes), 0),
                func.coalesce(func.avg(Movie.file_size_bytes), 0),
            )
            .group_by("audio")
        )
        by_audio = []
        for audio, count, total, avg_size in audio_storage.fetchall():
            by_audio.append({
                "audio": audio,
                "count": count,
                "total_bytes": int(total),
                "avg_bytes": int(avg_size),
            })

        # Storage by video codec
        codec_storage = await self.db.execute(
            select(
                func.coalesce(Movie.video_codec, "Unknown"),
                func.count(Movie.id),
                func.coalesce(func.sum(Movie.file_size_bytes), 0),
            )
            .group_by(Movie.video_codec)
        )
        by_codec = []
        for codec, count, total in codec_storage.fetchall():
            by_codec.append({
                "codec": codec or "Unknown",
                "count": count,
                "total_bytes": int(total),
            })

        # Top 20 largest movies
        largest = await self.db.execute(
            select(Movie)
            .where(Movie.file_size_bytes.isnot(None))
            .order_by(Movie.file_size_bytes.desc())
            .limit(20)
        )
        largest_movies = []
        for movie in largest.scalars().all():
            largest_movies.append({
                "id": movie.id,
                "title": movie.title,
                "year": movie.year,
                "quality": movie.display_quality,
                "file_size_bytes": movie.file_size_bytes,
                "resolution": movie.resolution,
                "dv_profile": movie.dv_profile,
            })

        # Top 20 smallest (worst quality-to-size ratio)
        smallest_dv = await self.db.execute(
            select(Movie)
            .where(
                Movie.file_size_bytes.isnot(None),
                Movie.dv_profile.isnot(None),
            )
            .order_by(Movie.file_size_bytes.asc())
            .limit(20)
        )
        smallest_dv_movies = []
        for movie in smallest_dv.scalars().all():
            smallest_dv_movies.append({
                "id": movie.id,
                "title": movie.title,
                "year": movie.year,
                "quality": movie.display_quality,
                "file_size_bytes": movie.file_size_bytes,
            })

        avg_size = total_bytes // movie_count if movie_count > 0 else 0

        return {
            "total_bytes": int(total_bytes),
            "total_movies": movie_count,
            "avg_file_size_bytes": int(avg_size),
            "by_resolution": by_resolution,
            "by_dv_status": by_dv_status,
            "by_audio": by_audio,
            "by_codec": by_codec,
            "largest_movies": largest_movies,
            "smallest_dv_movies": smallest_dv_movies,
        }

    # ------------------------------------------------------------------
    # Feature 7: Comparison View
    # ------------------------------------------------------------------

    async def compare_movie_with_torrent(
        self, movie_id: int, torrent_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Side-by-side comparison of current movie quality vs torrent.
        """
        result = await self.db.execute(select(Movie).where(Movie.id == movie_id))
        movie = result.scalar_one_or_none()

        if not movie:
            return {"error": "Movie not found"}

        current_score = calculate_library_quality_score({
            "dv_fel": movie.dv_fel,
            "dv_profile": movie.dv_profile,
            "resolution": movie.resolution,
            "has_atmos": movie.has_atmos,
        })

        from app.utils.quality_scoring import calculate_torrent_quality_score

        torrent_score = calculate_torrent_quality_score(torrent_metadata)

        is_upgrade = torrent_score > current_score
        score_diff = torrent_score - current_score

        # Build detailed comparison
        comparison = {
            "movie": {
                "id": movie.id,
                "title": movie.title,
                "year": movie.year,
                "resolution": movie.resolution,
                "dv_profile": movie.dv_profile,
                "dv_fel": movie.dv_fel,
                "has_atmos": movie.has_atmos,
                "audio_codec": movie.audio_codec,
                "audio_channels": movie.audio_channels,
                "video_codec": movie.video_codec,
                "hdr_type": movie.hdr_type,
                "file_size_bytes": movie.file_size_bytes,
                "quality_score": current_score,
                "display_quality": movie.display_quality,
            },
            "torrent": {
                "resolution": torrent_metadata.get("resolution"),
                "dv_profile": torrent_metadata.get("dv_profile"),
                "has_fel": torrent_metadata.get("has_fel", False),
                "has_atmos": torrent_metadata.get("has_atmos", False),
                "audio_codec": torrent_metadata.get("audio_codec"),
                "audio_channels": torrent_metadata.get("audio_channels"),
                "video_codec": torrent_metadata.get("video_codec"),
                "hdr_type": torrent_metadata.get("hdr_type"),
                "source": torrent_metadata.get("source"),
                "release_group": torrent_metadata.get("release_group"),
                "quality_score": torrent_score,
            },
            "is_upgrade": is_upgrade,
            "score_difference": score_diff,
            "upgrade_details": [],
        }

        # Enumerate specific improvements
        if torrent_metadata.get("has_fel") and not movie.dv_fel:
            comparison["upgrade_details"].append({
                "field": "FEL",
                "from": "No" if not movie.dv_profile else f"DV {movie.dv_profile}",
                "to": "P7 FEL",
                "impact": "major",
            })

        if torrent_metadata.get("has_atmos") and not movie.has_atmos:
            comparison["upgrade_details"].append({
                "field": "Audio",
                "from": movie.audio_codec or "Unknown",
                "to": "TrueHD Atmos",
                "impact": "moderate",
            })

        t_res = torrent_metadata.get("resolution")
        if t_res == "2160p" and movie.resolution != "2160p":
            comparison["upgrade_details"].append({
                "field": "Resolution",
                "from": movie.resolution or "Unknown",
                "to": "2160p",
                "impact": "major",
            })

        return comparison
