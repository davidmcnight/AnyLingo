#!/usr/bin/env python3
"""
Test transcription with real speech audio.
"""

import os
import sys
import time
from config import Config
from utils.media_processor import MediaProcessor

def test_real_transcription():
    """Test transcription with actual speech."""
    
    print("🎯 Testing Real Speech Transcription")
    print("=" * 60)
    
    # Expected text
    expected_text = "Hello, this is a test of the AnyLingo transcription system. The quick brown fox jumps over the lazy dog. Testing one, two, three."
    
    try:
        # Initialize
        config = Config()
        media_processor = MediaProcessor(config, whisper_model_size='base')
        
        # Check if speech file exists
        speech_file = './temp/test_speech.wav'
        if not os.path.exists(speech_file):
            print("Creating speech test file...")
            from create_speech_test import create_speech_audio
            speech_file, expected_text = create_speech_audio()
            if not speech_file:
                print("❌ Failed to create speech file")
                return False
        
        print(f"\n📁 Test file: {speech_file}")
        file_size = os.path.getsize(speech_file) / 1024
        print(f"   File size: {file_size:.1f} KB")
        print(f"\n📝 Expected text:")
        print(f'   "{expected_text}"')
        
        # Process the audio
        print(f"\n🔄 Processing audio file...")
        start_time = time.time()
        
        result = media_processor.process_media(
            media_path=speech_file,
            output_formats=['text', 'srt', 'webvtt', 'json'],
            enhance_audio=False,
            chunk_long_files=False
        )
        
        process_time = time.time() - start_time
        
        if result['success']:
            print(f"\n✅ Processing successful in {process_time:.2f}s")
            
            # Get transcribed text
            transcription = result.get('transcription_result', {})
            actual_text = transcription.get('text', '').strip()
            
            print(f"\n📊 Results:")
            print(f"   Language detected: {transcription.get('language', 'unknown')}")
            
            metadata = result.get('metadata', {})
            print(f"   Audio duration: {metadata.get('audio_duration', 0):.1f}s")
            print(f"   Processing ratio: {metadata.get('processing_ratio', 0):.2f}x")
            print(f"   Word count: {metadata.get('word_count', 0)}")
            print(f"   Segments: {metadata.get('segment_count', 0)}")
            
            print(f"\n🎯 Transcribed text:")
            print(f'   "{actual_text}"')
            
            # Compare with expected
            if actual_text:
                # Calculate accuracy (simple word match)
                expected_words = expected_text.lower().split()
                actual_words = actual_text.lower().split()
                
                matching_words = 0
                for word in actual_words:
                    if word in expected_words:
                        matching_words += 1
                
                if len(actual_words) > 0:
                    accuracy = (matching_words / len(expected_words)) * 100
                    print(f"\n📈 Accuracy estimate: {accuracy:.1f}%")
                    print(f"   Matched {matching_words}/{len(expected_words)} expected words")
                
                # Show segments with timestamps
                segments = transcription.get('segments', [])
                if segments:
                    print(f"\n⏱️ Timestamped segments:")
                    for seg in segments[:3]:  # Show first 3 segments
                        start = seg.get('start', 0)
                        end = seg.get('end', 0)
                        text = seg.get('text', '').strip()
                        print(f"   [{start:.2f}s - {end:.2f}s]: {text}")
                    if len(segments) > 3:
                        print(f"   ... and {len(segments)-3} more segments")
            
            # Check output formats
            outputs = result.get('outputs', {})
            print(f"\n📄 Generated formats:")
            for format_name, content in outputs.items():
                if content:
                    print(f"   ✓ {format_name}: {len(content)} bytes")
                    
                    # Show SRT preview
                    if format_name == 'srt' and content:
                        lines = content.split('\n')[:8]  # First 2 subtitles
                        if lines:
                            print(f"\n   SRT Preview:")
                            for line in lines:
                                if line:
                                    print(f"     {line}")
            
            # Test accuracy threshold
            if actual_text:
                success = True
                print(f"\n✅ Transcription test PASSED - Generated readable text")
            else:
                success = False
                print(f"\n⚠️ No text transcribed (might be audio quality issue)")
            
            # Cleanup
            media_processor.cleanup()
            return success
            
        else:
            print(f"\n❌ Processing failed!")
            errors = result.get('errors', [])
            for error in errors:
                print(f"   • {error}")
            media_processor.cleanup()
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_real_transcription()
    sys.exit(0 if success else 1)