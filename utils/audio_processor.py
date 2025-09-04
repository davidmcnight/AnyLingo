import os
import ffmpeg
import tempfile
from typing import Optional, Tuple, List, Dict
import subprocess
import numpy as np
from pydub import AudioSegment
import librosa
import soundfile as sf
import logging

class AudioProcessor:
    """Handles audio extraction, conversion, and preprocessing for transcription."""
    
    def __init__(self, config):
        self.config = config
        self.temp_folder = getattr(config, 'TEMP_FOLDER', './temp')
        
        # Optimal settings for Whisper
        self.target_sample_rate = 16000  # 16kHz for Whisper
        self.target_channels = 1  # Mono for Whisper
        
        # Create temp folder if it doesn't exist
        os.makedirs(self.temp_folder, exist_ok=True)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
    def process_media_file(self, input_path: str) -> Tuple[bool, str, str]:
        """
        Main entry point for processing any media file.
        Returns: (success, output_audio_path, message)
        """
        try:
            # Determine if it's audio or video
            is_video = self._is_video_file(input_path)
            
            if is_video:
                return self._extract_audio_from_video(input_path)
            else:
                return self._process_audio_file(input_path)
                
        except Exception as e:
            error_msg = f"Error processing media file: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def _is_video_file(self, filepath: str) -> bool:
        """Check if file is a video file based on extension."""
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v'}
        _, ext = os.path.splitext(filepath.lower())
        return ext in video_extensions
    
    def _extract_audio_from_video(self, video_path: str) -> Tuple[bool, str, str]:
        """Extract audio from video file using FFmpeg."""
        try:
            # Generate output path
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(self.temp_folder, f"{video_name}_audio.wav")
            
            self.logger.info(f"Extracting audio from video: {video_path}")
            
            # Use FFmpeg to extract audio with optimal settings for Whisper
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream, 
                output_path,
                acodec='pcm_s16le',  # 16-bit PCM
                ar=self.target_sample_rate,  # 16kHz sample rate
                ac=self.target_channels,  # Mono
                map='0:a:0'  # Select first audio stream
            )
            
            # Run FFmpeg
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
            # Verify output file exists and has content
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                return False, "", "Audio extraction failed - no output generated"
            
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            success_msg = f"Audio extracted successfully. Size: {file_size_mb:.2f}MB"
            self.logger.info(success_msg)
            
            return True, output_path, success_msg
            
        except ffmpeg.Error as e:
            error_message = e.stderr.decode('utf-8') if e.stderr else str(e)
            self.logger.error(f"FFmpeg error: {error_message}")
            return False, "", f"Audio extraction failed: {error_message}"
        except Exception as e:
            error_msg = f"Unexpected error during audio extraction: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def _process_audio_file(self, audio_path: str) -> Tuple[bool, str, str]:
        """Process existing audio file to optimal format for Whisper."""
        try:
            self.logger.info(f"Processing audio file: {audio_path}")
            
            # Check if already in optimal format
            if self._is_optimal_format(audio_path):
                self.logger.info("Audio file already in optimal format")
                return True, audio_path, "Audio file already optimized"
            
            # Convert to optimal format
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            output_path = os.path.join(self.temp_folder, f"{audio_name}_optimized.wav")
            
            # Load audio with librosa (handles many formats)
            audio_data, sample_rate = librosa.load(
                audio_path, 
                sr=self.target_sample_rate,
                mono=True
            )
            
            # Save as WAV with optimal settings
            sf.write(output_path, audio_data, self.target_sample_rate)
            
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            success_msg = f"Audio processed successfully. Size: {file_size_mb:.2f}MB"
            self.logger.info(success_msg)
            
            return True, output_path, success_msg
            
        except Exception as e:
            error_msg = f"Error processing audio file: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def _is_optimal_format(self, audio_path: str) -> bool:
        """Check if audio file is already in optimal format (16kHz, mono WAV)."""
        try:
            # Use librosa to check format quickly
            info = sf.info(audio_path)
            
            return (
                info.samplerate == self.target_sample_rate and
                info.channels == self.target_channels and
                audio_path.lower().endswith('.wav')
            )
        except:
            return False
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file in seconds."""
        try:
            duration = librosa.get_duration(path=audio_path)
            return duration
        except Exception as e:
            self.logger.error(f"Error getting audio duration: {e}")
            return 0.0
    
    def get_audio_info(self, audio_path: str) -> Dict[str, any]:
        """Get detailed information about audio file."""
        try:
            info = sf.info(audio_path)
            duration = self.get_audio_duration(audio_path)
            
            return {
                'duration': duration,
                'duration_formatted': self._format_duration(duration),
                'sample_rate': info.samplerate,
                'channels': info.channels,
                'format': info.format,
                'subtype': info.subtype,
                'file_size': os.path.getsize(audio_path),
                'file_size_mb': round(os.path.getsize(audio_path) / (1024 * 1024), 2),
                'is_optimal': self._is_optimal_format(audio_path)
            }
        except Exception as e:
            self.logger.error(f"Error getting audio info: {e}")
            return {}
    
    def chunk_audio(self, audio_path: str, chunk_duration: int = 300) -> List[Dict[str, any]]:
        """
        Split audio into chunks for processing large files.
        chunk_duration: duration in seconds (default 5 minutes)
        """
        try:
            duration = self.get_audio_duration(audio_path)
            
            # If file is short enough, return as single chunk
            if duration <= chunk_duration:
                return [{
                    'path': audio_path,
                    'start_time': 0,
                    'end_time': duration,
                    'duration': duration,
                    'chunk_index': 0
                }]
            
            chunks = []
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            
            # Load full audio
            audio_data, sample_rate = librosa.load(audio_path, sr=None)
            chunk_samples = int(chunk_duration * sample_rate)
            
            for i, start_sample in enumerate(range(0, len(audio_data), chunk_samples)):
                end_sample = min(start_sample + chunk_samples, len(audio_data))
                chunk_data = audio_data[start_sample:end_sample]
                
                # Save chunk
                chunk_path = os.path.join(
                    self.temp_folder,
                    f"{audio_name}_chunk_{i:03d}.wav"
                )
                sf.write(chunk_path, chunk_data, sample_rate)
                
                start_time = start_sample / sample_rate
                end_time = end_sample / sample_rate
                
                chunks.append({
                    'path': chunk_path,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'chunk_index': i
                })
            
            self.logger.info(f"Split audio into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            self.logger.error(f"Error chunking audio: {e}")
            return []
    
    def enhance_audio(self, audio_path: str) -> Tuple[bool, str, str]:
        """Apply basic audio enhancement (noise reduction, normalization)."""
        try:
            self.logger.info(f"Enhancing audio: {audio_path}")
            
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            output_path = os.path.join(self.temp_folder, f"{audio_name}_enhanced.wav")
            
            # Load audio
            audio_data, sample_rate = librosa.load(audio_path, sr=None)
            
            # Apply basic enhancement
            # 1. Normalize audio
            audio_data = librosa.util.normalize(audio_data)
            
            # 2. Apply simple noise gate (remove very quiet parts)
            threshold = 0.01  # Adjust as needed
            audio_data = np.where(np.abs(audio_data) < threshold, 0, audio_data)
            
            # Save enhanced audio
            sf.write(output_path, audio_data, sample_rate)
            
            return True, output_path, "Audio enhanced successfully"
            
        except Exception as e:
            error_msg = f"Error enhancing audio: {str(e)}"
            self.logger.error(error_msg)
            return False, "", error_msg
    
    def cleanup_file(self, filepath: str) -> bool:
        """Remove temporary audio file."""
        try:
            if os.path.exists(filepath) and filepath.startswith(self.temp_folder):
                os.remove(filepath)
                self.logger.info(f"Cleaned up file: {filepath}")
                return True
        except Exception as e:
            self.logger.error(f"Error cleaning up file {filepath}: {e}")
        return False
    
    def cleanup_chunks(self, chunks: List[Dict[str, any]]) -> None:
        """Clean up chunk files."""
        for chunk in chunks:
            self.cleanup_file(chunk['path'])
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds == 0:
            return "0:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"