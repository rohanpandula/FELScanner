"""
Test Prometheus metrics functionality
"""
import pytest
from app.core.metrics import (
    record_scan_metrics,
    record_movie_statistics,
    record_download_metrics,
    record_connection_status,
    record_http_request,
    record_background_task,
)


def test_record_scan_metrics():
    """Test scan metrics recording"""
    # Should not raise any exceptions
    record_scan_metrics("full", 120.5, 487, success=True)
    record_scan_metrics("verify", 45.2, 487, success=True)
    record_scan_metrics("monitor", 5.1, 10, success=False)


def test_record_movie_statistics():
    """Test movie statistics recording"""
    stats = {
        "total": 500,
        "dv_total": 300,
        "dv_p7": 150,
        "dv_p5": 100,
        "dv_fel": 75,
        "atmos_total": 200,
        "resolution_4k": 350,
        "resolution_1080p": 150,
    }

    # Should not raise any exceptions
    record_movie_statistics(stats)


def test_record_download_metrics():
    """Test download metrics recording"""
    pending = 5
    active_by_state = {
        "downloading": 3,
        "seeding": 10,
        "paused": 2,
    }

    # Should not raise any exceptions
    record_download_metrics(pending, active_by_state)


def test_record_connection_status():
    """Test connection status recording"""
    # Should not raise any exceptions
    record_connection_status("plex", True, 0.5)
    record_connection_status("qbittorrent", False, 2.0)
    record_connection_status("radarr", True, 0.3)


def test_record_http_request():
    """Test HTTP request metrics recording"""
    # Should not raise any exceptions
    record_http_request("GET", "/api/v1/movies", 200, 0.15)
    record_http_request("POST", "/api/v1/scan", 201, 0.05)
    record_http_request("GET", "/api/v1/downloads", 500, 1.2)


def test_record_background_task():
    """Test background task metrics recording"""
    # Should not raise any exceptions
    record_background_task("connection_check", 2.5, success=True)
    record_background_task("scan_job", 120.0, success=False)
