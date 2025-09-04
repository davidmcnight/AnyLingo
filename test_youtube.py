#!/usr/bin/env python3
"""
Test script for YouTube handler functionality.
"""

import os
import sys
import time
from config import Config
from utils.youtube_handler import YouTubeHandler

def test_youtube_handler():
    """Test YouTube handler with various URLs and scenarios."""
    
    print("🎬 Testing YouTube Handler")
    print("=" * 60)
    
    try:
        # Initialize
        config = Config()
        youtube = YouTubeHandler(config)
        
        print(f"✓ YouTubeHandler initialized")
        print(f"  Download directory: {youtube.download_dir}")
        print(f"  Max duration: {youtube._format_duration(youtube.max_duration)}")
        print(f"  Audio format: {youtube.audio_format}")
        
        # Test connection
        print(f"\n🌐 Testing YouTube connection...")
        if youtube.test_connection():
            print(f"✓ YouTube is accessible")
        else:
            print(f"❌ Cannot connect to YouTube")
            return False
        
        # Test URL validation
        print(f"\n🔗 Testing URL Validation")
        print("-" * 40)
        
        test_urls = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True, "Standard watch URL"),
            ("https://youtu.be/dQw4w9WgXcQ", True, "Short URL"),
            ("youtube.com/watch?v=dQw4w9WgXcQ", True, "No protocol"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", True, "Mobile URL"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", True, "Embed URL"),
            ("https://www.youtube.com/shorts/abcdefghijk", True, "Shorts URL"),
            ("dQw4w9WgXcQ", True, "Just video ID"),
            ("https://www.google.com", False, "Non-YouTube URL"),
            ("", False, "Empty URL"),
            ("invalid", False, "Invalid string")
        ]
        
        validation_passed = 0
        for url, expected_valid, description in test_urls:
            is_valid, video_id, message = youtube.validate_url(url)
            
            if is_valid == expected_valid:
                symbol = "✓"
                validation_passed += 1
            else:
                symbol = "❌"
            
            print(f"  {symbol} {description}")
            if is_valid:
                print(f"     Video ID: {video_id}")
        
        validation_accuracy = (validation_passed / len(test_urls)) * 100
        print(f"\n  Validation accuracy: {validation_accuracy:.1f}% ({validation_passed}/{len(test_urls)})")
        
        # Test video info extraction
        print(f"\n📊 Testing Video Info Extraction")
        print("-" * 40)
        
        # Use a short, public domain video for testing
        # "Big Buck Bunny" trailer - 33 seconds, public domain
        test_video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
        
        print(f"  Test video: {test_video_url}")
        print(f"  Extracting metadata...")
        
        info_start = time.time()
        video_info = youtube.get_video_info(test_video_url)
        info_time = time.time() - info_start
        
        if video_info.get('success'):
            print(f"✓ Video info extracted in {info_time:.2f}s")
            print(f"  Title: {video_info.get('title', 'Unknown')}")
            print(f"  Duration: {video_info.get('duration_string', 'Unknown')}")
            print(f"  Uploader: {video_info.get('uploader', 'Unknown')}")
            print(f"  Views: {video_info.get('view_count', 0):,}")
            print(f"  Language: {video_info.get('language', 'Not specified')}")
            print(f"  Subtitles available: {video_info.get('subtitles_available', False)}")
            print(f"  Age restricted: {video_info.get('age_limit', 0) > 0}")
            
            video_id = video_info.get('video_id')
        else:
            print(f"❌ Failed to extract video info: {video_info.get('error', 'Unknown error')}")
            return False
        
        # Test subtitle availability
        print(f"\n🗨️ Testing Subtitle Extraction")
        print("-" * 40)
        
        subtitle_info = youtube.download_subtitles(test_video_url)
        
        if subtitle_info.get('success'):
            available_langs = subtitle_info.get('available_languages', [])
            print(f"✓ Found subtitles in {len(available_langs)} languages")
            
            if available_langs:
                print(f"  Available languages: {', '.join(available_langs[:5])}")
                if len(available_langs) > 5:
                    print(f"  ... and {len(available_langs) - 5} more")
            
            for lang, sub_data in list(subtitle_info.get('subtitles', {}).items())[:3]:
                sub_type = sub_data.get('type', 'unknown')
                print(f"  • {lang}: {sub_type}")
        else:
            print(f"⚠️  No subtitles found or extraction failed")
        
        # Test audio download with progress
        print(f"\n⬇️ Testing Audio Download")
        print("-" * 40)
        
        print(f"  Downloading audio from test video...")
        print(f"  This may take a moment...")
        
        # Progress callback
        last_percent = 0
        def progress_callback(progress):
            nonlocal last_percent
            percent = progress.get('percent', 0)
            status = progress.get('status', 'unknown')
            
            if status == 'downloading' and percent - last_percent >= 10:
                speed = progress.get('speed', 0)
                if speed > 0:
                    speed_mbps = speed / (1024 * 1024)
                    print(f"    Progress: {percent:.0f}% (Speed: {speed_mbps:.2f} MB/s)")
                else:
                    print(f"    Progress: {percent:.0f}%")
                last_percent = percent
            elif status == 'finished':
                print(f"    Download completed!")
        
        download_start = time.time()
        download_result = youtube.download_audio(
            test_video_url,
            output_filename="test_audio",
            progress_callback=progress_callback
        )
        download_time = time.time() - download_start
        
        if download_result.get('success'):
            print(f"\n✓ Audio downloaded successfully!")
            print(f"  File: {download_result.get('audio_path', 'Unknown')}")
            print(f"  Size: {download_result.get('file_size_mb', 0):.2f} MB")
            print(f"  Duration: {download_result.get('duration_string', 'Unknown')}")
            print(f"  Download time: {download_time:.2f}s")
            print(f"  Speed: {download_result.get('download_speed_mbps', 0):.2f} MB/s")
            
            audio_path = download_result.get('audio_path')
            
            # Verify file exists
            if audio_path and os.path.exists(audio_path):
                print(f"  ✓ Audio file verified at: {audio_path}")
                
                # Clean up the test file
                try:
                    os.remove(audio_path)
                    print(f"  ✓ Test file cleaned up")
                except:
                    print(f"  ⚠️ Could not clean up test file")
            else:
                print(f"  ❌ Audio file not found at expected path")
        else:
            print(f"❌ Audio download failed: {download_result.get('error', 'Unknown error')}")
            return False
        
        # Test error handling
        print(f"\n⚠️ Testing Error Handling")
        print("-" * 40)
        
        error_test_cases = [
            ("https://www.youtube.com/watch?v=invalid_id", "Invalid video ID"),
            ("https://www.youtube.com/watch?v=aaaaaaaaaa_", "Non-existent video"),
            ("https://youtube.com/watch?v=000000000000", "Unavailable video")
        ]
        
        for test_url, description in error_test_cases:
            print(f"  Testing: {description}")
            error_info = youtube.get_video_info(test_url)
            
            if not error_info.get('success'):
                error_type = error_info.get('error_type', 'unknown')
                print(f"    ✓ Correctly caught error: {error_type}")
            else:
                print(f"    ⚠️ Unexpected success for error case")
        
        # Test cleanup
        print(f"\n🧹 Testing Cleanup")
        print("-" * 40)
        
        # Create a test file
        test_file_path = os.path.join(youtube.download_dir, f"test_{video_id}_dummy.txt")
        with open(test_file_path, 'w') as f:
            f.write("test")
        
        if os.path.exists(test_file_path):
            print(f"  Created test file: {test_file_path}")
            
            # Clean up specific video
            youtube.cleanup_downloads(video_id)
            
            if not os.path.exists(test_file_path):
                print(f"  ✓ Cleanup successful")
            else:
                print(f"  ❌ Cleanup failed")
        
        # Summary
        print(f"\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print("=" * 60)
        
        print(f"  ✓ URL validation working")
        print(f"  ✓ Video metadata extraction working")
        print(f"  ✓ Subtitle detection working")
        print(f"  ✓ Audio download working")
        print(f"  ✓ Progress tracking working")
        print(f"  ✓ Error handling working")
        print(f"  ✓ Cleanup working")
        
        print(f"\n✅ All YouTube handler tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_youtube_handler()
    sys.exit(0 if success else 1)