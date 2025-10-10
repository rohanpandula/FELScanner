#!/usr/bin/env python3
"""
Comprehensive test for IPT/qBit integration
Tests upgrade detector, download manager, and full workflow
"""
import asyncio
import sys
sys.path.insert(0, '/Users/rohan/Desktop/felscanner')

from integrations.upgrade_detector import UpgradeDetector
from integrations.qbittorrent import QBittorrentClient
from integrations.radarr import RadarrClient
from integrations.telegram_handler import TelegramDownloadHandler
from integrations.download_manager import DownloadManager
from scanner import MovieDatabase

# Test configuration
NOTIFICATION_CONFIG = {
    'notify_fel': True,
    'notify_fel_from_p5': True,
    'notify_fel_from_hdr': True,
    'notify_fel_duplicates': False,
    'notify_dv': False,
    'notify_dv_from_hdr': True,
    'notify_dv_profile_upgrades': True,
    'notify_atmos': False,
    'notify_atmos_only_if_no_atmos': True,
    'notify_atmos_with_dv_upgrade': True,
    'notify_resolution': False,
    'notify_resolution_only_upgrades': True,
    'notify_only_library_movies': True,
    'notify_expire_hours': 24
}

def test_upgrade_detector():
    """Test upgrade detector logic"""
    print("\n" + "="*80)
    print("TEST 1: UPGRADE DETECTOR LOGIC")
    print("="*80)

    detector = UpgradeDetector(NOTIFICATION_CONFIG)

    # Test cases
    test_cases = [
        {
            'name': 'P5 → P7 FEL (SHOULD NOTIFY)',
            'current': {'dv_profile': 5, 'is_fel': False, 'resolution': '2160p'},
            'new': {'dv_profile': 7, 'is_fel': True, 'resolution': '2160p'},
            'expected': True
        },
        {
            'name': 'P7 FEL → P7 FEL (SHOULD SKIP - duplicate)',
            'current': {'dv_profile': 7, 'is_fel': True, 'resolution': '2160p'},
            'new': {'dv_profile': 7, 'is_fel': True, 'resolution': '2160p'},
            'expected': False
        },
        {
            'name': 'HDR10 → P7 FEL (SHOULD NOTIFY)',
            'current': {'dv_profile': None, 'is_fel': False, 'resolution': '2160p'},
            'new': {'dv_profile': 7, 'is_fel': True, 'resolution': '2160p'},
            'expected': True
        },
        {
            'name': '1080p P7 FEL → 2160p P7 FEL (SHOULD SKIP - resolution notifications disabled)',
            'current': {'dv_profile': 7, 'is_fel': True, 'resolution': '1080p'},
            'new': {'dv_profile': 7, 'is_fel': True, 'resolution': '2160p'},
            'expected': False  # notify_resolution is False in config
        },
        {
            'name': 'P5 no Atmos → P5 with Atmos (depends on settings)',
            'current': {'dv_profile': 5, 'is_fel': False, 'has_atmos': False},
            'new': {'dv_profile': 5, 'is_fel': False, 'has_atmos': True},
            'expected': False  # notify_atmos is False
        }
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        # is_notification_worthy returns (bool, str) tuple
        notify, reason = detector.is_notification_worthy(test['current'], test['new'])
        status = "✓ PASS" if notify == test['expected'] else "✗ FAIL"

        if notify == test['expected']:
            passed += 1
        else:
            failed += 1

        print(f"\n{status}: {test['name']}")
        print(f"  Current: {test['current']}")
        print(f"  New: {test['new']}")
        print(f"  Expected: {test['expected']}, Got: {notify}")
        print(f"  Reason: {reason}")

    print(f"\n{'='*80}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*80}")

    return failed == 0

async def test_radarr_movie_lookup():
    """Test Radarr movie lookup"""
    print("\n" + "="*80)
    print("TEST 2: RADARR MOVIE LOOKUP")
    print("="*80)

    client = RadarrClient(
        base_url="http://10.0.0.35:7878",
        api_key="3518edb28ce2497d9b13fdc86ad703d2"
    )

    try:
        # Test 1: Get a random movie
        print("\nGetting first 5 movies from Radarr...")
        movies = await client.get_movies()
        print(f"✓ Found {len(movies)} movies total")

        if len(movies) > 0:
            test_movie = movies[0]
            print(f"\nTest movie: {test_movie.get('title')} ({test_movie.get('year')})")
            print(f"  Path: {test_movie.get('path')}")
            print(f"  Has File: {test_movie.get('hasFile')}")

            # Test 2: Search for this movie
            title = test_movie.get('title')
            year = test_movie.get('year')

            print(f"\nSearching for '{title}' ({year})...")
            found = await client.search_movie(title, year)

            if found:
                print(f"✓ Found movie via search")
                print(f"  Radarr ID: {found.get('id')}")
                print(f"  Folder: {found.get('path')}")

                # Test 3: Get folder path
                folder = await client.get_movie_folder(title, year)
                print(f"\n✓ Got folder path: {folder}")

                # Test 4: Get file info
                file_info = await client.get_movie_file_info(title, year)
                if file_info:
                    print(f"\n✓ Got file info:")
                    print(f"  Quality: {file_info.get('quality')}")
                    print(f"  Resolution: {file_info.get('resolution')}")
                    print(f"  Size: {file_info.get('file_size')} bytes")
            else:
                print("✗ Movie not found via search")
                return False

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        await client.close()

async def test_database_operations():
    """Test database operations"""
    print("\n" + "="*80)
    print("TEST 3: DATABASE OPERATIONS")
    print("="*80)

    db = MovieDatabase('exports/movie_database.db')

    try:
        # Test 1: Store pending download
        print("\n1. Storing pending download...")
        request_id = 'test_request_123'
        download_data = {
            'movie_title': 'Test Movie',
            'year': 2024,
            'torrent_url': 'magnet:?xt=urn:btih:test',
            'target_folder': '/test/path',
            'quality_type': 'fel',
            'telegram_message_id': 12345,
            'created_at': '2025-10-09T14:00:00',
            'expires_at': '2025-10-10T00:00:00'
        }

        db.store_pending_download(request_id, download_data)
        print("✓ Stored pending download")

        # Test 2: Retrieve pending download
        print("\n2. Retrieving pending download...")
        retrieved = db.get_pending_download('test_request_123')

        if retrieved:
            print("✓ Retrieved pending download:")
            print(f"  Movie: {retrieved.get('movie_title')}")
            print(f"  Status: {retrieved.get('status')}")
        else:
            print("✗ Failed to retrieve")
            return False

        # Test 3: Get all pending downloads
        print("\n3. Getting all pending downloads...")
        all_pending = db.get_all_pending_downloads()
        print(f"✓ Found {len(all_pending)} pending download(s)")

        # Test 4: Mark download as started
        print("\n4. Marking download as started...")
        db.mark_download_started('test_request_123', 'test_hash_abc')
        print("✓ Marked as started")

        # Test 5: Mark download as completed
        print("\n5. Marking download as completed...")
        db.mark_download_completed('test_request_123')
        print("✓ Marked as completed")

        # Test 6: Get download history
        print("\n6. Getting download history...")
        history = db.get_download_history(limit=5)
        print(f"✓ Found {len(history)} history record(s)")

        # Cleanup
        print("\n7. Cleaning up test data...")
        db.delete_pending_download('test_request_123')
        print("✓ Cleanup complete")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_torrent_parsing():
    """Test torrent title parsing"""
    print("\n" + "="*80)
    print("TEST 4: TORRENT TITLE PARSING")
    print("="*80)

    detector = UpgradeDetector(NOTIFICATION_CONFIG)

    test_torrents = [
        "Dune 2021 2160p UHD BluRay DV FEL BL+EL+RPU Atmos TrueHD 7.1 x265-GROUP",
        "Top.Gun.Maverick.2022.2160p.DV.Profile.7.FEL.Atmos.x265",
        "The Batman 2022 4K HDR10 DV P5 TrueHD Atmos",
        "Oppenheimer.2023.2160p.BluRay.x265.10bit.HDR",
        "Blade.Runner.2049.2017.1080p.DV.FEL.Atmos"
    ]

    for torrent in test_torrents:
        print(f"\nTorrent: {torrent}")
        quality = detector.parse_torrent_quality(torrent)
        print(f"  DV Profile: {quality.get('dv_profile')}")
        print(f"  FEL: {quality.get('is_fel')}")
        print(f"  Resolution: {quality.get('resolution')}")
        print(f"  Atmos: {quality.get('has_atmos')}")

    return True

async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("IPT/QBIT INTEGRATION TEST SUITE")
    print("="*80)

    results = {}

    # Test 1: Upgrade Detector
    results['upgrade_detector'] = test_upgrade_detector()

    # Test 2: Radarr Lookup
    results['radarr_lookup'] = await test_radarr_movie_lookup()

    # Test 3: Database Operations
    results['database'] = await test_database_operations()

    # Test 4: Torrent Parsing
    results['torrent_parsing'] = await test_torrent_parsing()

    # Summary
    print("\n" + "="*80)
    print("FINAL TEST RESULTS")
    print("="*80)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print("\n" + ("="*80))

    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")

    print("="*80 + "\n")

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
