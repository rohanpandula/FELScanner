import os
import time
import logging
import csv
import json
import sqlite3
import asyncio
import aiohttp
import threading
from lxml import etree
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, Any, Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from plexapi.server import PlexServer

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger()

class MovieDatabase:
    """Database for storing movie metadata"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._setup_db()
        
    def _setup_db(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Create movies table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                rating_key TEXT PRIMARY KEY,
                title TEXT,
                dv_profile TEXT,
                dv_fel INTEGER,
                has_atmos INTEGER,
                last_updated TEXT,
                extra_data TEXT
            )
            ''')

            # Create indices for faster lookups
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_title ON movies (title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_dv_profile ON movies (dv_profile)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_dv_fel ON movies (dv_fel)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_has_atmos ON movies (has_atmos)')

            # Create pending downloads table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_downloads (
                request_id TEXT PRIMARY KEY,
                movie_title TEXT,
                year INTEGER,
                torrent_url TEXT,
                target_folder TEXT,
                quality_type TEXT,
                status TEXT,
                telegram_message_id INTEGER,
                download_data TEXT,
                created_at TEXT,
                expires_at TEXT,
                approved_at TEXT,
                completed_at TEXT
            )
            ''')

            # Create download history table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                movie_title TEXT,
                quality_type TEXT,
                torrent_hash TEXT,
                status TEXT,
                started_at TEXT,
                completed_at TEXT
            )
            ''')

            # Create indices for downloads
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_downloads (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_created ON pending_downloads (created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_movie ON download_history (movie_title)')

            conn.commit()
    
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def update_movie(self, rating_key: str, title: str, dv_profile: Optional[str], 
                    dv_fel: bool, has_atmos: bool, extra_data: Optional[Dict] = None):
        """Update or insert movie metadata"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            extra_data_json = json.dumps(extra_data) if extra_data else None
            
            # Use datetime with microsecond precision for better sorting and granularity
            # While the UI will display a friendly format, this allows precise ordering
            timestamp = datetime.now().isoformat(timespec='microseconds')
            
            cursor.execute('''
            INSERT INTO movies (rating_key, title, dv_profile, dv_fel, has_atmos, last_updated, extra_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rating_key) DO UPDATE SET
                title = excluded.title,
                dv_profile = excluded.dv_profile,
                dv_fel = excluded.dv_fel,
                has_atmos = excluded.has_atmos,
                last_updated = excluded.last_updated,
                extra_data = excluded.extra_data
            ''', (rating_key, title, dv_profile, 1 if dv_fel else 0, 
                 1 if has_atmos else 0, timestamp, extra_data_json))
            conn.commit()
    
    def get_dv_movies(self):
        """Get all Dolby Vision movies"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT * FROM movies 
            WHERE dv_profile IS NOT NULL AND dv_profile != 'None'
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_p7_fel_movies(self):
        """Get all Profile 7 FEL movies"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT * FROM movies 
            WHERE dv_profile = '7' AND dv_fel = 1
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_atmos_movies(self):
        """Get all TrueHD Atmos movies"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT * FROM movies
            WHERE has_atmos = 1
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # Download management methods
    def store_pending_download(self, request_id: str, download_data: Dict):
        """Store pending download request"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO pending_downloads (
                request_id, movie_title, year, torrent_url, target_folder,
                quality_type, status, download_data, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request_id,
                download_data.get('movie_title'),
                download_data.get('year'),
                download_data.get('torrent_url'),
                download_data.get('target_folder'),
                download_data.get('quality_type'),
                'pending',
                json.dumps(download_data),
                download_data.get('created_at', datetime.now().isoformat())
            ))
            conn.commit()

    def get_pending_download(self, request_id: str) -> Optional[Dict]:
        """Get pending download by request ID"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT download_data FROM pending_downloads
            WHERE request_id = ?
            ''', (request_id,))
            result = cursor.fetchone()
            if result and result['download_data']:
                try:
                    return json.loads(result['download_data'])
                except:
                    pass
            return None

    def get_all_pending_downloads(self):
        """Get all pending downloads"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT * FROM pending_downloads
            WHERE status = 'pending'
            ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def mark_download_started(self, request_id: str, torrent_hash: Optional[str]):
        """Mark download as started"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Update pending download
            cursor.execute('''
            UPDATE pending_downloads
            SET status = 'downloading', approved_at = ?
            WHERE request_id = ?
            ''', (datetime.now().isoformat(), request_id))

            # Add to history
            pending = self.get_pending_download(request_id)
            if pending:
                cursor.execute('''
                INSERT INTO download_history (
                    request_id, movie_title, quality_type, torrent_hash, status, started_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    request_id,
                    pending.get('movie_title'),
                    pending.get('quality_type'),
                    torrent_hash,
                    'downloading',
                    datetime.now().isoformat()
                ))

            conn.commit()

    def mark_download_completed(self, request_id: str):
        """Mark download as completed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            cursor.execute('''
            UPDATE pending_downloads
            SET status = 'completed', completed_at = ?
            WHERE request_id = ?
            ''', (now, request_id))

            cursor.execute('''
            UPDATE download_history
            SET status = 'completed', completed_at = ?
            WHERE request_id = ?
            ''', (now, request_id))

            conn.commit()

    def delete_pending_download(self, request_id: str):
        """Delete pending download (after decline or expiry)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM pending_downloads WHERE request_id = ?', (request_id,))
            conn.commit()

    def get_download_history(self, limit: int = 50):
        """Get recent download history"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
            SELECT * FROM download_history
            ORDER BY started_at DESC
            LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]


class PlexDVScanner:
    """Improved scanner for Dolby Vision content in Plex"""
    
    def __init__(self, plex_url: str, plex_token: str, library_name: str,
                 collection_name_all_dv: str, collection_name_profile7: str,
                 collection_name_truehd_atmos: str, reports_folder_path: str):
        
        self.plex_url = plex_url
        self.plex_token = plex_token
        self.library_name = library_name
        self.collection_name_all_dv = collection_name_all_dv
        self.collection_name_profile7 = collection_name_profile7
        self.collection_name_truehd_atmos = collection_name_truehd_atmos
        self.reports_folder_path = reports_folder_path
        
        # Setup database
        os.makedirs(reports_folder_path, exist_ok=True)
        db_path = os.path.join(reports_folder_path, 'movie_database.db')
        self.db = MovieDatabase(db_path)
        
        # Setup Plex connection
        self.plex = PlexServer(plex_url, plex_token)
        self.movies_section = self.plex.library.section(library_name)
        
        # Session will be created on demand
        self.session = None
        self._session_lock = threading.Lock()
        self._is_closing = False
        
        # Progress callback
        self.progress_callback = None
        
        # Batch processing settings
        self.batch_size = 50
        
        # Worker pools
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
    
    async def _ensure_session(self):
        """Ensure HTTP session exists, creating it if needed"""
        if self._is_closing:
            raise RuntimeError("Scanner is shutting down")
            
        if not self.session:
            # Use a lock to prevent multiple threads from creating sessions simultaneously
            with self._session_lock:
                if not self.session:  # Double-check after acquiring lock
                    try:
                        # Verify that we have a running event loop
                        loop = asyncio.get_running_loop()
                        
                        connector = aiohttp.TCPConnector(
                            limit=20,           # Max connections overall
                            limit_per_host=10,  # Max connections per host
                            ttl_dns_cache=300,  # DNS cache TTL (5 minutes)
                            keepalive_timeout=60,  # Keep-alive timeout
                        )
                        
                        # Create an aiohttp session with the connector
                        self.session = aiohttp.ClientSession(
                            connector=connector,
                            headers={
                                'X-Plex-Token': self.plex_token,
                                'Accept': 'application/xml'
                            }
                        )
                    except RuntimeError as e:
                        # If there's no running event loop, report the error clearly
                        raise RuntimeError(f"No running event loop available to create HTTP session: {e}")
    
    async def close(self):
        """Close resources"""
        self._is_closing = True
        
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                log.error(f"Error closing session: {e}")
            finally:
                self.session = None
        
        if hasattr(self, 'thread_pool') and self.thread_pool:
            self.thread_pool.shutdown(wait=True)
    
    def set_progress_callback(self, callback_fn):
        """Set callback for progress updates"""
        self.progress_callback = callback_fn
    
    async def _batch_fetch_metadata(self, rating_keys: List[str]) -> List[str]:
        """Fetch metadata for a batch of movies in parallel"""
        if not rating_keys:
            return []
            
        # Process in smaller batches to avoid overwhelming the server
        results = []
        
        for i in range(0, len(rating_keys), self.batch_size):
            batch = rating_keys[i:i+self.batch_size]
            tasks = []
            
            for rating_key in batch:
                url = f"{self.plex_url}/library/metadata/{rating_key}"
                tasks.append(self._fetch_metadata_for_movie(url))
            
            try:    
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                # Filter out exceptions and None results
                valid_results = []
                for result in batch_results:
                    if isinstance(result, Exception):
                        log.error(f"Error in batch fetch: {result}")
                    elif result is not None:
                        valid_results.append(result)
                        
                results.extend(valid_results)
            except asyncio.CancelledError:
                log.warning("Batch fetch operation was cancelled")
                break
            except Exception as e:
                log.error(f"Error in batch fetch: {e}")
                
        return results
    
    async def _fetch_metadata_for_movie(self, url: str) -> Optional[str]:
        """Fetch metadata for a single movie"""
        if self._is_closing:
            return None
            
        try:
            await self._ensure_session()
            
            # Check again if we're closing after ensuring session (could have changed)
            if self._is_closing or not self.session:
                return None
                
            try:
                async with self.session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        log.warning(f"Failed to fetch metadata from {url}: {response.status}")
                        return None
            except asyncio.CancelledError:
                log.warning(f"Fetch operation for {url} was cancelled")
                return None
            except aiohttp.ClientError as e:
                log.error(f"HTTP client error fetching metadata from {url}: {e}")
                return None
            except Exception as e:
                log.error(f"Error fetching metadata from {url}: {e}")
                return None
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                log.error(f"Event loop is closed while trying to fetch {url}")
            elif "No running event loop" in str(e):
                log.error(f"No running event loop available for {url}")
            else:
                log.error(f"Runtime error fetching metadata from {url}: {e}")
            return None
        except Exception as e:
            log.error(f"Unexpected error fetching metadata from {url}: {e}")
            return None
    
    def _parse_xml_batch(self, xml_contents: List[str]) -> Generator[Tuple[str, Dict], None, None]:
        """Parse a batch of XML metadata for movies"""
        for xml_content in xml_contents:
            if not xml_content:
                continue
                
            try:
                root = etree.fromstring(xml_content.encode('utf-8'))
                
                # Find video elements
                for video in root.xpath('//Video'):
                    rating_key = video.get('ratingKey')
                    movie_title = video.get('title')
                    
                    # Enhanced year extraction from multiple possible locations
                    # Try the main year attribute first, then specific Release year, then originallyAvailableAt
                    year = video.get('year') 
                    if not year and video.xpath('.//Release/@year'):
                        year = video.xpath('.//Release/@year')[0]
                    if not year and video.get('originallyAvailableAt'):
                        try:
                            # Extract year from date format YYYY-MM-DD
                            year = video.get('originallyAvailableAt').split('-')[0]
                        except:
                            pass
                    
                    if not rating_key or not movie_title:
                        continue
                    
                    # Enhanced file size extraction from first valid Part element
                    file_size = None
                    for part in video.xpath('.//Part'):
                        if part.get('size'):
                            file_size = int(part.get('size'))
                            break
                    
                    # Extract video bitrate from the first video stream
                    video_bitrate = None
                    video_bitrate_raw = None
                    video_streams = video.xpath('.//Stream[@streamType="1"]')
                    if video_streams:
                        bitrate_attr = video_streams[0].get('bitrate')
                        if bitrate_attr and bitrate_attr.isdigit():
                            video_bitrate_raw = float(bitrate_attr) / 1000  # Convert to Mbps
                            # Store both raw and formatted versions
                            video_bitrate = f"{video_bitrate_raw:.1f} Mbps" 
                    
                    # Extract audio track details
                    audio_details = []
                    for stream in video.xpath('.//Stream[@streamType="2"]'):  # Audio streams
                        codec = stream.get("codec", "").upper()
                        channels = stream.get("channels", "")
                        layout = stream.get("audioChannelLayout", "").replace("(", "").replace(")", "")
                        audio_title = (stream.get("title", "") or "").lower()

                        # Detect Atmos/DTS-MA formats
                        format_tag = ""
                        if "truehd" in codec.lower() and "atmos" in audio_title:
                            format_tag = "Atmos"
                        elif codec == "DCA" and "ma" in audio_title:
                            format_tag = "DTS-HD MA"
                        elif codec == "AC3":
                            format_tag = f"AC3 {channels}.1" if channels else "AC3"
                        
                        audio_details.append(f"{codec} {format_tag}".strip())
                        
                    media_info = {
                        'title': movie_title,
                        'year': year,
                        'dv_profile': None,
                        'dv_fel': False,
                        'has_atmos': False,
                        'file_size': file_size,
                        'video_bitrate': video_bitrate,
                        'video_bitrate_raw': video_bitrate_raw,
                        'audio_tracks': ", ".join(audio_details) if audio_details else "Unknown"
                    }
                    
                    # Direct check for Profile 7 FEL streams (most efficient)
                    dv_p7_fel_streams = video.xpath(
                        './/Stream[@streamType="1"][@DOVIProfile="7"]'
                        '[@DOVIELPresent="1"][@DOVIBLPresent="1"]'
                    )
                    
                    if dv_p7_fel_streams:
                        media_info['dv_profile'] = '7'
                        media_info['dv_fel'] = True
                    else:
                        # Check for any Dolby Vision profile
                        dv_streams = video.xpath('.//Stream[@streamType="1"][@DOVIProfile]')
                        if dv_streams:
                            media_info['dv_profile'] = dv_streams[0].get('DOVIProfile')
                    
                    # Check for TrueHD Atmos
                    audio_streams = video.xpath('.//Stream[@streamType="2"][@codec="truehd"]')
                    for stream in audio_streams:
                        atmos_attrs = ['title', 'displayTitle', 'extendedDisplayTitle', 'audioChannelLayout']
                        if any('atmos' in (stream.get(attr, '') or '').lower() for attr in atmos_attrs):
                            media_info['has_atmos'] = True
                            break
                    
                    yield rating_key, media_info
            except Exception as e:
                log.error(f"Error parsing XML: {e}")
    
    async def scan_library_for_dv(self):
        """Scan library for Dolby Vision content using batch processing"""
        log.info(f"Scanning library '{self.library_name}' for DV content...")
        
        all_movies = self.movies_section.all()
        total = len(all_movies)

        # Create a mapping of rating keys to movie objects for later use
        movie_dict = {str(movie.ratingKey): movie for movie in all_movies}

        # Initialize lookup maps for later collection verification
        self.dv_movies_map: Dict[str, Dict] = {}
        self.fel_p7_movies_map: Dict[str, Dict] = {}
        self.atmos_movies_map: Dict[str, Dict] = {}
        
        # Get all rating keys for batch processing
        rating_keys = list(movie_dict.keys())
        
        # Process rating keys in larger batches for XML fetching
        processed = 0
        dv_movies, p7_fel_movies, atmos_movies = [], [], []
        
        for i in range(0, total, self.batch_size):
            if self._is_closing:
                log.info("Scan was interrupted due to shutdown")
                break
                
            batch_keys = rating_keys[i:i+self.batch_size]
            
            if self.progress_callback:
                processed += len(batch_keys)
                self.progress_callback(processed, total)
            
            # Fetch metadata for this batch
            xml_contents = await self._batch_fetch_metadata(batch_keys)
            
            # Parse all fetched XML content
            for rating_key, media_info in self._parse_xml_batch(xml_contents):
                # Update the database with new information
                movie = movie_dict.get(rating_key)
                if movie:
                    # Store extra data including file size
                    extra_data = {
                        'year': media_info.get('year'),
                        'file_size': media_info.get('file_size'),
                        'audio_tracks': media_info.get('audio_tracks'),
                        'video_bitrate': media_info.get('video_bitrate'),
                        'video_bitrate_raw': media_info.get('video_bitrate_raw'),
                        'dovi_profile': media_info.get('dv_profile')
                    }
                    
                    self.db.update_movie(
                        rating_key=rating_key,
                        title=movie.title,
                        dv_profile=media_info.get('dv_profile'),
                        dv_fel=media_info.get('dv_fel', False),
                        has_atmos=media_info.get('has_atmos', False),
                        extra_data=extra_data
                    )
                    
                    # Append to appropriate lists based on media info
                    if media_info.get('dv_profile'):
                        media_info['title'] = movie.title
                        dv_movies.append(media_info)
                        self.dv_movies_map[str(rating_key)] = media_info

                        if media_info.get('dv_profile') == '7' and media_info.get('dv_fel'):
                            p7_fel_movies.append(media_info)
                            self.fel_p7_movies_map[str(rating_key)] = media_info

                    if media_info.get('has_atmos'):
                        media_info['title'] = movie.title
                        atmos_movies.append(media_info)
                        self.atmos_movies_map[str(rating_key)] = media_info
        
        log.info(f"Found {len(dv_movies)} DV movies, {len(p7_fel_movies)} are Profile 7 FEL")
        log.info(f"Found {len(atmos_movies)} TrueHD Atmos movies")
        
        return dv_movies, p7_fel_movies, atmos_movies
    
    def create_json_output(self, dv_movies, atmos_movies=None, output_path=None, max_size_mb=5):
        """Create JSON output of scan results"""
        if not output_path:
            os.makedirs(self.reports_folder_path, exist_ok=True)
            output_path = os.path.join(
                self.reports_folder_path, 
                f"plex_dv_atmos_scan_{time.strftime('%Y%m%d_%H%M%S')}.json"
            )
            
        try:
            movie_data, dv_titles = [], set()
            
            # Process DV movies
            for movie in dv_movies:
                dv_titles.add(movie['title'])
                extra_data = movie.get('extra_data', {}) or {}
                movie_data.append({
                    'title': movie['title'],
                    'year': movie.get('year') or extra_data.get('year', ''),
                    'dv_profile': movie['dv_profile'],
                    'dv_fel': movie['dv_fel'],
                    'has_atmos': False,
                    'file_size': self._format_file_size(extra_data.get('file_size') or movie.get('file_size')),
                    'scan_date': datetime.now().isoformat()
                })
            
            # Process Atmos movies
            if atmos_movies:
                for movie in atmos_movies:
                    extra_data = movie.get('extra_data', {}) or {}
                    if movie['title'] in dv_titles:
                        for entry in movie_data:
                            if entry['title'] == movie['title']:
                                entry['has_atmos'] = True
                                break
                    else:
                        movie_data.append({
                            'title': movie['title'],
                            'year': movie.get('year') or extra_data.get('year', ''),
                            'dv_profile': None,
                            'dv_fel': False,
                            'has_atmos': True,
                            'file_size': self._format_file_size(extra_data.get('file_size') or movie.get('file_size')),
                            'scan_date': datetime.now().isoformat()
                        })
            
            report_data = {
                'scan_date': datetime.now().isoformat(),
                'library_name': self.library_name,
                'total_movies': len(self.movies_section.all()),
                'dv_count': len(dv_movies),
                'atmos_count': len(atmos_movies) if atmos_movies else 0,
                'movies': movie_data
            }
            
            # Write to file using context manager
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
                
            log.info(f"JSON output written to {output_path}")
            return output_path
        except Exception as e:
            log.error(f"Error writing JSON: {e}")
            return None

    def create_csv_output(self, dv_movies, atmos_movies=None, output_path=None, max_size_mb=5):
        """Create CSV output of scan results"""
        if not output_path:
            os.makedirs(self.reports_folder_path, exist_ok=True)
            output_path = os.path.join(
                self.reports_folder_path, 
                f"plex_dv_atmos_scan_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
        try:
            movie_dict = {}
            for movie in dv_movies:
                extra_data = movie.get('extra_data', {}) or {}
                movie_dict[movie['title']] = {
                    'dv_profile': movie['dv_profile'],
                    'dv_fel': movie['dv_fel'],
                    'has_atmos': False,
                    'year': movie.get('year') or extra_data.get('year', ''),
                    'file_size': extra_data.get('file_size') or movie.get('file_size')
                }
                
            if atmos_movies:
                for movie in atmos_movies:
                    extra_data = movie.get('extra_data', {}) or {}
                    if movie['title'] in movie_dict:
                        movie_dict[movie['title']]['has_atmos'] = True
                    else:
                        movie_dict[movie['title']] = {
                            'dv_profile': None,
                            'dv_fel': False,
                            'has_atmos': True,
                            'year': movie.get('year') or extra_data.get('year', ''),
                            'file_size': extra_data.get('file_size') or movie.get('file_size')
                        }
            
            # Use larger buffer for better performance
            buffer_size = min(8192, int(1024 * 1024 * 0.1))
            
            with open(output_path, 'w', newline='', encoding='utf-8', buffering=buffer_size) as f:
                writer = csv.writer(f, delimiter='|', quotechar='"')
                writer.writerow(["Title", "Year", "File Size", "DV Profile", "FEL", "TrueHD Atmos"])
                
                # Write in batches for better performance
                batch_size = 100
                rows, count = [], 0
                
                for title, info in movie_dict.items():
                    file_size_str = self._format_file_size(info.get('file_size')) if info.get('file_size') else "Unknown"
                    
                    rows.append([
                        title,
                        info.get('year', ''),
                        file_size_str,
                        info['dv_profile'] if info['dv_profile'] else "None",
                        "True" if info['dv_fel'] else "False",
                        "True" if info['has_atmos'] else "False"
                    ])
                    count += 1
                    
                    if count % batch_size == 0:
                        writer.writerows(rows)
                        rows = []
                        
                if rows:
                    writer.writerows(rows)
                    
            log.info(f"CSV output written to {output_path}")
            return output_path
        except Exception as e:
            log.error(f"Error writing CSV: {e}")
            return None
    
    def _format_file_size(self, size_bytes):
        """Format file size in a human-readable format"""
        if not size_bytes:
            return "Unknown"
            
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
            
        return f"{size_bytes:.2f} PB"
    
    async def update_add_to_collection(self, movies, coll_name):
        """Add movies to collection and return newly added items"""
        if not movies:
            return 0, []
            
        collection = None
        for c in self.movies_section.collections():
            if c.title == coll_name:
                collection = c
                break
                
        existing = set()
        if collection:
            for m in collection.items():
                existing.add(m.title)
                
        titles_to_add = [m['title'] for m in movies if m['title'] not in existing]
        if not titles_to_add:
            return 0, []
            
        # Get movie objects by title
        movie_dict = {m.title: m for m in self.movies_section.all()}
        to_add = [movie_dict[t] for t in titles_to_add if t in movie_dict]
        
        if not to_add:
            return 0, []
            
        newly_added = []
        for movie in to_add:
            # Get additional movie details if available
            additional_info = {}
            
            # Look up in our database for extra info
            with self.db.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT extra_data FROM movies WHERE title = ?", 
                    (movie.title,)
                )
                result = cursor.fetchone()
                if result and result['extra_data']:
                    try:
                        extra_data = json.loads(result['extra_data'])
                        additional_info.update(extra_data)
                    except:
                        pass
            
            newly_added.append({
                'title': movie.title,
                'collection': coll_name,
                'time': datetime.now().isoformat(),
                'year': movie.year if hasattr(movie, 'year') else additional_info.get('year'),
                'file_size': additional_info.get('file_size')
            })
            
        try:
            # Use ThreadPoolExecutor for this blocking operation
            if collection:
                await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    collection.addItems,
                    to_add
                )
            else:
                await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool,
                    lambda: self.movies_section.createCollection(title=coll_name, items=to_add)
                )
                
            log.info(f"Added {len(to_add)} movies to {coll_name}")
            return len(to_add), newly_added
        except Exception as e:
            log.error(f"Collection error: {e}")
            return 0, []

    async def _get_collection(self, collection_name: str):
        """Fetch a collection by name using a background thread to avoid blocking."""
        if not collection_name:
            return None

        loop = asyncio.get_running_loop()

        def fetch_collection():
            for collection in self.movies_section.collections():
                if collection.title == collection_name:
                    return collection
            return None

        return await loop.run_in_executor(self.thread_pool, fetch_collection)

    async def _remove_from_collection(self, movie, collection):
        """Remove an item from a Plex collection safely."""
        if not movie or not collection:
            return

        loop = asyncio.get_running_loop()

        def remove():
            try:
                movie.removeCollection(collection.title)
            except Exception:
                try:
                    collection.removeItems([movie])
                except Exception as e:
                    log.error(
                        f"Failed to remove {getattr(movie, 'title', 'Unknown')} from {collection.title}: {e}"
                    )

        await loop.run_in_executor(self.thread_pool, remove)

    def _get_movie_key(self, movie) -> Optional[str]:
        """Return the rating key for a Plex media item as a string."""
        if hasattr(movie, 'ratingKey') and movie.ratingKey is not None:
            return str(movie.ratingKey)
        if hasattr(movie, 'key') and movie.key is not None:
            return str(movie.key)
        return None
    
    async def verify_collections(self, return_removed_items=False, skip_collections=None):
        """
        Verify that all movies in collections actually have the traits they should.
        
        Args:
            return_removed_items (bool): Whether to return details of removed items
            skip_collections (list): List of collection names to skip verification
            
        Returns:
            (int, list): Total number of removed movies, and optionally a list of removed items
        """
        if skip_collections is None:
            skip_collections = []
        
        # First scan to get current state
        log.info("Verifying collection integrity with full DV checks...")
        await self.scan_library()
        
        total_removed = 0
        removed_items = []
        
        # Verify DV collection
        if self.collection_name_all_dv not in skip_collections:
            try:
                dv_collection = await self._get_collection(self.collection_name_all_dv)
                invalid_movies = []
                
                if dv_collection:
                    for movie in dv_collection.items():
                        movie_key = self._get_movie_key(movie)
                        if movie_key not in self.dv_movies_map:
                            invalid_movies.append(movie)
                            if return_removed_items:
                                removed_items.append({
                                    'title': movie.title,
                                    'year': getattr(movie, 'year', ''),
                                    'collection': self.collection_name_all_dv,
                                    'time': datetime.now().isoformat()
                                })
                
                    # Remove invalid movies
                    if invalid_movies:
                        for movie in invalid_movies:
                            await self._remove_from_collection(movie, dv_collection)
                        log.info(f"Removed {len(invalid_movies)} invalid movies from {self.collection_name_all_dv}")
                        total_removed += len(invalid_movies)
                    else:
                        log.info(f"No invalid movies found in {self.collection_name_all_dv}")
                else:
                    log.info(f"Collection {self.collection_name_all_dv} not found, skipping verification")
            except Exception as e:
                log.error(f"Error verifying {self.collection_name_all_dv}: {e}")
        else:
            log.info(f"Collection {self.collection_name_all_dv} is disabled, skipping verification")
        
        # Verify Profile 7 collection
        if self.collection_name_profile7 not in skip_collections:
            try:
                p7_collection = await self._get_collection(self.collection_name_profile7)
                invalid_movies = []
                
                if p7_collection:
                    for movie in p7_collection.items():
                        movie_key = self._get_movie_key(movie)
                        if movie_key not in self.fel_p7_movies_map:
                            invalid_movies.append(movie)
                            if return_removed_items:
                                removed_items.append({
                                    'title': movie.title,
                                    'year': getattr(movie, 'year', ''),
                                    'collection': self.collection_name_profile7,
                                    'time': datetime.now().isoformat()
                                })
                
                    # Remove invalid movies
                    if invalid_movies:
                        for movie in invalid_movies:
                            await self._remove_from_collection(movie, p7_collection)
                        log.info(f"Removed {len(invalid_movies)} invalid movies from {self.collection_name_profile7}")
                        total_removed += len(invalid_movies)
                    else:
                        log.info(f"No invalid movies found in {self.collection_name_profile7}")
                else:
                    log.info(f"Collection {self.collection_name_profile7} not found, skipping verification")
            except Exception as e:
                log.error(f"Error verifying {self.collection_name_profile7}: {e}")
        else:
            log.info(f"Collection {self.collection_name_profile7} is disabled, skipping verification")
        
        # Verify Atmos collection
        if self.collection_name_truehd_atmos not in skip_collections:
            try:
                atmos_collection = await self._get_collection(self.collection_name_truehd_atmos)
                invalid_movies = []
                
                if atmos_collection:
                    for movie in atmos_collection.items():
                        movie_key = self._get_movie_key(movie)
                        if movie_key not in self.atmos_movies_map:
                            invalid_movies.append(movie)
                            if return_removed_items:
                                removed_items.append({
                                    'title': movie.title,
                                    'year': getattr(movie, 'year', ''),
                                    'collection': self.collection_name_truehd_atmos,
                                    'time': datetime.now().isoformat()
                                })
                
                    # Remove invalid movies
                    if invalid_movies:
                        for movie in invalid_movies:
                            await self._remove_from_collection(movie, atmos_collection)
                        log.info(f"Removed {len(invalid_movies)} invalid movies from {self.collection_name_truehd_atmos}")
                        total_removed += len(invalid_movies)
                    else:
                        log.info(f"No invalid movies found in {self.collection_name_truehd_atmos}")
                else:
                    log.info(f"Collection {self.collection_name_truehd_atmos} not found, skipping verification")
            except Exception as e:
                log.error(f"Error verifying {self.collection_name_truehd_atmos}: {e}")
        else:
            log.info(f"Collection {self.collection_name_truehd_atmos} is disabled, skipping verification")
        
        if return_removed_items:
            return total_removed, removed_items
        return total_removed, None
    
    def get_stats(self):
        """Get library and collection statistics"""
        total = len(self.movies_section.all())
        all_dv_count, profile7_count, atmos_count = 0, 0, 0
        
        for c in self.movies_section.collections():
            if c.title == self.collection_name_all_dv:
                all_dv_count = len(c.items())
            elif c.title == self.collection_name_profile7:
                profile7_count = len(c.items())
            elif c.title == self.collection_name_truehd_atmos:
                atmos_count = len(c.items())
                
        return total, all_dv_count, profile7_count, atmos_count
    
    def get_p7_fel_movies(self):
        """Get all Profile 7 FEL movies"""
        return self.db.get_p7_fel_movies()
    
    # Unified scan API - always includes detailed P7/FEL checks
    async def scan_library(self):
        """Unified method for scanning library - always checks for DV Profile 7 FEL"""
        return await self.scan_library_for_dv()
