#!/usr/bin/env python3
"""
Test the complete YouTube to transcription pipeline.
"""

import os
import sys
import time
from config import Config
from utils.media_processor import MediaProcessor

def test_youtube_pipeline():
    """Test the complete YouTube processing pipeline."""
    
    print("🎬 Testing Complete YouTube → Transcription Pipeline")
    print("=" * 70)
    
    try:
        # Initialize
        config = Config()
        media_processor = MediaProcessor(config, whisper_model_size='tiny')  # Use tiny for faster testing
        
        print(f"✓ MediaProcessor initialized")
        print(f"  Whisper model: tiny (fast mode)")
        print(f"  YouTube handler: ready")
        print(f"  Transcription service: ready")
        
        # Test video: A short public domain video
        # "Big Buck Bunny" - short version, 1 minute
        test_url = "https://www.youtube.com/watch?v=YE7VzlLtp-4"
        
        print(f"\n🎯 Test Video URL:")
        print(f"  {test_url}")
        
        # Check if it's a valid YouTube URL
        if media_processor.is_youtube_url(test_url):
            print(f"  ✓ Valid YouTube URL detected")
        else:
            print(f"  ❌ Invalid YouTube URL")
            return False
        
        # Get video info first
        print(f"\n📊 Fetching Video Information...")
        info_start = time.time()
        video_info = media_processor.youtube_handler.get_video_info(test_url)
        info_time = time.time() - info_start
        
        if video_info.get('success'):
            print(f"✓ Video info retrieved in {info_time:.2f}s")
            print(f"  Title: {video_info.get('title', 'Unknown')[:60]}...")
            print(f"  Duration: {video_info.get('duration_string', 'Unknown')}")
            print(f"  Uploader: {video_info.get('uploader', 'Unknown')}")
            print(f"  Views: {video_info.get('view_count', 0):,}")
        else:
            print(f"❌ Failed to get video info: {video_info.get('error')}")
            return False
        
        # Process the YouTube video
        print(f"\n🔄 Processing YouTube Video...")
        print(f"  This will:")
        print(f"    1. Download audio from YouTube")
        print(f"    2. Optimize audio for transcription")
        print(f"    3. Transcribe with Whisper")
        print(f"    4. Generate output formats")
        print(f"\n  Starting pipeline...")
        
        # Progress callback for download
        last_progress = 0
        def progress_callback(progress):
            nonlocal last_progress
            percent = progress.get('percent', 0)
            if percent - last_progress >= 20:  # Update every 20%
                print(f"    Download progress: {percent:.0f}%")
                last_progress = percent
        
        pipeline_start = time.time()
        
        result = media_processor.process_youtube(
            youtube_url=test_url,
            output_formats=['text', 'srt', 'json'],
            progress_callback=progress_callback
        )
        
        pipeline_time = time.time() - pipeline_start
        
        if result['success']:
            print(f"\n✅ Pipeline completed successfully in {pipeline_time:.1f}s!")
            
            # Show processing stages
            print(f"\n📋 Processing Stages:")
            for stage_name, stage_data in result.get('processing_stages', {}).items():
                if stage_data.get('success'):
                    duration = stage_data.get('duration', 0)
                    message = stage_data.get('message', '')
                    print(f"  ✓ {stage_name}: {duration:.2f}s - {message}")
            
            # Show metadata
            metadata = result.get('metadata', {})
            if metadata:
                print(f"\n📊 Processing Metrics:")
                print(f"  Total time: {metadata.get('total_processing_time', 0):.1f}s")
                print(f"  Audio duration: {metadata.get('audio_duration', 0):.1f}s")
                print(f"  Processing ratio: {metadata.get('processing_ratio', 0):.2f}x")
                print(f"  Language detected: {metadata.get('language_detected', 'unknown')}")
                print(f"  Segments: {metadata.get('segment_count', 0)}")
                print(f"  Words: {metadata.get('word_count', 0)}")
                
                # YouTube specific metadata
                print(f"\n📺 YouTube Metadata:")
                print(f"  Video ID: {metadata.get('youtube_video_id', 'unknown')}")
                print(f"  Title: {metadata.get('youtube_title', 'Unknown')[:50]}...")
                print(f"  Uploader: {metadata.get('youtube_uploader', 'Unknown')}")
                print(f"  Views: {metadata.get('youtube_view_count', 0):,}")
            
            # Show transcription
            transcription = result.get('transcription_result', {})
            if transcription.get('success'):
                text = transcription.get('text', '')
                if text:
                    words = text.split()
                    preview_words = 30
                    if len(words) > preview_words:
                        preview = ' '.join(words[:preview_words]) + '...'
                    else:
                        preview = text
                    
                    print(f"\n📝 Transcription Preview:")
                    print(f'  "{preview}"')
                    
                    # Show some segments with timestamps
                    segments = transcription.get('segments', [])
                    if segments:
                        print(f"\n⏱️  First Few Segments:")
                        for i, seg in enumerate(segments[:3]):
                            start = seg.get('start', 0)
                            end = seg.get('end', 0)
                            text = seg.get('text', '').strip()
                            if text:
                                print(f"  [{start:.1f}s-{end:.1f}s]: {text[:60]}...")
                else:
                    print(f"\n📝 No text transcribed (might be music/no speech)")
            
            # Check outputs
            outputs = result.get('outputs', {})
            if outputs:
                print(f"\n📁 Generated Output Formats:")
                for format_name, content in outputs.items():
                    if content:
                        print(f"  ✓ {format_name}: {len(content)} bytes")
                        
                        # Show SRT preview if available
                        if format_name == 'srt' and content:
                            lines = content.split('\n')[:8]
                            if lines and lines[0]:
                                print(f"\n  SRT Subtitle Preview:")
                                for line in lines:
                                    if line:
                                        print(f"    {line}")
            
            # Check for any warnings
            errors = result.get('errors', [])
            if errors:
                print(f"\n⚠️  Warnings:")
                for error in errors:
                    print(f"  • {error}")
            
            print(f"\n🎉 SUCCESS: YouTube video fully processed!")
            print(f"  • Downloaded from YouTube ✓")
            print(f"  • Extracted audio ✓")
            print(f"  • Transcribed with Whisper ✓")
            print(f"  • Generated output formats ✓")
            
            return True
            
        else:
            print(f"\n❌ Pipeline failed!")
            errors = result.get('errors', [])
            for error in errors:
                print(f"  • {error}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        if 'media_processor' in locals():
            media_processor.cleanup()
            print(f"\n🧹 Cleanup completed")

if __name__ == "__main__":
    success = test_youtube_pipeline()
    sys.exit(0 if success else 1)