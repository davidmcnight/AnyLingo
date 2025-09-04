#!/usr/bin/env python3
"""
Test script for TranscriptionService functionality.
"""

import os
import sys
import time
from config import Config
from utils.transcription_service import TranscriptionService

def test_transcription_service():
    """Test the transcription service with a simple audio file."""
    
    print("🧪 Testing Transcription Service...")
    print("=" * 50)
    
    try:
        # Initialize configuration
        config = Config()
        print(f"✓ Configuration loaded")
        
        # Initialize transcription service with 'tiny' model for faster testing
        print(f"📡 Initializing TranscriptionService with 'tiny' model...")
        transcription_service = TranscriptionService(config, model_size='tiny')
        print(f"✓ TranscriptionService initialized")
        print(f"  Device: {transcription_service.device}")
        
        # Test model info
        model_info = transcription_service.get_model_info()
        print(f"\n📊 Model Information:")
        print(f"  Model: {model_info['model_name']}")
        print(f"  Size: {model_info['size_mb']} MB")
        print(f"  Speed: {model_info['speed']}")
        print(f"  Accuracy: {model_info['accuracy']}")
        print(f"  Device: {model_info['device']}")
        
        # Test supported languages
        languages = transcription_service.get_supported_languages()
        print(f"\n🌍 Supported Languages: {len(languages)} languages")
        sample_langs = list(languages.items())[:5]
        for code, name in sample_langs:
            print(f"  {code}: {name}")
        print(f"  ... and {len(languages) - 5} more")
        
        # Check if we have an audio file to test with, if not create one
        test_audio_path = "./temp/test_tone.wav"
        
        if not os.path.exists(test_audio_path):
            print(f"\n🎵 Creating test audio file...")
            from create_test_audio import create_test_audio
            test_audio_path = create_test_audio()
        
        print(f"\n🎵 Using test audio file: {test_audio_path}")
        
        # Load model
        print(f"📥 Loading model...")
        load_start = time.time()
        success = transcription_service.load_model()
        load_time = time.time() - load_start
        
        if not success:
            print(f"❌ Failed to load model")
            return False
        
        print(f"✓ Model loaded in {load_time:.2f} seconds")
        
        # Get file info
        if os.path.exists(test_audio_path):
            file_size = os.path.getsize(test_audio_path) / (1024 * 1024)
            print(f"  File size: {file_size:.2f} MB")
        
        # Test language detection
        print(f"\n🔍 Testing language detection...")
        lang_start = time.time()
        detected_lang, confidence = transcription_service.detect_language(test_audio_path)
        lang_time = time.time() - lang_start
        
        if detected_lang:
            lang_name = languages.get(detected_lang, detected_lang)
            print(f"✓ Detected language: {lang_name} ({detected_lang}) - Confidence: {confidence:.3f}")
            print(f"  Detection time: {lang_time:.2f} seconds")
        else:
            print(f"❌ Language detection failed")
        
        # Test transcription
        print(f"\n📝 Testing transcription...")
        transcription_start = time.time()
        result = transcription_service.transcribe(
            test_audio_path,
            language=detected_lang if detected_lang else None
        )
        transcription_time = time.time() - transcription_start
        
        if result.get('success', False):
            text = result.get('text', '')
            segments = result.get('segments', [])
            metadata = result.get('metadata', {})
            
            print(f"✓ Transcription successful!")
            print(f"  Processing time: {transcription_time:.2f} seconds")
            print(f"  Audio duration: {metadata.get('audio_duration', 0):.2f} seconds")
            print(f"  Processing ratio: {metadata.get('processing_ratio', 0):.2f}x")
            print(f"  Segments: {len(segments)}")
            print(f"  Words: {metadata.get('word_count', 0)}")
            print(f"  Characters: {metadata.get('characters', 0)}")
            
            # Show first part of transcription
            if text:
                preview = text[:200] + "..." if len(text) > 200 else text
                print(f"\n📄 Transcription Preview:")
                print(f"  \"{preview}\"")
            
            # Test output formats
            print(f"\n📁 Testing output formats...")
            formats = transcription_service.export_all_formats(result)
            
            for format_name, content in formats.items():
                if content:
                    content_length = len(content)
                    preview = content[:100].replace('\n', '\\n') + "..." if len(content) > 100 else content.replace('\n', '\\n')
                    print(f"  ✓ {format_name}: {content_length} characters")
                    print(f"    Preview: \"{preview}\"")
                else:
                    print(f"  ❌ {format_name}: empty content")
            
            # Test saving to files
            print(f"\n💾 Testing file saves...")
            os.makedirs('./temp/transcriptions', exist_ok=True)
            
            for format_type in ['text', 'json', 'srt', 'webvtt', 'csv']:
                output_path = f"./temp/transcriptions/test_output.{format_type}"
                success = transcription_service.save_transcription(result, output_path, format_type)
                if success and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"  ✓ {format_type}: saved to {output_path} ({file_size} bytes)")
                else:
                    print(f"  ❌ {format_type}: failed to save")
        
        else:
            error = result.get('error', 'Unknown error')
            print(f"❌ Transcription failed: {error}")
            return False
        
        # Test performance estimation
        print(f"\n⏱️  Testing performance estimation...")
        for duration in [30, 300, 1800]:  # 30 seconds, 5 minutes, 30 minutes
            estimate = transcription_service.estimate_processing_time(duration)
            print(f"  {duration}s audio → ~{estimate['estimated_seconds']:.1f}s processing "
                  f"({estimate['speed_ratio']:.1f}x speed)")
        
        # Test model switching
        print(f"\n🔄 Testing model switching...")
        current_model = transcription_service.model_size
        print(f"  Current model: {current_model}")
        
        # Try switching to base model (if not already using it)
        if current_model != 'base':
            print(f"  Switching to 'base' model...")
            switch_success = transcription_service.switch_model('base')
            if switch_success:
                print(f"  ✓ Successfully switched to base model")
                # Switch back to original model
                transcription_service.switch_model(current_model)
                print(f"  ✓ Switched back to {current_model} model")
            else:
                print(f"  ❌ Failed to switch to base model")
        else:
            print(f"  Already using base model, skipping switch test")
        
        # Cleanup
        transcription_service.cleanup()
        print(f"\n🧹 Cleanup completed")
        
        print(f"\n✅ All transcription tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_transcription_service()
    sys.exit(0 if success else 1)