from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
import os
import json
import logging
import asyncio
import time
import threading
import requests
import pytz
import shutil
from datetime import datetime, timedelta
from flask_compress import Compress
from plexapi.server import PlexServer
from scanner import PlexDVScanner
import sys
import subprocess
import tempfile
from typing import Any, Awaitable, Callable, Optional
from urllib.parse import urlparse
import re
from requests import exceptions as requests_exceptions


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'felscanner-secret-key')
compress = Compress()
compress.init_app(app)

# Get data directory from environment variable or use default
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
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
            'server': {'status': 'connected', 'message': 'Web server running'},
            'iptorrents': {'status': 'unknown', 'message': 'Not connected'}
        }
        self.lock = threading.RLock()  # For thread-safe state updates

# Create application state
state = AppState()


def _human_readable_size(num_bytes: int) -> str:
    """Return a human friendly file size string."""
    try:
        num = float(num_bytes)
    except (TypeError, ValueError):
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if num < 1024 or unit == units[-1]:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} {unit}"
        num /= 1024


def _list_reports(limit: Optional[int] = None) -> list[dict]:
    """Return the available reports sorted by newest first."""
    reports = []
    reports_dir = app.config.get('REPORTS_FOLDER_PATH', EXPORTS_DIR)
    if not os.path.isdir(reports_dir):
        return []

    for filename in os.listdir(reports_dir):
        if not (filename.endswith('.csv') or filename.endswith('.json')):
            continue
        file_path = os.path.join(reports_dir, filename)
        try:
            modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            size_bytes = os.path.getsize(file_path)
        except OSError:
            continue

        reports.append({
            'filename': filename,
            'date': modified,
            'size': size_bytes,
            'display_size': _human_readable_size(size_bytes)
        })

    reports.sort(key=lambda item: item['date'], reverse=True)
    if limit is not None:
        return reports[:limit]
    return reports


def _trigger_scan_operation(operation: str) -> tuple[bool, Optional[str]]:
    """Start a scan or verify job, returning (success, error_message)."""
    with state.lock:
        if state.is_scanning:
            return False, 'A scan is already in progress.'

    if operation not in ('scan', 'verify'):
        return False, 'Invalid operation.'

    try:
        if not state.scanner_obj:
            state.scanner_obj = initialize_scanner()

        if not state.scanner_obj:
            return False, 'Unable to initialise the scanner.'

        target = run_scan_thread if operation == 'scan' else run_verify_thread
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        return True, None
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)


def _toggle_monitor_action(action: str) -> tuple[bool, Optional[str]]:
    """Start or stop monitor mode."""
    with state.lock:
        is_scanning = state.is_scanning
        is_monitoring = state.monitor_active

    if action == 'start':
        if is_monitoring:
            return True, 'Monitor already running.'
        if is_scanning:
            return False, 'Cannot start monitor while a scan is running.'

        with state.lock:
            state.monitor_active = True

        monitor_thread = threading.Thread(target=run_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        return True, None

    if action == 'stop':
        if not is_monitoring:
            return True, 'Monitor already stopped.'

        with state.lock:
            state.monitor_active = False
        return True, None

    return False, 'Invalid monitor action.'


def _load_ipt_config() -> dict:
    """Load (and if necessary create) the IPT scanner configuration."""
    storage_dir = _iptscanner_storage_dir()
    config_path = _iptscanner_config_path()
    cookies_path = _iptscanner_cookies_path()
    known_path = _iptscanner_known_torrents_path()
    results_path = os.path.join(storage_dir, 'data', 'latest_results.json')

    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs(os.path.join(storage_dir, 'data'), exist_ok=True)

    default_config = {
        'searchTerm': 'BL+EL+RPU',
        'checkInterval': '0 */2 * * *',
        'enabled': True,
        'cookies': {'uid': '', 'pass': ''},
        'cookiesPath': cookies_path,
        'knownTorrentsPath': known_path,
        'resultsPath': results_path,
        'solverUrl': os.environ.get('FLARESOLVERR_URL', 'http://localhost:8191'),
        'solverTimeout': 60000,
        'debug': False,
        'cachedCookies': [],
        'lastUpdateTime': None
    }

    if not os.path.exists(config_path):
        with open(config_path, 'w') as handle:
            json.dump(default_config, handle, indent=4)
        return default_config

    try:
        with open(config_path, 'r') as handle:
            config = json.load(handle)
    except Exception:
        with open(config_path, 'w') as handle:
            json.dump(default_config, handle, indent=4)
        return default_config

    config.setdefault('searchTerm', default_config['searchTerm'])
    config.setdefault('checkInterval', default_config['checkInterval'])
    config.setdefault('enabled', True)
    config.setdefault('cookies', {'uid': '', 'pass': ''})
    config.setdefault('cookiesPath', cookies_path)
    config.setdefault('knownTorrentsPath', known_path)
    config.setdefault('resultsPath', results_path)
    config.setdefault('solverUrl', default_config['solverUrl'])
    config.setdefault('solverTimeout', default_config['solverTimeout'])
    config.setdefault('debug', False)
    config.setdefault('cachedCookies', [])
    config.setdefault('lastUpdateTime', None)

    try:
        config['solverTimeout'] = int(config.get('solverTimeout', default_config['solverTimeout']))
    except (TypeError, ValueError):
        config['solverTimeout'] = default_config['solverTimeout']

    if not isinstance(config.get('solverUrl'), str) or not config['solverUrl'].strip():
        config['solverUrl'] = default_config['solverUrl']

    return config


def _save_ipt_config(config: dict) -> bool:
    """Persist the IPT scanner configuration."""
    try:
        config['solverTimeout'] = int(config.get('solverTimeout', 60000))
        redacted = dict(config)
        if isinstance(redacted.get('cookies'), dict):
            redacted['cookies'] = {
                key: '***' if value else ''
                for key, value in redacted['cookies'].items()
            }
        if isinstance(redacted.get('cachedCookies'), list):
            redacted['cachedCookies'] = [
                {**cookie, 'value': '***'}
                if isinstance(cookie, dict) and cookie.get('value')
                else cookie
                for cookie in redacted['cachedCookies']
            ]
        log.debug(f"Saving IPT config: {redacted}")
        with open(_iptscanner_config_path(), 'w') as handle:
            json.dump(config, handle, indent=4)
        return True
    except Exception as exc:
        log.error(f"Failed to save IPT config: {exc}")
        return False


def _set_iptorrents_status(status: str, message: str) -> None:
    with state.lock:
        state.connection_status['iptorrents'] = {
            'status': status,
            'message': message
        }


def _write_ipt_cookies_file(config: dict) -> str:
    cookies_cfg = config.setdefault('cookies', {})
    uid = cookies_cfg.get('uid', '').strip()
    passkey = cookies_cfg.get('pass', '').strip()
    if not uid or not passkey:
        raise ValueError('UID and pass cookies are required.')

    cookies_path = config.get('cookiesPath', _iptscanner_cookies_path())
    cookie_payload: list[dict] = [
        {
            'name': 'uid',
            'value': uid,
            'domain': '.iptorrents.com',
            'path': '/',
            'expires': int(time.time()) + 86400 * 30
        },
        {
            'name': 'pass',
            'value': passkey,
            'domain': '.iptorrents.com',
            'path': '/',
            'expires': int(time.time()) + 86400 * 30
        }
    ]
    extra_cookies = []
    for cookie in config.get('cachedCookies', []):
        if not isinstance(cookie, dict):
            continue
        name = (cookie.get('name') or '').strip()
        if name in {'uid', 'pass'} or not name:
            continue
        extra_cookies.append({
            'name': name,
            'value': cookie.get('value', ''),
            'domain': cookie.get('domain', '.iptorrents.com'),
            'path': cookie.get('path', '/'),
            'expires': int(cookie.get('expires', time.time() + 86400))
        })

    cookie_payload.extend(extra_cookies)
    os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
    with open(cookies_path, 'w') as handle:
        json.dump(cookie_payload, handle, indent=2)
    return cookies_path


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Convert an ISO8601-like string to a datetime (UTC) if possible."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        value_str = str(value).strip()
        if not value_str:
            return None
        if value_str.endswith('Z'):
            value_str = value_str[:-1] + '+00:00'
        return datetime.fromisoformat(value_str)
    except Exception:
        return None


def _parse_relative_timestamp(text: str, now: datetime) -> Optional[datetime]:
    """Convert phrases like '2.5 hours ago' into an absolute timestamp."""
    if not text:
        return None

    cleaned = text.lower().strip()
    if 'ago' not in cleaned:
        return None
    if ' by ' in cleaned:
        cleaned = cleaned.split(' by ')[0].strip()

    parts = cleaned.split()
    if not parts:
        return None

    try:
        value = float(parts[0])
    except (TypeError, ValueError):
        return None

    if 'min' in cleaned:
        delta = timedelta(minutes=value)
    elif 'hour' in cleaned:
        delta = timedelta(hours=value)
    elif 'day' in cleaned:
        delta = timedelta(days=value)
    elif 'week' in cleaned:
        delta = timedelta(weeks=value)
    elif 'month' in cleaned:
        delta = timedelta(days=value * 30)
    elif 'year' in cleaned:
        delta = timedelta(days=value * 365)
    else:
        return None

    return now - delta


def _cron_interval_to_timedelta(expr: Optional[str]) -> timedelta:
    """Best-effort conversion from a cron string to a reasonable timedelta."""
    default = timedelta(hours=2)
    if not expr:
        return default
    parts = expr.strip().split()
    if len(parts) < 2:
        return default

    try:
        if parts[0].startswith('*/'):
            minutes = int(parts[0][2:])
            return timedelta(minutes=max(minutes, 1))
        if parts[0] == '0' and parts[1].startswith('*/'):
            hours = int(parts[1][2:])
            return timedelta(hours=max(hours, 1))
        if len(parts) >= 3 and parts[0] == '0' and parts[1] == '0' and parts[2].startswith('*/'):
            days = int(parts[2][2:])
            return timedelta(days=max(days, 1))
    except ValueError:
        return default

    return default


def _summarize_ipt_activity(config: dict, recent_items: list[dict]) -> tuple[int, Optional[datetime], Optional[datetime]]:
    """Return (new_items_last_24h, last_check_time, next_check_time)."""
    now = datetime.utcnow()
    new_count = 0

    for item in recent_items or []:
        raw_added = item.get('addedRaw') or item.get('added')
        timestamp = _parse_iso_datetime(raw_added)
        if timestamp is None and isinstance(raw_added, str):
            timestamp = _parse_relative_timestamp(raw_added, now)

        if timestamp is not None and now - timestamp <= timedelta(hours=24):
            new_count += 1

    last_check = _parse_iso_datetime(config.get('lastUpdateTime'))
    interval = _cron_interval_to_timedelta(config.get('checkInterval', '0 */2 * * *'))
    next_check = last_check + interval if last_check else None

    return new_count, last_check, next_check


def _format_human_datetime(value: Optional[datetime]) -> str:
    """Render a datetime as a concise human readable string."""
    if not value:
        return 'Unknown'
    now = datetime.utcnow()
    delta = abs(now - value)
    try:
        local_value = value.astimezone()
    except Exception:
        local_value = value
    if delta <= timedelta(hours=24):
        return local_value.strftime('%-I:%M %p')
    if delta <= timedelta(days=7):
        return local_value.strftime('%a %-I:%M %p')
    return local_value.strftime('%Y-%m-%d %-I:%M %p')


def _fetch_ipt_results(config: dict, limit: int = 50, force: bool = True) -> list[dict]:
    search_term = (config.get('searchTerm') or '').strip()
    if not search_term:
        raise ValueError('Search term is required.')

    cookies_path = _write_ipt_cookies_file(config)
    script_path = os.path.join(APP_ROOT, 'iptradar', 'fetch-once.js')
    if not os.path.exists(script_path):
        raise FileNotFoundError('IPT fetch script not found. Expected at iptradar/fetch-once.js')

    results_path = config.get('resultsPath') or os.path.join(_iptscanner_storage_dir(), 'data', 'latest_results.json')

    if not force and os.path.exists(results_path):
        try:
            with open(results_path, 'r') as handle:
                cached = json.load(handle)
            if isinstance(cached, dict) and cached.get('torrents'):
                return cached['torrents'][:limit]
        except Exception:
            pass

    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        temp_output = tmp_file.name

    solver_url = config.get('solverUrl', 'http://localhost:8191')
    solver_timeout = int(config.get('solverTimeout', 60000))
    cmd = [
        'node',
        script_path,
        '-c',
        cookies_path,
        '-s',
        search_term,
        '-o',
        temp_output,
        '-u',
        solver_url,
        '-t',
        str(solver_timeout)
    ]
    if config.get('debug'):
        cmd.append('--debug')

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        os.unlink(temp_output)
        stderr = result.stderr.strip() or result.stdout.strip() or 'Unknown error'
        raise RuntimeError(f'IPT fetch failed: {stderr}')

    try:
        with open(temp_output, 'r') as handle:
            data = json.load(handle)
    finally:
        os.unlink(temp_output)

    solver_cookies = data.get('solverCookies')
    if isinstance(solver_cookies, list):
        filtered_cookies = []
        for cookie in solver_cookies:
            if not isinstance(cookie, dict):
                continue
            name = (cookie.get('name') or '').strip()
            if name in {'uid', 'pass'} or not name:
                continue
            filtered_cookies.append({
                'name': name,
                'value': cookie.get('value', ''),
                'domain': cookie.get('domain', '.iptorrents.com'),
                'path': cookie.get('path', '/'),
                'expires': int(cookie.get('expires', time.time() + 86400))
            })
        config['cachedCookies'] = filtered_cookies

    if data.get('userAgent'):
        config['solverUserAgent'] = data['userAgent']

    raw_torrents = data.get('torrents', [])
    normalized = []
    for item in raw_torrents:
        if not isinstance(item, dict):
            continue
        normalized.append({
            'name': item.get('name') or item.get('title'),
            'link': item.get('link') or item.get('download_url'),
            'size': item.get('size'),
            'seeders': item.get('seeders', 0),
            'leechers': item.get('leechers', 0),
            'added': item.get('addedRaw') or item.get('added'),
            'isNew': item.get('isNew', False)
        })

    data['torrents'] = normalized
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, 'w') as handle:
        json.dump(data, handle, indent=2)

    config['lastUpdateTime'] = data.get('fetchedAt')
    _save_ipt_config(config)
    _set_iptorrents_status('connected', f'Fetched {len(normalized)} torrents')
    return normalized[:limit]


def _load_recent_ipt_results(config: dict, limit: int = 10) -> list[dict]:
    results_path = config.get('resultsPath') or os.path.join(_iptscanner_storage_dir(), 'data', 'latest_results.json')
    if not os.path.exists(results_path):
        return []

    try:
        with open(results_path, 'r') as handle:
            stored = json.load(handle)
    except Exception as exc:
        app.logger.error(f"Failed to load cached IPT results: {exc}")
        return []

    torrents = stored.get('torrents', [])
    if not isinstance(torrents, list):
        return []

    return [item for item in torrents[:limit] if isinstance(item, dict)]


def _perform_ipt_login_test(config: dict) -> tuple[bool, str]:
    try:
        torrents = _fetch_ipt_results(config, limit=5, force=True)
        if torrents:
            return True, f'Login successful. Found {len(torrents)} torrents.'
        return True, 'Login successful, but no torrents matched the search term.'
    except Exception as exc:
        _set_iptorrents_status('disconnected', str(exc))
        return False, str(exc)


def _test_plex_settings(plex_url: str, plex_token: str, library_name: str) -> int:
    """Validate Plex credentials and return the movie count."""
    if not plex_url or not plex_token or not library_name:
        raise ValueError("Plex URL, token, and library name are required.")

    plex_url = _validate_and_normalize_plex_url(plex_url)
    plex = PlexServer(plex_url, plex_token)
    movies_section = plex.library.section(library_name)
    return len(movies_section.all())


def _validate_and_normalize_plex_url(raw_url: str) -> str:
    """Ensure a Plex URL includes a scheme we can use."""
    if not raw_url or not raw_url.strip():
        raise ValueError("Plex URL is required.")

    cleaned = raw_url.strip()
    parsed = urlparse(cleaned)

    if not parsed.scheme:
        raise ValueError("Plex URL must include http:// or https:// (e.g. http://10.0.0.104:32400).")

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported Plex URL scheme. Use http:// or https://.")

    return cleaned


def _iptscanner_storage_dir() -> str:
    """Return the persistent IPT scanner storage directory, ensuring it exists."""
    storage_dir = os.path.join(DATA_DIR, 'iptscanner')
    os.makedirs(storage_dir, exist_ok=True)
    os.makedirs(os.path.join(storage_dir, 'data'), exist_ok=True)
    os.makedirs(os.path.join(storage_dir, 'profile'), exist_ok=True)
    return storage_dir


def _iptscanner_config_path() -> str:
    return os.path.join(_iptscanner_storage_dir(), 'config.json')


def _iptscanner_cookies_path() -> str:
    return os.path.join(_iptscanner_storage_dir(), 'cookies.json')


def _iptscanner_known_torrents_path() -> str:
    return os.path.join(_iptscanner_storage_dir(), 'data', 'known_torrents.json')


def _iptscanner_profile_dir() -> str:
    return os.path.join(_iptscanner_storage_dir(), 'profile')


def _iptscanner_script_dir() -> str:
    return os.path.join(APP_ROOT, 'iptscanner')


def _begin_background_operation(status_label: str) -> None:
    """Mark the application as busy with a background scan/verify."""
    with state.lock:
        state.is_scanning = True
        state.scan_results['status'] = status_label
        state.scan_results['scan_progress'] = 0
        state.last_collection_changes = {
            'added': [],
            'removed': [],
            'added_items': [],
            'removed_items': []
        }


def _finalize_background_operation(status_label: str) -> None:
    """Release scan locks and normalise status if nothing updated it."""
    with state.lock:
        state.is_scanning = False
        if state.scan_results.get('status') == status_label:
            state.scan_results['status'] = 'idle'


def _run_background_coroutine(
    coroutine_factory: Callable[[], Awaitable[Any]],
    status_label: str
) -> Optional[Any]:
    """Utility to execute an async workflow inside a worker thread safely."""
    _begin_background_operation(status_label)
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coroutine_factory())
    except Exception as exc:
        log.error(f"Error during {status_label}: {exc}")
        with state.lock:
            state.scan_results['status'] = f"error: {str(exc)}"
    finally:
        try:
            if loop is not None and not loop.is_closed():
                loop.close()
        except Exception as close_error:
            log.debug(f"Error closing event loop for {status_label}: {close_error}")
        finally:
            asyncio.set_event_loop(None)
            _finalize_background_operation(status_label)

# Load settings from file
def load_settings():
    try:
        if not os.path.exists(app.config['SETTINGS_FILE']):
            log.warning(f"Settings file not found at {app.config['SETTINGS_FILE']}, using default settings")
            return
            
        log.info(f"Loading settings from {app.config['SETTINGS_FILE']}")
        with open(app.config['SETTINGS_FILE'], 'r') as f:
            settings = json.load(f)
            
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
            'setup_completed': app.config['SETUP_COMPLETED'],
            'last_scan_results': app.config['LAST_SCAN_RESULTS']
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
        plex_url = _validate_and_normalize_plex_url(app.config['PLEX_URL'])
        plex = PlexServer(plex_url, app.config['PLEX_TOKEN'])
        movies_section = plex.library.section(app.config['LIBRARY_NAME'])
        movie_count = len(movies_section.all())
        
        with state.lock:
            state.connection_status['plex'] = {
                'status': 'connected',
                'message': f'Connected (Found {movie_count} movies)'
            }
        return True
    except ValueError as err:
        with state.lock:
            state.connection_status['plex'] = {
                'status': 'disconnected',
                'message': f'Error: {err}'
            }
        return False
    except requests_exceptions.SSLError as err:
        hint = ("SSL certificate verification failed. If you're using a self-signed certificate or connecting by "
                "IP address, try http:// instead of https:// or install a trusted certificate.")
        with state.lock:
            state.connection_status['plex'] = {
                'status': 'disconnected',
                'message': f'Error: {hint} ({err})'
            }
        return False
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
        
        return scanner
    except Exception as e:
        log.error(f"Error initializing scanner: {e}")
        return None

# Run scan in a thread with its own event loop
def run_scan_thread():
    """Run a scan in a new thread with its own event loop"""
    _run_background_coroutine(async_run_scan, 'scanning')


# Run verify in a thread with its own event loop
def run_verify_thread():
    """Run a verify operation in a new thread with its own event loop"""
    _run_background_coroutine(async_run_verify, 'verifying')

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
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

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

        plex_url = _validate_and_normalize_plex_url(plex_url.strip())
        plex_token = plex_token.strip()
        library_name = library_name.strip()

        plex = PlexServer(plex_url, plex_token)
        movies_section = plex.library.section(library_name)
        movie_count = len(movies_section.all())

        # Persist the validated credentials so the dashboard immediately benefits.
        app.config['PLEX_URL'] = plex_url
        app.config['PLEX_TOKEN'] = plex_token
        app.config['LIBRARY_NAME'] = library_name
        app.config['SETUP_COMPLETED'] = True
        if not save_settings():
            log.warning("Plex test succeeded but saving settings failed.")
        
        return jsonify({'success': True, 'movie_count': movie_count})
    except ValueError as err:
        return jsonify({'success': False, 'error': str(err)})
    except requests_exceptions.SSLError as err:
        hint = ("SSL certificate verification failed. If you're using a self-signed certificate or connecting by "
                "IP address, try http:// instead of https:// or install a trusted certificate.")
        return jsonify({'success': False, 'error': f"{hint} ({err})"})
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
    operation = request.json.get('operation', 'scan')
    success, message = _trigger_scan_operation(operation)
    if success:
        return jsonify({'success': True})
    status = 500
    if message:
        lowered = message.lower()
        if 'invalid' in lowered or 'progress' in lowered or 'cannot' in lowered:
            status = 400
    return jsonify({'error': message or 'Failed to start scan'}), status

@app.route('/api/monitor', methods=['POST'])
def toggle_monitor():
    action = request.json.get('action')
    success, message = _toggle_monitor_action(action)
    if success:
        status = 'started' if action == 'start' else 'stopped'
        return jsonify({'success': True, 'status': status})
    return jsonify({'error': message or 'Invalid action or state'}), 400

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
    full_reports = request.args.get('full', 'false').lower() == 'true'
    
    reports = _list_reports()
    serialised = [
        {
            'filename': item['filename'],
            'date': item['date'].isoformat(),
            'size': item['size']
        }
        for item in reports
    ]
    return jsonify(serialised if full_reports else serialised[:5])

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
        'telegram_notify_atmos': app.config['TELEGRAM_NOTIFY_ATMOS']
    })

@app.route('/api/settings', methods=['POST'])
def save_settings_api():
    try:
        settings = request.json
        
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
        
        save_settings()
        check_plex_connection()
        check_telegram_connection()
        
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
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# IPTScanner API Endpoints
@app.route('/api/iptscanner/settings', methods=['GET', 'POST'])
def iptscanner_settings():
    try:
        config = _load_ipt_config()
        if request.method == 'GET':
            cookies_cfg = config.get('cookies', {})
            has_cookies = bool(cookies_cfg.get('uid') and cookies_cfg.get('pass'))
            response_payload = {
                'search_term': config.get('searchTerm', ''),
                'searchTerm': config.get('searchTerm', ''),
                'check_interval': config.get('checkInterval', '0 */2 * * *'),
                'checkInterval': config.get('checkInterval', '0 */2 * * *'),
                'solver_url': config.get('solverUrl', 'http://localhost:8191'),
                'solverUrl': config.get('solverUrl', 'http://localhost:8191'),
                'solver_timeout': config.get('solverTimeout', 60000),
                'solverTimeout': config.get('solverTimeout', 60000),
                'enabled': config.get('enabled', True),
                'debug': config.get('debug', False),
                'has_cookies': has_cookies,
                'hasCookies': has_cookies,
                'last_update_time': config.get('lastUpdateTime'),
                'lastUpdateTime': config.get('lastUpdateTime')
            }
            return jsonify(response_payload)

        payload = request.get_json(silent=True) or {}

        if 'search_term' in payload and isinstance(payload['search_term'], str):
            config['searchTerm'] = payload['search_term'].strip()
        if 'searchTerm' in payload and isinstance(payload['searchTerm'], str):
            config['searchTerm'] = payload['searchTerm'].strip()
        if 'check_interval' in payload and isinstance(payload['check_interval'], str):
            config['checkInterval'] = payload['check_interval'].strip()
        if 'checkInterval' in payload and isinstance(payload['checkInterval'], str):
            config['checkInterval'] = payload['checkInterval'].strip()

        cookies_cfg = config.setdefault('cookies', {})
        if 'uid' in payload:
            cookies_cfg['uid'] = payload['uid'].strip()
        if 'pass' in payload:
            cookies_cfg['pass'] = payload['pass'].strip()

        enabled_value = payload.get('enabled')
        if enabled_value is not None:
            if isinstance(enabled_value, str):
                config['enabled'] = enabled_value.strip().lower() in {'1', 'true', 'yes', 'on'}
            else:
                config['enabled'] = bool(enabled_value)

        solver_url = payload.get('solver_url') or payload.get('solverUrl')
        if isinstance(solver_url, str) and solver_url.strip():
            config['solverUrl'] = solver_url.strip()

        solver_timeout = payload.get('solver_timeout', payload.get('solverTimeout'))
        if solver_timeout is not None:
            try:
                timeout_int = int(solver_timeout)
                if timeout_int <= 0:
                    raise ValueError
                config['solverTimeout'] = timeout_int
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'solver_timeout must be a positive integer milliseconds'}), 400

        if 'debug' in payload:
            config['debug'] = bool(payload['debug'])

        saved = _save_ipt_config(config)
        if saved:
            schedule_ipt_scanner(config)
        return jsonify({'success': saved})
    except Exception as exc:
        app.logger.error(f"Error updating IPT settings: {exc}")
        return jsonify({'success': False, 'error': str(exc)}), 500
                

@app.route('/api/iptscanner/torrents', methods=['GET'])
def iptscanner_torrents():
    try:
        config = _load_ipt_config()
        refresh = request.args.get('refresh', 'false').lower() == 'true'

        if refresh:
            torrents = _fetch_ipt_results(config, force=True)
        else:
            torrents = _load_recent_ipt_results(config)
            if not torrents:
                torrents = _fetch_ipt_results(config, force=True)

        return jsonify({
            'torrents': torrents,
            'searchTerm': config.get('searchTerm', ''),
            'lastCheck': config.get('lastUpdateTime')
        })
    except ValueError as exc:
        _set_iptorrents_status('disconnected', str(exc))
        return jsonify({'error': str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 500
    except Exception as e:
        app.logger.error(f"Error getting IPTorrents results: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/iptscanner/test-login', methods=['POST'])
def test_ipt_login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        config = _load_ipt_config()
        if 'searchTerm' in data:
            config['searchTerm'] = data['searchTerm'].strip()

        cookies_cfg = config.setdefault('cookies', {})
        if data.get('uid'):
            cookies_cfg['uid'] = data['uid'].strip()
        if data.get('pass'):
            cookies_cfg['pass'] = data['pass'].strip()

        success, message = _perform_ipt_login_test(config)
        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        app.logger.error(f"Error in test_ipt_login: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Helper function to schedule the IPT scanner
def schedule_ipt_scanner(config):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
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

        if not config.get('enabled', True):
            app.logger.info("IPTScanner disabled; skipping job scheduling")
            return

        interval_hours = 2  # Default 2 hours
        cron_expr = config.get('checkInterval', '0 */2 * * *')
        if '*/1' in cron_expr:
            interval_hours = 1
        elif '*/6' in cron_expr:
            interval_hours = 6
        elif '*/12' in cron_expr:
            interval_hours = 12
        elif '0 0' in cron_expr:  # Daily at midnight
            interval_hours = 24

        app.logger.info(f"Setting IPTScanner interval to {interval_hours} hours")

        scheduler.add_job(
            func=run_ipt_scanner,
            trigger='interval',
            hours=interval_hours,
            id='iptscanner',
            replace_existing=True
        )
        app.logger.info(f"IPTScanner scheduled to run every {interval_hours} hours")
    except Exception as e:
        app.logger.error(f"Error initializing scheduler: {str(e)}")

def run_ipt_scanner(config=None):
    """Fetch the latest results from Prowlarr and store them for later viewing."""
    try:
        cfg = config or _load_ipt_config()
        results = _fetch_prowlarr_results(cfg)

        storage_dir = _iptscanner_storage_dir()
        data_dir = os.path.join(storage_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        app_data_path = os.path.join(data_dir, 'torrents.json')

        with open(app_data_path, 'w') as handle:
            json.dump(results, handle, indent=2)

        cfg['lastUpdateTime'] = datetime.now().isoformat()
        _save_ipt_config(cfg)
        _set_prowlarr_status('connected', f"Cached {len(results)} results")
        return results
    except ValueError as exc:
        app.logger.error(f"Prowlarr configuration error: {exc}")
        return False
    except requests.RequestException as exc:
        app.logger.error(f"Error fetching results from Prowlarr: {exc}")
        return False
    except Exception as exc:
        app.logger.error(f"Error in run_ipt_scanner: {exc}")
        return False


# ---------------------------------------------------------------------------
# Basic HTML views
# ---------------------------------------------------------------------------

@app.route('/dashboard')
def dashboard():
    # Refresh connection statuses so the UI reflects the latest state each visit.
    try:
        check_plex_connection()
    except Exception as exc:  # pragma: no cover - defensive logging
        app.logger.debug(f"Plex status refresh failed: {exc}")

    ipt_config = _load_ipt_config()
    recent_ipt_entries = _load_recent_ipt_results(ipt_config, limit=50)

    try:
        new_24h, last_check_dt, next_check_dt = _summarize_ipt_activity(ipt_config, recent_ipt_entries)
        cookies_cfg = ipt_config.get('cookies', {})
        if cookies_cfg.get('uid'):
            if last_check_dt:
                parts = [f"Last: {_format_human_datetime(last_check_dt)}"]
                if next_check_dt:
                    parts.append(f"Next: {_format_human_datetime(next_check_dt)}")
                parts.append(f"{new_24h} new / 24h")
                _set_iptorrents_status('connected', ' | '.join(parts))
            else:
                _set_iptorrents_status('connected', f"{new_24h} new / 24h | Awaiting first check")
        else:
            _set_iptorrents_status('disconnected', 'Cookies not configured')
    except Exception as exc:  # pragma: no cover
        app.logger.debug(f"IPT status refresh failed: {exc}")

    with state.lock:
        scan_results = dict(state.scan_results)
        connection_status = dict(state.connection_status)
        is_scanning = state.is_scanning
        monitor_active = state.monitor_active
        last_scan_time = state.last_scan_time
        next_scan_time = state.next_scan_time

    last_scan_results = app.config.get('LAST_SCAN_RESULTS', {
        'total': 0,
        'dv_count': 0,
        'p7_count': 0,
        'atmos_count': 0
    })

    recent_reports = _list_reports(limit=5)
    recent_ipt = recent_ipt_entries[:10]

    return render_template(
        'dashboard.html',
        active_page='dashboard',
        scan_results=scan_results,
        last_scan_results=last_scan_results,
        connection_status=connection_status,
        is_scanning=is_scanning,
        monitor_active=monitor_active,
        last_scan_time=last_scan_time,
        next_scan_time=next_scan_time,
        plex_url=app.config.get('PLEX_URL', ''),
        library_name=app.config.get('LIBRARY_NAME', ''),
        recent_reports=recent_reports,
        ipt_results=recent_ipt,
        setup_completed=app.config.get('SETUP_COMPLETED', False)
    )


@app.route('/reports')
def reports_page():
    reports = _list_reports()
    return render_template(
        'reports.html',
        active_page='reports',
        reports=reports,
        reports_dir=app.config.get('REPORTS_FOLDER_PATH', EXPORTS_DIR)
    )


@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        form = request.form
        action = form.get('action', 'save')
        plex_url_input = form.get('plex_url', '').strip()
        plex_token_input = form.get('plex_token', '').strip()
        library_name_input = form.get('library_name', '').strip()

        if action == 'test-plex':
            plex_url_to_test = plex_url_input or app.config.get('PLEX_URL', '')
            plex_token_to_test = plex_token_input or app.config.get('PLEX_TOKEN', '')
            library_name_to_test = library_name_input or app.config.get('LIBRARY_NAME', '')

            if not plex_url_to_test or not plex_token_to_test or not library_name_to_test:
                flash('Provide Plex URL, token, and library name before testing.', 'error')
                return redirect(url_for('settings_page'))

            try:
                movie_count = _test_plex_settings(plex_url_to_test, plex_token_to_test, library_name_to_test)
                flash(f'Success! Connected to Plex and found {movie_count} movies.', 'success')

                # Optimistically apply the tested credentials so the dashboard can use them immediately.
                updated = False
                if plex_url_input:
                    app.config['PLEX_URL'] = plex_url_to_test
                    updated = True
                if plex_token_input:
                    app.config['PLEX_TOKEN'] = plex_token_to_test
                    updated = True
                if library_name_input:
                    app.config['LIBRARY_NAME'] = library_name_to_test
                    updated = True

                if updated:
                    # Mark setup as completed if the user just provided all core fields.
                    if plex_url_input and plex_token_input and library_name_input:
                        app.config['SETUP_COMPLETED'] = True

                    if not save_settings():
                        app.logger.warning("Test connection succeeded but saving settings failed.")
                        flash('Unable to persist the tested settings. Please use Save Settings to try again.', 'error')

            except ValueError as exc:
                flash(str(exc), 'error')
            except requests_exceptions.SSLError as exc:
                flash(f'SSL error: {exc}', 'error')
            except Exception as exc:
                flash(f'Failed to connect to Plex: {exc}', 'error')

            return redirect(url_for('settings_page'))

        plex_url = plex_url_input
        plex_token = plex_token_input
        library_name = library_name_input

        if plex_url:
            try:
                plex_url = _validate_and_normalize_plex_url(plex_url)
            except ValueError as exc:
                flash(str(exc), 'error')
                return redirect(url_for('settings_page'))

        scan_frequency = form.get('scan_frequency', '').strip()
        try:
            scan_frequency_value = int(scan_frequency) if scan_frequency else 24
        except ValueError:
            flash('Scan frequency must be a number (hours).', 'error')
            return redirect(url_for('settings_page'))

        app.config['PLEX_URL'] = plex_url
        app.config['PLEX_TOKEN'] = plex_token
        app.config['LIBRARY_NAME'] = library_name
        app.config['COLLECTION_NAME_ALL_DV'] = form.get('collection_name_all_dv', '').strip() or 'All Dolby Vision'
        app.config['COLLECTION_NAME_PROFILE7'] = form.get('collection_name_profile7', '').strip() or 'DV FEL Profile 7'
        app.config['COLLECTION_NAME_TRUEHD_ATMOS'] = form.get('collection_name_truehd_atmos', '').strip() or 'TrueHD Atmos'
        app.config['COLLECTION_ENABLE_DV'] = 'collection_enable_dv' in form
        app.config['COLLECTION_ENABLE_P7'] = 'collection_enable_p7' in form
        app.config['COLLECTION_ENABLE_ATMOS'] = 'collection_enable_atmos' in form
        app.config['SCAN_FREQUENCY'] = scan_frequency_value
        app.config['AUTO_START_MODE'] = form.get('auto_start', 'none')
        try:
            max_reports = int(form.get('max_reports_size', app.config.get('MAX_REPORTS_SIZE', 5)) or 5)
        except ValueError:
            flash('Max reports size must be a number.', 'error')
            return redirect(url_for('settings_page'))
        app.config['MAX_REPORTS_SIZE'] = max_reports
        app.config['USE_WHOLE_NUMBERS'] = 'use_whole_numbers' in form
        app.config['TELEGRAM_ENABLED'] = 'telegram_enabled' in form
        app.config['TELEGRAM_TOKEN'] = form.get('telegram_token', '').strip() if app.config['TELEGRAM_ENABLED'] else ''
        app.config['TELEGRAM_CHAT_ID'] = form.get('telegram_chat_id', '').strip() if app.config['TELEGRAM_ENABLED'] else ''
        app.config['TELEGRAM_NOTIFY_ALL_UPDATES'] = 'telegram_notify_all_updates' in form
        app.config['TELEGRAM_NOTIFY_NEW_MOVIES'] = 'telegram_notify_new_movies' in form
        app.config['TELEGRAM_NOTIFY_DV'] = 'telegram_notify_dv' in form
        app.config['TELEGRAM_NOTIFY_P7'] = 'telegram_notify_p7' in form
        app.config['TELEGRAM_NOTIFY_ATMOS'] = 'telegram_notify_atmos' in form
        app.config['SETUP_COMPLETED'] = 'setup_completed' in form

        if save_settings():
            flash('Settings saved successfully.', 'success')
        else:
            flash('Failed to save settings.', 'error')

        return redirect(url_for('settings_page'))

    settings = {
        'plex_url': app.config.get('PLEX_URL', ''),
        'plex_token': app.config.get('PLEX_TOKEN', ''),
        'library_name': app.config.get('LIBRARY_NAME', ''),
        'collection_name_all_dv': app.config.get('COLLECTION_NAME_ALL_DV', 'All Dolby Vision'),
        'collection_name_profile7': app.config.get('COLLECTION_NAME_PROFILE7', 'DV FEL Profile 7'),
        'collection_name_truehd_atmos': app.config.get('COLLECTION_NAME_TRUEHD_ATMOS', 'TrueHD Atmos'),
        'collection_enable_dv': app.config.get('COLLECTION_ENABLE_DV', True),
        'collection_enable_p7': app.config.get('COLLECTION_ENABLE_P7', True),
        'collection_enable_atmos': app.config.get('COLLECTION_ENABLE_ATMOS', True),
        'scan_frequency': app.config.get('SCAN_FREQUENCY', 24),
        'auto_start': app.config.get('AUTO_START_MODE', 'none'),
        'max_reports_size': app.config.get('MAX_REPORTS_SIZE', 5),
        'use_whole_numbers': app.config.get('USE_WHOLE_NUMBERS', True),
        'telegram_enabled': app.config.get('TELEGRAM_ENABLED', False),
        'telegram_token': app.config.get('TELEGRAM_TOKEN', ''),
        'telegram_chat_id': app.config.get('TELEGRAM_CHAT_ID', ''),
        'telegram_notify_all_updates': app.config.get('TELEGRAM_NOTIFY_ALL_UPDATES', False),
        'telegram_notify_new_movies': app.config.get('TELEGRAM_NOTIFY_NEW_MOVIES', True),
        'telegram_notify_dv': app.config.get('TELEGRAM_NOTIFY_DV', True),
        'telegram_notify_p7': app.config.get('TELEGRAM_NOTIFY_P7', True),
        'telegram_notify_atmos': app.config.get('TELEGRAM_NOTIFY_ATMOS', True),
        'setup_completed': app.config.get('SETUP_COMPLETED', False)
    }

    return render_template('settings.html', active_page='settings', settings=settings)


@app.route('/iptscanner', methods=['GET', 'POST'])
def iptscanner_page():
    config = _load_ipt_config()
    prowlarr_cfg = config.setdefault('prowlarr', {
        'baseUrl': 'http://10.0.0.11:9696',
        'apiKey': '',
        'indexerId': 1
    })

    if request.method == 'POST':
        form = request.form
        action = form.get('action', 'save').lower()

        if action == 'test-login':
            base_url_input = form.get('prowlarr_url', '').strip()
            api_key_input = form.get('prowlarr_api_key', '').strip()
            indexer_input = form.get('prowlarr_indexer_id', '').strip()

            base_url = base_url_input or prowlarr_cfg.get('baseUrl', '')
            api_key = api_key_input or prowlarr_cfg.get('apiKey', '')
            try:
                indexer_id = int(indexer_input) if indexer_input else int(prowlarr_cfg.get('indexerId', 0) or 0)
            except ValueError:
                flash('Indexer ID must be a number.', 'error')
                return redirect(url_for('iptscanner_page'))

            success, message = _perform_ipt_login_test(base_url, api_key, indexer_id)
            flash(message, 'success' if success else 'error')

            if base_url_input:
                prowlarr_cfg['baseUrl'] = base_url_input
            if api_key_input:
                prowlarr_cfg['apiKey'] = api_key_input
            if indexer_input:
                prowlarr_cfg['indexerId'] = indexer_id

            _save_ipt_config(config)
            if success:
                schedule_ipt_scanner(config)

            return redirect(url_for('iptscanner_page'))

        base_url_val = form.get('prowlarr_url', '').strip()
        api_key_val = form.get('prowlarr_api_key', '').strip()
        indexer_val = form.get('prowlarr_indexer_id', '').strip()

        prowlarr_cfg['baseUrl'] = base_url_val
        prowlarr_cfg['apiKey'] = api_key_val

        if indexer_val:
            try:
                prowlarr_cfg['indexerId'] = int(indexer_val)
            except ValueError:
                flash('Indexer ID must be a number.', 'error')
                return redirect(url_for('iptscanner_page'))

        search_term = form.get('search_term', '').strip()
        if search_term:
            config['searchTerm'] = search_term

        interval = form.get('check_interval', '').strip()
        if interval:
            config['checkInterval'] = interval

        saved = _save_ipt_config(config)
        if saved:
            schedule_ipt_scanner(config)
        flash(
            'IPT scanner settings saved.' if saved else 'Failed to save IPT scanner settings.',
            'success' if saved else 'error'
        )
        return redirect(url_for('iptscanner_page'))

    ipt_settings = {
        'prowlarr_url': prowlarr_cfg.get('baseUrl', ''),
        'prowlarr_api_key': prowlarr_cfg.get('apiKey', ''),
        'prowlarr_indexer_id': prowlarr_cfg.get('indexerId', 1),
        'search_term': config.get('searchTerm', ''),
        'check_interval': config.get('checkInterval', '0 */2 * * *'),
        'last_update_time': config.get('lastUpdateTime')
    }

    return render_template(
        'iptscanner.html',
        active_page='iptscanner',
        settings=ipt_settings
    )


@app.post('/actions/scan')
def start_scan_action():
    operation = request.form.get('operation', 'scan')
    success, message = _trigger_scan_operation(operation)
    if success:
        verb = 'Scan' if operation == 'scan' else 'Verification'
        flash(f'{verb} started.', 'success')
    else:
        flash(message or 'Failed to start the requested operation.', 'error')
    return redirect(url_for('dashboard'))


@app.post('/actions/monitor')
def monitor_action():
    action = request.form.get('action', 'start')
    success, message = _toggle_monitor_action(action)
    if success:
        if action == 'start':
            flash('Monitor mode started.', 'success')
        else:
            flash('Monitor mode stopped.', 'success')
    else:
        flash(message or 'Failed to update monitor mode.', 'error')
    return redirect(url_for('dashboard'))

def init_iptscanner():
    """Initialize the IPT scanner components at startup"""
    try:
        app.logger.info("Initializing IPT scanner...")
        config = _load_ipt_config()
        _save_ipt_config(config)
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

# Ensure the IPT scanner is ready both for direct execution and WSGI imports
init_iptscanner()

@app.route('/api/iptscanner/test-run', methods=['POST'])
def test_run_iptscanner():
    """Test run the IPT scanner"""
    try:
        app.logger.info("Manual test run of Prowlarr scanner triggered")
        results = run_ipt_scanner()
        if results:
            return jsonify({'success': True, 'count': len(results)})
        return jsonify({'success': False, 'error': 'Unable to fetch results from Prowlarr'}), 500
    except Exception as e:
        app.logger.error(f"Error in test_run_iptscanner: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == "__main__":
    # Start the app
    app.run(host='0.0.0.0', port=5000, debug=True)
