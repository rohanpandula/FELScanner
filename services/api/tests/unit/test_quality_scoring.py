"""
Unit tests for consolidated quality scoring module
"""
import pytest

from app.utils.quality_scoring import (
    calculate_library_quality_score,
    calculate_torrent_quality_score,
)


# --- Library scoring ---


class TestLibraryQualityScore:
    def test_fel_4k_atmos(self):
        """FEL + 4K + Atmos = 130"""
        data = {"dv_fel": True, "dv_profile": "P7", "resolution": "2160p", "has_atmos": True}
        assert calculate_library_quality_score(data) == 130

    def test_fel_only(self):
        """FEL alone = 100"""
        data = {"dv_fel": True, "dv_profile": "P7", "resolution": None, "has_atmos": False}
        assert calculate_library_quality_score(data) == 100

    def test_dv_4k(self):
        """DV (not FEL) + 4K = 70"""
        data = {"dv_fel": False, "dv_profile": "P8", "resolution": "2160p", "has_atmos": False}
        assert calculate_library_quality_score(data) == 70

    def test_dv_only(self):
        """DV alone = 50"""
        data = {"dv_fel": False, "dv_profile": "P5", "resolution": None, "has_atmos": False}
        assert calculate_library_quality_score(data) == 50

    def test_4k_only(self):
        """4K alone = 20"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": "2160p", "has_atmos": False}
        assert calculate_library_quality_score(data) == 20

    def test_4k_string(self):
        """'4K' string treated same as 2160p"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": "4K", "has_atmos": False}
        assert calculate_library_quality_score(data) == 20

    def test_1080p(self):
        """1080p = 10"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": "1080p", "has_atmos": False}
        assert calculate_library_quality_score(data) == 10

    def test_atmos_only(self):
        """Atmos alone = 10"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": None, "has_atmos": True}
        assert calculate_library_quality_score(data) == 10

    def test_empty(self):
        """No features = 0"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": None, "has_atmos": False}
        assert calculate_library_quality_score(data) == 0

    def test_720p_not_scored(self):
        """720p gets no resolution bonus"""
        data = {"dv_fel": False, "dv_profile": None, "resolution": "720p", "has_atmos": False}
        assert calculate_library_quality_score(data) == 0

    def test_fel_trumps_dv(self):
        """FEL gets 100, not 100+50"""
        data = {"dv_fel": True, "dv_profile": "P7", "resolution": None, "has_atmos": False}
        assert calculate_library_quality_score(data) == 100

    def test_missing_keys_default(self):
        """Missing keys treated as falsy"""
        assert calculate_library_quality_score({}) == 0


# --- Torrent scoring ---


class TestTorrentQualityScore:
    def test_full_combo(self):
        """FEL + 2160p + Atmos + REMUX + TrueHD + HEVC = 200"""
        data = {
            "has_fel": True,
            "dv_profile": "P7",
            "has_dv": True,
            "resolution": "2160p",
            "has_atmos": True,
            "source": "REMUX",
            "audio_codec": "TrueHD",
            "video_codec": "HEVC",
        }
        assert calculate_torrent_quality_score(data) == 200

    def test_p8_2160p(self):
        """P8 + 2160p = 140"""
        data = {
            "has_fel": False,
            "dv_profile": "P8",
            "has_dv": True,
            "resolution": "2160p",
            "has_atmos": False,
            "source": None,
            "audio_codec": None,
            "video_codec": None,
        }
        assert calculate_torrent_quality_score(data) == 140

    def test_generic_dv(self):
        """Generic DV (not P8, not FEL) = 80"""
        data = {
            "has_fel": False,
            "dv_profile": "P5",
            "has_dv": True,
            "resolution": None,
            "has_atmos": False,
            "source": None,
            "audio_codec": None,
            "video_codec": None,
        }
        assert calculate_torrent_quality_score(data) == 80

    def test_remux_vs_bluray(self):
        """REMUX scores higher than BluRay"""
        base = {
            "has_fel": False, "dv_profile": None, "has_dv": False,
            "resolution": None, "has_atmos": False,
            "audio_codec": None, "video_codec": None,
        }
        remux = calculate_torrent_quality_score({**base, "source": "REMUX"})
        bluray = calculate_torrent_quality_score({**base, "source": "BluRay"})
        assert remux > bluray
        assert remux == 15
        assert bluray == 10

    def test_truehd_vs_dtshd(self):
        """TrueHD scores higher than DTS-HD MA"""
        base = {
            "has_fel": False, "dv_profile": None, "has_dv": False,
            "resolution": None, "has_atmos": False, "source": None,
            "video_codec": None,
        }
        truehd = calculate_torrent_quality_score({**base, "audio_codec": "TrueHD"})
        dtshd = calculate_torrent_quality_score({**base, "audio_codec": "DTS-HD MA"})
        assert truehd > dtshd
        assert truehd == 10
        assert dtshd == 8

    def test_1080p(self):
        """1080p = 30"""
        data = {
            "has_fel": False, "dv_profile": None, "has_dv": False,
            "resolution": "1080p", "has_atmos": False,
            "source": None, "audio_codec": None, "video_codec": None,
        }
        assert calculate_torrent_quality_score(data) == 30

    def test_empty(self):
        """No features = 0"""
        assert calculate_torrent_quality_score({}) == 0
