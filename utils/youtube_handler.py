import os
import re
import time
import logging
import json
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs
import yt_dlp


class YouTubeHandler:
    """Handles YouTube video download and audio extraction using yt-dlp."""
    
    # Supported YouTube URL patterns
    URL_PATTERNS = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?m\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    
    def __init__(self, config):
        """Initialize YouTube handler with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Download settings
        self.download_dir = getattr(config, 'YOUTUBE_DOWNLOAD_DIR', './temp/youtube')
        self.max_duration = getattr(config, 'YOUTUBE_MAX_DURATION', 3600)  # 1 hour default
        self.max_filesize = getattr(config, 'YOUTUBE_MAX_FILESIZE', 500 * 1024 * 1024)  # 500MB
        self.audio_format = getattr(config, 'YOUTUBE_AUDIO_FORMAT', 'wav')
        self.audio_quality = getattr(config, 'YOUTUBE_AUDIO_QUALITY', '192')
        
        # Rate limiting
        self.rate_limit = getattr(config, 'YOUTUBE_RATE_LIMIT', '1M')  # 1MB/s
        self.sleep_interval = getattr(config, 'YOUTUBE_SLEEP_INTERVAL', 1)
        
        # Create download directory
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Progress tracking
        self.download_progress = {}
        
        self.logger.info(f"YouTubeHandler initialized with download dir: {self.download_dir}")
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], str]:
        """
        Validate YouTube URL and extract video ID.
        
        Returns:
            (is_valid, video_id, message)
        """
        if not url:
            return False, None, "Empty URL provided"
        
        # Try to match URL patterns
        for pattern in self.URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                self.logger.info(f"Valid YouTube URL detected, video ID: {video_id}")
                return True, video_id, "Valid YouTube URL"
        
        # Check if it's just a video ID
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
            self.logger.info(f"Direct video ID provided: {url}")
            return True, url, "Valid video ID"
        
        return False, None, "Invalid YouTube URL format"
    
    def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Extract video metadata without downloading.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dict with video information
        """
        try:
            # Validate URL first
            is_valid, video_id, message = self.validate_url(url)
            if not is_valid:
                return {
                    'success': False,
                    'error': message,
                    'url': url
                }
            
            # Configure yt-dlp for info extraction only
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'logger': self.logger
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    
                    # Extract relevant metadata
                    metadata = {
                        'success': True,
                        'video_id': info.get('id', video_id),
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'duration_string': self._format_duration(info.get('duration', 0)),
                        'uploader': info.get('uploader', 'Unknown'),
                        'upload_date': info.get('upload_date', ''),
                        'view_count': info.get('view_count', 0),
                        'like_count': info.get('like_count', 0),
                        'description': info.get('description', '')[:500],  # First 500 chars
                        'thumbnail': info.get('thumbnail', ''),
                        'webpage_url': info.get('webpage_url', url),
                        'is_live': info.get('is_live', False),
                        'was_live': info.get('was_live', False),
                        'availability': info.get('availability', 'public'),
                        'age_limit': info.get('age_limit', 0),
                        'categories': info.get('categories', []),
                        'tags': info.get('tags', [])[:10],  # First 10 tags
                        'language': info.get('language', None),
                        'subtitles_available': len(info.get('subtitles', {})) > 0,
                        'automatic_captions_available': len(info.get('automatic_captions', {})) > 0
                    }
                    
                    # Check duration limit
                    if metadata['duration'] > self.max_duration:
                        metadata['warning'] = f"Video duration ({metadata['duration_string']}) exceeds maximum allowed ({self._format_duration(self.max_duration)})"
                    
                    self.logger.info(f"Retrieved info for: {metadata['title']} ({metadata['duration_string']})")
                    return metadata
                    
                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e)
                    self.logger.error(f"YouTube download error: {error_msg}")
                    
                    # Parse specific error types
                    if 'Private video' in error_msg:
                        return {'success': False, 'error': 'Video is private', 'error_type': 'private'}
                    elif 'Video unavailable' in error_msg:
                        return {'success': False, 'error': 'Video is unavailable', 'error_type': 'unavailable'}
                    elif 'age' in error_msg.lower():
                        return {'success': False, 'error': 'Age-restricted video', 'error_type': 'age_restricted'}
                    elif 'geo' in error_msg.lower():
                        return {'success': False, 'error': 'Video is geo-blocked', 'error_type': 'geo_blocked'}
                    else:
                        return {'success': False, 'error': error_msg, 'error_type': 'download_error'}
                        
        except Exception as e:
            error_msg = f"Error getting video info: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'url': url
            }
    
    def download_audio(self, 
                      url: str, 
                      output_filename: Optional[str] = None,
                      progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Download audio from YouTube video.
        
        Args:
            url: YouTube video URL
            output_filename: Custom output filename (without extension)
            progress_callback: Function to call with progress updates
            
        Returns:
            Dict with download results
        """
        try:
            # First get video info
            info = self.get_video_info(url)
            if not info.get('success'):
                return info
            
            video_id = info.get('video_id')
            video_title = info.get('title', 'unknown')
            duration = info.get('duration', 0)
            
            # Check duration limit
            if duration > self.max_duration:
                return {
                    'success': False,
                    'error': f"Video too long ({self._format_duration(duration)} > {self._format_duration(self.max_duration)})",
                    'video_info': info
                }
            
            # Prepare output path
            if output_filename:
                output_path = os.path.join(self.download_dir, f"{output_filename}.{self.audio_format}")
            else:
                # Sanitize title for filename
                safe_title = re.sub(r'[^\w\s-]', '', video_title)[:50]
                safe_title = re.sub(r'[-\s]+', '-', safe_title)
                output_path = os.path.join(self.download_dir, f"{safe_title}_{video_id}.{self.audio_format}")
            
            # Progress hook
            def progress_hook(d):
                if d['status'] == 'downloading':
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)
                    
                    if total > 0:
                        percent = (downloaded / total) * 100
                    else:
                        percent = 0
                    
                    self.download_progress[video_id] = {
                        'percent': percent,
                        'downloaded': downloaded,
                        'total': total,
                        'speed': speed,
                        'eta': eta,
                        'status': 'downloading'
                    }
                    
                    if progress_callback:
                        progress_callback(self.download_progress[video_id])
                        
                elif d['status'] == 'finished':
                    self.download_progress[video_id] = {
                        'percent': 100,
                        'status': 'finished'
                    }
                    if progress_callback:
                        progress_callback(self.download_progress[video_id])
            
            # Configure yt-dlp for audio download
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path.replace(f'.{self.audio_format}', '.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extract_audio': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': self.audio_format,
                    'preferredquality': self.audio_quality,
                }],
                'postprocessor_args': {
                    'FFmpegExtractAudio': ['-ar', '16000']  # 16kHz for Whisper
                },
                'progress_hooks': [progress_hook],
                'ratelimit': self._parse_rate_limit(self.rate_limit),
                'sleep_interval': self.sleep_interval,
                'max_filesize': self.max_filesize,
                'logger': self.logger
            }
            
            # Download the audio
            self.logger.info(f"Starting audio download for: {video_title}")
            download_start = time.time()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            download_time = time.time() - download_start
            
            # Check if file was created
            # yt-dlp might change extension based on actual format
            actual_output = None
            for ext in [self.audio_format, 'mp3', 'wav', 'm4a', 'opus', 'webm']:
                potential_path = output_path.replace(f'.{self.audio_format}', f'.{ext}')
                if os.path.exists(potential_path):
                    actual_output = potential_path
                    break
            
            if not actual_output:
                return {
                    'success': False,
                    'error': 'Download completed but audio file not found',
                    'expected_path': output_path
                }
            
            # Get file size
            file_size = os.path.getsize(actual_output)
            
            # Clean up progress tracking
            if video_id in self.download_progress:
                del self.download_progress[video_id]
            
            result = {
                'success': True,
                'audio_path': actual_output,
                'video_id': video_id,
                'video_title': video_title,
                'duration': duration,
                'duration_string': self._format_duration(duration),
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'download_time': round(download_time, 2),
                'download_speed_mbps': round((file_size / (1024 * 1024)) / download_time, 2) if download_time > 0 else 0,
                'video_info': info
            }
            
            self.logger.info(f"Audio downloaded successfully: {actual_output} ({result['file_size_mb']}MB in {result['download_time']}s)")
            return result
            
        except Exception as e:
            error_msg = f"Error downloading audio: {str(e)}"
            self.logger.error(error_msg)
            
            # Clean up any partial downloads
            self.cleanup_downloads(video_id if 'video_id' in locals() else None)
            
            return {
                'success': False,
                'error': error_msg,
                'url': url
            }
    
    def download_subtitles(self, url: str, languages: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Download subtitles/captions from YouTube video.
        
        Args:
            url: YouTube video URL
            languages: List of language codes to download (None = all available)
            
        Returns:
            Dict with subtitle information and content
        """
        try:
            # Configure yt-dlp for subtitle extraction
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': languages if languages else ['all'],
                'logger': self.logger
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                subtitles = {}
                
                # Manual subtitles
                if 'subtitles' in info:
                    for lang, subs in info['subtitles'].items():
                        if subs and len(subs) > 0:
                            subtitles[lang] = {
                                'type': 'manual',
                                'url': subs[0].get('url', '') if isinstance(subs, list) else '',
                                'ext': subs[0].get('ext', 'vtt') if isinstance(subs, list) else 'vtt'
                            }
                
                # Automatic captions
                if 'automatic_captions' in info:
                    for lang, subs in info['automatic_captions'].items():
                        if lang not in subtitles and subs and len(subs) > 0:
                            subtitles[lang] = {
                                'type': 'automatic',
                                'url': subs[0].get('url', '') if isinstance(subs, list) else '',
                                'ext': subs[0].get('ext', 'vtt') if isinstance(subs, list) else 'vtt'
                            }
                
                return {
                    'success': True,
                    'video_id': info.get('id'),
                    'title': info.get('title'),
                    'subtitles': subtitles,
                    'available_languages': list(subtitles.keys()),
                    'count': len(subtitles)
                }
                
        except Exception as e:
            error_msg = f"Error downloading subtitles: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'url': url
            }
    
    def get_download_progress(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get current download progress for a video."""
        return self.download_progress.get(video_id)
    
    def cleanup_downloads(self, video_id: Optional[str] = None):
        """
        Clean up downloaded files.
        
        Args:
            video_id: Specific video ID to clean up (None = clean all)
        """
        try:
            if video_id:
                # Clean specific video files
                pattern = f"*{video_id}*"
            else:
                # Clean all files in download directory
                pattern = "*"
            
            import glob
            files = glob.glob(os.path.join(self.download_dir, pattern))
            
            for file in files:
                try:
                    os.remove(file)
                    self.logger.info(f"Cleaned up: {file}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove {file}: {e}")
            
            # Clear progress tracking
            if video_id and video_id in self.download_progress:
                del self.download_progress[video_id]
            elif not video_id:
                self.download_progress.clear()
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds == 0:
            return "0:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _parse_rate_limit(self, rate_str: str) -> Optional[int]:
        """Parse rate limit string (e.g., '1M' -> 1048576)."""
        if not rate_str:
            return None
            
        rate_str = rate_str.strip().upper()
        
        if rate_str[-1] == 'K':
            return int(float(rate_str[:-1]) * 1024)
        elif rate_str[-1] == 'M':
            return int(float(rate_str[:-1]) * 1024 * 1024)
        else:
            try:
                return int(rate_str)
            except:
                return None
    
    def test_connection(self) -> bool:
        """Test if YouTube is accessible."""
        try:
            # Try to get info for a known public video (YouTube Rewind 2018 - most disliked)
            test_url = "https://www.youtube.com/watch?v=YbJOTdZBX1g"
            info = self.get_video_info(test_url)
            return info.get('success', False)
        except:
            return False