"""
Celery tasks for media processing (files and YouTube videos).
Handles asynchronous transcription and translation operations.
"""

from celery import shared_task, current_task
from celery.exceptions import SoftTimeLimitExceeded
import os
import json
import time
from typing import Dict, Any
from datetime import datetime

# Initialize shared resources
media_processor = None
file_handler = None
config = None

def get_media_processor():
    """Get or create MediaProcessor instance (lazy loading)."""
    global media_processor, config
    if media_processor is None:
        # Import here to avoid import-time issues
        from config import Config
        from utils.media_processor import MediaProcessor
        if config is None:
            config = Config()
        media_processor = MediaProcessor(config, whisper_model_size='base')
    return media_processor

def get_file_handler():
    """Get or create FileHandler instance."""
    global file_handler, config
    if file_handler is None:
        # Import here to avoid import-time issues
        from config import Config
        from utils.file_handler import FileHandler
        if config is None:
            config = Config()
        file_handler = FileHandler(config)
    return file_handler

def update_progress(current: int, total: int, message: str = ""):
    """Update task progress."""
    if current_task:
        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'percent': int((current / total) * 100) if total > 0 else 0,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

@shared_task(bind=True)
def process_media_file_task(self, file_path: str, target_language: str = None, 
                           output_formats: list = None) -> Dict[str, Any]:
    """
    Async task to process uploaded media files.
    
    Args:
        file_path: Path to the uploaded file
        target_language: Target language for translation (optional)
        output_formats: List of output formats to generate
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Initialize
        processor = get_media_processor()
        
        # Default output formats
        if output_formats is None:
            output_formats = ['text', 'srt', 'json']
        
        # Update progress - Starting
        update_progress(0, 100, "Initializing media processing...")
        
        # Check file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Update progress - Processing
        update_progress(20, 100, "Processing audio/video file...")
        
        # Process the media file
        result = processor.process_media(
            media_path=file_path,
            target_language=target_language,
            output_formats=output_formats,
            progress_callback=lambda p: update_progress(
                20 + int(p.get('percent', 0) * 0.7),  # 20-90% range
                100,
                p.get('message', 'Processing...')
            )
        )
        
        # Update progress - Finalizing
        update_progress(90, 100, "Finalizing results...")
        
        # Store results
        if result.get('success'):
            # Save outputs to files for download
            task_id = self.request.id
            output_dir = os.path.join(config.TEMP_FOLDER, 'results', task_id)
            os.makedirs(output_dir, exist_ok=True)
            
            outputs_saved = {}
            for format_name, content in result.get('outputs', {}).items():
                if content:
                    output_file = os.path.join(output_dir, f'output.{format_name}')
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    outputs_saved[format_name] = output_file
            
            result['output_files'] = outputs_saved
            result['task_id'] = task_id
        
        # Update progress - Complete
        update_progress(100, 100, "Processing complete!")
        
        return result
        
    except SoftTimeLimitExceeded:
        return {
            'success': False,
            'error': 'Task exceeded time limit',
            'errors': ['Processing took too long and was terminated']
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'errors': [f'Unexpected error: {str(e)}']
        }

@shared_task(bind=True)
def process_youtube_task(self, youtube_url: str, target_language: str = None,
                        output_formats: list = None) -> Dict[str, Any]:
    """
    Async task to process YouTube videos.
    
    Args:
        youtube_url: YouTube video URL
        target_language: Target language for translation (optional)
        output_formats: List of output formats to generate
        
    Returns:
        Dictionary with processing results
    """
    try:
        # Initialize
        processor = get_media_processor()
        
        # Default output formats
        if output_formats is None:
            output_formats = ['text', 'srt', 'json']
        
        # Update progress - Starting
        update_progress(0, 100, "Validating YouTube URL...")
        
        # Validate URL
        if not processor.is_youtube_url(youtube_url):
            raise ValueError(f"Invalid YouTube URL: {youtube_url}")
        
        # Update progress - Getting video info
        update_progress(5, 100, "Fetching video information...")
        
        # Get video info
        video_info = processor.youtube_handler.get_video_info(youtube_url)
        
        if not video_info.get('success'):
            raise ValueError(video_info.get('error', 'Failed to get video info'))
        
        # Check duration limit (configurable, default 2 hours)
        max_duration = getattr(config, 'YOUTUBE_MAX_DURATION', 7200)  # 2 hours default
        duration = video_info.get('duration', 0)
        if duration > max_duration:
            max_duration_hours = max_duration / 3600
            raise ValueError(f"Video too long ({duration}s > {max_duration}s). Maximum duration is {max_duration_hours:.1f} hours.")
        
        # Update progress - Downloading
        update_progress(10, 100, f"Downloading: {video_info.get('title', 'video')[:50]}...")
        
        # Process the YouTube video with progress tracking
        def youtube_progress_callback(progress):
            """Map YouTube processing progress to task progress."""
            stage = progress.get('stage', 'processing')
            percent = progress.get('percent', 0)
            
            if stage == 'downloading':
                # 10-30% for download
                task_percent = 10 + int(percent * 0.2)
                message = f"Downloading: {percent:.0f}%"
            elif stage == 'processing':
                # 30-80% for transcription
                task_percent = 30 + int(percent * 0.5)
                message = f"Processing audio: {percent:.0f}%"
            elif stage == 'transcribing':
                # 50-80% specifically for transcription
                task_percent = 50 + int(percent * 0.3)
                message = f"Transcribing: {percent:.0f}%"
            elif stage == 'translating':
                # 80-95% for translation
                task_percent = 80 + int(percent * 0.15)
                message = f"Translating: {percent:.0f}%"
            else:
                # Default
                task_percent = min(10 + int(percent * 0.8), 95)
                message = progress.get('message', 'Processing...')
            
            update_progress(task_percent, 100, message)
        
        # Process YouTube video
        result = processor.process_youtube(
            youtube_url=youtube_url,
            target_language=target_language,
            output_formats=output_formats,
            progress_callback=youtube_progress_callback
        )
        
        # Update progress - Finalizing
        update_progress(95, 100, "Saving results...")
        
        # Store results
        if result.get('success'):
            # Save outputs to files for download
            task_id = self.request.id
            output_dir = os.path.join(config.TEMP_FOLDER, 'results', task_id)
            os.makedirs(output_dir, exist_ok=True)
            
            outputs_saved = {}
            for format_name, content in result.get('outputs', {}).items():
                if content:
                    output_file = os.path.join(output_dir, f'output.{format_name}')
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    outputs_saved[format_name] = output_file
            
            result['output_files'] = outputs_saved
            result['task_id'] = task_id
            
            # Add video info to result
            result['video_info'] = {
                'title': video_info.get('title'),
                'duration': video_info.get('duration'),
                'uploader': video_info.get('uploader'),
                'view_count': video_info.get('view_count')
            }
        
        # Update progress - Complete
        update_progress(100, 100, "YouTube video processed successfully!")
        
        return result
        
    except SoftTimeLimitExceeded:
        return {
            'success': False,
            'error': 'Task exceeded time limit',
            'errors': ['Processing took too long and was terminated']
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'errors': [f'Unexpected error: {str(e)}']
        }