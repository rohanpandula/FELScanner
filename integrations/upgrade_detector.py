"""
Upgrade Detector

Smart logic to determine if a new release is actually an upgrade worth notifying about.
Prevents notification spam by only alerting on genuine quality improvements.
"""

import logging
import re
from typing import Dict, Tuple, Optional, Any

log = logging.getLogger(__name__)


class UpgradeDetector:
    """Determines if a new release is a notification-worthy upgrade"""

    def __init__(self, notification_config: Dict[str, Any]):
        """
        Initialize with notification preferences

        Args:
            notification_config: Dict of notification settings
        """
        self.config = notification_config

    def is_notification_worthy(
        self,
        current_quality: Dict[str, Any],
        new_quality: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Determine if new release warrants notification

        Args:
            current_quality: Current movie quality details
            new_quality: New release quality details

        Returns:
            (should_notify: bool, reason: str)
        """
        # Parse qualities
        current = self.parse_quality(current_quality)
        new = self.parse_quality(new_quality)

        # Check for exact duplicate
        if self.is_duplicate(current, new):
            return False, "Already have this exact quality"

        # Check FEL upgrade notifications
        if self.config.get('notify_fel', True):
            if new['is_fel']:
                # New release is FEL
                if current['is_fel']:
                    # Already have FEL
                    if not self.config.get('notify_fel_duplicates', False):
                        return False, "Already have P7 FEL version"
                    else:
                        return True, "Additional P7 FEL copy (per settings)"
                else:
                    # Upgrade to FEL!
                    if current['has_dv']:
                        # Upgrade from lower DV profile to FEL
                        if self.config.get('notify_fel_from_p5', True):
                            return True, f"Upgrade: DV P{current['dv_profile']} → P7 FEL ⭐"
                    else:
                        # Upgrade from HDR10/SDR to FEL
                        if self.config.get('notify_fel_from_hdr', True):
                            return True, "Upgrade: HDR10/SDR → P7 FEL ⭐"

        # Check general DV upgrade notifications
        if self.config.get('notify_dv', False):
            if new['has_dv'] and not current['has_dv']:
                # Upgrade from no DV to DV
                if self.config.get('notify_dv_from_hdr', True):
                    return True, f"Upgrade: No DV → DV P{new['dv_profile']}"

            if self.config.get('notify_dv_profile_upgrades', True):
                if new['has_dv'] and current['has_dv']:
                    # Both have DV, check for profile upgrade
                    if new['dv_profile'] and current['dv_profile']:
                        if new['dv_profile'] > current['dv_profile']:
                            return True, f"Upgrade: DV P{current['dv_profile']} → P{new['dv_profile']}"

        # Check Atmos upgrade notifications
        if self.config.get('notify_atmos', False):
            if new['has_atmos'] and not current['has_atmos']:
                # New Atmos version
                if self.config.get('notify_atmos_only_if_no_atmos', True):
                    # Check if this is standalone Atmos or combo upgrade
                    if new['has_dv'] and current['has_dv']:
                        if new['dv_profile'] and current['dv_profile']:
                            if new['dv_profile'] > current['dv_profile']:
                                # Combo upgrade: better DV + Atmos
                                if self.config.get('notify_atmos_with_dv_upgrade', True):
                                    return True, f"Combo upgrade: DV P{current['dv_profile']} → P{new['dv_profile']} + Atmos 🎵"

                    # Standalone Atmos addition
                    return True, "Added: TrueHD Atmos 🎵"

        # Check resolution upgrades
        if self.config.get('notify_resolution', False):
            if self.is_resolution_upgrade(current, new):
                if self.config.get('notify_resolution_only_upgrades', True):
                    return True, f"Upgrade: {current['resolution']} → {new['resolution']}"

        # No notification criteria met
        return False, "Not an upgrade per notification settings"

    def parse_quality(self, quality_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize quality details

        Args:
            quality_data: Raw quality data from Plex/torrent

        Returns:
            Normalized quality dict
        """
        dv_profile = quality_data.get('dv_profile')
        if dv_profile:
            try:
                dv_profile = int(dv_profile)
            except (ValueError, TypeError):
                dv_profile = None

        return {
            'has_dv': dv_profile is not None,
            'dv_profile': dv_profile,
            'is_fel': bool(quality_data.get('dv_fel', False) or quality_data.get('is_fel', False)),
            'has_atmos': bool(quality_data.get('has_atmos', False)),
            'resolution': quality_data.get('resolution', 'unknown').lower(),
            'file_size': quality_data.get('file_size', 0),
            'bitrate': quality_data.get('bitrate', 0)
        }

    def is_duplicate(self, current: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """
        Check if new quality is exact duplicate of current

        Args:
            current: Parsed current quality
            new: Parsed new quality

        Returns:
            True if duplicate
        """
        # Check DV profile match
        if current['dv_profile'] != new['dv_profile']:
            return False

        # Check FEL status match
        if current['is_fel'] != new['is_fel']:
            return False

        # Check Atmos match
        if current['has_atmos'] != new['has_atmos']:
            return False

        # Check resolution match (fuzzy)
        if not self._resolution_matches(current['resolution'], new['resolution']):
            return False

        return True

    def is_resolution_upgrade(self, current: Dict[str, Any], new: Dict[str, Any]) -> bool:
        """
        Check if new resolution is better than current

        Args:
            current: Parsed current quality
            new: Parsed new quality

        Returns:
            True if resolution upgrade
        """
        resolution_order = {
            'unknown': 0,
            'sd': 1,
            '480p': 1,
            '720p': 2,
            'hd': 2,
            '1080p': 3,
            'full hd': 3,
            'fhd': 3,
            '2160p': 4,
            '4k': 4,
            'uhd': 4,
            '8k': 5
        }

        current_res = current['resolution'].lower()
        new_res = new['resolution'].lower()

        current_value = resolution_order.get(current_res, 0)
        new_value = resolution_order.get(new_res, 0)

        return new_value > current_value

    def _resolution_matches(self, res1: str, res2: str) -> bool:
        """Check if two resolutions are equivalent"""
        resolution_aliases = {
            '720p': ['hd', '720p'],
            '1080p': ['full hd', 'fhd', '1080p'],
            '2160p': ['4k', 'uhd', '2160p', '4k uhd'],
            '8k': ['8k', '4320p']
        }

        res1_lower = res1.lower()
        res2_lower = res2.lower()

        # Direct match
        if res1_lower == res2_lower:
            return True

        # Check aliases
        for canonical, aliases in resolution_aliases.items():
            if res1_lower in aliases and res2_lower in aliases:
                return True

        return False

    def parse_torrent_quality(self, torrent_title: str) -> Dict[str, Any]:
        """
        Parse quality information from torrent title

        Args:
            torrent_title: Torrent title string

        Returns:
            Quality dict suitable for parse_quality()
        """
        title_upper = torrent_title.upper()

        quality = {
            'dv_profile': None,
            'is_fel': False,
            'has_atmos': False,
            'resolution': 'unknown'
        }

        # Check for DV Profile 7 FEL
        if 'PROFILE 7' in title_upper or 'P7' in title_upper or 'PROFILE7' in title_upper:
            quality['dv_profile'] = 7

        # Check for FEL markers
        if 'FEL' in title_upper or 'BL+EL' in title_upper or 'BL EL' in title_upper:
            quality['is_fel'] = True
            if not quality['dv_profile']:
                # FEL implies Profile 7
                quality['dv_profile'] = 7

        # Check for other DV profiles
        if not quality['dv_profile']:
            profile_match = re.search(r'(?:PROFILE\s?|P)([58])', title_upper)
            if profile_match:
                quality['dv_profile'] = int(profile_match.group(1))
            elif 'DOLBY VISION' in title_upper or 'DV' in title_upper or 'DOVI' in title_upper:
                # Generic DV, assume Profile 5 (most common)
                quality['dv_profile'] = 5

        # Check for Atmos
        if 'ATMOS' in title_upper or 'TRUEHD ATMOS' in title_upper:
            quality['has_atmos'] = True

        # Parse resolution
        if '2160P' in title_upper or '4K' in title_upper or 'UHD' in title_upper:
            quality['resolution'] = '2160p'
        elif '1080P' in title_upper or 'FHD' in title_upper:
            quality['resolution'] = '1080p'
        elif '720P' in title_upper or 'HD' in title_upper:
            quality['resolution'] = '720p'
        elif '480P' in title_upper or 'SD' in title_upper:
            quality['resolution'] = '480p'

        return quality
