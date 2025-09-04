import os
import json
import logging
import time
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import timedelta

import whisper
import torch
import numpy as np


class TranscriptionService:
    """Handles speech-to-text transcription using OpenAI Whisper."""
    
    # Available Whisper models with their characteristics
    MODEL_INFO = {
        'tiny': {
            'size_mb': 39,
            'multilingual': True,
            'speed': 'fastest',
            'accuracy': 'lowest',
            'vram_mb': 1000
        },
        'base': {
            'size_mb': 74,
            'multilingual': True,
            'speed': 'fast',
            'accuracy': 'good',
            'vram_mb': 1000
        },
        'small': {
            'size_mb': 244,
            'multilingual': True,
            'speed': 'medium',
            'accuracy': 'better',
            'vram_mb': 2000
        },
        'medium': {
            'size_mb': 769,
            'multilingual': True,
            'speed': 'slow',
            'accuracy': 'high',
            'vram_mb': 5000
        },
        'large': {
            'size_mb': 1550,
            'multilingual': True,
            'speed': 'slowest',
            'accuracy': 'highest',
            'vram_mb': 10000
        }
    }
    
    def __init__(self, config, model_size: str = 'base'):
        """
        Initialize TranscriptionService.
        
        Args:
            config: Application configuration
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
        """
        self.config = config
        self.model_size = model_size
        self.model = None
        self.device = self._get_optimal_device()
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Model cache directory
        self.cache_dir = getattr(config, 'MODEL_CACHE_DIR', './models')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Performance settings
        self.enable_gpu = getattr(config, 'WHISPER_GPU_ENABLED', True)
        self.batch_size = getattr(config, 'WHISPER_BATCH_SIZE', 1)
        
        self.logger.info(f"TranscriptionService initialized with model: {model_size}, device: {self.device}")
    
    def _get_optimal_device(self) -> str:
        """Determine the best device for processing."""
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon GPU
        else:
            return "cpu"
    
    def load_model(self, force_reload: bool = False) -> bool:
        """
        Load the Whisper model. Downloads if not cached.
        
        Args:
            force_reload: Force reload even if model is already loaded
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.model is not None and not force_reload:
                self.logger.info(f"Model {self.model_size} already loaded")
                return True
            
            self.logger.info(f"Loading Whisper model: {self.model_size}")
            
            # Check if we have enough disk space (rough estimate)
            model_size_mb = self.MODEL_INFO[self.model_size]['size_mb']
            
            # Load model with appropriate device
            load_start = time.time()
            target_device = self.device if self.enable_gpu else "cpu"
            
            try:
                self.model = whisper.load_model(
                    self.model_size, 
                    device=target_device,
                    download_root=self.cache_dir
                )
                load_time = time.time() - load_start
                
                self.logger.info(f"Model {self.model_size} loaded successfully in {load_time:.2f}s")
                self.logger.info(f"Model device: {next(self.model.parameters()).device}")
                
                return True
                
            except Exception as device_error:
                if target_device == "mps":
                    # Common issue with MPS backend on Apple Silicon - fall back to CPU
                    self.logger.warning(f"MPS backend failed ({str(device_error)[:100]}...), falling back to CPU")
                    self.device = "cpu"
                    
                    self.model = whisper.load_model(
                        self.model_size, 
                        device="cpu",
                        download_root=self.cache_dir
                    )
                    load_time = time.time() - load_start
                    
                    self.logger.info(f"Model {self.model_size} loaded successfully on CPU in {load_time:.2f}s")
                    return True
                else:
                    # Re-raise if it's not an MPS-related error
                    raise device_error
            
        except Exception as e:
            self.logger.error(f"Error loading model {self.model_size}: {str(e)}")
            return False
    
    def detect_language(self, audio_path: str) -> Tuple[Optional[str], float]:
        """
        Detect the language of the audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Tuple of (language_code, confidence) or (None, 0.0) on error
        """
        try:
            if not self.model:
                if not self.load_model():
                    return None, 0.0
            
            self.logger.info(f"Detecting language for: {audio_path}")
            
            # Load audio and pad/trim it to fit 30 seconds
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)
            
            # Make log-Mel spectrogram and move to the same device as the model
            mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
            
            # Detect the spoken language
            _, probs = self.model.detect_language(mel)
            detected_language = max(probs, key=probs.get)
            confidence = probs[detected_language]
            
            self.logger.info(f"Detected language: {detected_language} (confidence: {confidence:.3f})")
            
            return detected_language, confidence
            
        except Exception as e:
            self.logger.error(f"Error detecting language: {str(e)}")
            return None, 0.0
    
    def transcribe(self, 
                   audio_path: str, 
                   language: Optional[str] = None,
                   task: str = "transcribe",
                   temperature: float = 0.0,
                   beam_size: Optional[int] = None,
                   best_of: Optional[int] = None,
                   patience: Optional[float] = None,
                   word_timestamps: bool = False) -> Dict[str, Any]:
        """
        Transcribe audio file to text with timestamps.
        
        Args:
            audio_path: Path to audio file
            language: Language code (if None, auto-detect)
            task: 'transcribe' or 'translate'
            temperature: Temperature for sampling
            beam_size: Number of beams for beam search
            best_of: Number of candidates when sampling
            patience: Patience for beam search
            word_timestamps: Enable word-level timestamps
            
        Returns:
            Dict containing transcription results
        """
        try:
            if not self.model:
                if not self.load_model():
                    return {"success": False, "error": "Failed to load model"}
            
            self.logger.info(f"Transcribing audio: {audio_path}")
            start_time = time.time()
            
            # Prepare transcription options
            options = {
                "task": task,
                "temperature": temperature,
                "fp16": False,  # Use fp16 only if supported
                "verbose": False
            }
            
            # Add optional parameters
            if language:
                options["language"] = language
            if beam_size:
                options["beam_size"] = beam_size
            if best_of:
                options["best_of"] = best_of
            if patience:
                options["patience"] = patience
            if word_timestamps:
                options["word_timestamps"] = True
            
            # Perform transcription
            result = self.model.transcribe(audio_path, **options)
            
            processing_time = time.time() - start_time
            
            # Calculate audio duration for performance metrics
            audio_duration = len(whisper.load_audio(audio_path)) / 16000  # Whisper uses 16kHz
            
            # Process and enhance result
            enhanced_result = self._process_transcription_result(
                result, 
                audio_path, 
                processing_time, 
                audio_duration
            )
            
            self.logger.info(f"Transcription completed in {processing_time:.2f}s "
                           f"(audio: {audio_duration:.2f}s, "
                           f"ratio: {processing_time/audio_duration:.2f}x)")
            
            return enhanced_result
            
        except Exception as e:
            self.logger.error(f"Error transcribing audio: {str(e)}")
            return {
                "success": False, 
                "error": str(e),
                "audio_path": audio_path
            }
    
    def _process_transcription_result(self, 
                                    raw_result: Dict, 
                                    audio_path: str, 
                                    processing_time: float,
                                    audio_duration: float) -> Dict[str, Any]:
        """Process and enhance raw transcription result."""
        try:
            # Extract basic information
            text = raw_result.get('text', '').strip()
            language = raw_result.get('language', 'unknown')
            segments = raw_result.get('segments', [])
            
            # Process segments
            processed_segments = []
            for i, segment in enumerate(segments):
                processed_segment = {
                    'id': i,
                    'start': round(segment.get('start', 0.0), 2),
                    'end': round(segment.get('end', 0.0), 2),
                    'text': segment.get('text', '').strip(),
                    'confidence': segment.get('avg_logprob', 0.0)
                }
                
                # Add word-level timestamps if available
                if 'words' in segment:
                    processed_segment['words'] = [
                        {
                            'word': word.get('word', ''),
                            'start': round(word.get('start', 0.0), 2),
                            'end': round(word.get('end', 0.0), 2),
                            'confidence': word.get('probability', 0.0)
                        }
                        for word in segment['words']
                    ]
                
                processed_segments.append(processed_segment)
            
            # Create enhanced result
            result = {
                'success': True,
                'text': text,
                'language': language,
                'segments': processed_segments,
                'metadata': {
                    'audio_path': audio_path,
                    'audio_duration': round(audio_duration, 2),
                    'processing_time': round(processing_time, 2),
                    'processing_ratio': round(processing_time / audio_duration, 2),
                    'model_size': self.model_size,
                    'device': str(self.device),
                    'segment_count': len(processed_segments),
                    'word_count': len(text.split()) if text else 0,
                    'characters': len(text),
                    'timestamp': time.time()
                }
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing transcription result: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to process result: {str(e)}",
                "raw_result": raw_result
            }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages."""
        return whisper.tokenizer.LANGUAGES
    
    def get_model_info(self, model_size: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a model."""
        target_model = model_size or self.model_size
        if target_model not in self.MODEL_INFO:
            return {}
        
        info = self.MODEL_INFO[target_model].copy()
        info['model_name'] = target_model
        info['is_loaded'] = self.model is not None and self.model_size == target_model
        info['device'] = self.device
        
        return info
    
    def estimate_processing_time(self, audio_duration_seconds: float) -> Dict[str, float]:
        """Estimate processing time based on model and audio duration."""
        # These are rough estimates based on typical performance
        speed_multipliers = {
            'tiny': 10.0,    # 10x faster than real-time
            'base': 8.0,     # 8x faster than real-time
            'small': 4.0,    # 4x faster than real-time
            'medium': 2.0,   # 2x faster than real-time
            'large': 1.0     # 1x (same as real-time)
        }
        
        # Adjust for device
        device_multiplier = 1.0
        if self.device == 'cuda':
            device_multiplier = 3.0  # GPU is roughly 3x faster
        elif self.device == 'mps':
            device_multiplier = 2.0  # Apple Silicon is roughly 2x faster
        
        base_speed = speed_multipliers.get(self.model_size, 1.0)
        estimated_time = audio_duration_seconds / (base_speed * device_multiplier)
        
        return {
            'estimated_seconds': round(estimated_time, 2),
            'estimated_minutes': round(estimated_time / 60, 2),
            'speed_ratio': round(base_speed * device_multiplier, 2),
            'model_factor': base_speed,
            'device_factor': device_multiplier
        }
    
    def switch_model(self, new_model_size: str) -> bool:
        """Switch to a different model size."""
        if new_model_size not in self.MODEL_INFO:
            self.logger.error(f"Invalid model size: {new_model_size}")
            return False
        
        if new_model_size == self.model_size and self.model is not None:
            self.logger.info(f"Model {new_model_size} is already loaded")
            return True
        
        self.logger.info(f"Switching from {self.model_size} to {new_model_size}")
        
        # Clear current model
        if self.model is not None:
            try:
                del self.model
                self.model = None
                # Force garbage collection
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    # Clear MPS cache if available
                    if hasattr(torch.mps, 'empty_cache'):
                        torch.mps.empty_cache()
            except Exception as e:
                self.logger.warning(f"Error during model cleanup: {str(e)}")
        
        # Update model size and load new model
        old_model_size = self.model_size
        self.model_size = new_model_size
        
        # Try to load new model, fall back to CPU if there are device issues
        success = self.load_model()
        
        if not success and self.device == "mps":
            self.logger.warning(f"Failed to load {new_model_size} on MPS, trying CPU")
            original_device = self.device
            self.device = "cpu"
            success = self.load_model()
            if not success:
                # Restore original device and model size
                self.device = original_device
                self.model_size = old_model_size
                self.logger.error(f"Failed to load model {new_model_size} on both MPS and CPU")
        
        return success
    
    def export_text(self, result: Dict[str, Any]) -> str:
        """Export transcription as plain text."""
        if not result.get('success', False):
            return ""
        return result.get('text', '')
    
    def export_json(self, result: Dict[str, Any], pretty: bool = True) -> str:
        """Export transcription as JSON."""
        if pretty:
            return json.dumps(result, indent=2, ensure_ascii=False)
        else:
            return json.dumps(result, ensure_ascii=False)
    
    def export_srt(self, result: Dict[str, Any]) -> str:
        """
        Export transcription as SRT subtitle format.
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            String in SRT format
        """
        if not result.get('success', False):
            return ""
        
        segments = result.get('segments', [])
        srt_content = []
        
        for i, segment in enumerate(segments, 1):
            start_time = self._seconds_to_srt_time(segment.get('start', 0.0))
            end_time = self._seconds_to_srt_time(segment.get('end', 0.0))
            text = segment.get('text', '').strip()
            
            if text:  # Only include segments with text
                srt_content.append(f"{i}")
                srt_content.append(f"{start_time} --> {end_time}")
                srt_content.append(text)
                srt_content.append("")  # Empty line between subtitles
        
        return "\n".join(srt_content)
    
    def export_webvtt(self, result: Dict[str, Any]) -> str:
        """
        Export transcription as WebVTT subtitle format.
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            String in WebVTT format
        """
        if not result.get('success', False):
            return ""
        
        segments = result.get('segments', [])
        webvtt_content = ["WEBVTT", ""]  # WebVTT header
        
        for segment in segments:
            start_time = self._seconds_to_webvtt_time(segment.get('start', 0.0))
            end_time = self._seconds_to_webvtt_time(segment.get('end', 0.0))
            text = segment.get('text', '').strip()
            
            if text:  # Only include segments with text
                webvtt_content.append(f"{start_time} --> {end_time}")
                webvtt_content.append(text)
                webvtt_content.append("")  # Empty line between subtitles
        
        return "\n".join(webvtt_content)
    
    def export_segments_csv(self, result: Dict[str, Any]) -> str:
        """Export transcription segments as CSV."""
        if not result.get('success', False):
            return ""
        
        segments = result.get('segments', [])
        csv_lines = ["Start,End,Duration,Text,Confidence"]
        
        for segment in segments:
            start = segment.get('start', 0.0)
            end = segment.get('end', 0.0)
            duration = end - start
            text = segment.get('text', '').strip().replace('"', '""')  # Escape quotes
            confidence = segment.get('confidence', 0.0)
            
            csv_lines.append(f"{start},{end},{duration:.2f},\"{text}\",{confidence:.3f}")
        
        return "\n".join(csv_lines)
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _seconds_to_webvtt_time(self, seconds: float) -> str:
        """Convert seconds to WebVTT time format (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    def export_all_formats(self, result: Dict[str, Any]) -> Dict[str, str]:
        """
        Export transcription in all available formats.
        
        Args:
            result: Transcription result dictionary
            
        Returns:
            Dictionary with format names as keys and content as values
        """
        return {
            'text': self.export_text(result),
            'json': self.export_json(result),
            'srt': self.export_srt(result),
            'webvtt': self.export_webvtt(result),
            'csv': self.export_segments_csv(result)
        }
    
    def save_transcription(self, result: Dict[str, Any], output_path: str, format_type: str = 'json') -> bool:
        """
        Save transcription result to file.
        
        Args:
            result: Transcription result dictionary
            output_path: Output file path
            format_type: Format type ('text', 'json', 'srt', 'webvtt', 'csv')
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            format_exporters = {
                'text': self.export_text,
                'json': self.export_json,
                'srt': self.export_srt,
                'webvtt': self.export_webvtt,
                'csv': self.export_segments_csv
            }
            
            if format_type not in format_exporters:
                self.logger.error(f"Unsupported format: {format_type}")
                return False
            
            content = format_exporters[format_type](result)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Transcription saved to {output_path} in {format_type} format")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving transcription: {str(e)}")
            return False
    
    def cleanup(self):
        """Clean up resources."""
        if self.model is not None:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.logger.info("Model cleanup completed")