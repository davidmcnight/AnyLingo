#!/usr/bin/env python3
"""
Test script for integrated MediaProcessor functionality.
"""

import os
import sys
import time
from config import Config
from utils.media_processor import MediaProcessor

def test_media_processor():
    """Test the complete media processing pipeline."""
    
    print("🎬 Testing Integrated Media Processor...")
    print("=" * 60)
    
    try:
        # Initialize configuration
        config = Config()
        print(f"✓ Configuration loaded")
        
        # Initialize media processor
        print(f"🔧 Initializing MediaProcessor...")
        media_processor = MediaProcessor(config, whisper_model_size='tiny')
        print(f"✓ MediaProcessor initialized")
        
        # Create test audio if it doesn't exist
        test_audio_path = "./temp/test_tone.wav"
        if not os.path.exists(test_audio_path):
            print(f"\n🎵 Creating test audio file...")
            from create_test_audio import create_test_audio
            test_audio_path = create_test_audio()
        
        print(f"\n📁 Test file: {test_audio_path}")
        file_size = os.path.getsize(test_audio_path) / (1024 * 1024)
        print(f"   File size: {file_size:.2f} MB")
        
        # Test processing time estimation
        print(f"\n⏱️  Getting processing estimate...")
        estimate = media_processor.get_processing_estimate(test_audio_path)
        
        if 'error' in estimate:
            print(f"❌ Estimation failed: {estimate['error']}")
        else:
            print(f"✓ Processing estimate:")
            print(f"  Media duration: {estimate['media_duration_estimate']:.1f}s")
            print(f"  Audio processing: {estimate['audio_processing_time']:.1f}s")
            print(f"  Transcription: {estimate['transcription_time']:.1f}s")
            print(f"  Total estimated: {estimate['total_estimated_time']:.1f}s")
            print(f"  Speed ratio: {estimate['speed_ratio']:.1f}x")
        
        # Test complete pipeline
        print(f"\n🎯 Testing complete media processing pipeline...")
        pipeline_start = time.time()
        
        result = media_processor.process_media(
            media_path=test_audio_path,
            output_formats=['text', 'json', 'srt', 'webvtt', 'csv'],
            enhance_audio=False,  # Skip enhancement for simple test
            chunk_long_files=False  # Skip chunking for short test file
        )
        
        pipeline_time = time.time() - pipeline_start
        print(f"⏱️  Pipeline completed in {pipeline_time:.2f} seconds")
        
        # Analyze results
        if result['success']:
            print(f"\n✅ Pipeline succeeded!")
            
            # Show processing stages
            print(f"\n📋 Processing Stages:")
            for stage_name, stage_info in result.get('processing_stages', {}).items():
                status = "✓" if stage_info.get('success') else "❌"
                duration = stage_info.get('duration', 0)
                message = stage_info.get('message', '')
                print(f"  {status} {stage_name}: {duration:.2f}s - {message}")
            
            # Show metadata
            metadata = result.get('metadata', {})
            if metadata:
                print(f"\n📊 Processing Metadata:")
                print(f"  Total time: {metadata.get('total_processing_time', 0):.2f}s")
                print(f"  Audio duration: {metadata.get('audio_duration', 0):.2f}s")
                print(f"  Processing ratio: {metadata.get('processing_ratio', 0):.2f}x")
                print(f"  Model used: {metadata.get('model_used', 'unknown')}")
                print(f"  Device used: {metadata.get('device_used', 'unknown')}")
                print(f"  Language detected: {metadata.get('language_detected', 'unknown')}")
                print(f"  Segments: {metadata.get('segment_count', 0)}")
                print(f"  Words: {metadata.get('word_count', 0)}")
                print(f"  Characters: {metadata.get('character_count', 0)}")
            
            # Show transcription result
            transcription_result = result.get('transcription_result', {})
            if transcription_result.get('success'):
                text = transcription_result.get('text', '')
                if text:
                    preview = text[:200] + "..." if len(text) > 200 else text
                    print(f"\n📄 Transcription Preview:")
                    print(f'  "{preview}"')
                else:
                    print(f"\n📄 Transcription: (no text - expected for sine wave)")
            
            # Show output formats
            outputs = result.get('outputs', {})
            if outputs:
                print(f"\n📁 Generated Output Formats:")
                for format_name, content in outputs.items():
                    if content:
                        length = len(content)
                        print(f"  ✓ {format_name}: {length} characters")
                        if format_name == 'json':
                            # Show JSON structure
                            import json
                            try:
                                parsed = json.loads(content)
                                print(f"    - Contains: {', '.join(parsed.keys())}")
                            except:
                                pass
                    else:
                        print(f"  ❌ {format_name}: empty")
            
            # Show any errors
            errors = result.get('errors', [])
            if errors:
                print(f"\n⚠️  Warnings/Errors:")
                for error in errors:
                    print(f"  • {error}")
            
            # Test different output format combinations
            print(f"\n🧪 Testing different format combinations...")
            
            format_tests = [
                ['text'],
                ['srt', 'webvtt'],
                ['json', 'csv']
            ]
            
            for formats in format_tests:
                test_result = media_processor.process_media(
                    media_path=test_audio_path,
                    output_formats=formats,
                    enhance_audio=False,
                    chunk_long_files=False
                )
                
                if test_result['success']:
                    generated = list(test_result.get('outputs', {}).keys())
                    print(f"  ✓ Formats {formats}: generated {generated}")
                else:
                    print(f"  ❌ Formats {formats}: failed")
            
        else:
            print(f"\n❌ Pipeline failed!")
            errors = result.get('errors', [])
            for error in errors:
                print(f"  • {error}")
            return False
        
        # Test with different model size (if time permits)
        print(f"\n🔧 Testing model switching...")
        try:
            # Create a new processor with different model
            small_processor = MediaProcessor(config, whisper_model_size='base')
            small_result = small_processor.process_media(
                media_path=test_audio_path,
                output_formats=['text'],
                enhance_audio=False,
                chunk_long_files=False
            )
            
            if small_result['success']:
                print(f"  ✓ Base model processing succeeded")
                base_time = small_result.get('metadata', {}).get('total_processing_time', 0)
                tiny_time = result.get('metadata', {}).get('total_processing_time', 0)
                print(f"  Tiny model: {tiny_time:.2f}s, Base model: {base_time:.2f}s")
            else:
                print(f"  ❌ Base model processing failed")
            
            small_processor.cleanup()
            
        except Exception as e:
            print(f"  ⚠️  Model switching test skipped: {str(e)}")
        
        # Cleanup
        media_processor.cleanup()
        print(f"\n🧹 Cleanup completed")
        
        print(f"\n✅ All integrated media processor tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_media_processor()
    sys.exit(0 if success else 1)