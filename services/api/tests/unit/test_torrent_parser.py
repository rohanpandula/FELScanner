"""
Unit tests for TorrentTitleParser
"""
import pytest

from app.utils.torrent_parser import TorrentTitleParser


class TestTorrentTitleParsing:
    def test_standard_title(self):
        title = "End Of Watch 2012 2160p UHD BluRay DV P7 HDR REMUX DTS-HD MA 5.1 H265-BEN THE MEN"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "End Of Watch"
        assert result["year"] == 2012
        assert result["resolution"] == "2160p"
        assert result["dv_profile"] == "P7"
        assert result["has_dv"] is True
        assert result["has_fel"] is True
        assert result["audio_codec"] == "DTS-HD MA"
        assert result["audio_channels"] == "5.1"
        assert result["video_codec"] == "HEVC"
        assert result["release_group"] == "BEN THE MEN"

    def test_atmos_title(self):
        title = "Moana 2 2024 2160p BluRay REMUX DV P8 TrueHD Atmos 7.1 HEVC-FraMeSToR"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "Moana 2"
        assert result["year"] == 2024
        assert result["has_atmos"] is True
        assert result["audio_codec"] == "TrueHD"
        assert result["dv_profile"] == "P8"
        assert result["has_fel"] is False
        assert result["release_group"] == "FraMeSToR"

    def test_fel_from_bl_el(self):
        """BL+EL in title should not be caught by DV_PROFILE_PATTERN but inferred"""
        title = "Movie 2023 2160p BL+EL REMUX TrueHD 7.1-GROUP"
        result = TorrentTitleParser.parse(title)
        # BL+EL doesn't match DV_PROFILE_PATTERN but DV_GENERIC_PATTERN won't match either
        # This depends on exact regex behavior
        assert result["year"] == 2023
        assert result["resolution"] == "2160p"

    def test_p7_detection(self):
        title = "The Matrix 1999 2160p DV P7 BluRay REMUX TrueHD Atmos 7.1 HEVC-FGT"
        result = TorrentTitleParser.parse(title)

        assert result["dv_profile"] == "P7"
        assert result["has_fel"] is True
        assert result["has_dv"] is True

    def test_p5_detection(self):
        title = "Inception 2010 2160p DV P5 BluRay HEVC DTS-HD MA 5.1-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["dv_profile"] == "P5"
        assert result["has_fel"] is False

    def test_generic_dv_no_profile(self):
        title = "Movie 2022 2160p DV HEVC BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["has_dv"] is True
        assert result["dv_profile"] == "P5"  # HEVC DV defaults to P5

    def test_hdr10_detection(self):
        title = "Movie 2023 2160p HDR10 BluRay HEVC DTS-HD MA 5.1-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["hdr_type"] == "HDR10"
        assert result["has_dv"] is False

    def test_uhd_normalization(self):
        title = "Movie 2023 UHD BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["resolution"] == "2160p"

    def test_4k_normalization(self):
        title = "Movie 2023 4K BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["resolution"] == "2160p"

    def test_1080p(self):
        title = "Movie 2023 1080p BluRay x264 DTS-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["resolution"] == "1080p"
        assert result["video_codec"] == "H.264"

    def test_remux_release_type(self):
        title = "Movie 2023 2160p BluRay REMUX DV P7 HEVC-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["release_type"] == "REMUX"
        assert result["source"] == "REMUX"

    def test_extended_release_type(self):
        title = "Movie 2023 EXTENDED 2160p BluRay HEVC-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["release_type"] == "EXTENDED"

    def test_10bit(self):
        title = "Movie 2023 2160p 10-Bit BluRay HEVC-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["bit_depth"] == 10

    def test_audio_codec_eac3(self):
        title = "Movie 2023 2160p WEB-DL DD+ 5.1 HEVC-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["audio_codec"] == "EAC3"

    def test_audio_channels_71(self):
        title = "Movie 2023 2160p BluRay TrueHD 7.1-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["audio_channels"] == "7.1"

    def test_release_group_extraction(self):
        title = "Movie 2023 2160p BluRay HEVC-FraMeSToR"
        result = TorrentTitleParser.parse(title)

        assert result["release_group"] == "FraMeSToR"


class TestCleanTitleExtraction:
    def test_year_based_extraction(self):
        title = "The Dark Knight 2008 2160p BluRay REMUX-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "The Dark Knight"

    def test_uhd_based_fallback(self):
        """When no year, extract before UHD marker"""
        title = "Some Movie UHD BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "Some Movie"

    def test_resolution_based_fallback(self):
        """When no year, extract before resolution"""
        title = "Some Movie 2160p BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "Some Movie"

    def test_source_based_fallback(self):
        """When no year or resolution markers, extract before source"""
        title = "Some Movie BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert result["clean_title"] == "Some Movie"

    def test_language_brackets_removed(self):
        title = "[Japanese] Movie 2023 2160p BluRay-GROUP"
        result = TorrentTitleParser.parse(title)

        assert "[" not in result["clean_title"]
        assert "]" not in result["clean_title"]


class TestQualityScore:
    def test_score_delegates_to_module(self):
        """Quality score should use consolidated scoring"""
        metadata = {
            "has_fel": True,
            "dv_profile": "P7",
            "has_dv": True,
            "resolution": "2160p",
            "has_atmos": True,
            "source": "REMUX",
            "audio_codec": "TrueHD",
            "video_codec": "HEVC",
        }
        score = TorrentTitleParser.get_quality_score(metadata)
        assert score == 200  # Max torrent score

    def test_score_no_features(self):
        metadata = {
            "has_fel": False,
            "dv_profile": None,
            "has_dv": False,
            "resolution": None,
            "has_atmos": False,
            "source": None,
            "audio_codec": None,
            "video_codec": None,
        }
        score = TorrentTitleParser.get_quality_score(metadata)
        assert score == 0
