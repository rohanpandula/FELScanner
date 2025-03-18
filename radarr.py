#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import logging
import os
from urllib.parse import urljoin

# Set up logging
log = logging.getLogger('radarr')

class RadarrAPI:
    def __init__(self, url=None, api_key=None):
        self.url = url
        self.api_key = api_key
        self.timeout = 15  # Default timeout in seconds
    
    def set_config(self, url, api_key):
        """Update the Radarr configuration"""
        self.url = url
        self.api_key = api_key
    
    def get_config_from_env(self):
        """Get Radarr configuration from environment variables"""
        self.url = os.environ.get('RADARR_URL', self.url)
        self.api_key = os.environ.get('RADARR_API_KEY', self.api_key)
        return self.url and self.api_key
    
    def _make_request(self, endpoint, method='GET', params=None, data=None):
        """Make a request to the Radarr API"""
        if not self.url or not self.api_key:
            if not self.get_config_from_env():
                log.error('Radarr URL or API key not configured')
                return None
        
        # Ensure URL has trailing slash
        base_url = self.url if self.url.endswith('/') else f"{self.url}/"
        
        # Add API key to params
        if params is None:
            params = {}
        params['apikey'] = self.api_key
        
        try:
            url = urljoin(base_url, endpoint.lstrip('/'))
            log.debug(f"Making {method} request to Radarr: {url}")
            
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as e:
            log.error(f"Error communicating with Radarr: {str(e)}")
            return None
    
    def test_connection(self):
        """Test connection to Radarr"""
        try:
            result = self._make_request('/api/v3/system/status')
            if result:
                version = result.get('version', 'unknown')
                return {
                    'success': True, 
                    'message': f'Connected to Radarr v{version}',
                    'version': version
                }
            return {'success': False, 'error': 'Failed to connect to Radarr'}
        except Exception as e:
            log.exception("Error testing Radarr connection")
            return {'success': False, 'error': str(e)}
    
    def get_movies(self):
        """Get all movies from Radarr"""
        return self._make_request('/api/v3/movie')
    
    def search_movie_by_title_year(self, title, year):
        """Search for a movie by title and year (exact match)"""
        if not title or not year:
            return None
        
        # Clean up title and year for matching
        clean_title = title.lower().strip()
        year_str = str(year).strip()
        
        # Get all movies
        movies = self.get_movies()
        if not movies:
            return None
        
        # Try exact match first
        for movie in movies:
            movie_title = movie.get('title', '').lower().strip()
            movie_year = str(movie.get('year', '')).strip()
            
            if movie_title == clean_title and movie_year == year_str:
                return movie
        
        # Try fuzzy matching if exact match fails
        for movie in movies:
            movie_title = movie.get('title', '').lower().strip()
            movie_year = str(movie.get('year', '')).strip()
            
            # Match title approximately and year exactly
            if movie_year == year_str and (
                clean_title in movie_title or 
                movie_title in clean_title or
                self._title_similarity(clean_title, movie_title) > 0.8
            ):
                return movie
        
        return None
    
    def _title_similarity(self, title1, title2):
        """Calculate similarity between titles (simple implementation)"""
        # Remove common words that might cause false matches
        common_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']
        
        def clean(title):
            # Remove special characters and convert to lowercase
            t = re.sub(r'[^\w\s]', '', title.lower())
            # Remove common words
            return ' '.join([w for w in t.split() if w not in common_words])
        
        t1 = clean(title1)
        t2 = clean(title2)
        
        # If either is empty after cleaning, return 0
        if not t1 or not t2:
            return 0
            
        # Calculate similarity as proportion of shared words
        words1 = set(t1.split())
        words2 = set(t2.split())
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0
            
        return len(intersection) / len(union)
    
    def check_profile7(self, movie):
        """Check if a movie has Profile 7 Dolby Vision"""
        if not movie:
            return False
            
        # Check for file info if movie has been downloaded
        if not movie.get('hasFile', False):
            return False
            
        # Get movie file details
        movie_id = movie.get('id')
        if not movie_id:
            return False
            
        try:
            # Get movie file details
            movie_file = self._make_request(f'/api/v3/moviefile/{movie.get("movieFile", {}).get("id")}')
            
            if movie_file:
                # Check media info for DV profile
                media_info = movie_file.get('mediaInfo', {})
                
                # Look for Profile 7 indicators in videoProfiles
                video_profiles = media_info.get('videoProfiles', '')
                if 'dovi' in video_profiles.lower() or 'dolby vision' in video_profiles.lower():
                    # If it mentions Dolby Vision, check for Profile 7 specifically
                    if 'profile 7' in video_profiles.lower() or 'fel' in video_profiles.lower():
                        return True
                
                # Check in the video dynamic range
                video_dynamic_range = media_info.get('videoDynamicRange', '')
                if 'dovi' in video_dynamic_range.lower() and ('profile 7' in video_dynamic_range.lower() or 'fel' in video_dynamic_range.lower()):
                    return True
                    
                # Also check scene names or file path for profile 7 indicators
                if movie_file.get('relativePath'):
                    path = movie_file.get('relativePath').lower()
                    scene_name = os.path.basename(path).lower()
                    
                    p7_indicators = ['p7', 'profile7', 'profile 7', 'fel', 'p7.fel', 'fel.p7', 'dv.fel']
                    for indicator in p7_indicators:
                        if indicator in scene_name:
                            return True
        except Exception as e:
            log.error(f"Error checking Profile 7 status: {str(e)}")
        
        return False

    def lookup_movie(self, title, year):
        """Lookup a movie in Radarr TMDb database"""
        try:
            params = {'term': f'{title} {year}'}
            results = self._make_request('/api/v3/movie/lookup', params=params)
            if results:
                # Find closest match
                for result in results:
                    if result.get('title', '').lower() == title.lower() and str(result.get('year', '')) == str(year):
                        return result
                return results[0]  # Return first result if no exact match
            return None
        except Exception as e:
            log.error(f"Error looking up movie: {str(e)}")
            return None

# Create a singleton instance
radarr_api = RadarrAPI()

# Global functions that use the singleton instance
def set_config(url, api_key):
    """Update the Radarr configuration using the singleton instance"""
    radarr_api.set_config(url, api_key)

def test_connection():
    """Test connection to Radarr using the singleton instance"""
    return radarr_api.test_connection()

def get_movies():
    """Get all movies from Radarr using the singleton instance"""
    return radarr_api.get_movies()

def search_movie_by_title_year(title, year):
    """Search for a movie by title and year using the singleton instance"""
    return radarr_api.search_movie_by_title_year(title, year)

def check_profile7(movie):
    """Check if a movie has Profile 7 Dolby Vision using the singleton instance"""
    return radarr_api.check_profile7(movie)

def lookup_movie(title, year):
    """Lookup a movie in Radarr TMDb database using the singleton instance"""
    return radarr_api.lookup_movie(title, year) 