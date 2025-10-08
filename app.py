from flask import Flask, jsonify, render_template, request
import os
import json
import logging
import asyncio
import time
import threading
import requests
import pytz
import re
from datetime import datetime, timedelta
from flask_compress import Compress
from plexapi.server import PlexServer
from scanner import PlexDVScanner, MovieDatabase
from integrations.radarr import RadarrClient
from typing import Any, Dict, List, Optional, Set, Tuple
import sys
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
compress = Compress()
compress.init_app(app)

# Get data directory from environment variable or use default
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
log.info(f"Using data directory: {DATA_DIR}")

# Create exports directory if it doesn't exist
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)
log.info(f"Exports directory: {EXPORTS_DIR}")

# Update file paths to use DATA_DIR
app.config.update(
    # Original paths updated to use DATA_DIR
    REPORTS_FOLDER_PATH=EXPORTS_DIR,
    SETTINGS_FILE=os.path.join(DATA_DIR, "settings.json"),
    PLEX_URL=os.environ.get('PLEX_URL', ""),
    PLEX_TOKEN=os.environ.get('PLEX_TOKEN', ""),
    LIBRARY_NAME=os.environ.get('LIBRARY_NAME', "Movies"),
    COLLECTION_NAME_ALL_DV="All Dolby Vision",
    COLLECTION_NAME_PROFILE7="DV FEL Profile 7",
    COLLECTION_NAME_TRUEHD_ATMOS="TrueHD Atmos",
    COLLECTION_ENABLE_DV=True,
    COLLECTION_ENABLE_P7=True,
    COLLECTION_ENABLE_ATMOS=True,
    AUTO_START_MODE="none",
    MAX_REPORTS_SIZE=5,
    SCAN_FREQUENCY=24,
    RADARR_BASE_URL=os.environ.get('RADARR_BASE_URL', ""),
    RADARR_API_KEY=os.environ.get('RADARR_API_KEY', ""),
    RADARR_ROOT_FOLDER_ID=os.environ.get('RADARR_ROOT_FOLDER_ID', ""),
    RADARR_QUALITY_PROFILE_ID=os.environ.get('RADARR_QUALITY_PROFILE_ID', ""),
    RADARR_AUTO_IMPORT=os.environ.get('RADARR_AUTO_IMPORT', 'false').lower() == 'true',
    RADARR_DRY_RUN=os.environ.get('RADARR_DRY_RUN', 'true').lower() != 'false',
    TELEGRAM_ENABLED=os.environ.get('TELEGRAM_ENABLED', 'false').lower() == 'true',
    TELEGRAM_TOKEN=os.environ.get('TELEGRAM_TOKEN', ""),
    TELEGRAM_CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID', ""),
    TELEGRAM_NOTIFY_ALL_UPDATES=False,
    TELEGRAM_NOTIFY_NEW_MOVIES=True,
    TELEGRAM_NOTIFY_DV=True,
    TELEGRAM_NOTIFY_P7=True,
    TELEGRAM_NOTIFY_ATMOS=True,
    SETUP_COMPLETED=False,
    LAST_SCAN_RESULTS={'total': 0, 'dv_count': 0, 'p7_count': 0, 'atmos_count': 0}
)

# Queue for Telegram notifications
notification_queue = None
notification_thread = None

# Application state
class AppState:
    def __init__(self):
        self.scanner_obj = None
        self.is_scanning = False
        self.monitor_active = False
        self.last_scan_time = None
        self.next_scan_time = None
        self.scan_results = {
            'total': 0,
            'dv_count': 0,
            'p7_count': 0,
            'atmos_count': 0,
            'scan_progress': 0,
            'status': 'idle'
        }
        self.last_collection_changes = {'added': [], 'removed': []}
        self.connection_status = {
            'plex': {'status': 'unknown', 'message': 'Not connected'},
            'telegram': {'status': 'unknown', 'message': 'Not connected'},
            'server': {'status': 'connected', 'message': 'Web server running'}
        }
        self.radarr_stats = {
            'status': 'disabled',
            'message': 'Radarr integration not configured',
            'matched': 0,
            'monitored': 0,
            'total_known': 0,
            'movies_in_radarr': 0,
            'last_checked': None,
            'root_folders': [],
            'quality_profiles': []
        }
        self.movie_db: Optional[MovieDatabase] = None
        self.lock = threading.RLock()  # For thread-safe state updates

# Create application state
state = AppState()

RADARR_STATUS_TTL = 60  # seconds


def run_async_task(coro):
    """Run an async coroutine in a dedicated event loop"""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


def get_movie_database() -> MovieDatabase:
    with state.lock:
        if state.movie_db:
            return state.movie_db

    db_path = os.path.join(app.config['REPORTS_FOLDER_PATH'], 'movie_database.db')
    movie_db = MovieDatabase(db_path)

    with state.lock:
        state.movie_db = movie_db

    return movie_db


async def build_radarr_index(base_url: str, api_key: str) -> Dict[str, Any]:
    client = RadarrClient(base_url, api_key)
    try:
        movies = await client.get_movies()
        root_folders = await client.get_root_folders()
        quality_profiles = await client.get_quality_profiles()
    finally:
        await client.close()

    profile_map = {str(profile.get('id')): profile.get('name') for profile in quality_profiles or []}

    index: Dict[str, Any] = {
        'movies': movies or [],
        'by_tmdb': {},
        'by_imdb': {},
        'profiles': profile_map,
        'root_folders': [{'id': folder.get('id'), 'path': folder.get('path')} for folder in root_folders or []],
        'quality_profiles': [{'id': profile.get('id'), 'name': profile.get('name')} for profile in quality_profiles or []]
    }

    for movie in index['movies']:
        movie_copy = dict(movie)
        quality_profile_id = movie.get('qualityProfileId')
        if quality_profile_id is not None:
            movie_copy['qualityProfileName'] = profile_map.get(str(quality_profile_id)) or profile_map.get(quality_profile_id)

        tmdb_id = movie.get('tmdbId')
        imdb_id = movie.get('imdbId')

        if tmdb_id:
            index['by_tmdb'][str(tmdb_id)] = movie_copy
        if imdb_id:
            index['by_imdb'][imdb_id] = movie_copy

    return index


def compute_radarr_stats(index: Dict[str, Any]) -> Dict[str, Any]:
    matched = 0
    monitored = 0
    total_known = 0

    try:
        movies = get_movie_database().get_all_movies()
    except Exception as exc:
        log.error(f"Failed to read movie database for Radarr stats: {exc}")
        movies = []

    total_known = len(movies)

    for movie in movies:
        radarr_movie = None
        extra_data = movie.get('extra_data')

        external_ids = {}
        if extra_data:
            try:
                extra = json.loads(extra_data)
                external_ids = extra.get('external_ids') or {}
            except Exception:
                external_ids = {}

        tmdb_id = external_ids.get('tmdb')
        imdb_id = external_ids.get('imdb')

        if tmdb_id and str(tmdb_id) in index.get('by_tmdb', {}):
            radarr_movie = index['by_tmdb'][str(tmdb_id)]
        elif imdb_id and imdb_id in index.get('by_imdb', {}):
            radarr_movie = index['by_imdb'][imdb_id]

        if radarr_movie:
            matched += 1
            if radarr_movie.get('monitored'):
                monitored += 1

    return {
        'matched': matched,
        'monitored': monitored,
        'total_known': total_known,
        'movies_in_radarr': len(index.get('movies', []))
    }


def _normalize_release_name(value: Optional[str]) -> str:
    if not value:
        return ''
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def _get_iptscanner_dirs() -> List[str]:
    """Return possible IPT scanner data directories, preferring DATA_DIR."""

    script_root = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(DATA_DIR, 'iptscanner'),
        os.path.join(script_root, 'iptscanner'),
    ]

    resolved: List[str] = []
    seen: Set[str] = set()

    for path in candidates:
        norm = os.path.normpath(path)
        if norm not in seen:
            resolved.append(norm)
            seen.add(norm)

    return resolved


def load_iptorrents_snapshot() -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    """Load the latest IPTorrents search snapshot for filtering."""

    iptscanner_dirs = _get_iptscanner_dirs()

    config_path: Optional[str] = None
    for directory in iptscanner_dirs:
        candidate = os.path.join(directory, 'config.json')
        if os.path.exists(candidate):
            config_path = candidate
            break

    if config_path is None and iptscanner_dirs:
        # Fall back to the first candidate so error messages remain helpful
        config_path = os.path.join(iptscanner_dirs[0], 'config.json')

    search_term = "BL+EL+RPU"
    last_check = None

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as config_file:
                config = json.load(config_file)
            last_check = config.get('lastUpdateTime')
            search_term = config.get('iptorrents', {}).get('searchTerm', search_term)
        except Exception as exc:
            log.error(f"Failed to load IPTorrents config for snapshot: {exc}")

    torrents: List[Dict[str, Any]] = []

    torrent_candidates: List[str] = []
    seen_paths: Set[str] = set()

    for directory in iptscanner_dirs:
        for relative in (
            'known_torrents.json',
            'torrents.json',
            os.path.join('data', 'known_torrents.json'),
            os.path.join('data', 'torrents.json'),
        ):
            candidate_path = os.path.normpath(os.path.join(directory, relative))
            if candidate_path not in seen_paths:
                torrent_candidates.append(candidate_path)
                seen_paths.add(candidate_path)

    for path in torrent_candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as torrent_file:
                    data = json.load(torrent_file)
                if isinstance(data, list):
                    torrents = data
                    break
            except Exception as exc:
                log.error(f"Failed to read IPTorrents data from {path}: {exc}")

    if torrents:
        for torrent in torrents:
            added_text = torrent.get('added', '')
            if 'sortTime' in torrent or not isinstance(added_text, str):
                continue

            try:
                if 'min ago' in added_text:
                    minutes = float(added_text.split(' ')[0])
                    torrent['sortTime'] = time.time() - (minutes * 60)
                elif 'hr ago' in added_text:
                    hours = float(added_text.split(' ')[0])
                    torrent['sortTime'] = time.time() - (hours * 3600)
                elif 'day ago' in added_text:
                    days = float(added_text.split(' ')[0])
                    torrent['sortTime'] = time.time() - (days * 86400)
                elif 'wk ago' in added_text:
                    weeks = float(added_text.split(' ')[0])
                    torrent['sortTime'] = time.time() - (weeks * 604800)
            except Exception:
                torrent['sortTime'] = torrent.get('sortTime', 0)

        torrents.sort(
            key=lambda torrent: (
                0 if torrent.get('isNew', False) else 1,
                -(torrent.get('sortTime', 0) or 0)
            ),
            reverse=False
        )

    return torrents, search_term, last_check


def filter_releases_with_ipt(
    releases: List[Dict[str, Any]],
    torrents: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not torrents:
        return releases, {'matches': 0, 'available_titles': 0}

    normalized_torrents: List[Tuple[str, str]] = []
    seen_norms = set()

    for torrent in torrents:
        candidate_names = [
            torrent.get('title'),
            torrent.get('name'),
            torrent.get('releaseTitle'),
            torrent.get('cleanName'),
        ]

        for candidate in candidate_names:
            norm = _normalize_release_name(candidate)
            if norm and norm not in seen_norms:
                normalized_torrents.append((norm, candidate or ''))
                seen_norms.add(norm)

    matched_releases: List[Dict[str, Any]] = []
    match_count = 0

    for release in releases:
        release_names = [
            release.get('title'),
            release.get('releaseTitle'),
            release.get('movieTitle'),
        ]

        matched_title = None

        for release_name in release_names:
            release_norm = _normalize_release_name(release_name)
            if not release_norm:
                continue

            for torrent_norm, torrent_name in normalized_torrents:
                if not torrent_norm:
                    continue

                if release_norm in torrent_norm or torrent_norm in release_norm:
                    matched_title = torrent_name
                    break

            if matched_title:
                break

        if matched_title:
            release_copy = dict(release)
            release_copy['iptMatchTitle'] = matched_title
            matched_releases.append(release_copy)
            match_count += 1

    return matched_releases, {
        'matches': match_count,
        'available_titles': len(normalized_torrents),
    }

# Load settings from file
def load_settings():
    try:
        if not os.path.exists(app.config['SETTINGS_FILE']):
            log.warning(f"Settings file not found at {app.config['SETTINGS_FILE']}, using default settings")
            return

        log.info(f"Loading settings from {app.config['SETTINGS_FILE']}")
        with open(app.config['SETTINGS_FILE'], 'r') as f:
            settings = json.load(f)

        def _to_bool(value, default=None):
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
            
        # Load Plex settings - don't override env variables
        if 'plex_url' in settings and not os.environ.get('PLEX_URL'):
            app.config['PLEX_URL'] = settings['plex_url']
        if 'plex_token' in settings and not os.environ.get('PLEX_TOKEN'):
            app.config['PLEX_TOKEN'] = settings['plex_token']
        if 'library_name' in settings and not os.environ.get('LIBRARY_NAME'):
            app.config['LIBRARY_NAME'] = settings['library_name']
            
        # Load collection settings
        if 'collection_name_all_dv' in settings:
            app.config['COLLECTION_NAME_ALL_DV'] = settings['collection_name_all_dv']
        if 'collection_name_profile7' in settings:
            app.config['COLLECTION_NAME_PROFILE7'] = settings['collection_name_profile7']
        if 'collection_name_truehd_atmos' in settings:
            app.config['COLLECTION_NAME_TRUEHD_ATMOS'] = settings['collection_name_truehd_atmos']
        if 'collection_enable_dv' in settings:
            app.config['COLLECTION_ENABLE_DV'] = settings['collection_enable_dv']
        if 'collection_enable_p7' in settings:
            app.config['COLLECTION_ENABLE_P7'] = settings['collection_enable_p7']
        if 'collection_enable_atmos' in settings:
            app.config['COLLECTION_ENABLE_ATMOS'] = settings['collection_enable_atmos']
        if 'auto_start' in settings:
            app.config['AUTO_START_MODE'] = settings['auto_start']
        if 'max_reports_size' in settings:
            app.config['MAX_REPORTS_SIZE'] = settings['max_reports_size']
            
        # Load scan settings - don't override env variables
        app.config['SCAN_FREQUENCY'] = settings.get('scan_frequency', 24)
        
        if not os.environ.get('TELEGRAM_ENABLED'):
            app.config['TELEGRAM_ENABLED'] = settings.get('telegram_enabled', app.config['TELEGRAM_ENABLED'])
        if not os.environ.get('TELEGRAM_TOKEN'):
            app.config['TELEGRAM_TOKEN'] = settings.get('telegram_token', app.config['TELEGRAM_TOKEN'])
        if not os.environ.get('TELEGRAM_CHAT_ID'):
            app.config['TELEGRAM_CHAT_ID'] = settings.get('telegram_chat_id', app.config['TELEGRAM_CHAT_ID'])
            
        app.config['TELEGRAM_NOTIFY_ALL_UPDATES'] = settings.get('telegram_notify_all_updates', False)
        app.config['TELEGRAM_NOTIFY_NEW_MOVIES'] = settings.get('telegram_notify_new_movies', True)
        app.config['TELEGRAM_NOTIFY_DV'] = settings.get('telegram_notify_dv', True)
        app.config['TELEGRAM_NOTIFY_P7'] = settings.get('telegram_notify_p7', True)
        app.config['TELEGRAM_NOTIFY_ATMOS'] = settings.get('telegram_notify_atmos', True)

        # Load Radarr settings
        radarr_settings = settings.get('radarr', {})
        app.config['RADARR_BASE_URL'] = settings.get('radarr_base_url', radarr_settings.get('base_url', app.config['RADARR_BASE_URL']))
        app.config['RADARR_API_KEY'] = settings.get('radarr_api_key', radarr_settings.get('api_key', app.config['RADARR_API_KEY']))
        app.config['RADARR_ROOT_FOLDER_ID'] = settings.get('radarr_root_folder_id', radarr_settings.get('root_folder_id', app.config['RADARR_ROOT_FOLDER_ID']))
        app.config['RADARR_QUALITY_PROFILE_ID'] = settings.get('radarr_quality_profile_id', radarr_settings.get('quality_profile_id', app.config['RADARR_QUALITY_PROFILE_ID']))
        app.config['RADARR_AUTO_IMPORT'] = _to_bool(
            settings.get('radarr_auto_import', radarr_settings.get('auto_import', app.config['RADARR_AUTO_IMPORT'])),
            app.config['RADARR_AUTO_IMPORT']
        )
        app.config['RADARR_DRY_RUN'] = _to_bool(
            settings.get('radarr_dry_run', radarr_settings.get('dry_run', app.config['RADARR_DRY_RUN'])),
            app.config['RADARR_DRY_RUN']
        )

        # Load setup_completed setting and log it
        setup_completed_value = settings.get('setup_completed', app.config['SETUP_COMPLETED'])
        log.info(f"Setting setup_completed to {setup_completed_value} (from settings file value: {settings.get('setup_completed', 'not found')})")
        app.config['SETUP_COMPLETED'] = setup_completed_value
        
        # Load stored scan results
        if 'last_scan_results' in settings:
            app.config['LAST_SCAN_RESULTS'] = settings['last_scan_results']
            
            with state.lock:
                # Update scan_results with the stored values
                state.scan_results.update({
                    'total': app.config['LAST_SCAN_RESULTS']['total'],
                    'dv_count': app.config['LAST_SCAN_RESULTS']['dv_count'],
                    'p7_count': app.config['LAST_SCAN_RESULTS']['p7_count'], 
                    'atmos_count': app.config['LAST_SCAN_RESULTS']['atmos_count']
                })
        
        # Load last scan time
        if 'last_scan_time' in settings:
            try:
                from datetime import datetime
                last_scan_time = datetime.fromisoformat(settings['last_scan_time'])
                with state.lock:
                    state.last_scan_time = last_scan_time
                app.config['LAST_SCAN_TIME'] = settings['last_scan_time']
                log.info(f"Restored last scan time: {last_scan_time}")
            except Exception as e:
                log.error(f"Error parsing last_scan_time: {e}")
                
        # Log final configuration state after loading
        log.info(f"Configuration after loading settings: SETUP_COMPLETED = {app.config['SETUP_COMPLETED']}")
        return True
    except Exception as e:
        log.error(f"Error loading settings: {e}")
        return False

# Save settings to file
def save_settings():
    try:
        settings = {
            'plex_url': app.config['PLEX_URL'],
            'plex_token': app.config['PLEX_TOKEN'],
            'library_name': app.config['LIBRARY_NAME'],
            'collection_name_all_dv': app.config['COLLECTION_NAME_ALL_DV'],
            'collection_name_profile7': app.config['COLLECTION_NAME_PROFILE7'],
            'collection_name_truehd_atmos': app.config['COLLECTION_NAME_TRUEHD_ATMOS'],
            'collection_enable_dv': app.config['COLLECTION_ENABLE_DV'],
            'collection_enable_p7': app.config['COLLECTION_ENABLE_P7'],
            'collection_enable_atmos': app.config['COLLECTION_ENABLE_ATMOS'],
            'auto_start': app.config['AUTO_START_MODE'],
            'max_reports_size': app.config['MAX_REPORTS_SIZE'],
            'scan_frequency': app.config.get('SCAN_FREQUENCY', 24),
            'telegram_enabled': app.config['TELEGRAM_ENABLED'],
            'telegram_token': app.config['TELEGRAM_TOKEN'],
            'telegram_chat_id': app.config['TELEGRAM_CHAT_ID'],
            'telegram_notify_all_updates': app.config['TELEGRAM_NOTIFY_ALL_UPDATES'],
            'telegram_notify_new_movies': app.config['TELEGRAM_NOTIFY_NEW_MOVIES'],
            'telegram_notify_dv': app.config['TELEGRAM_NOTIFY_DV'],
            'telegram_notify_p7': app.config['TELEGRAM_NOTIFY_P7'],
            'telegram_notify_atmos': app.config['TELEGRAM_NOTIFY_ATMOS'],
            'radarr_base_url': app.config['RADARR_BASE_URL'],
            'radarr_api_key': app.config['RADARR_API_KEY'],
            'radarr_root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
            'radarr_quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID'],
            'radarr_auto_import': app.config['RADARR_AUTO_IMPORT'],
            'radarr_dry_run': app.config['RADARR_DRY_RUN'],
            'setup_completed': app.config['SETUP_COMPLETED'],
            'last_scan_results': app.config['LAST_SCAN_RESULTS']
        }

        settings['radarr'] = {
            'base_url': app.config['RADARR_BASE_URL'],
            'api_key': app.config['RADARR_API_KEY'],
            'root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
            'quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID'],
            'auto_import': app.config['RADARR_AUTO_IMPORT'],
            'dry_run': app.config['RADARR_DRY_RUN']
        }
        
        # Save the last scan time if available
        with state.lock:
            if state.last_scan_time:
                settings['last_scan_time'] = state.last_scan_time.isoformat()
                app.config['LAST_SCAN_TIME'] = state.last_scan_time.isoformat()
        
        with open(app.config['SETTINGS_FILE'], 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        log.error(f"Error saving settings: {e}")
        return False

# Check Plex connection
def check_plex_connection():
    try:
        plex = PlexServer(app.config['PLEX_URL'], app.config['PLEX_TOKEN'])
        movies_section = plex.library.section(app.config['LIBRARY_NAME'])
        movie_count = len(movies_section.all())
        
        with state.lock:
            state.connection_status['plex'] = {
                'status': 'connected',
                'message': f'Connected (Found {movie_count} movies)'
            }
        return True
    except Exception as e:
        with state.lock:
            state.connection_status['plex'] = {
                'status': 'disconnected',
                'message': f'Error: {str(e)}'
            }
        return False

# Check Telegram connection
def check_telegram_connection():
    if not app.config['TELEGRAM_ENABLED']:
        with state.lock:
            state.connection_status['telegram'] = {
                'status': 'disabled',
                'message': 'Notifications disabled'
            }
        return False
        
    try:
        api_url = f"https://api.telegram.org/bot{app.config['TELEGRAM_TOKEN']}/getMe"
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        if data['ok']:
            bot_name = data['result']['username']
            with state.lock:
                state.connection_status['telegram'] = {
                    'status': 'connected',
                    'message': f'Connected (@{bot_name})'
                }
            return True
        else:
            with state.lock:
                state.connection_status['telegram'] = {
                    'status': 'disconnected',
                    'message': 'Invalid bot token'
                }
            return False
    except Exception as e:
        with state.lock:
            state.connection_status['telegram'] = {
                'status': 'disconnected',
                'message': f'Error: {str(e)}'
            }
        return False

# Background processing for Telegram notification queue
def process_notification_queue():
    global notification_queue
    
    if not notification_queue:
        notification_queue = []
    
    while True:
        if notification_queue:
            try:
                message, notification_type = notification_queue.pop(0)
                send_telegram_message(message)
                # Sleep to avoid too many requests
                time.sleep(1)
            except Exception as e:
                log.error(f"Error processing notification: {e}")
        else:
            # Sleep when queue is empty
            time.sleep(1)

# Start notification processor thread
def start_notification_processor():
    global notification_thread
    
    if notification_thread is None or not notification_thread.is_alive():
        notification_thread = threading.Thread(target=process_notification_queue)
        notification_thread.daemon = True
        notification_thread.start()

# Send Telegram notification
def send_telegram_notification(message, notification_type=None):
    """
    Queue a notification for sending via Telegram
    notification_type can be one of: 'all_updates', 'new_movies', 'dv', 'p7', 'atmos', or None
    If None, the message will be sent regardless of preferences
    """
    global notification_queue
    
    if not app.config['TELEGRAM_ENABLED']:
        return False
        
    # Check notification preferences if a type is specified
    if notification_type:
        if notification_type == 'all_updates' and not app.config['TELEGRAM_NOTIFY_ALL_UPDATES']:
            return False
        if notification_type == 'new_movies' and not app.config['TELEGRAM_NOTIFY_NEW_MOVIES']:
            return False
        if notification_type == 'dv' and not app.config['TELEGRAM_NOTIFY_DV']:
            return False
        if notification_type == 'p7' and not app.config['TELEGRAM_NOTIFY_P7']:
            return False
        if notification_type == 'atmos' and not app.config['TELEGRAM_NOTIFY_ATMOS']:
            return False
    
    # Add to notification queue
    if notification_queue is None:
        notification_queue = []
        
    notification_queue.append((message, notification_type))
    return True

# Send Telegram message directly (used by queue processor)
def send_telegram_message(message):
    try:
        api_url = f"https://api.telegram.org/bot{app.config['TELEGRAM_TOKEN']}/sendMessage"
        payload = {
            'chat_id': app.config['TELEGRAM_CHAT_ID'],
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(api_url, json=payload, timeout=10)
        return response.json()['ok']
    except Exception as e:
        log.error(f"Telegram notification error: {e}")
        return False

# Manage reports storage
def manage_reports_storage():
    total_size = 0
    report_files = []
    
    for filename in os.listdir(app.config['REPORTS_FOLDER_PATH']):
        if filename.endswith('.csv') or filename.endswith('.json'):
            file_path = os.path.join(app.config['REPORTS_FOLDER_PATH'], filename)
            file_size = os.path.getsize(file_path)
            report_files.append((file_path, filename, os.path.getmtime(file_path), file_size))
            total_size += file_size
            
    # Sort by modification time (oldest first)
    report_files.sort(key=lambda x: x[2])
    
    # Remove oldest files if total size exceeds limit
    max_size_bytes = app.config['MAX_REPORTS_SIZE'] * 1024 * 1024
    while total_size > max_size_bytes and report_files:
        file_to_remove = report_files.pop(0)
        try:
            os.remove(file_to_remove[0])
            total_size -= file_to_remove[3]
            log.info(f"Removed old report file: {file_to_remove[1]} to maintain size limit")
        except Exception as e:
            log.error(f"Error removing report file: {e}")

# Update scan progress
def update_scan_progress(current, total):
    with state.lock:
        state.scan_results['scan_progress'] = int(current / total * 100) if total > 0 else 0

def initialize_scanner():
    try:
        # Create a scanner object (the aiohttp session will be created later when needed)
        scanner = PlexDVScanner(
            app.config['PLEX_URL'],
            app.config['PLEX_TOKEN'],
            app.config['LIBRARY_NAME'],
            app.config['COLLECTION_NAME_ALL_DV'],
            app.config['COLLECTION_NAME_PROFILE7'],
            app.config['COLLECTION_NAME_TRUEHD_ATMOS'],
            app.config['REPORTS_FOLDER_PATH']
        )
        scanner.set_progress_callback(update_scan_progress)

        with state.lock:
            state.movie_db = scanner.db

        return scanner
    except Exception as e:
        log.error(f"Error initializing scanner: {e}")
        return None

# Run scan in a thread with its own event loop
def run_scan_thread():
    """Run a scan in a new thread with its own event loop"""
    with state.lock:
        # Preserve last_scan_time while we scan
        # Store scan status and reset progress
        state.is_scanning = True
        state.scan_results['status'] = 'scanning'
        state.scan_results['scan_progress'] = 0
        
        # Reset collection changes but keep added/removed structure
        state.last_collection_changes = {'added_items': [], 'removed_items': []}
    
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async scan function in this loop
        log_entries = loop.run_until_complete(async_run_scan())
        
        # Close the loop when done
        loop.close()
    except Exception as e:
        log.error(f"Error in scan thread: {e}")
        with state.lock:
            state.scan_results['status'] = f"error: {str(e)}"
    finally:
        with state.lock:
            state.is_scanning = False

# Run verify in a thread with its own event loop
def run_verify_thread():
    """Run a verify operation in a new thread with its own event loop"""
    with state.lock:
        # Preserve last_scan_time while we verify
        # Store scan status and reset progress
        state.is_scanning = True
        state.scan_results['status'] = 'verifying'
        state.scan_results['scan_progress'] = 0
        
        # Reset collection changes but keep added/removed structure
        state.last_collection_changes = {'added_items': [], 'removed_items': []}
    
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async verify function in this loop
        log_entries = loop.run_until_complete(async_run_verify())
        
        # Close the loop when done
        loop.close()
    except Exception as e:
        log.error(f"Error in verify thread: {e}")
        with state.lock:
            state.scan_results['status'] = f"error: {str(e)}"
    finally:
        with state.lock:
            state.is_scanning = False

# Run full scan (async implementation)
async def async_run_scan():
    log_entries = []
    try:
        log_entries.append({
            'type': 'info',
            'message': f"Starting scan of library '{app.config['LIBRARY_NAME']}'..."
        })
        
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()

        if not state.scanner_obj:
            raise Exception("Failed to initialize scanner")

        radarr_index = None
        radarr_error = None
        if app.config['RADARR_BASE_URL'] and app.config['RADARR_API_KEY']:
            try:
                radarr_index = await build_radarr_index(app.config['RADARR_BASE_URL'], app.config['RADARR_API_KEY'])
                state.scanner_obj.set_radarr_index(radarr_index)
            except Exception as exc:
                radarr_error = str(exc)
                log.error(f"Radarr integration error: {exc}")
                state.scanner_obj.set_radarr_index(None)
        else:
            state.scanner_obj.set_radarr_index(None)

        # Perform full scan with Profile 7 / FEL detection
        dv_movies, p7_fel_movies, atmos_movies = await state.scanner_obj.scan_library()
        
        log_entries.append({
            'type': 'success',
            'message': f"Found {len(dv_movies)} Dolby Vision movies, {len(p7_fel_movies)} are Profile 7 FEL"
        })
        
        log_entries.append({
            'type': 'success',
            'message': f"Found {len(atmos_movies)} TrueHD Atmos movies"
        })
        
        # Create JSON output
        json_path = state.scanner_obj.create_json_output(
            dv_movies, atmos_movies, max_size_mb=app.config['MAX_REPORTS_SIZE']
        )
        
        if json_path:
            log_entries.append({
                'type': 'success',
                'message': f"Created JSON report at {os.path.basename(json_path)}"
            })
        else:
            log_entries.append({
                'type': 'error',
                'message': "Failed to create JSON report"
            })
        
        # Add movies to collections and track changes for notifications
        added_dv = added_p7 = added_atmos = 0
        dv_added_items = p7_added_items = atmos_added_items = []
        
        # Update All Dolby Vision collection if enabled
        if app.config['COLLECTION_ENABLE_DV']:
            added_dv, dv_added_items = await state.scanner_obj.update_add_to_collection(
                dv_movies, app.config['COLLECTION_NAME_ALL_DV']
            )
            
            log_entries.append({
                'type': 'info',
                'message': f"Added {added_dv} movies to '{app.config['COLLECTION_NAME_ALL_DV']}' collection"
            })
        else:
            log_entries.append({
                'type': 'info',
                'message': f"'{app.config['COLLECTION_NAME_ALL_DV']}' collection is disabled, skipping"
            })
        
        # Update Profile 7 FEL collection if enabled
        if app.config['COLLECTION_ENABLE_P7']:
            added_p7, p7_added_items = await state.scanner_obj.update_add_to_collection(
                p7_fel_movies, app.config['COLLECTION_NAME_PROFILE7']
            )
            
            log_entries.append({
                'type': 'info',
                'message': f"Added {added_p7} movies to '{app.config['COLLECTION_NAME_PROFILE7']}' collection"
            })
        else:
            log_entries.append({
                'type': 'info',
                'message': f"'{app.config['COLLECTION_NAME_PROFILE7']}' collection is disabled, skipping"
            })
        
        # Update TrueHD Atmos collection if enabled
        if app.config['COLLECTION_ENABLE_ATMOS']:
            added_atmos, atmos_added_items = await state.scanner_obj.update_add_to_collection(
                atmos_movies, app.config['COLLECTION_NAME_TRUEHD_ATMOS']
            )
            
            log_entries.append({
                'type': 'info',
                'message': f"Added {added_atmos} movies to '{app.config['COLLECTION_NAME_TRUEHD_ATMOS']}' collection"
            })
        else:
            log_entries.append({
                'type': 'info',
                'message': f"'{app.config['COLLECTION_NAME_TRUEHD_ATMOS']}' collection is disabled, skipping"
            })
        
        # Combine all added items
        all_added_items = dv_added_items + p7_added_items + atmos_added_items
        
        with state.lock:
            if all_added_items:
                state.last_collection_changes['added'] = all_added_items
                state.last_collection_changes['added_items'] = all_added_items
        
        # Send Telegram notifications for new additions
        if app.config['TELEGRAM_ENABLED'] and app.config['TELEGRAM_NOTIFY_NEW_MOVIES'] and all_added_items:
            # Filter notifications by type if needed
            dv_items = [item for item in all_added_items 
                       if item['collection'] == app.config['COLLECTION_NAME_ALL_DV']]
            
            p7_items = [item for item in all_added_items 
                       if item['collection'] == app.config['COLLECTION_NAME_PROFILE7']]
            
            atmos_items = [item for item in all_added_items 
                          if item['collection'] == app.config['COLLECTION_NAME_TRUEHD_ATMOS']]
            
            to_notify = []
            if app.config['TELEGRAM_NOTIFY_DV']:
                to_notify.extend(dv_items)
                
            if app.config['TELEGRAM_NOTIFY_P7']:
                to_notify.extend([item for item in p7_items if item not in to_notify])
                
            if app.config['TELEGRAM_NOTIFY_ATMOS']:
                to_notify.extend([item for item in atmos_items if item not in to_notify])
            
            if to_notify:
                notification = '<b>🎬 FELScanner: New Movies Added</b>\n\n'
                
                # Limit to 10 items to avoid overly long messages
                for item in to_notify[:10]:
                    notification += f"• <b>{item['title']}</b> added to {item['collection']}\n"
                
                if len(to_notify) > 10:
                    notification += f"\n<i>...and {len(to_notify) - 10} more</i>"
                
                send_telegram_notification(notification, 'new_movies')
        
        # Get updated collection stats
        total, dv_count, p7_count, atmos_count = state.scanner_obj.get_stats()
        
        with state.lock:
            state.scan_results['total'] = total
            state.scan_results['dv_count'] = dv_count
            state.scan_results['p7_count'] = p7_count
            state.scan_results['atmos_count'] = atmos_count
            state.scan_results['status'] = 'completed'
            state.scan_results['scan_progress'] = 100
            state.last_scan_time = datetime.now()
        
        # Store results in app config for persistence
        app.config['LAST_SCAN_RESULTS'] = {
            'total': total,
            'dv_count': dv_count,
            'p7_count': p7_count,
            'atmos_count': atmos_count
        }

        # Save to disk
        save_settings()

        # Update Radarr stats after scan
        if radarr_index:
            radarr_stats = compute_radarr_stats(radarr_index)
            radarr_stats.update({
                'status': 'connected',
                'message': f"Connected to Radarr ({radarr_stats['matched']} matched)",
                'root_folders': radarr_index.get('root_folders', []),
                'quality_profiles': radarr_index.get('quality_profiles', []),
                'last_checked': datetime.now(pytz.UTC).isoformat()
            })
        elif radarr_error:
            radarr_stats = {
                'status': 'error',
                'message': radarr_error,
                'matched': 0,
                'monitored': 0,
                'total_known': 0,
                'movies_in_radarr': 0,
                'root_folders': [],
                'quality_profiles': [],
                'last_checked': datetime.now(pytz.UTC).isoformat()
            }
        else:
            radarr_stats = {
                'status': 'disabled',
                'message': 'Radarr integration not configured',
                'matched': 0,
                'monitored': 0,
                'total_known': 0,
                'movies_in_radarr': 0,
                'root_folders': [],
                'quality_profiles': [],
                'last_checked': datetime.now(pytz.UTC).isoformat()
            }

        with state.lock:
            state.radarr_stats = radarr_stats

        # Send scan complete notification
        if app.config['TELEGRAM_ENABLED'] and app.config['TELEGRAM_NOTIFY_ALL_UPDATES']:
            message = f"""<b>🎬 FELScanner</b>
<b>Scan Complete!</b>

Total Movies: {total}
Dolby Vision: {dv_count} ({round(dv_count/total*100 if total>0 else 0)}%)
Profile 7 FEL: {p7_count} ({round(p7_count/total*100 if total>0 else 0)}%)
TrueHD Atmos: {atmos_count} ({round(atmos_count/total*100 if total>0 else 0)}%)

Added {added_dv} movies to DV collection
Added {added_p7} movies to P7 collection
Added {added_atmos} movies to Atmos collection"""
            
            send_telegram_notification(message, 'all_updates')
        
        # Clean up old reports
        manage_reports_storage()
        
        return log_entries
    except Exception as e:
        log.error(f"Scan error: {e}")
        
        with state.lock:
            state.scan_results['status'] = f"error: {str(e)}"
        
        log_entries.append({'type': 'error', 'message': f"Scan error: {str(e)}"})
        return log_entries

# Run verify collections (async implementation)
async def async_run_verify():
    log_entries = []
    try:
        log_entries.append({'type': 'info', 'message': 'Starting collection verification...'})
        
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()
            
        if not state.scanner_obj:
            raise Exception("Failed to initialize scanner")
        
        # Full verification with P7/FEL detection
        total_removed = 0
        all_removed_items = []
        
        # Set up the disabled collections warning
        disabled_collections = []
        if not app.config['COLLECTION_ENABLE_DV']:
            disabled_collections.append(app.config['COLLECTION_NAME_ALL_DV'])
        if not app.config['COLLECTION_ENABLE_P7']:
            disabled_collections.append(app.config['COLLECTION_NAME_PROFILE7'])
        if not app.config['COLLECTION_ENABLE_ATMOS']:
            disabled_collections.append(app.config['COLLECTION_NAME_TRUEHD_ATMOS'])
            
        if disabled_collections:
            log_entries.append({
                'type': 'info',
                'message': f"Skipping disabled collections: {', '.join(disabled_collections)}"
            })
            
        # Verify collections using the scanner
        removed_count, removed_items = await state.scanner_obj.verify_collections(
            return_removed_items=True,
            skip_collections=disabled_collections
        )
        
        total_removed += removed_count
        all_removed_items.extend(removed_items or [])
        
        log_entries.append({
            'type': 'success',
            'message': f'Verification complete, removed {total_removed} mismatched items'
        })
        
        # Update collection changes if items were removed
        with state.lock:
            if all_removed_items:
                state.last_collection_changes['removed'] = all_removed_items
                state.last_collection_changes['removed_items'] = all_removed_items
        
        # Send Telegram notification for removed items if enabled
        if (app.config['TELEGRAM_ENABLED'] and 
            app.config['TELEGRAM_NOTIFY_ALL_UPDATES'] and 
            all_removed_items):
            notification = '<b>🎬 FELScanner: Items Removed</b>\n\n'
            
            for item in all_removed_items[:10]:
                notification += f"• <b>{item['title']}</b> removed from {item['collection']}\n"
            
            if len(all_removed_items) > 10:
                notification += f"\n<i>...and {len(all_removed_items)-10} more</i>"
            
            send_telegram_notification(notification, 'all_updates')
        
        # Get updated stats
        total, dv_count, p7_count, atmos_count = state.scanner_obj.get_stats()
        
        with state.lock:
            state.scan_results['total'] = total
            state.scan_results['dv_count'] = dv_count
            state.scan_results['p7_count'] = p7_count
            state.scan_results['atmos_count'] = atmos_count
            state.scan_results['status'] = 'completed'
            state.scan_results['scan_progress'] = 100
            state.last_scan_time = datetime.now()
        
        # Save the last scan results
        app.config['LAST_SCAN_RESULTS'] = {
            'total': total,
            'dv_count': dv_count,
            'p7_count': p7_count,
            'atmos_count': atmos_count
        }
        
        save_settings()
        
        return log_entries
    except Exception as e:
        log.error(f"Verification error: {e}")
        
        with state.lock:
            state.scan_results['status'] = f"error: {str(e)}"
        
        log_entries.append({'type': 'error', 'message': f"Verification error: {str(e)}"})
        return log_entries

# Run monitoring mode (thread function)
def run_monitor():
    with state.lock:
        state.monitor_active = True
        state.scan_results['status'] = 'monitoring'
        
        # Set initial next scan time
        state.next_scan_time = datetime.now() + timedelta(hours=app.config.get('SCAN_FREQUENCY', 24))
    
    try:
        # Send notification that monitoring has started
        if app.config['TELEGRAM_ENABLED'] and app.config['TELEGRAM_NOTIFY_ALL_UPDATES']:
            message = (
                "<b>🎬 FELScanner</b>\n"
                "<b>Monitoring Started</b>\n\n"
                f"The scanner will check for new content every {app.config.get('SCAN_FREQUENCY', 24)} hours."
            )
            send_telegram_notification(message, 'all_updates')
        
        # Main monitoring loop
        while True:
            with state.lock:
                if not state.monitor_active:
                    break
                    
                # Calculate time until next scan
                now = datetime.now()
                time_until_scan = (state.next_scan_time - now).total_seconds()
                is_scanning_now = state.is_scanning
            
            # If it's time to scan or we missed the window, do a scan
            if time_until_scan <= 0 and not is_scanning_now:
                # Run scan in a thread with its own event loop
                run_scan_thread()
                
                # Update next scan time
                with state.lock:
                    state.next_scan_time = datetime.now() + timedelta(
                        hours=app.config.get('SCAN_FREQUENCY', 24)
                    )
                    
                # Check if monitoring was stopped during scan
                with state.lock:
                    if not state.monitor_active:
                        break
            
            # Sleep to avoid high CPU usage
            time.sleep(60)
    except Exception as e:
        log.error(f"Monitor error: {e}")
        
        with state.lock:
            state.scan_results['status'] = f"monitor error: {str(e)}"
    finally:
        with state.lock:
            state.monitor_active = False
            state.scan_results['status'] = 'idle'

# Function to perform post-setup tasks
def _post_setup_tasks(wizard_data):
    """Performs tasks after initial setup, like checking connections and starting auto-scan."""
    try:
        # Check Plex connection
        check_plex_connection()
        
        # Check Telegram connection if enabled
        if wizard_data.get('telegram_enabled'):
            check_telegram_connection()
            
            # Send a welcome message
            welcome_msg = (
                "<b>🎬 FELScanner Setup Complete!</b>\n\n"
                "Your scanner has been successfully set up and is now ready to scan your Plex library for:\n"
                "• Dolby Vision content\n"
                "• Profile 7 FEL content\n"
                "• TrueHD Atmos audio tracks\n\n"
                "You will receive notifications based on your preferences."
            )
            send_telegram_notification(welcome_msg)
        
        # Start notification processing
        start_notification_processor()
        
        # Start auto scan based on selection
        auto_start = wizard_data.get('auto_start', 'none')
        if auto_start == 'scan':
            # Run scan in a thread with proper event loop
            run_scan_thread()
        elif auto_start == 'verify':
            # Run verify in a thread with proper event loop
            run_verify_thread()
        elif auto_start == 'monitor':
            # Start monitor mode
            monitor_thread = threading.Thread(target=run_monitor)
            monitor_thread.daemon = True
            monitor_thread.start()
    except Exception as e:
        log.error(f"Error in post-setup tasks: {e}")

# Routes
@app.after_request
def add_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=604800'
    return response

@app.route('/')
def index():
    # Pass initial values from stored results and setup status
    initial_data = {
        'total': app.config['LAST_SCAN_RESULTS']['total'],
        'dv_count': app.config['LAST_SCAN_RESULTS']['dv_count'],
        'p7_count': app.config['LAST_SCAN_RESULTS']['p7_count'],
        'atmos_count': app.config['LAST_SCAN_RESULTS']['atmos_count']
    }
    setup_completed = app.config['SETUP_COMPLETED']
    log.info(f"Rendering index template with setup_completed={setup_completed}")
    return render_template('index.html', initial_data=initial_data, setup_completed=setup_completed)

@app.route('/api/status')
def api_status():
    with state.lock:
        # Make sure to format the collection changes properly for the frontend
        collection_changes = {
            'added_items': state.last_collection_changes.get('added_items', []) 
                or state.last_collection_changes.get('added', []),
            'removed_items': state.last_collection_changes.get('removed_items', [])
                or state.last_collection_changes.get('removed', [])
        }
        
        # Ensure we have a last_scan_time if it was previously set
        last_scan_time = state.last_scan_time
        if not last_scan_time and 'LAST_SCAN_RESULTS' in app.config:
            # Try to recover from settings if available
            try:
                last_scan_time = app.config.get('LAST_SCAN_TIME')
            except:
                pass
        
        response = {
            'status': {
                'is_scanning': state.is_scanning,
                'last_scan_time': last_scan_time,
                'next_scan_time': state.next_scan_time
            },
            'results': state.scan_results,
            'collection_changes': collection_changes
        }
        
    return jsonify(response)

@app.route('/api/check-setup')
def check_setup():
    # Log the current setup status for debugging
    log.info(f"Check setup called, SETUP_COMPLETED = {app.config['SETUP_COMPLETED']}")
    # Return the actual value from configuration
    return jsonify({'setup_completed': app.config['SETUP_COMPLETED']})

@app.route('/api/save-wizard', methods=['POST'])
def save_wizard_settings():
    try:
        wizard_data = request.json
        
        # Update app configuration
        app.config['PLEX_URL'] = wizard_data['plex_url']
        app.config['PLEX_TOKEN'] = wizard_data['plex_token']
        app.config['LIBRARY_NAME'] = wizard_data['library_name']
        app.config['COLLECTION_NAME_ALL_DV'] = wizard_data['collection_name_all_dv']
        app.config['COLLECTION_NAME_PROFILE7'] = wizard_data['collection_name_profile7']
        app.config['COLLECTION_NAME_TRUEHD_ATMOS'] = wizard_data['collection_name_truehd_atmos']
        app.config['MAX_REPORTS_SIZE'] = wizard_data['max_reports_size']
        app.config['TELEGRAM_ENABLED'] = wizard_data['telegram_enabled']
        
        if wizard_data['telegram_enabled']:
            app.config['TELEGRAM_TOKEN'] = wizard_data['telegram_token']
            app.config['TELEGRAM_CHAT_ID'] = wizard_data['telegram_chat_id']
            
        app.config['SETUP_COMPLETED'] = True
        
        # Test Plex connection
        plex_ok = check_plex_connection()
        
        if save_settings():
            # Run post-setup tasks in a separate thread
            setup_thread = threading.Thread(target=_post_setup_tasks, args=(wizard_data,))
            setup_thread.daemon = True
            setup_thread.start()
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    try:
        data = request.json
        plex_url = data.get('plex_url')
        plex_token = data.get('plex_token')
        library_name = data.get('library_name')
        
        if not plex_url or not plex_token or not library_name:
            return jsonify({'success': False, 'error': 'Missing required fields'})
            
        plex = PlexServer(plex_url, plex_token)
        movies_section = plex.library.section(library_name)
        movie_count = len(movies_section.all())
        
        return jsonify({'success': True, 'movie_count': movie_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    try:
        data = request.json
        token = data.get('token')
        chat_id = data.get('chat_id')
        no_message = data.get('no_message', False)
        
        if not token or not chat_id:
            return jsonify({'success': False, 'error': 'Missing required fields'})
            
        api_url = f"https://api.telegram.org/bot{token}/getMe"
        response = requests.get(api_url)
        bot_data = response.json()
        
        if not bot_data.get('ok'):
            return jsonify({'success': False, 'error': 'Invalid bot token'})
        
        # If no_message is True, just check if the bot token is valid and don't send a message
        if no_message:
            return jsonify({'success': True})
            
        test_message = f"<b>🎬 FELScanner</b>\n\nTest message sent at {datetime.now().strftime('%H:%M:%S')}"
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': test_message, 'parse_mode': 'HTML'}
        response = requests.post(api_url, json=payload)
        result = response.json()
        
        if result.get('ok'):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': result.get('description', 'Failed to send message')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/scan', methods=['POST'])
def start_scan():
    with state.lock:
        if state.is_scanning:
            return jsonify({'error': 'Scan already in progress'}), 400
    
    operation = request.json.get('operation', 'scan')
    if operation not in ['scan', 'verify']:
        return jsonify({'error': 'Invalid operation'}), 400
        
    try:
        # Initialize the scanner synchronously first
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()
            
        if not state.scanner_obj:
            return jsonify({'error': 'Failed to initialize scanner'}), 500
            
        # Start the scan in a background thread
        if operation == 'scan':
            thread = threading.Thread(target=run_scan_thread)
        else:  # verify
            thread = threading.Thread(target=run_verify_thread)
            
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitor', methods=['POST'])
def toggle_monitor():
    action = request.json.get('action')
    
    with state.lock:
        is_scanning = state.is_scanning
        is_monitoring = state.monitor_active
    
    if action == 'start' and not is_monitoring:
        if is_scanning:
            return jsonify({'error': 'Scan already in progress'}), 400
            
        with state.lock:
            state.monitor_active = True
            
        monitor_thread = threading.Thread(target=run_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return jsonify({'success': True, 'status': 'started'})
    elif action == 'stop' and is_monitoring:
        with state.lock:
            state.monitor_active = False
            
        return jsonify({'success': True, 'status': 'stopping'})
        
    return jsonify({'error': 'Invalid action or state'}), 400

@app.route('/api/collection/p7movies')
def get_p7_movies():
    try:
        # Initialize scanner if needed
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()
            
        if not state.scanner_obj:
            return jsonify({'error': 'Failed to initialize scanner', 'movies': []})
        
        # Get all P7 FEL movies directly from database
        p7_movies = state.scanner_obj.get_p7_fel_movies()
        
        # Convert to frontend format
        formatted_movies = []
        for movie in p7_movies:
            extra_data = {}
            if movie.get('extra_data'):
                try:
                    extra_data = json.loads(movie['extra_data'])
                except:
                    pass
            
            formatted_movies.append({
                'title': movie['title'],
                'year': extra_data.get('year', ''),
                'dv_profile': '7', # Always 7 for P7 movies
                'file_size': extra_data.get('file_size'),
                'audio': extra_data.get('audio_tracks', 'Unknown'),
                'bitrate': extra_data.get('video_bitrate', 'Unknown'),
                'added_at': movie.get('last_updated', ''),
                'extra_data': extra_data
            })
        
        return jsonify({'movies': formatted_movies})
    except Exception as e:
        return jsonify({'error': str(e), 'movies': []})

@app.route('/api/collection/dvmovies')
def get_dv_movies():
    try:
        # Initialize scanner if needed
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()
            
        if not state.scanner_obj:
            return jsonify({'error': 'Failed to initialize scanner', 'movies': []})
        
        # Get all Dolby Vision movies directly from database
        dv_movies = state.scanner_obj.db.get_dv_movies()
        
        # Convert to frontend format
        formatted_movies = []
        for movie in dv_movies:
            extra_data = {}
            if movie.get('extra_data'):
                try:
                    extra_data = json.loads(movie['extra_data'])
                except:
                    pass
            
            formatted_movies.append({
                'title': movie['title'],
                'year': extra_data.get('year', ''),
                'dv_profile': movie.get('dv_profile', ''),
                'file_size': extra_data.get('file_size'),
                'audio': extra_data.get('audio_tracks', 'Unknown'),
                'bitrate': extra_data.get('video_bitrate', 'Unknown'),
                'added_at': movie.get('last_updated', ''),
                'extra_data': extra_data
            })
        
        return jsonify({'movies': formatted_movies})
    except Exception as e:
        return jsonify({'error': str(e), 'movies': []})

@app.route('/api/collection/atmosmovies')
def get_atmos_movies():
    try:
        # Initialize scanner if needed
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()
            
        if not state.scanner_obj:
            return jsonify({'error': 'Failed to initialize scanner', 'movies': []})
        
        # Get all TrueHD Atmos movies directly from database
        atmos_movies = state.scanner_obj.db.get_atmos_movies()
        
        # Convert to frontend format
        formatted_movies = []
        for movie in atmos_movies:
            extra_data = {}
            if movie.get('extra_data'):
                try:
                    extra_data = json.loads(movie['extra_data'])
                except:
                    pass
            
            formatted_movies.append({
                'title': movie['title'],
                'year': extra_data.get('year', ''),
                'file_size': extra_data.get('file_size'),
                'audio': extra_data.get('audio_tracks', 'Unknown'),
                'bitrate': extra_data.get('video_bitrate', 'Unknown'),
                'added_at': movie.get('last_updated', ''),
                'extra_data': extra_data
            })
        
        return jsonify({'movies': formatted_movies})
    except Exception as e:
        return jsonify({'error': str(e), 'movies': []})

@app.route('/api/reports')
def list_reports():
    reports = []
    full_reports = request.args.get('full', 'false').lower() == 'true'
    
    try:
        for filename in os.listdir(app.config['REPORTS_FOLDER_PATH']):
            if filename.endswith('.csv') or filename.endswith('.json'):
                file_path = os.path.join(app.config['REPORTS_FOLDER_PATH'], filename)
                reports.append({
                    'filename': filename,
                    'date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
                    'size': os.path.getsize(file_path)
                })
    except Exception as e:
        log.error(f"Error listing reports: {e}")
        
    sorted_reports = sorted(reports, key=lambda x: x['date'], reverse=True)
    return jsonify(sorted_reports if full_reports else sorted_reports[:5])

@app.route('/api/reports/<filename>')
def download_report(filename):
    if not (filename.endswith('.csv') or filename.endswith('.json')) or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
        
    file_path = os.path.join(app.config['REPORTS_FOLDER_PATH'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content_type = 'text/csv' if filename.endswith('.csv') else 'application/json'
    return content, 200, {'Content-Type': content_type}

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({
        'plex_url': app.config['PLEX_URL'],
        'plex_token': app.config['PLEX_TOKEN'],
        'library_name': app.config['LIBRARY_NAME'],
        'collection_name_all_dv': app.config['COLLECTION_NAME_ALL_DV'],
        'collection_name_profile7': app.config['COLLECTION_NAME_PROFILE7'],
        'collection_name_truehd_atmos': app.config['COLLECTION_NAME_TRUEHD_ATMOS'],
        'collection_enable_dv': app.config['COLLECTION_ENABLE_DV'],
        'collection_enable_p7': app.config['COLLECTION_ENABLE_P7'],
        'collection_enable_atmos': app.config['COLLECTION_ENABLE_ATMOS'],
        'poll_interval': 300,
        'auto_start': app.config['AUTO_START_MODE'],
        'max_reports_size': app.config['MAX_REPORTS_SIZE'],
        'scan_frequency': app.config.get('SCAN_FREQUENCY', 24),
        'use_whole_numbers': app.config.get('USE_WHOLE_NUMBERS', True),
        'telegram_enabled': app.config['TELEGRAM_ENABLED'],
        'telegram_token': app.config['TELEGRAM_TOKEN'],
        'telegram_chat_id': app.config['TELEGRAM_CHAT_ID'],
        'telegram_notify_all_updates': app.config['TELEGRAM_NOTIFY_ALL_UPDATES'],
        'telegram_notify_new_movies': app.config['TELEGRAM_NOTIFY_NEW_MOVIES'],
        'telegram_notify_dv': app.config['TELEGRAM_NOTIFY_DV'],
        'telegram_notify_p7': app.config['TELEGRAM_NOTIFY_P7'],
        'telegram_notify_atmos': app.config['TELEGRAM_NOTIFY_ATMOS'],
        'radarr_base_url': app.config['RADARR_BASE_URL'],
        'radarr_api_key': app.config['RADARR_API_KEY'],
        'radarr_root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
        'radarr_quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID'],
        'radarr_auto_import': app.config['RADARR_AUTO_IMPORT'],
        'radarr_dry_run': app.config['RADARR_DRY_RUN'],
        'radarr_root_folders': state.radarr_stats.get('root_folders', []),
        'radarr_quality_profiles': state.radarr_stats.get('quality_profiles', [])
    })

@app.route('/api/settings', methods=['POST'])
def save_settings_api():
    try:
        settings = request.json

        def _to_bool(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        
        # Update configuration
        if 'plex_url' in settings and settings['plex_url']:
            app.config['PLEX_URL'] = settings['plex_url']
            
        if 'plex_token' in settings and settings['plex_token']:
            app.config['PLEX_TOKEN'] = settings['plex_token']
            
        if 'library_name' in settings and settings['library_name']:
            app.config['LIBRARY_NAME'] = settings['library_name']
            
        if 'collection_name_all_dv' in settings and settings['collection_name_all_dv']:
            app.config['COLLECTION_NAME_ALL_DV'] = settings['collection_name_all_dv']
            
        if 'collection_name_profile7' in settings and settings['collection_name_profile7']:
            app.config['COLLECTION_NAME_PROFILE7'] = settings['collection_name_profile7']
            
        if 'collection_name_truehd_atmos' in settings and settings['collection_name_truehd_atmos']:
            app.config['COLLECTION_NAME_TRUEHD_ATMOS'] = settings['collection_name_truehd_atmos']
        
        # Collection enable/disable settings
        if 'collection_enable_dv' in settings:
            app.config['COLLECTION_ENABLE_DV'] = settings['collection_enable_dv']
            
        if 'collection_enable_p7' in settings:
            app.config['COLLECTION_ENABLE_P7'] = settings['collection_enable_p7']
            
        if 'collection_enable_atmos' in settings:
            app.config['COLLECTION_ENABLE_ATMOS'] = settings['collection_enable_atmos']
            
        if 'auto_start' in settings:
            app.config['AUTO_START_MODE'] = settings['auto_start']
            
        if 'max_reports_size' in settings and isinstance(settings['max_reports_size'], (int, float)) and settings['max_reports_size'] > 0:
            app.config['MAX_REPORTS_SIZE'] = int(settings['max_reports_size'])
            
        if 'scan_frequency' in settings and isinstance(settings['scan_frequency'], (int, float)) and settings['scan_frequency'] > 0:
            app.config['SCAN_FREQUENCY'] = int(settings['scan_frequency'])
            
        # Add use_whole_numbers setting
        if 'use_whole_numbers' in settings:
            app.config['USE_WHOLE_NUMBERS'] = settings['use_whole_numbers']
            
        if 'telegram_enabled' in settings:
            app.config['TELEGRAM_ENABLED'] = settings['telegram_enabled']
            
        if 'telegram_token' in settings and settings['telegram_token']:
            app.config['TELEGRAM_TOKEN'] = settings['telegram_token']
            
        if 'telegram_chat_id' in settings and settings['telegram_chat_id']:
            app.config['TELEGRAM_CHAT_ID'] = settings['telegram_chat_id']
        
        # Save Telegram notification preferences
        if 'telegram_notify_all_updates' in settings:
            app.config['TELEGRAM_NOTIFY_ALL_UPDATES'] = settings['telegram_notify_all_updates']
            
        if 'telegram_notify_new_movies' in settings:
            app.config['TELEGRAM_NOTIFY_NEW_MOVIES'] = settings['telegram_notify_new_movies']
            
        if 'telegram_notify_dv' in settings:
            app.config['TELEGRAM_NOTIFY_DV'] = settings['telegram_notify_dv']
            
        if 'telegram_notify_p7' in settings:
            app.config['TELEGRAM_NOTIFY_P7'] = settings['telegram_notify_p7']
            
        if 'telegram_notify_atmos' in settings:
            app.config['TELEGRAM_NOTIFY_ATMOS'] = settings['telegram_notify_atmos']

        if 'radarr_base_url' in settings:
            app.config['RADARR_BASE_URL'] = settings['radarr_base_url'] or ''

        if 'radarr_api_key' in settings:
            app.config['RADARR_API_KEY'] = settings['radarr_api_key'] or ''

        if 'radarr_root_folder_id' in settings:
            app.config['RADARR_ROOT_FOLDER_ID'] = settings['radarr_root_folder_id'] or ''

        if 'radarr_quality_profile_id' in settings:
            app.config['RADARR_QUALITY_PROFILE_ID'] = settings['radarr_quality_profile_id'] or ''

        if 'radarr_auto_import' in settings:
            app.config['RADARR_AUTO_IMPORT'] = _to_bool(settings['radarr_auto_import'])

        if 'radarr_dry_run' in settings:
            app.config['RADARR_DRY_RUN'] = _to_bool(settings['radarr_dry_run'])

        save_settings()
        check_plex_connection()
        check_telegram_connection()

        with state.lock:
            state.radarr_stats['last_checked'] = None
            if state.scanner_obj and hasattr(state.scanner_obj, 'set_radarr_index'):
                state.scanner_obj.set_radarr_index(None)

        # Reset scanner to pick up new settings
        with state.lock:
            if state.scanner_obj and hasattr(state.scanner_obj, 'close'):
                try:
                    # Create a temporary event loop if needed
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(state.scanner_obj.close())
                except Exception as e:
                    log.error(f"Error closing scanner: {e}")
            state.scanner_obj = None
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/radarr/test', methods=['POST'])
def radarr_test_connection():
    data = request.get_json() or {}
    base_url = (data.get('base_url') or data.get('radarr_base_url') or app.config['RADARR_BASE_URL'] or '').strip()
    api_key = (data.get('api_key') or data.get('radarr_api_key') or app.config['RADARR_API_KEY'] or '').strip()

    if not base_url or not api_key:
        return jsonify({'success': False, 'error': 'Radarr base URL and API key are required'}), 400

    try:
        index = run_async_task(build_radarr_index(base_url, api_key))
        response = {
            'success': True,
            'root_folders': index.get('root_folders', []),
            'quality_profiles': index.get('quality_profiles', []),
            'movies_in_radarr': len(index.get('movies', []))
        }
        return jsonify(response)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@app.route('/api/radarr/status')
def radarr_status():
    if not app.config['RADARR_BASE_URL'] or not app.config['RADARR_API_KEY']:
        response = {
            'configured': False,
            'status': 'disabled',
            'message': 'Radarr integration not configured',
            'matched': 0,
            'monitored': 0,
            'total_known': 0,
            'movies_in_radarr': 0,
            'root_folders': [],
            'quality_profiles': [],
            'auto_import': app.config['RADARR_AUTO_IMPORT'],
            'dry_run': app.config['RADARR_DRY_RUN'],
            'root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
            'quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID']
        }
        return jsonify(response)

    refresh = request.args.get('refresh', 'false').lower() == 'true'

    with state.lock:
        cached_stats = dict(state.radarr_stats)

    if not refresh and cached_stats.get('last_checked'):
        try:
            last_checked = datetime.fromisoformat(cached_stats['last_checked'])
            if datetime.now(pytz.UTC) - last_checked < timedelta(seconds=RADARR_STATUS_TTL):
                cached_stats.update({
                    'configured': True,
                    'auto_import': app.config['RADARR_AUTO_IMPORT'],
                    'dry_run': app.config['RADARR_DRY_RUN'],
                    'root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
                    'quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID']
                })
                return jsonify(cached_stats)
        except Exception:
            pass

    try:
        index = run_async_task(build_radarr_index(app.config['RADARR_BASE_URL'], app.config['RADARR_API_KEY']))
        stats = compute_radarr_stats(index)
        stats.update({
            'status': 'connected',
            'message': f"Connected to Radarr ({stats['matched']} matched)",
            'root_folders': index.get('root_folders', []),
            'quality_profiles': index.get('quality_profiles', []),
            'last_checked': datetime.now(pytz.UTC).isoformat()
        })
        with state.lock:
            state.radarr_stats = stats

        stats.update({
            'configured': True,
            'auto_import': app.config['RADARR_AUTO_IMPORT'],
            'dry_run': app.config['RADARR_DRY_RUN'],
            'root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
            'quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID']
        })
        return jsonify(stats)
    except Exception as exc:
        error_stats = {
            'configured': True,
            'status': 'error',
            'message': str(exc),
            'matched': 0,
            'monitored': 0,
            'total_known': 0,
            'movies_in_radarr': 0,
            'root_folders': [],
            'quality_profiles': [],
            'last_checked': datetime.now(pytz.UTC).isoformat(),
            'auto_import': app.config['RADARR_AUTO_IMPORT'],
            'dry_run': app.config['RADARR_DRY_RUN'],
            'root_folder_id': app.config['RADARR_ROOT_FOLDER_ID'],
            'quality_profile_id': app.config['RADARR_QUALITY_PROFILE_ID']
        }
        with state.lock:
            state.radarr_stats = error_stats
        return jsonify(error_stats), 500


@app.route('/api/radarr/check', methods=['POST'])
def radarr_check():
    if not app.config['RADARR_BASE_URL'] or not app.config['RADARR_API_KEY']:
        return jsonify({'success': False, 'error': 'Radarr integration not configured'}), 400

    payload = request.get_json() or {}

    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    tmdb_id = payload.get('tmdb_id') or payload.get('tmdbId')
    imdb_id = payload.get('imdb_id') or payload.get('imdbId')
    title = payload.get('title')
    year = payload.get('year')
    add_requested = _to_bool(payload.get('add'), False)
    profile_override = payload.get('quality_profile_id') or payload.get('qualityProfileId')
    root_override = payload.get('root_folder_id') or payload.get('rootFolderId')
    dry_run_override = payload.get('dry_run')

    if not (tmdb_id or imdb_id or title):
        return jsonify({'success': False, 'error': 'A TMDB ID, IMDB ID, or title is required'}), 400

    async def _radarr_check():
        client = RadarrClient(app.config['RADARR_BASE_URL'], app.config['RADARR_API_KEY'])
        try:
            existing = []
            if tmdb_id or imdb_id:
                try:
                    existing = await client.get_movie(tmdb_id=tmdb_id, imdb_id=imdb_id)
                except Exception as exc:
                    log.debug(f"Radarr get_movie failed: {exc}")
                    existing = []

            lookup = []
            if not existing:
                lookup_term = None
                if title and year:
                    lookup_term = f"{title} ({year})"
                elif title:
                    lookup_term = title

                try:
                    lookup = await client.lookup_movie(tmdb_id=tmdb_id, imdb_id=imdb_id, term=lookup_term)
                except Exception as exc:
                    log.debug(f"Radarr lookup failed: {exc}")
                    lookup = []

            dry_run_flag = _to_bool(dry_run_override, app.config['RADARR_DRY_RUN'])

            response: Dict[str, Any] = {
                'success': True,
                'match_type': 'none',
                'auto_import': app.config['RADARR_AUTO_IMPORT'],
                'dry_run': dry_run_flag,
                'existing': None,
                'candidates': [],
                'added': False
            }

            if existing:
                movie_data = existing[0]
                response['match_type'] = 'existing'
                response['existing'] = {
                    'title': movie_data.get('title'),
                    'monitored': movie_data.get('monitored'),
                    'quality_profile_id': movie_data.get('qualityProfileId'),
                    'quality_profile_name': movie_data.get('qualityProfileName'),
                    'path': movie_data.get('path'),
                    'has_file': movie_data.get('hasFile'),
                    'tmdbId': movie_data.get('tmdbId'),
                    'imdbId': movie_data.get('imdbId'),
                    'id': movie_data.get('id')
                }
            elif lookup:
                response['match_type'] = 'lookup'
                response['candidates'] = [
                    {
                        'title': candidate.get('title'),
                        'year': candidate.get('year'),
                        'tmdbId': candidate.get('tmdbId'),
                        'imdbId': candidate.get('imdbId'),
                        'quality_profile_id': candidate.get('qualityProfileId'),
                        'title_slug': candidate.get('titleSlug')
                    }
                    for candidate in lookup
                ]

                if add_requested:
                    quality_profile_id = profile_override or app.config['RADARR_QUALITY_PROFILE_ID']
                    root_folder_id = root_override or app.config['RADARR_ROOT_FOLDER_ID']

                    if not quality_profile_id or not root_folder_id:
                        raise ValueError('Radarr quality profile and root folder must be configured to add movies')

                    root_folders = await client.get_root_folders()
                    root_folder_path = None
                    for folder in root_folders:
                        if str(folder.get('id')) == str(root_folder_id):
                            root_folder_path = folder.get('path')
                            break

                    if not root_folder_path:
                        raise ValueError('Selected Radarr root folder was not found')

                    candidate = lookup[0]
                    movie_payload = {
                        'title': candidate.get('title'),
                        'qualityProfileId': int(quality_profile_id),
                        'tmdbId': candidate.get('tmdbId'),
                        'year': candidate.get('year'),
                        'titleSlug': candidate.get('titleSlug'),
                        'images': candidate.get('images', []),
                        'monitored': app.config['RADARR_AUTO_IMPORT'],
                        'rootFolderPath': root_folder_path,
                        'minimumAvailability': candidate.get('minimumAvailability', 'announced'),
                        'addOptions': {
                            'searchForMovie': True
                        }
                    }

                    if candidate.get('imdbId'):
                        movie_payload['imdbId'] = candidate.get('imdbId')

                    if candidate.get('studio'):
                        movie_payload['studio'] = candidate.get('studio')

                    if candidate.get('tags'):
                        movie_payload['tags'] = candidate.get('tags')

                    if dry_run_flag:
                        response['added'] = False
                        response['message'] = 'Dry run enabled - movie would be added to Radarr'
                    else:
                        await client.add_movie(movie_payload)
                        response['added'] = True
                        response['message'] = 'Movie added to Radarr'

            return response
        finally:
            await client.close()

    try:
        result = run_async_task(_radarr_check())
        return jsonify(result)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400


@app.route('/api/radarr/releases', methods=['POST'])
def radarr_releases():
    base_url = (app.config.get('RADARR_BASE_URL') or '').strip()
    api_key = (app.config.get('RADARR_API_KEY') or '').strip()

    if not base_url or not api_key:
        return jsonify({'success': False, 'error': 'Radarr integration is not configured'}), 400

    data = request.get_json(silent=True) or {}

    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)

    tmdb_id = data.get('tmdb_id') or data.get('tmdbId')
    imdb_id = data.get('imdb_id') or data.get('imdbId')
    movie_id = data.get('movie_id') or data.get('movieId')
    term = data.get('term')
    refresh = _to_bool(data.get('refresh') or data.get('force_refresh') or data.get('forceRefresh', False))
    filter_ipt = _to_bool(data.get('filter_ipt') or data.get('filterIpt', False))

    if movie_id is not None:
        movie_id = str(movie_id).strip() or None
        if movie_id and movie_id.isdigit():
            movie_id = int(movie_id)
        else:
            try:
                movie_id = int(movie_id) if movie_id else None
            except (TypeError, ValueError):
                movie_id = None

    if tmdb_id is not None:
        tmdb_id = str(tmdb_id).strip() or None
    if imdb_id is not None:
        imdb_id = str(imdb_id).strip() or None
    if term is not None:
        term = str(term).strip() or None

    if not any([movie_id, tmdb_id, imdb_id, term]):
        return jsonify({'success': False, 'error': 'A TMDB ID, IMDB ID, Radarr movie ID, or search term is required'}), 400

    async def _radarr_release_lookup() -> Dict[str, Any]:
        client = RadarrClient(base_url, api_key)
        try:
            radarr_movie = None
            resolved_movie_id = movie_id

            if resolved_movie_id is None and (tmdb_id or imdb_id):
                try:
                    movie_matches = await client.get_movie(tmdb_id=tmdb_id, imdb_id=imdb_id)
                    if movie_matches:
                        radarr_movie = movie_matches[0]
                        resolved_movie_id = radarr_movie.get('id')
                except Exception as exc:
                    log.error(f"Failed to fetch Radarr movie for release lookup: {exc}")

            releases: List[Dict[str, Any]] = []

            if refresh and resolved_movie_id:
                try:
                    await client.trigger_movie_search(int(resolved_movie_id))
                except Exception as exc:
                    log.warning(f"Radarr release refresh failed for movie {resolved_movie_id}: {exc}")

            try:
                releases = await client.search_releases(
                    movie_id=int(resolved_movie_id) if resolved_movie_id else None,
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    term=term,
                )
            except ValueError as exc:
                raise RuntimeError(str(exc))

            filter_summary: Dict[str, Any] = {'matches': 0, 'available_titles': 0}
            ipt_snapshot: Dict[str, Any] = {}
            filtered_releases = releases

            if filter_ipt:
                torrents, search_term, last_check = load_iptorrents_snapshot()
                ipt_snapshot = {
                    'search_term': search_term,
                    'last_check': last_check,
                    'torrents_loaded': len(torrents),
                }

                if torrents:
                    filtered_releases, filter_summary = filter_releases_with_ipt(releases, torrents)
                else:
                    ipt_snapshot['message'] = 'No IPTorrents data available for filtering'

            return {
                'success': True,
                'releases': filtered_releases,
                'total_releases': len(releases),
                'filtered_out': len(releases) - len(filtered_releases),
                'filter_applied': filter_ipt,
                'filter_summary': filter_summary,
                'ipt_snapshot': ipt_snapshot,
                'radarr_movie': radarr_movie,
                'resolved_movie_id': resolved_movie_id,
            }
        finally:
            await client.close()

    try:
        result = run_async_task(_radarr_release_lookup())
        return jsonify(result)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

@app.route('/api/reset-settings', methods=['POST'])
def reset_settings():
    try:
        # Reset app configuration to defaults
        app.config['PLEX_URL'] = "http://localhost:32400"
        app.config['PLEX_TOKEN'] = ""
        app.config['LIBRARY_NAME'] = "Movies"
        app.config['COLLECTION_NAME_ALL_DV'] = "All Dolby Vision"
        app.config['COLLECTION_NAME_PROFILE7'] = "DV FEL Profile 7"
        app.config['COLLECTION_NAME_TRUEHD_ATMOS'] = "TrueHD Atmos"
        app.config['AUTO_START_MODE'] = "none"
        app.config['MAX_REPORTS_SIZE'] = 5
        app.config['TELEGRAM_ENABLED'] = False
        app.config['TELEGRAM_TOKEN'] = ""
        app.config['TELEGRAM_CHAT_ID'] = ""
        app.config['TELEGRAM_NOTIFY_ALL_UPDATES'] = False
        app.config['TELEGRAM_NOTIFY_NEW_MOVIES'] = True
        app.config['TELEGRAM_NOTIFY_DV'] = True
        app.config['TELEGRAM_NOTIFY_P7'] = True
        app.config['TELEGRAM_NOTIFY_ATMOS'] = True
        app.config['RADARR_BASE_URL'] = ""
        app.config['RADARR_API_KEY'] = ""
        app.config['RADARR_ROOT_FOLDER_ID'] = ""
        app.config['RADARR_QUALITY_PROFILE_ID'] = ""
        app.config['RADARR_AUTO_IMPORT'] = False
        app.config['RADARR_DRY_RUN'] = True
        app.config['SETUP_COMPLETED'] = False
        app.config['LAST_SCAN_RESULTS'] = {'total': 0, 'dv_count': 0, 'p7_count': 0, 'atmos_count': 0}
        
        # Save updated settings
        save_settings()
        
        # Clear data if requested
        if request.json.get('clear_data', False):
            try:
                for file in os.listdir(app.config['REPORTS_FOLDER_PATH']):
                    file_path = os.path.join(app.config['REPORTS_FOLDER_PATH'], file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            except Exception as e:
                log.error(f"Error clearing data: {e}")
        
        # Reset scanner
        with state.lock:
            if state.scanner_obj and hasattr(state.scanner_obj, 'close'):
                try:
                    # Create a temporary event loop if needed
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(state.scanner_obj.close())
                except Exception as e:
                    log.error(f"Error closing scanner: {e}")
            state.scanner_obj = None
                
            state.scan_results = {
                'total': 0,
                'dv_count': 0,
                'p7_count': 0,
                'atmos_count': 0,
                'scan_progress': 0,
                'status': 'idle'
            }

            state.last_collection_changes = {'added': [], 'removed': []}
            state.radarr_stats = {
                'status': 'disabled',
                'message': 'Radarr integration not configured',
                'matched': 0,
                'monitored': 0,
                'total_known': 0,
                'movies_in_radarr': 0,
                'last_checked': None,
                'root_folders': [],
                'quality_profiles': []
            }

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# IPTScanner API Endpoints
@app.route('/api/iptscanner/settings', methods=['GET', 'POST'])
def iptscanner_settings():
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'config.json')
        
        # Create the config if it doesn't exist
        if not os.path.exists(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path))
        
        # Default config
        default_config = {
            "iptorrents": {
                "url": "https://iptorrents.com/login",
                "searchUrl": "https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=adv#torrents",
                "searchTerm": "BL+EL+RPU",
                "cookiePath": ""
            },
            "telegram": {
                "enabled": False,
                "botToken": "",
                "chatId": ""
            },
            "checkInterval": "0 */2 * * *",
            "dataPath": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'data', 'known_torrents.json'),
            "configPath": config_path,
            "cookiesPath": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'cookies.json'),
            "headless": True,
            "debug": False,
            "loginComplete": False,
            "userDataDir": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'browser-profile'),
            "lastUpdateTime": None
        }
        
        # Ensure the config file exists
        if not os.path.exists(config_path):
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
        
        if request.method == 'GET':
            # Read and return current settings
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Convert to more readable format for the frontend
                frontend_config = {
                    "enabled": True,
                    "searchTerm": config["iptorrents"]["searchTerm"],
                    "checkInterval": config["checkInterval"],
                    "headless": config["headless"],
                    "debug": config["debug"],
                    "uid": config.get("uid", ""),
                    "pass": config.get("pass", "")
                }
                
                return jsonify(frontend_config)
            except Exception as e:
                app.logger.error(f"Error reading IPTScanner config: {str(e)}")
                # Return a simplified default if we can't read the file
                return jsonify({
                    "enabled": True,
                    "searchTerm": "BL+EL+RPU",
                    "checkInterval": "0 */2 * * *",
                    "headless": True,
                    "debug": False,
                    "uid": "",
                    "pass": ""
                })
        else:  # POST
            # Update settings
            new_config = request.get_json()
            
            try:
                # Read existing config
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Map frontend settings to JS config format
                if "searchTerm" in new_config:
                    config["iptorrents"]["searchTerm"] = new_config["searchTerm"]
                    config["iptorrents"]["searchUrl"] = f"https://iptorrents.com/t?q={new_config['searchTerm']}&qf=adv#torrents"
                
                if "checkInterval" in new_config:
                    # If the value for checkInterval is a key (like '2hour'), convert it to cron
                    if new_config['checkInterval'] in ['15min', '30min', '1hour', '2hour', '6hour', '12hour', '1day']:
                        cron_map = {
                            '15min': '*/15 * * * *',
                            '30min': '*/30 * * * *',
                            '1hour': '0 */1 * * *',
                            '2hour': '0 */2 * * *',
                            '6hour': '0 */6 * * *',
                            '12hour': '0 */12 * * *',
                            '1day': '0 0 * * *'
                        }
                        config["checkInterval"] = cron_map.get(new_config['checkInterval'], '0 */2 * * *')
                    else:
                        config["checkInterval"] = new_config["checkInterval"]
                
                if "headless" in new_config:
                    config["headless"] = new_config["headless"]
                
                if "debug" in new_config:
                    config["debug"] = new_config["debug"]
                
                # Only save non-empty credentials
                if "uid" in new_config and "pass" in new_config:
                    if new_config["uid"] and new_config["pass"]:
                        config["uid"] = new_config["uid"]
                        config["pass"] = new_config["pass"]
                        
                        # Also update cookies.json
                        cookies = [
                            {
                                "name": "uid",
                                "value": new_config["uid"],
                                "domain": ".iptorrents.com",
                                "path": "/",
                                "expires": int(datetime.now().timestamp() + 86400 * 30)
                            },
                            {
                                "name": "pass",
                                "value": new_config["pass"],
                                "domain": ".iptorrents.com",
                                "path": "/",
                                "expires": int(datetime.now().timestamp() + 86400 * 30)
                            }
                        ]
                        
                        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'cookies.json')
                        with open(cookies_path, 'w') as f:
                            json.dump(cookies, f)
                            app.logger.info(f"Updated cookies")
                
                # Update Radarr settings if provided
                if "radarr" in new_config:
                    config["radarr"] = new_config["radarr"]
                
                # Write back the updated config
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                
                app.logger.info(f"Updated IPTScanner config")
                
                # Update the schedule
                schedule_ipt_scanner(config)
                
                return jsonify({"success": True})
            except Exception as e:
                app.logger.error(f"Error updating IPTScanner config: {str(e)}")
                return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        app.logger.error(f"IPTScanner settings endpoint error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/iptscanner/torrents', methods=['GET'])
def iptscanner_torrents():
    try:
        # If the check_only parameter is set, just check if cookies exist
        check_only = request.args.get('check_only', 'false').lower() == 'true'

        iptscanner_dirs = _get_iptscanner_dirs()

        cookies_file: Optional[str] = None
        for directory in iptscanner_dirs:
            candidate = os.path.join(directory, 'cookies.json')
            if os.path.exists(candidate):
                cookies_file = candidate
                break

        if cookies_file is None:
            base_dir = iptscanner_dirs[0] if iptscanner_dirs else os.path.join(DATA_DIR, 'iptscanner')
            cookies_file = os.path.join(base_dir, 'cookies.json')

        # Check if cookies file exists
        if not os.path.exists(cookies_file):
            return jsonify({'error': 'No cookies file found. Please add your IPTorrents cookies.'})

        # If check_only is true, just return success
        if check_only:
            return jsonify({'success': True, 'message': 'Cookies file exists'})
        
        # Rest of the function logic to get torrents
        refresh = request.args.get('refresh', 'false').lower() == 'true'

        if refresh:
            app.logger.info("Force refresh requested for IPTorrents data")
            # Run the JS script to get fresh data
            iptscanner_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner')
            js_script = os.path.join(iptscanner_dir, 'monitor-iptorrents.js')
            cmd = ['node', js_script, '--one-time']

            try:
                app.logger.info(f"Running command: {' '.join(cmd)}")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    text=True,
                    cwd=iptscanner_dir
                )
                
                stdout, stderr = process.communicate()
                
                if stdout:
                    app.logger.info(f"Refresh stdout: {stdout[:200]}...")
                if stderr:
                    app.logger.error(f"Refresh stderr: {stderr[:200]}...")

                app.logger.info("Refresh completed")

                # Update lastUpdateTime in config file
                config_path: Optional[str] = None
                for directory in iptscanner_dirs:
                    candidate = os.path.join(directory, 'config.json')
                    if os.path.exists(candidate):
                        config_path = candidate
                        break

                if config_path is None and iptscanner_dirs:
                    config_path = os.path.join(iptscanner_dirs[0], 'config.json')

                if config_path and os.path.exists(config_path):
                    try:
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                        config['lastUpdateTime'] = datetime.now().isoformat()
                        with open(config_path, 'w') as f:
                            json.dump(config, f, indent=4)
                    except Exception as e:
                        app.logger.error(f"Error updating config after refresh: {str(e)}")
            except Exception as e:
                app.logger.error(f"Error during refresh: {str(e)}")

        torrents, search_term, last_check = load_iptorrents_snapshot()

        if not torrents:
            app.logger.warning("No torrents found in IPTorrents snapshot")
            return jsonify({
                "torrents": [],
                "lastCheck": last_check,
                "searchTerm": search_term
            })

        return jsonify({
            "torrents": torrents,
            "lastCheck": last_check,
            "searchTerm": search_term
        })
    except Exception as e:
        app.logger.error(f"Error getting IPTScanner torrents: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/iptscanner/test-login', methods=['POST'])
def test_ipt_login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        uid = data.get('uid')
        passkey = data.get('passkey', data.get('pass'))
        
        if not uid or not passkey:
            return jsonify({'success': False, 'error': 'UID and passkey are required'}), 400

        # Get data directory from environment variable or use default
        data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        iptscanner_dir = os.path.join(data_dir, 'iptscanner')
        
        # Create directory if it doesn't exist
        os.makedirs(iptscanner_dir, exist_ok=True)
        
        # Create the cookies.json file
        cookies_path = os.path.join(iptscanner_dir, 'cookies.json')
        
        # Create cookies in proper format for puppeteer
        cookies = [
            {
                "name": "uid",
                "value": uid,
                "domain": ".iptorrents.com",
                "path": "/",
                "expires": int(datetime.now().timestamp() + 86400 * 30)
            },
            {
                "name": "pass",
                "value": passkey,
                "domain": ".iptorrents.com",
                "path": "/",
                "expires": int(datetime.now().timestamp() + 86400 * 30)
            }
        ]
        
        app.logger.info(f"Saving cookies to {cookies_path}")
        
        with open(cookies_path, 'w') as f:
            json.dump(cookies, f, indent=4)
        
        # Update the config.json file as well
        config_path = os.path.join(iptscanner_dir, 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Update config with credentials
                config['uid'] = uid
                config['pass'] = passkey
                config['loginComplete'] = True
                config['cookiesPath'] = cookies_path
                
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                    app.logger.info("Updated config with credentials")
            except Exception as e:
                app.logger.error(f"Error updating config: {str(e)}")
        
        # Run the JS login test script path
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner')
        js_script = os.path.join(script_dir, 'login-test.js')
        
        # Create a simple test script if it doesn't exist
        if not os.path.exists(js_script):
            app.logger.info("Creating login test script")
            test_script = """
const fs = require('fs');
const puppeteer = require('puppeteer');

// Check if cookie path was provided
const cookiePath = process.argv[2];
if (!cookiePath) {
    console.error('DEBUG: No cookie path provided');
    process.exit(1);
}

console.error('DEBUG: Script started');
console.error('DEBUG: Starting login test...');
console.error('DEBUG: Loading cookies from: ' + cookiePath);

// Load cookies
if (!fs.existsSync(cookiePath)) {
    console.error('DEBUG: Cookies file not found at: ' + cookiePath);
    // Try alternative paths
    const altPath1 = cookiePath.replace('/data/', '/app/');
    const altPath2 = cookiePath.replace('/app/', '/data/');
    
    console.error('DEBUG: Trying alternative path: ' + altPath1);
    if (fs.existsSync(altPath1)) {
        console.error('DEBUG: Found cookies at alternative path: ' + altPath1);
        cookiePath = altPath1;
    } else {
        console.error('DEBUG: Trying alternative path: ' + altPath2);
        if (fs.existsSync(altPath2)) {
            console.error('DEBUG: Found cookies at alternative path: ' + altPath2);
            cookiePath = altPath2;
        } else {
            console.error('DEBUG: Cookies file not found at any path');
            console.log(JSON.stringify({ success: false, error: 'Cookies file not found' }));
            process.exit(1);
        }
    }
}

const cookies = JSON.parse(fs.readFileSync(cookiePath, 'utf8'));
console.error('DEBUG: Loaded ' + cookies.length + ' cookies');

async function testLogin() {
    let browser;
    try {
        // Launch headless browser
        browser = await puppeteer.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36');
        
        // Go to IPTorrents and set cookies
        await page.goto('https://iptorrents.com');
        await page.setCookie(...cookies);
        
        // Navigate to the site and check if we're logged in
        await page.goto('https://iptorrents.com/t');
        
        // Check for login status by looking for user menu or logout link
        const userMenu = await page.$('a[href*="/u/"]') || await page.$('a.logout');
        const isLoggedIn = !!userMenu;
        
        console.log(JSON.stringify({ success: isLoggedIn }));
        await browser.close();
    } catch (err) {
        console.error('Error during login test:', err.message);
        if (browser) await browser.close();
        console.log(JSON.stringify({ success: false, error: err.message }));
        process.exit(1);
    }
}

testLogin();
"""
            with open(js_script, 'w') as f:
                f.write(test_script)
        
        app.logger.info(f"Running login test with Node.js using cookies at {cookies_path}")
        
        # Check if node_modules are installed
        node_modules = os.path.join(script_dir, 'node_modules')
        if not os.path.exists(node_modules):
            app.logger.warning("Node modules not installed, attempting to install puppeteer")
            try:
                subprocess.run(['npm', 'install', 'puppeteer', '--no-save'], cwd=script_dir, check=True)
            except Exception as e:
                app.logger.error(f"Failed to install puppeteer: {str(e)}")
                return jsonify({'success': False, 'error': f"Failed to install required dependencies: {str(e)}"}), 500
        
        # Run the test script
        try:
            process = subprocess.run(
                ['node', js_script, cookies_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=script_dir,
                timeout=60
            )
            
            # Log the output for debugging
            app.logger.info(f"Test login stdout: {process.stdout}")
            app.logger.info(f"Test login stderr: {process.stderr}")
            
            if process.returncode != 0:
                app.logger.error(f"Login test failed with return code {process.returncode}")
                return jsonify({'success': False, 'error': 'Login test script failed'}), 500
            
            # Parse the result from stdout
            try:
                result = json.loads(process.stdout.strip())
                if result.get('success'):
                    return jsonify({'success': True, 'message': 'Login successful! Cookies have been saved.'})
                else:
                    error_msg = result.get('error', 'Invalid credentials or site error')
                    return jsonify({'success': False, 'error': f'Login failed: {error_msg}'})
            except json.JSONDecodeError:
                app.logger.error(f"Failed to parse test login result: {process.stdout}")
                return jsonify({'success': False, 'error': 'Invalid response from login test'}), 500
                
        except subprocess.TimeoutExpired:
            app.logger.error("Login test timed out after 60 seconds")
            return jsonify({'success': False, 'error': 'Login test timed out'}), 500
        except Exception as e:
            app.logger.error(f"Error running login test: {str(e)}")
            return jsonify({'success': False, 'error': f'Error running login test: {str(e)}'}), 500
            
    except Exception as e:
        app.logger.error(f"Error in test_ipt_login: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper function to schedule the IPT scanner
def schedule_ipt_scanner(config):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        import pytz
        
        global scheduler
        
        # Initialize scheduler if not already done
        if 'scheduler' not in globals() or scheduler is None:
            # Use scheduler with explicit UTC timezone (supported)
            scheduler = BackgroundScheduler(
                daemon=True, 
                job_defaults={'misfire_grace_time': 3600},
                timezone=pytz.utc
            )
            scheduler.start()
            app.logger.info("Scheduler started")
        
        # Remove existing IPT scanner jobs
        for job in scheduler.get_jobs():
            if job.id == 'iptscanner':
                scheduler.remove_job(job.id)
                app.logger.info("Removed existing IPTScanner job")
        
        # Add new job if enabled
        if config.get('enabled', True):
            # Convert cron expression to interval hours for simplicity
            interval_hours = 2  # Default 2 hours
            
            cron_expr = config.get('checkInterval', '0 */2 * * *')
            if '*/1' in cron_expr:
                interval_hours = 1
            elif '*/2' in cron_expr:
                interval_hours = 2
            elif '*/6' in cron_expr:
                interval_hours = 6
            elif '*/12' in cron_expr:
                interval_hours = 12
            elif '0 0' in cron_expr:  # Daily at midnight
                interval_hours = 24
            
            app.logger.info(f"Setting IPTScanner interval to {interval_hours} hours")
            
            # Add job with interval trigger instead of cron
            scheduler.add_job(
                func=run_ipt_scanner,
                args=[config],
                trigger='interval',
                hours=interval_hours,
                id='iptscanner',
                replace_existing=True
            )
            
            # Run immediately if debug is enabled
            if config.get('debug', False):
                app.logger.info("Debug mode enabled, running IPTScanner immediately")
                run_ipt_scanner(config)
            
            app.logger.info(f"IPTScanner scheduled to run every {interval_hours} hours")
    except Exception as e:
        app.logger.error(f"Error initializing scheduler: {str(e)}")

def run_ipt_scanner(config=None):
    """Run the IPT scanner with the provided configuration"""
    try:
        app.logger.info("Running IPT scanner...")
        
        # Get data directory from environment variable or use default
        data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        iptscanner_dir = os.path.join(data_dir, 'iptscanner')
        
        # Create the data directory if it doesn't exist
        os.makedirs(iptscanner_dir, exist_ok=True)
        
        # Get the path to the IPT scanner script
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner')
        script_path = os.path.join(script_dir, 'monitor-iptorrents.js')
        
        app.logger.info(f"Script directory: {script_dir}")
        app.logger.info(f"Script path: {script_path}")
        app.logger.info(f"Data directory: {data_dir}")
        app.logger.info(f"IPT scanner directory: {iptscanner_dir}")
        
        # Check if the script exists
        if not os.path.exists(script_path):
            app.logger.error(f"IPT scanner script not found at {script_path}")
            return False
        
        # Check and log cookie file existence
        cookies_path = os.path.join(iptscanner_dir, 'cookies.json')
        app.logger.info(f"Cookies path: {cookies_path}, exists: {os.path.exists(cookies_path)}")
        
        if os.path.exists(cookies_path):
            try:
                with open(cookies_path, 'r') as f:
                    cookies_content = f.read()
                app.logger.info(f"Cookies file content length: {len(cookies_content)} bytes")
            except Exception as e:
                app.logger.error(f"Error reading cookies file: {str(e)}")
        
        # Run the script
        try:
            # Prepare the command
            cmd = ['node', script_path, '--one-time']
            
            # Add the config path if provided
            if config:
                config_path = os.path.join(iptscanner_dir, 'config.json')
                app.logger.info(f"Writing config to: {config_path}")
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=4)
                cmd.append(config_path)
            
            # Verify config file existence
            config_path = os.path.join(iptscanner_dir, 'config.json')
            app.logger.info(f"Config path: {config_path}, exists: {os.path.exists(config_path)}")
            
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config_content = json.load(f)
                    app.logger.info(f"Config file content keys: {list(config_content.keys())}")
                except Exception as e:
                    app.logger.error(f"Error reading config file: {str(e)}")
            
            app.logger.info(f"Running command: {' '.join(cmd)}")
            
            # Set up path for npm modules
            env = os.environ.copy()
            node_modules_path = os.path.join(script_dir, 'node_modules')
            app.logger.info(f"Node modules path: {node_modules_path}, exists: {os.path.exists(node_modules_path)}")
            
            # Run the script and capture output
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=script_dir,
                env=env
            )
            
            # Log output in real-time
            stdout_data = []
            stderr_data = []
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    app.logger.info(f"IPT Scanner: {line}")
                    stdout_data.append(line)
            
            # Get stderr after process completes
            stderr = process.stderr.read()
            if stderr:
                for line in stderr.splitlines():
                    if line.strip():
                        app.logger.error(f"IPT Scanner Error: {line.strip()}")
                        stderr_data.append(line.strip())
            
            # Wait for process to complete, with timeout
            try:
                process.wait(timeout=300)  # 5 minute timeout
            except subprocess.TimeoutExpired:
                app.logger.error("IPT scanner process timed out and was terminated")
                process.kill()
                return False
            
            # Check exit code
            if process.returncode != 0:
                app.logger.error(f"IPT scanner exited with error code {process.returncode}")
                return False
            else:
                app.logger.info("IPT scanner completed successfully")
                return True
                
        except Exception as e:
            app.logger.error(f"Error executing IPT scanner: {str(e)}")
            return False
    
    except Exception as e:
        app.logger.error(f"Error in run_ipt_scanner: {str(e)}")
        return False

def init_iptscanner():
    """Initialize the IPT scanner components at startup"""
    try:
        app.logger.info("Initializing IPT scanner...")
        
        # Get data directory from environment variable or use default
        data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        iptscanner_dir = os.path.join(data_dir, 'iptscanner')
        
        # Create the iptscanner directory if it doesn't exist
        os.makedirs(iptscanner_dir, exist_ok=True)
        os.makedirs(os.path.join(iptscanner_dir, 'data'), exist_ok=True)
        os.makedirs(os.path.join(iptscanner_dir, 'profile'), exist_ok=True)
        
        # Ensure config.json exists
        config_path = os.path.join(iptscanner_dir, 'config.json')
        
        if not os.path.exists(config_path):
            app.logger.info(f"Creating default IPT scanner config at {config_path}")
            default_config = {
                "iptorrents": {
                    "url": "https://iptorrents.com/login",
                    "searchUrl": "https://iptorrents.com/t?q=BL%2BEL%2BRPU&qf=adv#torrents",
                    "searchTerm": "BL+EL+RPU",
                    "cookiePath": os.path.join(iptscanner_dir, 'cookies.json')
                },
                "telegram": {
                    "enabled": False,
                    "botToken": "",
                    "chatId": ""
                },
                "checkInterval": "0 */2 * * *",
                "dataPath": os.path.join(iptscanner_dir, 'data', 'known_torrents.json'),
                "configPath": config_path,
                "cookiesPath": os.path.join(iptscanner_dir, 'cookies.json'),
                "headless": True,
                "debug": False,
                "loginComplete": False,
                "userDataDir": os.path.join(iptscanner_dir, 'profile'),
                "lastUpdateTime": None
            }
            
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=4)
                
        app.logger.info("IPT scanner initialized")
        return True
    except Exception as e:
        app.logger.error(f"Error initializing IPT scanner: {str(e)}")
        return False

# Load settings at startup
load_settings()

# Start notification processor
start_notification_processor()

# Auto-start if configured
if app.config['SETUP_COMPLETED'] and app.config['AUTO_START_MODE'] == 'monitor':
    monitor_thread = threading.Thread(target=run_monitor)
    monitor_thread.daemon = True
    monitor_thread.start()

# Replace the @app.before_first_request decorator
# Old code:
# @app.before_first_request
# def init_iptscanner():

# New initialization approach
init_iptscanner()


@app.route('/api/iptscanner/test-run', methods=['POST'])
def test_run_iptscanner():
    """Test run the IPT scanner"""
    try:
        app.logger.info("Manual test run of IPT scanner triggered")
        
        # Get data directory
        data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        iptscanner_dir = os.path.join(data_dir, 'iptscanner')
        config_path = os.path.join(iptscanner_dir, 'config.json')
        
        # Check if node_modules exist and install if needed
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner')
        node_modules_path = os.path.join(script_dir, 'node_modules')
        
        if not os.path.exists(node_modules_path):
            app.logger.info("Node modules not found, installing...")
            try:
                subprocess.run(['npm', 'install', '--no-cache'], cwd=script_dir, check=True)
                app.logger.info("Node modules installed successfully")
            except Exception as e:
                app.logger.error(f"Failed to install node modules: {str(e)}")
                return jsonify({'success': False, 'error': f'Failed to install node modules: {str(e)}'}), 500
        
        # Check if config exists
        if not os.path.exists(config_path):
            return jsonify({'success': False, 'error': f'Config file not found at {config_path}'}), 404
            
        # Load the config
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to load config: {str(e)}'}), 500
            
        # Run the scanner
        result = run_ipt_scanner(config)
        
        if result:
            return jsonify({'success': True, 'message': 'IPT scanner test run completed successfully'})
        else:
            return jsonify({'success': False, 'error': 'IPT scanner test run failed, check logs for details'}), 500
            
    except Exception as e:
        app.logger.error(f"Error in test_run_iptscanner: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


# Add this at the bottom of the file, before app.run()
if __name__ == "__main__":
    # Initialize IPTScanner
    init_iptscanner()

    # Start the app
    app.run(host='0.0.0.0', port=5000, debug=True)
