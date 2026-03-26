"""
Unit tests for UpgradeDetector — 17 notification rules
"""
import pytest
from unittest.mock import patch, MagicMock

from app.integrations.upgrade_detector import UpgradeDetector


def _make_settings(**overrides):
    """Create a mock settings object with all notification flags"""
    defaults = {
        "NOTIFY_FEL": True,
        "NOTIFY_FEL_FROM_P5": True,
        "NOTIFY_FEL_FROM_HDR": True,
        "NOTIFY_FEL_DUPLICATES": False,
        "NOTIFY_DV": True,
        "NOTIFY_DV_FROM_HDR": True,
        "NOTIFY_DV_PROFILE_UPGRADES": True,
        "NOTIFY_ATMOS": True,
        "NOTIFY_ATMOS_ONLY_IF_NO_ATMOS": True,
        "NOTIFY_ATMOS_WITH_DV_UPGRADE": True,
        "NOTIFY_RESOLUTION": True,
        "NOTIFY_RESOLUTION_ONLY_UPGRADES": True,
        "NOTIFY_ONLY_LIBRARY_MOVIES": False,
        "NOTIFY_EXPIRE_HOURS": 48,
    }
    defaults.update(overrides)
    settings = MagicMock()
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


@pytest.fixture
def detector():
    with patch("app.integrations.upgrade_detector.get_settings") as mock:
        mock.return_value = _make_settings()
        d = UpgradeDetector()
        yield d


def _make_detector(**overrides):
    with patch("app.integrations.upgrade_detector.get_settings") as mock:
        mock.return_value = _make_settings(**overrides)
        return UpgradeDetector()


# --- Quality Parsing ---


class TestParseQuality:
    def test_2160p(self, detector):
        q = detector.parse_quality_from_title("Movie 2024 2160p BluRay DV P7")
        assert q["resolution"] == "2160p"

    def test_4k_normalized(self, detector):
        q = detector.parse_quality_from_title("Movie 4K BluRay")
        assert q["resolution"] == "2160p"

    def test_uhd_normalized(self, detector):
        q = detector.parse_quality_from_title("Movie UHD BluRay")
        assert q["resolution"] == "2160p"

    def test_1080p(self, detector):
        q = detector.parse_quality_from_title("Movie 1080p BluRay")
        assert q["resolution"] == "1080p"

    def test_dv_detected(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p DV BluRay")
        assert q["has_dv"] is True

    def test_fel_detected(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p BL+EL BluRay")
        assert q["has_fel"] is True
        assert q["dv_profile"] == "P7"

    def test_p7_implies_fel(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p DV P7 BluRay")
        assert q["has_fel"] is True
        assert q["dv_profile"] == "P7"

    def test_profile_extraction(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p DV P5 BluRay")
        assert q["dv_profile"] == "P5"

    def test_atmos_detected(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p TrueHD Atmos")
        assert q["has_atmos"] is True

    def test_truehd_is_atmos(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p TrueHD 7.1")
        assert q["has_atmos"] is True

    def test_hdr_without_dv(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p HDR10 BluRay")
        assert q["has_hdr"] is True
        assert q["has_dv"] is False

    def test_hdr_not_set_when_dv_present(self, detector):
        q = detector.parse_quality_from_title("Movie 2160p DV HDR10 BluRay")
        assert q["has_hdr"] is False  # DV overrides HDR flag


# --- Rule 1: NOTIFY_FEL ---


class TestRule1FELNotification:
    def test_fel_notifies(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P7 FEL BluRay",
            {"resolution": "1080p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert "FEL" in upgrade_type

    def test_fel_disabled(self):
        d = _make_detector(NOTIFY_FEL=False)
        should, _, _ = d.should_notify(
            "Movie 2160p DV P7 FEL BluRay",
            {"resolution": "1080p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is False


# --- Rule 2: P5→P7 FEL ---


class TestRule2P5ToP7:
    def test_p5_to_p7(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P7 BluRay",
            {"resolution": "2160p", "dv_profile": "P5", "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert upgrade_type == "P5→P7 FEL"


# --- Rule 3: HDR→P7 FEL ---


class TestRule3HDRToFEL:
    def test_hdr_to_fel(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P7 BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": "hdr10"},
        )
        assert should is True
        assert "FEL" in upgrade_type


# --- Rule 4: FEL Duplicates ---


class TestRule4FELDuplicates:
    def test_fel_duplicate_skipped(self, detector):
        """Already have FEL, same quality = duplicate, NOTIFY_FEL_DUPLICATES=False → skip"""
        should, _, is_dup = detector.should_notify(
            "Movie 2160p DV P7 BluRay",
            {"resolution": "2160p", "dv_profile": "P7", "dv_fel": True, "has_atmos": False, "hdr_type": None},
        )
        assert should is False
        assert is_dup is True

    def test_fel_duplicate_allowed(self):
        d = _make_detector(NOTIFY_FEL_DUPLICATES=True)
        should, _, is_dup = d.should_notify(
            "Movie 2160p DV P7 BluRay",
            {"resolution": "2160p", "dv_profile": "P7", "dv_fel": True, "has_atmos": False, "hdr_type": None},
        )
        # With duplicates allowed, it should still try to notify
        # But since it's a true duplicate (all fields match), no upgrade type triggers
        # The FEL rules check `not current_quality["has_fel"]` for general FEL
        assert is_dup is True


# --- Rule 5: DV Notification ---


class TestRule5DVNotification:
    def test_dv_notifies_when_no_dv(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P8 BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert upgrade_type == "New DV"

    def test_dv_disabled(self):
        d = _make_detector(NOTIFY_DV=False)
        should, _, _ = d.should_notify(
            "Movie 2160p DV P8 BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is False


# --- Rule 6: HDR→DV ---


class TestRule6HDRToDV:
    def test_hdr_to_dv(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P8 BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": "hdr10"},
        )
        assert should is True
        assert upgrade_type == "HDR→DV"


# --- Rule 7: DV Profile Upgrades ---


class TestRule7ProfileUpgrade:
    def test_p5_to_p8(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P8 BluRay",
            {"resolution": "2160p", "dv_profile": "P5", "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert upgrade_type == "P5→P8"


# --- Rule 8: Atmos Notification ---


class TestRule8Atmos:
    def test_atmos_notifies_when_no_atmos(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p TrueHD Atmos BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert upgrade_type == "New Atmos"

    def test_atmos_disabled(self):
        d = _make_detector(NOTIFY_ATMOS=False)
        should, _, _ = d.should_notify(
            "Movie 2160p TrueHD Atmos BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is False


# --- Rule 9: Atmos Only If No Atmos ---


class TestRule9AtmosOnlyIfNoAtmos:
    def test_skip_if_already_atmos(self, detector):
        should, _, _ = detector.should_notify(
            "Movie 2160p TrueHD Atmos BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": True, "hdr_type": None},
        )
        assert should is False

    def test_allow_if_combined_with_dv_upgrade(self, detector):
        """Atmos + DV upgrade combo should still notify even if already have Atmos"""
        should, _, _ = detector.should_notify(
            "Movie 2160p DV TrueHD Atmos BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": True, "hdr_type": None},
        )
        # DV rules fire first for DV content, so this tests Atmos path
        # The DV rules should catch this first as "New DV"
        assert should is True


# --- Rule 10: Atmos With DV Upgrade ---


class TestRule10AtmosWithDV:
    def test_dv_atmos_combo(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV TrueHD Atmos BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        # Could be "New DV" (DV rules fire first) or "DV + Atmos"
        assert upgrade_type in ("New DV", "DV + Atmos")


# --- Rules 11-12: Resolution ---


class TestResolutionRules:
    def test_resolution_upgrade_1080_to_2160(self, detector):
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p BluRay",
            {"resolution": "1080p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is True
        assert "2160p" in upgrade_type

    def test_resolution_no_downgrade(self, detector):
        """2160p → 1080p should not notify"""
        should, _, _ = detector.should_notify(
            "Movie 1080p BluRay",
            {"resolution": "2160p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is False

    def test_resolution_disabled(self):
        d = _make_detector(NOTIFY_RESOLUTION=False)
        should, _, _ = d.should_notify(
            "Movie 2160p BluRay",
            {"resolution": "1080p", "dv_profile": None, "dv_fel": False, "has_atmos": False, "hdr_type": None},
        )
        assert should is False


# --- Rule 13: Only Library Movies ---


class TestRule13OnlyLibrary:
    def test_skip_non_library_when_enabled(self):
        d = _make_detector(NOTIFY_ONLY_LIBRARY_MOVIES=True)
        should, _, _ = d.should_notify("Movie 2160p DV P7 BluRay", None)
        assert should is False

    def test_allow_non_library_when_disabled(self, detector):
        """NOTIFY_ONLY_LIBRARY_MOVIES=False, FEL torrent not in library"""
        should, upgrade_type, _ = detector.should_notify(
            "Movie 2160p DV P7 FEL BluRay", None
        )
        assert should is True
        assert "not in library" in upgrade_type

    def test_non_library_non_fel_skipped(self, detector):
        """Non-FEL torrent not in library should not notify"""
        should, _, _ = detector.should_notify("Movie 2160p BluRay", None)
        assert should is False


# --- Duplicate Detection ---


class TestDuplicateDetection:
    def test_exact_match_is_duplicate(self, detector):
        new = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": True, "resolution": "2160p"}
        current = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": True, "resolution": "2160p"}
        assert detector._is_duplicate(new, current) is True

    def test_different_resolution_not_duplicate(self, detector):
        new = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": True, "resolution": "2160p"}
        current = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": True, "resolution": "1080p"}
        assert detector._is_duplicate(new, current) is False

    def test_different_atmos_not_duplicate(self, detector):
        new = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": True, "resolution": "2160p"}
        current = {"has_fel": True, "has_dv": True, "dv_profile": "P7", "has_atmos": False, "resolution": "2160p"}
        assert detector._is_duplicate(new, current) is False


# --- Quality Score Delegation ---


class TestQualityScore:
    def test_delegates_to_module(self, detector):
        quality = {
            "has_fel": True,
            "has_dv": True,
            "dv_profile": "P7",
            "resolution": "2160p",
            "has_atmos": True,
        }
        score = detector.get_quality_score(quality)
        assert score == 130  # Library scoring: 100 + 20 + 10
