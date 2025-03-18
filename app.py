#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# FELScanner - A tool to scan Plex libraries for Dolby Vision movies and create collections
# Version: 1.1.0

import os
import sys
import logging
import threading
import json
import time
import re
from datetime import datetime
import random
import subprocess
import glob
from collections import defaultdict
import concurrent.futures
import psutil
from functools import lru_cache
import shutil
import math
import traceback
import socket
from datetime import timedelta
import asyncio
import uuid
import argparse

# Import the scanner module
from scanner import PlexDVScanner

import requests
from flask import Flask, render_template, request, jsonify, send_file
from plexapi.server import PlexServer
from plexapi.exceptions import NotFound
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# Import the Radarr API module
try:
    import radarr
except ImportError:
    print("Radarr module not found, will be imported later")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()

# Initialize Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')

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
    AUTO_START_MODE="none",  # Options: 'none', 'scan', 'monitor'
    SETUP_COMPLETED=False,
    MAX_REPORTS_SIZE=5,  # Maximum size in MB for the reports folder
    LAST_SCAN_RESULTS={
        'total': 0,
        'dv_count': 0,
        'p7_count': 0,
        'atmos_count': 0
    },
    TELEGRAM_ENABLED=os.environ.get('TELEGRAM_ENABLED', 'false').lower() == 'true',
    TELEGRAM_TOKEN=os.environ.get('TELEGRAM_TOKEN', ""),
    TELEGRAM_CHAT_ID=os.environ.get('TELEGRAM_CHAT_ID', ""),
    TELEGRAM_NOTIFY_ALL_UPDATES=False,
    TELEGRAM_NOTIFY_NEW_MOVIES=True,
    TELEGRAM_NOTIFY_DV=True,
    TELEGRAM_NOTIFY_P7=True,
    TELEGRAM_NOTIFY_ATMOS=True,
    # Radarr configuration
    RADARR_ENABLED=os.environ.get('RADARR_ENABLED', 'false').lower() == 'true',
    RADARR_URL=os.environ.get('RADARR_URL', ""),
    RADARR_API_KEY=os.environ.get('RADARR_API_KEY', "")
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
            'radarr': {'status': 'unknown', 'message': 'Not configured'},
            'server': {'status': 'connected', 'message': 'Web server running'}
        }
        self.lock = threading.RLock()  # For thread-safe state updates

# Create application state
state = AppState()

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
        # Skip check if telegram is disabled
        state.connection_status['telegram'] = {
            'status': 'disabled',
            'message': 'Telegram notifications are disabled'
        }
        return False
    
    try:
        api_url = f"https://api.telegram.org/bot{app.config['TELEGRAM_TOKEN']}/getMe"
        response = requests.get(api_url, timeout=10)
        bot_data = response.json()
        
        if bot_data.get('ok', False):
            state.connection_status['telegram'] = {
                'status': 'connected',
                'message': f"Connected to bot: @{bot_data['result']['username']}"
            }
            return True
        else:
            state.connection_status['telegram'] = {
                'status': 'error',
                'message': 'Invalid bot token'
            }
            return False
    except requests.exceptions.RequestException as e:
        state.connection_status['telegram'] = {
            'status': 'error',
            'message': f'Connection error: {str(e)}'
        }
        log.error(f"Telegram connection error: {e}")
        return False

# Check Radarr connection
def check_radarr_connection():
    if not app.config['RADARR_ENABLED']:
        # Skip check if Radarr is disabled
        state.connection_status['radarr'] = {
            'status': 'disabled',
            'message': 'Radarr integration is disabled'
        }
        return False
    
    try:
        # Configure the Radarr API with current settings
        import radarr
        radarr.set_config(app.config['RADARR_URL'], app.config['RADARR_API_KEY'])
        
        # Test the connection
        result = radarr.test_connection()
        
        if result['success']:
            state.connection_status['radarr'] = {
                'status': 'connected',
                'message': result['message']
            }
            return True
        else:
            state.connection_status['radarr'] = {
                'status': 'error',
                'message': result.get('error', 'Unknown error')
            }
            return False
    except Exception as e:
        state.connection_status['radarr'] = {
            'status': 'error',
            'message': f'Connection error: {str(e)}'
        }
        log.error(f"Radarr connection error: {e}")
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

@app.route('/api/test-radarr', methods=['POST'])
def test_radarr():
    try:
        data = request.json
        url = data.get('url')
        api_key = data.get('api_key')
        
        if not url or not api_key:
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Configure the Radarr API with the provided settings
        import radarr
        radarr.set_config(url, api_key)
        
        # Test the connection
        result = radarr.test_connection()
        
        # Return the result
        if result['success']:
            return jsonify({
                'success': True, 
                'version': result.get('version', 'Unknown'), 
                'message': result.get('message', 'Connected successfully')
            })
        else:
            return jsonify({
                'success': False, 
                'error': result.get('error', 'Failed to connect to Radarr')
            })
    except Exception as e:
        app.logger.error(f"Error testing Radarr connection: {str(e)}")
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
        
        # Get data directory
        data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
        cookies_file = os.path.join(data_dir, 'iptscanner', 'cookies.json')
        
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
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'config.json')
                if os.path.exists(config_path):
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
        
        # First check for torrents in the JS script's output directory
        js_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'known_torrents.json')
        
        # Directory for our app's data
        app_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'data')
        os.makedirs(app_data_dir, exist_ok=True)
        
        # Also check our app's data directory
        app_data_path = os.path.join(app_data_dir, 'torrents.json')
        
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'iptscanner', 'config.json')
        last_check = None
        search_term = "BL+EL+RPU"
        radarr_config = None
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                last_check = config.get('lastUpdateTime')
                search_term = config.get('iptorrents', {}).get('searchTerm', search_term)
                radarr_config = config.get('radarr', {})
                
                # If no lastUpdateTime in config, set it now
                if not last_check:
                    config['lastUpdateTime'] = datetime.now().isoformat()
                    last_check = config['lastUpdateTime']
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=4)
            except Exception as e:
                app.logger.error(f"Error reading config for torrents: {str(e)}")
        
        # Check both possible locations for the torrents data
        torrents = []
        
        # First try the JS output file
        if os.path.exists(js_data_path):
            try:
                with open(js_data_path, 'r') as f:
                    js_data = json.load(f)
                    if isinstance(js_data, list):
                        torrents = js_data
                    else:
                        # If it's just the known torrent IDs, we need to handle differently
                        torrents = []
                app.logger.info(f"Loaded {len(torrents)} torrents from JavaScript output file")
            except Exception as e:
                app.logger.error(f"Error reading JavaScript torrents file: {str(e)}")
        
        # If that fails, try our app's data directory
        if not torrents and os.path.exists(app_data_path):
            try:
                with open(app_data_path, 'r') as f:
                    torrents = json.load(f)
                app.logger.info(f"Loaded {len(torrents)} torrents from app data directory")
            except Exception as e:
                app.logger.error(f"Error reading app torrents file: {str(e)}")
        
        # If we still have no torrents, return empty list
        if not torrents:
            app.logger.warning("No torrents found in either location")
            return jsonify({
                "torrents": [],
                "lastCheck": last_check,
                "searchTerm": search_term
            })
        
        # Check if we have valid Radarr configuration and should add Radarr information
        radarr_enabled = radarr_config and radarr_config.get('enabled', False)
        radarr_url = radarr_config.get('url') if radarr_enabled else None
        radarr_api_key = radarr_config.get('apiKey') if radarr_enabled else None
        
        # Initialize Radarr API if enabled
        radarr_movies = None
        if radarr_enabled and radarr_url and radarr_api_key:
            try:
                import radarr
                radarr.set_config(radarr_url, radarr_api_key)
                # Get all movies from Radarr
                radarr_movies = radarr.get_movies()
                app.logger.info(f"Retrieved {len(radarr_movies) if radarr_movies else 0} movies from Radarr")
            except Exception as e:
                app.logger.error(f"Error connecting to Radarr: {str(e)}")
        
        # If torrents is a List, process and return it
        if isinstance(torrents, list):
            # Parse time strings to ensure correct sorting
            for torrent in torrents:
                # Get added text and convert to a timestamp for sorting
                added_text = torrent.get('added', '')
                
                # Set a default sort time if none exists
                if 'sortTime' not in torrent:
                    # Parse the time string
                    if 'min ago' in added_text:
                        mins = float(added_text.split(' ')[0])
                        torrent['sortTime'] = time.time() - (mins * 60)
                    elif 'hr ago' in added_text:
                        hours = float(added_text.split(' ')[0])
                        torrent['sortTime'] = time.time() - (hours * 3600)
                    elif 'day ago' in added_text:
                        days = float(added_text.split(' ')[0])
                        torrent['sortTime'] = time.time() - (days * 86400)
                    elif 'wk ago' in added_text:
                        weeks = float(added_text.split(' ')[0])
                        torrent['sortTime'] = time.time() - (weeks * 604800)
                    else:
                        torrent['sortTime'] = 0
                
                # Add Radarr information if we have movies loaded
                if radarr_movies:
                    torrent['radarrStatus'] = 'unknown'
                    torrent_title = torrent.get('title', '')
                    
                    # Try to extract title and year from the torrent name
                    movie_info = extract_movie_info(torrent_title)
                    if movie_info:
                        title, year = movie_info.get('title'), movie_info.get('year')
                        
                        if title and year:
                            # Search for the movie in Radarr by title and year
                            import radarr
                            radarr.set_config(radarr_url, radarr_api_key)
                            
                            movie = radarr.search_movie_by_title_year(title, year)
                            if movie:
                                # Movie found in Radarr
                                torrent['radarrStatus'] = 'found'
                                torrent['radarrInfo'] = {
                                    'id': movie.get('id'),
                                    'title': movie.get('title'),
                                    'year': movie.get('year'),
                                    'monitored': movie.get('monitored', False),
                                    'hasFile': movie.get('hasFile', False),
                                    'status': movie.get('status', 'unknown')
                                }
                            else:
                                # Movie not found in Radarr
                                torrent['radarrStatus'] = 'notFound'
                        else:
                            # Couldn't extract title and year
                            torrent['radarrStatus'] = 'parseError'
                    else:
                        # Couldn't extract title and year
                        torrent['radarrStatus'] = 'parseError'
            
            # Sort torrents by isNew and then by added date
            sorted_torrents = sorted(
                torrents, 
                key=lambda t: (0 if t.get('isNew', False) else 1, -(t.get('sortTime', 0) or 0)),
                reverse=False  # Don't reverse since we're using negative sortTime
            )
            
            return jsonify({
                "torrents": sorted_torrents,
                "lastCheck": last_check,
                "searchTerm": search_term,
                "radarrEnabled": radarr_enabled
            })
        
        # If we get here, the format is unexpected - just return it as-is
        app.logger.warning(f"Unexpected torrents format: {type(torrents)}")
        return jsonify({
            "torrents": torrents,
            "lastCheck": last_check,
            "searchTerm": search_term,
            "radarrEnabled": radarr_enabled
        })
    except Exception as e:
        app.logger.error(f"Error getting IPTScanner torrents: {str(e)}")
        return jsonify({"error": str(e)}), 500

def extract_movie_info(torrent_title):
    """
    Extract movie title and year from a torrent name
    
    Example formats:
    - Movie.Name.2020.2160p.BluRay.x265.10bit.HDR.DTS-HD.MA.TrueHD.7.1.Atmos-SWTYBLZ
    - Movie Name (2020) 2160p BluRay x265 10bit HDR DTS-HD MA TrueHD 7.1 Atmos-SWTYBLZ
    """
    try:
        # Pattern to match movie name followed by year in parentheses or dots
        pattern1 = r'(.+?)[\.\s]\(?(\d{4})\)?[\.\s]'
        pattern2 = r'(.+?)[\.\s]\[?(\d{4})\]?[\.\s]'
        
        match = re.search(pattern1, torrent_title)
        if not match:
            match = re.search(pattern2, torrent_title)
        
        if match:
            title = match.group(1).replace('.', ' ').strip()
            year = match.group(2)
            
            # Return structured data
            return {
                'title': title,
                'year': year
            }
        
        return None
    except Exception as e:
        app.logger.error(f"Error extracting movie info from '{torrent_title}': {str(e)}")
        return None

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
        
        # Return success with just the credentials saved
        return jsonify({'success': True, 'message': 'Credentials saved successfully'})
    except Exception as e:
        app.logger.error(f"Error in test_ipt_login: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/iptscanner/test-radarr', methods=['POST'])
def test_radarr_in_config():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        url = data.get('url')
        api_key = data.get('apiKey')
        
        if not url or not api_key:
            return jsonify({'success': False, 'error': 'URL and API key are required'}), 400
        
        # Configure the Radarr API with the provided settings
        import radarr
        radarr_api = radarr.radarr_api
        radarr_api.set_config(url, api_key)
        
        # Test the connection
        result = radarr_api.test_connection()
        
        # Update the config.json file with Radarr settings if successful
        if result['success']:
            try:
                # Get data directory from environment variable or use default
                data_dir = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
                iptscanner_dir = os.path.join(data_dir, 'iptscanner')
                config_path = os.path.join(iptscanner_dir, 'config.json')
                
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    
                    # Add or update Radarr configuration
                    if 'radarr' not in config:
                        config['radarr'] = {}
                    
                    config['radarr']['url'] = url
                    config['radarr']['apiKey'] = api_key
                    config['radarr']['enabled'] = True
                    
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=4)
                        app.logger.info("Updated config with Radarr settings")
            except Exception as e:
                app.logger.error(f"Error updating config with Radarr settings: {str(e)}")
                # Return success but mention config wasn't updated
                return jsonify({
                    'success': True, 
                    'version': result.get('version', 'Unknown'),
                    'message': result.get('message', 'Connected successfully'),
                    'config_updated': False,
                    'config_error': str(e)
                })
        
        # Return the result
        if result['success']:
            return jsonify({
                'success': True, 
                'version': result.get('version', 'Unknown'), 
                'message': result.get('message', 'Connected successfully'),
                'config_updated': True
            })
        else:
            return jsonify({
                'success': False, 
                'error': result.get('error', 'Failed to connect to Radarr')
            })
    except Exception as e:
        app.logger.error(f"Radarr test connection error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Start the Flask application when run directly
if __name__ == '__main__':
    import sys
    import traceback
    
    try:
        print("Starting Flask application...", file=sys.stderr)
        
        host = '0.0.0.0'
        port = 5000
        debug = True
        
        # Parse command line arguments
        if '--host' in sys.argv:
            idx = sys.argv.index('--host')
            if idx + 1 < len(sys.argv):
                host = sys.argv[idx + 1]
                print(f"Setting host to: {host}", file=sys.stderr)
        
        if '--port' in sys.argv:
            idx = sys.argv.index('--port')
            if idx + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[idx + 1])
                    print(f"Setting port to: {port}", file=sys.stderr)
                except ValueError:
                    print(f"Invalid port number: {sys.argv[idx + 1]}", file=sys.stderr)
        
        if '--debug' in sys.argv:
            debug = True
            print("Debug mode enabled", file=sys.stderr)
        elif '--no-debug' in sys.argv:
            debug = False
            print("Debug mode disabled", file=sys.stderr)
        
        print(f"Attempting to start Flask app with host={host}, port={port}, debug={debug}", file=sys.stderr)
        
        # Log flask version
        import flask
        print(f"Flask version: {flask.__version__}", file=sys.stderr)
        
        # Force flush stdout/stderr to ensure logs are written
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Start the Flask app
        app.run(host=host, port=port, debug=debug)
    except Exception as e:
        print(f"ERROR: Failed to start Flask application: {e}", file=sys.stderr)
        print("Traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)
