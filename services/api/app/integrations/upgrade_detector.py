"""
Upgrade Detector
Implements 17 notification rules for determining upgrade eligibility
"""
import re
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class UpgradeDetector:
    """
    Upgrade detection with configurable notification rules

    Implements all 17 notification rules from v1:
    1. FEL notifications (NOTIFY_FEL)
    2. P5→P7 FEL upgrades (NOTIFY_FEL_FROM_P5)
    3. HDR→P7 FEL upgrades (NOTIFY_FEL_FROM_HDR)
    4. FEL duplicates (NOTIFY_FEL_DUPLICATES)
    5. General DV notifications (NOTIFY_DV)
    6. HDR→DV upgrades (NOTIFY_DV_FROM_HDR)
    7. DV profile upgrades (NOTIFY_DV_PROFILE_UPGRADES)
    8. Atmos notifications (NOTIFY_ATMOS)
    9. Atmos only if no current Atmos (NOTIFY_ATMOS_ONLY_IF_NO_ATMOS)
    10. Atmos with DV upgrade combo (NOTIFY_ATMOS_WITH_DV_UPGRADE)
    11. Resolution notifications (NOTIFY_RESOLUTION)
    12. Resolution only upgrades (NOTIFY_RESOLUTION_ONLY_UPGRADES)
    13. Only library movies (NOTIFY_ONLY_LIBRARY_MOVIES)
    14. Expiration hours (NOTIFY_EXPIRE_HOURS)
    """

    # Quality parsing patterns
    RESOLUTION_PATTERN = re.compile(r"(2160p|1080p|720p|4K|UHD)", re.IGNORECASE)
    DV_PATTERN = re.compile(r"(DV|DoVi|Dolby\.?Vision)", re.IGNORECASE)
    FEL_PATTERN = re.compile(r"(FEL|BL\+EL|P7)", re.IGNORECASE)
    PROFILE_PATTERN = re.compile(r"P([4-9])", re.IGNORECASE)
    ATMOS_PATTERN = re.compile(r"(Atmos|TrueHD)", re.IGNORECASE)
    HDR_PATTERN = re.compile(r"\b(HDR10?|HDR)\b", re.IGNORECASE)

    def __init__(self):
        """Initialize upgrade detector with settings"""
        self.settings = get_settings()

    def parse_quality_from_title(self, title: str) -> dict[str, Any]:
        """
        Parse quality information from torrent title

        Args:
            title: Torrent title

        Returns:
            dict: Parsed quality information
        """
        quality = {
            "resolution": None,
            "has_dv": False,
            "has_fel": False,
            "dv_profile": None,
            "has_atmos": False,
            "has_hdr": False,
        }

        # Resolution
        res_match = self.RESOLUTION_PATTERN.search(title)
        if res_match:
            res = res_match.group(1).lower()
            if res in ("2160p", "4k", "uhd"):
                quality["resolution"] = "2160p"
            elif res == "1080p":
                quality["resolution"] = "1080p"
            elif res == "720p":
                quality["resolution"] = "720p"

        # Dolby Vision
        if self.DV_PATTERN.search(title):
            quality["has_dv"] = True

        # FEL
        if self.FEL_PATTERN.search(title):
            quality["has_fel"] = True
            quality["dv_profile"] = "P7"

        # DV Profile
        profile_match = self.PROFILE_PATTERN.search(title)
        if profile_match:
            quality["dv_profile"] = f"P{profile_match.group(1)}"

        # Atmos
        if self.ATMOS_PATTERN.search(title):
            quality["has_atmos"] = True

        # HDR (but not if DV is present)
        if self.HDR_PATTERN.search(title) and not quality["has_dv"]:
            quality["has_hdr"] = True

        return quality

    def should_notify(
        self,
        torrent_title: str,
        current_movie: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None, bool]:
        """
        Determine if a torrent should trigger a notification

        Args:
            torrent_title: Torrent title to evaluate
            current_movie: Current movie metadata from library (None if not in library)

        Returns:
            tuple: (should_notify, upgrade_type, is_duplicate)
                - should_notify: Whether to send notification
                - upgrade_type: Description of upgrade ("P5->P7", "HDR->DV", etc.) or None
                - is_duplicate: Whether this is a duplicate quality
        """
        # Parse new torrent quality
        new_quality = self.parse_quality_from_title(torrent_title)

        # Rule 13: Only library movies
        if self.settings.NOTIFY_ONLY_LIBRARY_MOVIES and not current_movie:
            logger.debug(
                "upgrade_detector.skipped_not_in_library",
                torrent=torrent_title,
            )
            return False, None, False

        # If not in library, check if we should notify anyway
        if not current_movie:
            # Only notify for FEL if NOTIFY_FEL is enabled
            if new_quality["has_fel"] and self.settings.NOTIFY_FEL:
                return True, "FEL (not in library)", False
            return False, None, False

        # Get current quality
        current_quality = {
            "resolution": current_movie.get("resolution"),
            "has_dv": current_movie.get("dv_profile") is not None,
            "has_fel": current_movie.get("dv_fel", False),
            "dv_profile": current_movie.get("dv_profile"),
            "has_atmos": current_movie.get("has_atmos", False),
            "has_hdr": current_movie.get("hdr_type") == "hdr10",
        }

        # Check for duplicate
        is_duplicate = self._is_duplicate(new_quality, current_quality)

        # FEL RULES (Rules 1-4)
        if new_quality["has_fel"]:
            # Rule 1: FEL notifications
            if not self.settings.NOTIFY_FEL:
                return False, None, is_duplicate

            # Rule 4: FEL duplicates
            if is_duplicate and not self.settings.NOTIFY_FEL_DUPLICATES:
                logger.debug("upgrade_detector.skipped_fel_duplicate", torrent=torrent_title)
                return False, None, True

            # Rule 2: P5→P7 FEL upgrades
            if current_quality["dv_profile"] == "P5" and self.settings.NOTIFY_FEL_FROM_P5:
                return True, "P5→P7 FEL", is_duplicate

            # Rule 3: HDR→P7 FEL upgrades
            if current_quality["has_hdr"] and self.settings.NOTIFY_FEL_FROM_HDR:
                return True, "HDR→P7 FEL", is_duplicate

            # General FEL notification
            if not current_quality["has_fel"]:
                return True, "New FEL", is_duplicate

        # DOLBY VISION RULES (Rules 5-7)
        if new_quality["has_dv"] and not new_quality["has_fel"]:
            # Rule 5: General DV notifications
            if not self.settings.NOTIFY_DV:
                return False, None, is_duplicate

            # Rule 6: HDR→DV upgrades
            if current_quality["has_hdr"] and self.settings.NOTIFY_DV_FROM_HDR:
                return True, "HDR→DV", is_duplicate

            # Rule 7: DV profile upgrades
            if (
                current_quality["has_dv"]
                and self.settings.NOTIFY_DV_PROFILE_UPGRADES
            ):
                # Check for profile upgrade (P4→P5, P5→P8, etc.)
                current_profile = current_quality.get("dv_profile")
                new_profile = new_quality.get("dv_profile")

                if current_profile and new_profile and current_profile != new_profile:
                    return True, f"{current_profile}→{new_profile}", is_duplicate

            # General DV upgrade
            if not current_quality["has_dv"]:
                return True, "New DV", is_duplicate

        # ATMOS RULES (Rules 8-10)
        if new_quality["has_atmos"]:
            # Rule 8: Atmos notifications
            if not self.settings.NOTIFY_ATMOS:
                return False, None, is_duplicate

            # Rule 9: Only if no current Atmos
            if (
                self.settings.NOTIFY_ATMOS_ONLY_IF_NO_ATMOS
                and current_quality["has_atmos"]
            ):
                # Skip unless combined with DV upgrade
                if not (new_quality["has_dv"] and not current_quality["has_dv"]):
                    return False, None, is_duplicate

            # Rule 10: Atmos with DV upgrade
            if (
                new_quality["has_dv"]
                and not current_quality["has_dv"]
                and self.settings.NOTIFY_ATMOS_WITH_DV_UPGRADE
            ):
                return True, "DV + Atmos", is_duplicate

            # General Atmos notification
            if not current_quality["has_atmos"]:
                return True, "New Atmos", is_duplicate

        # RESOLUTION RULES (Rules 11-12)
        if new_quality["resolution"]:
            # Rule 11: Resolution notifications
            if not self.settings.NOTIFY_RESOLUTION:
                return False, None, is_duplicate

            # Rule 12: Only resolution upgrades
            if self.settings.NOTIFY_RESOLUTION_ONLY_UPGRADES:
                current_res = current_quality.get("resolution")
                new_res = new_quality["resolution"]

                # Check if it's an upgrade
                res_order = {"720p": 1, "1080p": 2, "2160p": 3}
                current_order = res_order.get(current_res, 0)
                new_order = res_order.get(new_res, 0)

                if new_order > current_order:
                    return True, f"{current_res}→{new_res}", is_duplicate
                else:
                    return False, None, is_duplicate
            else:
                # Any resolution change
                if current_quality.get("resolution") != new_quality["resolution"]:
                    return True, f"Resolution: {new_quality['resolution']}", is_duplicate

        # No notification rules matched
        return False, None, is_duplicate

    def _is_duplicate(
        self,
        new_quality: dict[str, Any],
        current_quality: dict[str, Any],
    ) -> bool:
        """
        Check if new quality is a duplicate of current

        Args:
            new_quality: Parsed new torrent quality
            current_quality: Current movie quality

        Returns:
            bool: True if duplicate
        """
        # Check key quality indicators
        if new_quality["has_fel"] != current_quality["has_fel"]:
            return False

        if new_quality["has_dv"] != current_quality["has_dv"]:
            return False

        if new_quality["dv_profile"] != current_quality["dv_profile"]:
            return False

        if new_quality["has_atmos"] != current_quality["has_atmos"]:
            return False

        if new_quality["resolution"] != current_quality["resolution"]:
            return False

        # All key quality indicators match - it's a duplicate
        return True

    def get_quality_score(self, quality: dict[str, Any]) -> int:
        """
        Calculate quality score.

        Delegates to the consolidated quality scoring module.

        Args:
            quality: Quality dictionary

        Returns:
            int: Quality score
        """
        from app.utils.quality_scoring import calculate_library_quality_score

        return calculate_library_quality_score({
            "dv_fel": quality.get("has_fel", False),
            "dv_profile": quality.get("dv_profile") if quality.get("has_dv") else None,
            "resolution": quality.get("resolution"),
            "has_atmos": quality.get("has_atmos", False),
        })
