"""
Unit tests for PlexScanner detection methods
"""
import pytest
from unittest.mock import patch, MagicMock

from app.integrations.plex.scanner import PlexScanner


@pytest.fixture
def scanner():
    with patch("app.integrations.plex.scanner.get_settings") as mock:
        mock.return_value = MagicMock(
            PLEX_URL="http://test:32400",
            PLEX_TOKEN="test-token",
            PLEX_TIMEOUT=30,
        )
        s = PlexScanner()
        yield s


# --- DV Profile Detection ---


class TestDetectDVProfile:
    def test_dvhe_04(self, scanner):
        stream = {"@codec": "dvhe.04.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P4"
        assert has_fel is False

    def test_dvhe_05(self, scanner):
        stream = {"@codec": "dvhe.05.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P5"
        assert has_fel is False

    def test_dvhe_07_is_fel(self, scanner):
        stream = {"@codec": "dvhe.07.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P7"
        assert has_fel is True

    def test_dvhe_08(self, scanner):
        stream = {"@codec": "dvhe.08.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P8"
        assert has_fel is False

    def test_dvh1_07_is_fel(self, scanner):
        stream = {"@codec": "dvh1.07.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P7"
        assert has_fel is True

    def test_dvh1_08(self, scanner):
        stream = {"@codec": "dvh1.08.06", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P8"
        assert has_fel is False

    def test_dovi_profile_attribute(self, scanner):
        """DOVIProfile attribute overrides codec detection"""
        stream = {"@codec": "hevc", "@DOVIProfile": "7", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P7"
        assert has_fel is True

    def test_dovi_profile_5(self, scanner):
        stream = {"@codec": "hevc", "@DOVIProfile": "5", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P5"
        assert has_fel is False

    def test_colorspace_fallback(self, scanner):
        """colorSpace=dolbyvision defaults to P5"""
        stream = {"@codec": "hevc", "@DOVIProfile": "", "@colorSpace": "dolbyvision"}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile == "P5"
        assert has_fel is False

    def test_no_dv(self, scanner):
        stream = {"@codec": "hevc", "@DOVIProfile": "", "@colorSpace": "bt2020nc"}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert profile is None
        assert has_fel is False

    def test_fel_in_codec_string(self, scanner):
        stream = {"@codec": "hevc BL+EL", "@DOVIProfile": "", "@colorSpace": ""}
        profile, has_fel = scanner.detect_dv_profile(stream)
        assert has_fel is True
        assert profile == "P7"  # FEL without profile defaults to P7


# --- Atmos Detection ---


class TestDetectAtmos:
    def test_explicit_atmos_in_profile(self, scanner):
        streams = [{"@codec": "truehd", "@profile": "Atmos", "@title": "", "@channels": "8"}]
        assert scanner.detect_atmos(streams) is True

    def test_atmos_in_title(self, scanner):
        streams = [{"@codec": "truehd", "@profile": "", "@title": "TrueHD Atmos 7.1"}]
        assert scanner.detect_atmos(streams) is True

    def test_atmos_in_display_title(self, scanner):
        streams = [{"@codec": "truehd", "@profile": "", "@title": "", "@displayTitle": "English (TrueHD Atmos 7.1)"}]
        assert scanner.detect_atmos(streams) is True

    def test_truehd_8_channels_is_atmos(self, scanner):
        """TrueHD with 8 channels = Atmos (7.1 with height channels)"""
        streams = [{"@codec": "truehd", "@profile": "", "@title": "", "@channels": "8"}]
        assert scanner.detect_atmos(streams) is True

    def test_truehd_6_channels_not_atmos(self, scanner):
        """TrueHD with 6 channels (5.1) is NOT Atmos"""
        streams = [{"@codec": "truehd", "@profile": "", "@title": "", "@channels": "6"}]
        assert scanner.detect_atmos(streams) is False

    def test_non_truehd_not_atmos(self, scanner):
        """DTS-HD MA is not Atmos even with 8 channels"""
        streams = [{"@codec": "dca", "@profile": "", "@title": "", "@channels": "8"}]
        assert scanner.detect_atmos(streams) is False

    def test_no_audio_streams(self, scanner):
        assert scanner.detect_atmos([]) is False

    def test_multiple_streams_first_atmos(self, scanner):
        streams = [
            {"@codec": "truehd", "@profile": "Atmos", "@title": "", "@channels": "8"},
            {"@codec": "aac", "@profile": "", "@title": "", "@channels": "2"},
        ]
        assert scanner.detect_atmos(streams) is True

    def test_invalid_channels_value(self, scanner):
        """Non-numeric channels should not crash"""
        streams = [{"@codec": "truehd", "@profile": "", "@title": "", "@channels": "unknown"}]
        assert scanner.detect_atmos(streams) is False


# --- Resolution Parsing ---


class TestParseResolution:
    def test_4k(self, scanner):
        assert scanner.parse_resolution({"@height": "2160"}) == "2160p"

    def test_1080(self, scanner):
        assert scanner.parse_resolution({"@height": "1080"}) == "1080p"

    def test_720(self, scanner):
        assert scanner.parse_resolution({"@height": "720"}) == "720p"

    def test_above_2160(self, scanner):
        assert scanner.parse_resolution({"@height": "4320"}) == "2160p"

    def test_between_1080_2160(self, scanner):
        assert scanner.parse_resolution({"@height": "1440"}) == "1080p"

    def test_below_720(self, scanner):
        assert scanner.parse_resolution({"@height": "480"}) == "480p"

    def test_missing_height(self, scanner):
        assert scanner.parse_resolution({}) is None

    def test_non_numeric(self, scanner):
        assert scanner.parse_resolution({"@height": "unknown"}) is None


# --- Quality Score Delegation ---


class TestQualityScore:
    def test_delegates_to_module(self, scanner):
        version = {"dv_fel": True, "dv_profile": "P7", "resolution": "2160p", "has_atmos": True}
        score = scanner._calculate_quality_score(version)
        assert score == 130  # Library scoring: 100 + 20 + 10

    def test_no_features(self, scanner):
        version = {"dv_fel": False, "dv_profile": None, "resolution": None, "has_atmos": False}
        score = scanner._calculate_quality_score(version)
        assert score == 0
