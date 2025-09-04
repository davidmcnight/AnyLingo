import os
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union

from .audio_processor import AudioProcessor
from .transcription_service import TranscriptionService
from .youtube_handler import YouTubeHandler


class MediaProcessor:
    """Integrated media processing service combining audio processing and transcription."""
    
    def __init__(self, config, whisper_model_size: str = 'base'):
        """
        Initialize MediaProcessor with audio and transcription services.
        
        Args:
            config: Application configuration
            whisper_model_size: Whisper model size to use
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize component services
        self.audio_processor = AudioProcessor(config)
        self.transcription_service = TranscriptionService(config, whisper_model_size)
        self.youtube_handler = YouTubeHandler(config)
        
        # Pipeline settings
        self.auto_cleanup = getattr(config, 'AUTO_CLEANUP_TEMP_FILES', True)
        self.chunk_large_files = getattr(config, 'CHUNK_LARGE_FILES', True)
        self.max_chunk_duration = getattr(config, 'MAX_CHUNK_DURATION', 300)  # 5 minutes
        
        self.logger.info(f"MediaProcessor initialized with Whisper model: {whisper_model_size}")
    
    def process_media(self, 
                     media_path: str,
                     target_language: Optional[str] = None,
                     output_formats: List[str] = None,
                     enhance_audio: bool = False,
                     chunk_long_files: bool = None) -> Dict[str, Any]:
        """
        Complete media processing pipeline: extract audio → transcribe → generate outputs.
        
        Args:
            media_path: Path to input media file (video or audio)
            target_language: Target language code for transcription (None for auto-detect)
            output_formats: List of desired output formats ['text', 'json', 'srt', 'webvtt', 'csv']
            enhance_audio: Whether to apply audio enhancement
            chunk_long_files: Whether to chunk long files (None = use config default)
            
        Returns:
            Dict containing processing results and outputs
        """
        
        if output_formats is None:
            output_formats = ['text', 'json', 'srt']
        
        if chunk_long_files is None:
            chunk_long_files = self.chunk_large_files
        
        start_time = time.time()
        result = {
            'success': False,
            'media_path': media_path,
            'processing_stages': {},
            'outputs': {},
            'metadata': {},
            'temp_files': [],
            'errors': []
        }
        
        try:
            self.logger.info(f"Starting media processing pipeline for: {media_path}")
            
            # Stage 1: Audio Processing
            self.logger.info("Stage 1: Audio extraction and processing")
            stage1_start = time.time()
            
            audio_result = self.audio_processor.process_media_file(media_path)
            audio_success, audio_path, audio_message = audio_result
            
            stage1_time = time.time() - stage1_start
            result['processing_stages']['audio_processing'] = {
                'success': audio_success,
                'duration': stage1_time,
                'message': audio_message,
                'output_path': audio_path if audio_success else None
            }
            
            if not audio_success:
                result['errors'].append(f"Audio processing failed: {audio_message}")
                return result
            
            result['temp_files'].append(audio_path)
            
            # Get audio information
            audio_info = self.audio_processor.get_audio_info(audio_path)
            audio_duration = audio_info.get('duration', 0)
            
            self.logger.info(f"Audio processing completed: {audio_message}")
            self.logger.info(f"Audio duration: {audio_duration:.2f}s")
            
            # Stage 2: Audio Enhancement (optional)
            if enhance_audio:
                self.logger.info("Stage 2: Audio enhancement")
                enhance_start = time.time()
                
                enhance_result = self.audio_processor.enhance_audio(audio_path)
                enhance_success, enhanced_path, enhance_message = enhance_result
                
                enhance_time = time.time() - enhance_start
                result['processing_stages']['audio_enhancement'] = {
                    'success': enhance_success,
                    'duration': enhance_time,
                    'message': enhance_message,
                    'output_path': enhanced_path if enhance_success else None
                }
                
                if enhance_success:
                    # Use enhanced audio for transcription
                    audio_path = enhanced_path
                    result['temp_files'].append(enhanced_path)
                    self.logger.info(f"Audio enhancement completed: {enhance_message}")
                else:
                    result['errors'].append(f"Audio enhancement failed: {enhance_message}")
                    self.logger.warning(f"Audio enhancement failed, using original: {enhance_message}")
            
            # Stage 3: Chunking (if needed)
            chunks = []
            if chunk_long_files and audio_duration > self.max_chunk_duration:
                self.logger.info(f"Stage 3: Chunking long audio ({audio_duration:.1f}s > {self.max_chunk_duration}s)")
                chunk_start = time.time()
                
                chunks = self.audio_processor.chunk_audio(audio_path, self.max_chunk_duration)
                
                chunk_time = time.time() - chunk_start
                result['processing_stages']['chunking'] = {
                    'success': len(chunks) > 0,
                    'duration': chunk_time,
                    'message': f"Split into {len(chunks)} chunks",
                    'chunk_count': len(chunks)
                }
                
                # Add chunk files to temp files list
                for chunk in chunks:
                    result['temp_files'].append(chunk['path'])
                
                self.logger.info(f"Audio chunked into {len(chunks)} segments")
            else:
                # Single file processing
                chunks = [{
                    'path': audio_path,
                    'start_time': 0,
                    'end_time': audio_duration,
                    'duration': audio_duration,
                    'chunk_index': 0
                }]
            
            # Stage 4: Transcription
            self.logger.info(f"Stage 4: Transcription ({len(chunks)} segment{'s' if len(chunks) > 1 else ''})")
            transcription_start = time.time()
            
            # Load transcription model if not already loaded
            model_load_start = time.time()
            if not self.transcription_service.load_model():
                result['errors'].append("Failed to load transcription model")
                return result
            model_load_time = time.time() - model_load_start
            
            # Process each chunk
            transcription_results = []
            total_transcription_time = 0
            
            for i, chunk in enumerate(chunks):
                chunk_start_time = time.time()
                self.logger.info(f"Transcribing chunk {i+1}/{len(chunks)}")
                
                # Transcribe chunk
                chunk_result = self.transcription_service.transcribe(
                    chunk['path'],
                    language=target_language
                )
                
                if chunk_result.get('success', False):
                    # Adjust timestamps for multi-chunk files
                    if len(chunks) > 1:
                        chunk_offset = chunk['start_time']
                        for segment in chunk_result.get('segments', []):
                            segment['start'] += chunk_offset
                            segment['end'] += chunk_offset
                    
                    transcription_results.append(chunk_result)
                    
                    chunk_time = time.time() - chunk_start_time
                    total_transcription_time += chunk_time
                    
                    self.logger.info(f"Chunk {i+1} transcribed in {chunk_time:.2f}s")
                else:
                    error_msg = chunk_result.get('error', 'Unknown error')
                    result['errors'].append(f"Transcription failed for chunk {i+1}: {error_msg}")
                    self.logger.error(f"Chunk {i+1} transcription failed: {error_msg}")
            
            # Combine results from all chunks
            if transcription_results:
                combined_result = self._combine_transcription_results(transcription_results)
                
                total_transcription_duration = time.time() - transcription_start
                result['processing_stages']['transcription'] = {
                    'success': True,
                    'duration': total_transcription_duration,
                    'model_load_time': model_load_time,
                    'transcription_time': total_transcription_time,
                    'chunk_count': len(chunks),
                    'message': f"Transcribed {len(chunks)} chunk{'s' if len(chunks) > 1 else ''} successfully"
                }
                
                # Stage 5: Output Generation
                self.logger.info("Stage 5: Generating output formats")
                output_start = time.time()
                
                outputs = {}
                for format_type in output_formats:
                    try:
                        if format_type == 'text':
                            outputs[format_type] = self.transcription_service.export_text(combined_result)
                        elif format_type == 'json':
                            outputs[format_type] = self.transcription_service.export_json(combined_result)
                        elif format_type == 'srt':
                            outputs[format_type] = self.transcription_service.export_srt(combined_result)
                        elif format_type == 'webvtt':
                            outputs[format_type] = self.transcription_service.export_webvtt(combined_result)
                        elif format_type == 'csv':
                            outputs[format_type] = self.transcription_service.export_segments_csv(combined_result)
                        else:
                            self.logger.warning(f"Unsupported output format: {format_type}")
                    except Exception as e:
                        result['errors'].append(f"Failed to generate {format_type} format: {str(e)}")
                
                output_time = time.time() - output_start
                result['processing_stages']['output_generation'] = {
                    'success': len(outputs) > 0,
                    'duration': output_time,
                    'formats': list(outputs.keys()),
                    'message': f"Generated {len(outputs)} output format{'s' if len(outputs) > 1 else ''}"
                }
                
                # Final result assembly
                total_time = time.time() - start_time
                
                result.update({
                    'success': True,
                    'transcription_result': combined_result,
                    'outputs': outputs,
                    'metadata': {
                        'total_processing_time': total_time,
                        'audio_duration': audio_duration,
                        'processing_ratio': total_time / max(audio_duration, 0.1),
                        'model_used': self.transcription_service.model_size,
                        'device_used': self.transcription_service.device,
                        'chunks_processed': len(chunks),
                        'enhancement_applied': enhance_audio,
                        'language_detected': combined_result.get('language', 'unknown'),
                        'word_count': combined_result.get('metadata', {}).get('word_count', 0),
                        'segment_count': len(combined_result.get('segments', [])),
                        'character_count': len(combined_result.get('text', ''))
                    }
                })
                
                self.logger.info(f"Media processing completed successfully in {total_time:.2f}s")
                
            else:
                result['errors'].append("No transcription results obtained")
                return result
        
        except Exception as e:
            error_msg = f"Error in media processing pipeline: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        finally:
            # Cleanup temporary files if requested
            if self.auto_cleanup:
                self._cleanup_temp_files(result['temp_files'])
                result['temp_files'] = []
        
        return result
    
    def _combine_transcription_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple transcription results into a single result."""
        if not results:
            return {'success': False, 'error': 'No results to combine'}
        
        if len(results) == 1:
            return results[0]
        
        # Combine text
        combined_text = []
        combined_segments = []
        combined_language = results[0].get('language', 'unknown')
        
        total_processing_time = 0
        total_audio_duration = 0
        total_word_count = 0
        total_characters = 0
        
        for result in results:
            if result.get('success', False):
                text = result.get('text', '').strip()
                if text:
                    combined_text.append(text)
                
                segments = result.get('segments', [])
                combined_segments.extend(segments)
                
                metadata = result.get('metadata', {})
                total_processing_time += metadata.get('processing_time', 0)
                total_audio_duration += metadata.get('audio_duration', 0)
                total_word_count += metadata.get('word_count', 0)
                total_characters += metadata.get('characters', 0)
        
        # Re-index segments
        for i, segment in enumerate(combined_segments):
            segment['id'] = i
        
        return {
            'success': True,
            'text': ' '.join(combined_text),
            'language': combined_language,
            'segments': combined_segments,
            'metadata': {
                'processing_time': total_processing_time,
                'audio_duration': total_audio_duration,
                'word_count': total_word_count,
                'characters': total_characters,
                'segment_count': len(combined_segments),
                'chunk_count': len(results),
                'model_size': self.transcription_service.model_size,
                'device': str(self.transcription_service.device)
            }
        }
    
    def _cleanup_temp_files(self, temp_files: List[str]):
        """Clean up temporary files."""
        for file_path in temp_files:
            try:
                if os.path.exists(file_path):
                    self.audio_processor.cleanup_file(file_path)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup {file_path}: {e}")
    
    def get_processing_estimate(self, media_path: str) -> Dict[str, Any]:
        """Get processing time estimate for a media file."""
        try:
            # Get audio info (might need to process first for video files)
            if self.audio_processor._is_video_file(media_path):
                # For video files, we can't easily get duration without processing
                # Return rough estimates based on file size
                file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
                estimated_duration = file_size_mb * 2  # Rough estimate: 2 seconds per MB
            else:
                # For audio files, get actual duration
                audio_info = self.audio_processor.get_audio_info(media_path)
                estimated_duration = audio_info.get('duration', 0)
            
            if estimated_duration == 0:
                return {'error': 'Could not determine media duration'}
            
            # Get transcription time estimate
            transcription_estimate = self.transcription_service.estimate_processing_time(estimated_duration)
            
            # Add audio processing overhead (usually fast)
            audio_processing_time = max(5, estimated_duration * 0.1)  # 5s minimum, or 10% of duration
            
            total_estimate = audio_processing_time + transcription_estimate['estimated_seconds']
            
            return {
                'media_duration_estimate': estimated_duration,
                'audio_processing_time': audio_processing_time,
                'transcription_time': transcription_estimate['estimated_seconds'],
                'total_estimated_time': total_estimate,
                'speed_ratio': estimated_duration / total_estimate if total_estimate > 0 else 0,
                'model_info': {
                    'model_size': self.transcription_service.model_size,
                    'device': self.transcription_service.device,
                    'speed_factor': transcription_estimate['speed_ratio']
                }
            }
            
        except Exception as e:
            return {'error': f'Could not estimate processing time: {str(e)}'}
    
    def process_youtube(self,
                        youtube_url: str,
                        target_language: Optional[str] = None,
                        output_formats: List[str] = None,
                        progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process YouTube video: download audio → transcribe → generate outputs.
        
        Args:
            youtube_url: YouTube video URL
            target_language: Target language for transcription (None for auto-detect)
            output_formats: List of desired output formats
            progress_callback: Callback for download progress updates
            
        Returns:
            Dict containing processing results
        """
        
        start_time = time.time()
        result = {
            'success': False,
            'youtube_url': youtube_url,
            'processing_stages': {},
            'outputs': {},
            'metadata': {},
            'temp_files': [],
            'errors': []
        }
        
        try:
            self.logger.info(f"Starting YouTube processing for: {youtube_url}")
            
            # Stage 1: Validate URL and get video info
            self.logger.info("Stage 1: YouTube URL validation and metadata extraction")
            stage1_start = time.time()
            
            # Validate URL
            is_valid, video_id, message = self.youtube_handler.validate_url(youtube_url)
            if not is_valid:
                result['errors'].append(f"Invalid YouTube URL: {message}")
                return result
            
            # Get video info
            video_info = self.youtube_handler.get_video_info(youtube_url)
            if not video_info.get('success'):
                result['errors'].append(f"Failed to get video info: {video_info.get('error', 'Unknown error')}")
                return result
            
            stage1_time = time.time() - stage1_start
            result['processing_stages']['youtube_validation'] = {
                'success': True,
                'duration': stage1_time,
                'video_id': video_id,
                'title': video_info.get('title', 'Unknown'),
                'video_duration': video_info.get('duration', 0),
                'message': 'Video info retrieved successfully'
            }
            
            # Store video metadata
            result['video_info'] = video_info
            
            # Stage 2: Download audio from YouTube
            self.logger.info("Stage 2: Downloading audio from YouTube")
            stage2_start = time.time()
            
            download_result = self.youtube_handler.download_audio(
                youtube_url,
                progress_callback=progress_callback
            )
            
            if not download_result.get('success'):
                result['errors'].append(f"Audio download failed: {download_result.get('error', 'Unknown error')}")
                return result
            
            audio_path = download_result.get('audio_path')
            result['temp_files'].append(audio_path)
            
            stage2_time = time.time() - stage2_start
            result['processing_stages']['youtube_download'] = {
                'success': True,
                'duration': stage2_time,
                'file_size_mb': download_result.get('file_size_mb', 0),
                'download_speed_mbps': download_result.get('download_speed_mbps', 0),
                'message': f"Audio downloaded successfully ({download_result.get('file_size_mb', 0):.1f}MB)"
            }
            
            self.logger.info(f"Audio downloaded to: {audio_path}")
            
            # Stage 3: Process the downloaded audio file
            self.logger.info("Stage 3: Processing downloaded audio")
            
            # Use the standard media processing pipeline
            media_result = self.process_media(
                media_path=audio_path,
                target_language=target_language,
                output_formats=output_formats,
                enhance_audio=False,
                chunk_long_files=True
            )
            
            # Merge results
            result['success'] = media_result.get('success', False)
            result['transcription_result'] = media_result.get('transcription_result', {})
            result['outputs'] = media_result.get('outputs', {})
            
            # Update metadata with YouTube-specific info
            if media_result.get('metadata'):
                result['metadata'] = media_result['metadata']
                result['metadata'].update({
                    'youtube_video_id': video_id,
                    'youtube_title': video_info.get('title', 'Unknown'),
                    'youtube_uploader': video_info.get('uploader', 'Unknown'),
                    'youtube_duration': video_info.get('duration', 0),
                    'youtube_view_count': video_info.get('view_count', 0),
                    'subtitles_available': video_info.get('subtitles_available', False)
                })
            
            # Add media processing stages
            if media_result.get('processing_stages'):
                result['processing_stages'].update(media_result['processing_stages'])
            
            # Add any errors from media processing
            if media_result.get('errors'):
                result['errors'].extend(media_result['errors'])
            
            # Cleanup downloaded file if auto-cleanup is enabled
            if self.auto_cleanup and audio_path:
                try:
                    self.youtube_handler.cleanup_downloads(video_id)
                    self.logger.info(f"Cleaned up YouTube download for video ID: {video_id}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup YouTube download: {e}")
            
            total_time = time.time() - start_time
            result['metadata']['total_processing_time'] = total_time
            
            self.logger.info(f"YouTube video processed successfully in {total_time:.2f}s")
            
        except Exception as e:
            error_msg = f"Error processing YouTube video: {str(e)}"
            result['errors'].append(error_msg)
            self.logger.error(error_msg)
        
        return result
    
    def is_youtube_url(self, input_str: str) -> bool:
        """Check if the input string is a YouTube URL."""
        is_valid, _, _ = self.youtube_handler.validate_url(input_str)
        return is_valid
    
    def cleanup(self):
        """Clean up all resources."""
        self.transcription_service.cleanup()
        self.youtube_handler.cleanup_downloads()
        self.logger.info("MediaProcessor cleanup completed")