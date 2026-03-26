"""
Quality Scoring — Single Source of Truth

Two scoring contexts:
1. Library scoring: for ranking Plex versions and upgrade detection
2. Torrent scoring: for ranking IPT search results (more granular)
"""
from typing import Any


def calculate_library_quality_score(data: dict[str, Any]) -> int:
    """
    Calculate quality score for library version ranking and upgrade detection.

    Used by: PlexScanner, Movie model, UpgradeDetector

    Score breakdown:
    - FEL (P7): +100
    - Dolby Vision (other): +50
    - 4K/2160p: +20
    - 1080p: +10
    - TrueHD Atmos: +10
    - Max: 140

    Args:
        data: Dict with keys: dv_fel (bool), dv_profile (str|None),
              resolution (str|None), has_atmos (bool)

    Returns:
        int: Quality score
    """
    score = 0

    if data.get("dv_fel"):
        score += 100
    elif data.get("dv_profile"):
        score += 50

    resolution = data.get("resolution")
    if resolution in ("2160p", "4K"):
        score += 20
    elif resolution == "1080p":
        score += 10

    if data.get("has_atmos"):
        score += 10

    return score


def calculate_torrent_quality_score(data: dict[str, Any]) -> int:
    """
    Calculate quality score for ranking IPT torrent results.

    More granular than library scoring — accounts for source,
    audio codec, and video codec.

    Score breakdown:
    - FEL (P7): +100 / P8: +90 / Other DV: +80
    - 2160p: +50 / 1080p: +30
    - Atmos: +20
    - REMUX: +15 / BluRay: +10
    - TrueHD: +10 / DTS-HD MA: +8
    - HEVC: +5
    - Max: 200

    Args:
        data: Dict with keys: has_fel, dv_profile, has_dv, resolution,
              has_atmos, source, audio_codec, video_codec

    Returns:
        int: Quality score
    """
    score = 0

    # DV tier
    if data.get("has_fel"):
        score += 100
    elif data.get("dv_profile") == "P8":
        score += 90
    elif data.get("has_dv"):
        score += 80

    # Resolution
    if data.get("resolution") == "2160p":
        score += 50
    elif data.get("resolution") == "1080p":
        score += 30

    # Atmos
    if data.get("has_atmos"):
        score += 20

    # Source quality
    source = (data.get("source") or "").upper()
    if source == "REMUX":
        score += 15
    elif "BLURAY" in source:
        score += 10

    # Audio quality
    audio_codec = data.get("audio_codec")
    if audio_codec == "TrueHD":
        score += 10
    elif audio_codec == "DTS-HD MA":
        score += 8

    # Video codec
    if data.get("video_codec") == "HEVC":
        score += 5

    return score
