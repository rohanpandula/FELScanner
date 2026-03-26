"""
Torrent Title Parser
Sophisticated regex-based metadata extraction from IPT torrent titles
"""
import re
from typing import Any


class TorrentTitleParser:
    """
    Parse torrent titles to extract structured metadata

    Extracts: year, resolution, source, DV profile, FEL, HDR type, Atmos,
    audio codec, video codec, release type, release group, languages
    """

    # Regex patterns for metadata extraction
    YEAR_PATTERN = re.compile(r'\b(19\d{2}|20\d{2})\b')
    RESOLUTION_PATTERN = re.compile(r'\b(2160p|1080p|720p|4K|UHD)\b', re.IGNORECASE)
    SOURCE_PATTERN = re.compile(r'\b(BluRay|Blu-ray|WEB-DL|WEBRip|HDTV|REMUX|Remux)\b', re.IGNORECASE)

    # Dolby Vision patterns
    DV_PROFILE_PATTERN = re.compile(r'\bDV\s*P(\d)\b|\bProfile\s*(\d)\b', re.IGNORECASE)
    DV_GENERIC_PATTERN = re.compile(r'\bDV\b(?!D)', re.IGNORECASE)  # DV but not DVD

    # HDR patterns
    HDR_PATTERN = re.compile(r'\b(HDR10\+?|HDR|DV-HDR10|Dolby\s*Vision)\b', re.IGNORECASE)

    # Audio patterns
    ATMOS_PATTERN = re.compile(r'\b(Atmos|TrueHD.*?Atmos)\b', re.IGNORECASE)
    AUDIO_CODEC_PATTERN = re.compile(
        r'\b(TrueHD|DTS-HD\s*MA|DTS-X|DTS|Dts-HDMa|DD\+?|EAC3|AC-?3|AAC|LPCM|FLAC)\b',
        re.IGNORECASE
    )
    AUDIO_CHANNELS_PATTERN = re.compile(r'\b(\d)\s*[\. ]?\s*(\d)(?:\s*ch)?\b')

    # Video codec patterns
    VIDEO_CODEC_PATTERN = re.compile(r'\b(HEVC|H\.?265|x265|H\.?264|x264|AVC)\b', re.IGNORECASE)

    # Bit depth
    BIT_DEPTH_PATTERN = re.compile(r'\b10[- ]?Bit\b', re.IGNORECASE)

    # Release type
    RELEASE_TYPE_PATTERN = re.compile(
        r'\b(REMUX|Remux|REPACK|PROPER|EXTENDED|UNRATED|Director\'?s?\s*Cut|iNTERNAL|INTERNAL)\b',
        re.IGNORECASE
    )

    # Release group (usually at the end after a dash)
    RELEASE_GROUP_PATTERN = re.compile(r'-([A-Za-z0-9]+(?:\s+[A-Z]+\s+[A-Z]+)?)$')

    # Languages (in brackets or specific keywords)
    LANGUAGE_PATTERN = re.compile(r'\[(.*?)\]|MULTI|DUAL', re.IGNORECASE)

    @classmethod
    def parse(cls, title: str) -> dict[str, Any]:
        """
        Parse a torrent title and extract all metadata

        Args:
            title: Raw torrent title string

        Returns:
            dict: Extracted metadata with keys:
                - clean_title: Movie title without metadata tags
                - year: Release year (int or None)
                - resolution: Resolution string (2160p, 1080p, etc.)
                - source: Source type (BluRay, REMUX, etc.)
                - dv_profile: Dolby Vision profile (P5, P7, P8, etc.)
                - has_dv: Boolean if DV detected
                - has_fel: Boolean if FEL (P7) detected
                - hdr_type: HDR type (DV, HDR10, DV-HDR10)
                - has_atmos: Boolean if Atmos detected
                - audio_codec: Primary audio codec
                - audio_channels: Audio channel layout (5.1, 7.1, etc.)
                - video_codec: Video codec (HEVC, H265, etc.)
                - bit_depth: Bit depth (10, etc.)
                - release_type: Release type (REMUX, EXTENDED, etc.)
                - release_group: Release group name
                - languages: List of languages
        """
        metadata = {
            'clean_title': None,
            'year': None,
            'resolution': None,
            'source': None,
            'dv_profile': None,
            'has_dv': False,
            'has_fel': False,
            'hdr_type': None,
            'has_atmos': False,
            'audio_codec': None,
            'audio_channels': None,
            'video_codec': None,
            'bit_depth': None,
            'release_type': None,
            'release_group': None,
            'languages': [],
        }

        # Year
        year_match = cls.YEAR_PATTERN.search(title)
        if year_match:
            metadata['year'] = int(year_match.group(1))

        # Resolution
        res_match = cls.RESOLUTION_PATTERN.search(title)
        if res_match and res_match.group(1):
            resolution = res_match.group(1).lower()
            # Normalize UHD and 4K to 2160p
            if resolution in ('uhd', '4k'):
                metadata['resolution'] = '2160p'
            else:
                metadata['resolution'] = resolution

        # Source
        source_match = cls.SOURCE_PATTERN.search(title)
        if source_match and source_match.group(1):
            metadata['source'] = source_match.group(1)

        # Dolby Vision Profile
        dv_profile_match = cls.DV_PROFILE_PATTERN.search(title)
        if dv_profile_match:
            profile_num = dv_profile_match.group(1) or dv_profile_match.group(2)
            metadata['dv_profile'] = f'P{profile_num}'
            metadata['has_dv'] = True
            metadata['has_fel'] = (profile_num == '7')
        elif cls.DV_GENERIC_PATTERN.search(title):
            # DV mentioned but no specific profile
            metadata['has_dv'] = True
            # Try to infer from other markers
            if 'HEVC DV' in title or 'DV HEVC' in title:
                metadata['dv_profile'] = 'P5'  # Common fallback

        # HDR Type
        hdr_match = cls.HDR_PATTERN.search(title)
        if hdr_match and hdr_match.group(1):
            hdr_text = hdr_match.group(1).upper()
            if 'DV-HDR10' in hdr_text or 'DV/HDR10' in hdr_text:
                metadata['hdr_type'] = 'DV/HDR10'
            elif 'DV' in hdr_text or 'DOLBY' in hdr_text:
                metadata['hdr_type'] = 'DV'
            elif 'HDR10+' in hdr_text:
                metadata['hdr_type'] = 'HDR10+'
            elif 'HDR10' in hdr_text or 'HDR' in hdr_text:
                metadata['hdr_type'] = 'HDR10'

        # Override if we detected DV profile
        if metadata['has_dv'] and not metadata['hdr_type']:
            metadata['hdr_type'] = 'DV'

        # Atmos
        if cls.ATMOS_PATTERN.search(title):
            metadata['has_atmos'] = True

        # Audio Codec
        audio_match = cls.AUDIO_CODEC_PATTERN.search(title)
        if audio_match and audio_match.group(1):
            codec = audio_match.group(1).upper()
            # Normalize variations
            if 'TRUEHD' in codec:
                metadata['audio_codec'] = 'TrueHD'
            elif 'DTS-HD' in codec or 'DTSHDMA' in codec or 'DTS-HDMA' in codec:
                metadata['audio_codec'] = 'DTS-HD MA'
            elif 'DTS-X' in codec:
                metadata['audio_codec'] = 'DTS-X'
            elif codec == 'DTS':
                metadata['audio_codec'] = 'DTS'
            elif 'EAC3' in codec or 'DD+' in codec:
                metadata['audio_codec'] = 'EAC3'
            elif 'AC3' in codec or 'AC-3' in codec:
                metadata['audio_codec'] = 'AC3'
            else:
                metadata['audio_codec'] = codec

        # Audio Channels
        channels_match = cls.AUDIO_CHANNELS_PATTERN.search(title)
        if channels_match:
            ch1, ch2 = channels_match.groups()
            metadata['audio_channels'] = f'{ch1}.{ch2}'

        # Video Codec
        video_match = cls.VIDEO_CODEC_PATTERN.search(title)
        if video_match and video_match.group(1):
            codec = video_match.group(1).upper()
            if codec in ('HEVC', 'H265', 'H.265', 'X265'):
                metadata['video_codec'] = 'HEVC'
            elif codec in ('H264', 'H.264', 'X264', 'AVC'):
                metadata['video_codec'] = 'H.264'
            else:
                metadata['video_codec'] = codec

        # Bit Depth
        if cls.BIT_DEPTH_PATTERN.search(title):
            metadata['bit_depth'] = 10

        # Release Type
        release_type_match = cls.RELEASE_TYPE_PATTERN.search(title)
        if release_type_match and release_type_match.group(1):
            rtype = release_type_match.group(1).upper()
            if 'REMUX' in rtype:
                metadata['release_type'] = 'REMUX'
            elif 'EXTENDED' in rtype:
                metadata['release_type'] = 'EXTENDED'
            elif 'DIRECTOR' in rtype:
                metadata['release_type'] = "Director's Cut"
            elif 'INTERNAL' in rtype:
                metadata['release_type'] = 'INTERNAL'
            else:
                metadata['release_type'] = rtype

        # Release Group
        group_match = cls.RELEASE_GROUP_PATTERN.search(title)
        if group_match and group_match.group(1):
            metadata['release_group'] = group_match.group(1)

        # Languages
        lang_matches = cls.LANGUAGE_PATTERN.findall(title)
        languages = []
        for match in lang_matches:
            if isinstance(match, tuple):
                match = match[0] if match[0] else match[1]
            if match and match not in ('MULTI', 'DUAL'):
                # Parse bracketed languages like "[Japanese]" or "[French English]"
                langs = match.replace('[', '').replace(']', '').split()
                languages.extend(langs)
            elif match in ('MULTI', 'DUAL'):
                languages.append(match)
        metadata['languages'] = list(set(languages))  # Remove duplicates

        # Clean title - extract title without metadata tags
        clean_title = title

        # First try: Remove everything after the year
        if metadata['year']:
            year_pos = title.find(str(metadata['year']))
            if year_pos > 0:
                clean_title = title[:year_pos].strip()
        else:
            # Second try: Remove everything after resolution/UHD/4K markers
            res_patterns = [
                r'(\s+UHD\b)',  # Match UHD as whole word
                r'(\s+4K\b)',    # Match 4K as whole word
                r'(\s+2160p)',
                r'(\s+1080p)',
                r'(\s+720p)',
            ]
            for pattern in res_patterns:
                match = re.search(pattern, title, re.IGNORECASE)
                if match:
                    clean_title = title[:match.start()].strip()
                    break

            # Third try: Remove everything after source markers if no resolution
            if clean_title == title:
                source_patterns = [
                    r'(\s+BluRay)',
                    r'(\s+Blu-ray)',
                    r'(\s+WEB-DL)',
                    r'(\s+WEBRip)',
                    r'(\s+REMUX)',
                ]
                for pattern in source_patterns:
                    match = re.search(pattern, title, re.IGNORECASE)
                    if match:
                        clean_title = title[:match.start()].strip()
                        break

        # Remove language brackets from clean title
        clean_title = re.sub(r'\[.*?\]', '', clean_title).strip()

        # Remove common prefixes/suffixes
        clean_title = re.sub(r'\s*-\s*$', '', clean_title)

        metadata['clean_title'] = clean_title

        return metadata

    @classmethod
    def get_quality_score(cls, metadata: dict[str, Any]) -> int:
        """
        Calculate quality score for ranking torrents.

        Delegates to the consolidated quality scoring module.

        Args:
            metadata: Parsed torrent metadata

        Returns:
            int: Quality score
        """
        from app.utils.quality_scoring import calculate_torrent_quality_score

        return calculate_torrent_quality_score(metadata)
