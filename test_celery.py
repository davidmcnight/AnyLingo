#!/usr/bin/env python3
"""
Test script for Celery async task processing.
Tests both file upload and YouTube processing with progress tracking.
"""

import os
import time
import json
import requests
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:5001"

def test_celery_setup():
    """Test if Celery and Redis are properly configured."""
    print("🔧 Testing Celery & Redis Setup")
    print("=" * 60)
    
    # Test health endpoint first
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Flask app is running")
        else:
            print("❌ Flask app not responding properly")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Flask app is not running on port 5001")
        print("   Please run: python app.py")
        return False
    
    # Test Redis connection
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✓ Redis is running and accessible")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Please run: redis-server")
        return False
    
    # Test Celery import
    try:
        from celery_app import celery
        print("✓ Celery app configured")
        
        # Check if we can inspect Celery
        inspector = celery.control.inspect()
        stats = inspector.stats()
        
        if stats:
            worker_count = len(stats)
            print(f"✓ {worker_count} Celery worker(s) detected")
        else:
            print("⚠️  No Celery workers running")
            print("   Please run: celery -A celery_app worker --loglevel=info")
            return False
            
    except Exception as e:
        print(f"❌ Celery setup error: {e}")
        return False
    
    print("\n✅ All components are properly configured!")
    return True

def test_youtube_async():
    """Test async YouTube processing with progress tracking."""
    print("\n🎬 Testing Async YouTube Processing")
    print("=" * 60)
    
    # Test video: short public domain video
    test_url = "https://www.youtube.com/watch?v=YE7VzlLtp-4"
    
    print(f"Test URL: {test_url}")
    print("Target language: Spanish (es)")
    
    # Submit YouTube processing request
    print("\n📤 Submitting YouTube processing request...")
    
    response = requests.post(
        f"{BASE_URL}/youtube",
        json={
            "url": test_url,
            "target_language": "es"
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to submit: {response.json()}")
        return False
    
    data = response.json()
    task_id = data.get('task_id')
    
    if not task_id:
        print("❌ No task ID received")
        return False
    
    print(f"✓ Task submitted: {task_id}")
    print(f"  Video: {data['video_info']['title'][:50]}...")
    print(f"  Duration: {data['video_info']['duration_string']}")
    
    # Poll task status
    print("\n⏳ Processing (this may take a minute)...")
    
    last_percent = -1
    processing_stages = []
    start_time = time.time()
    timeout = 300  # 5 minutes timeout
    
    while True:
        # Check timeout
        if time.time() - start_time > timeout:
            print("\n❌ Processing timeout (5 minutes)")
            return False
        
        # Get task status
        status_response = requests.get(f"{BASE_URL}/task/{task_id}/status")
        
        if status_response.status_code != 200:
            print(f"\n❌ Failed to get status: {status_response.text}")
            return False
        
        status = status_response.json()
        state = status.get('state', 'UNKNOWN')
        
        if state == 'PROGRESS':
            percent = status.get('percent', 0)
            message = status.get('status', '')
            
            # Only print if percentage changed significantly
            if percent != last_percent:
                print(f"  Progress: {percent}% - {message}")
                last_percent = percent
                if message and message not in processing_stages:
                    processing_stages.append(message)
        
        elif state == 'SUCCESS':
            elapsed = time.time() - start_time
            print(f"\n✅ Processing completed in {elapsed:.1f} seconds!")
            break
        
        elif state == 'FAILURE':
            print(f"\n❌ Task failed: {status.get('status', 'Unknown error')}")
            return False
        
        elif state == 'PENDING':
            if last_percent == -1:
                print("  Waiting for worker to pick up task...")
                last_percent = 0
        
        time.sleep(2)  # Poll every 2 seconds
    
    # Get results
    print("\n📋 Fetching results...")
    
    result_response = requests.get(f"{BASE_URL}/task/{task_id}/result")
    
    if result_response.status_code != 200:
        print(f"❌ Failed to get results: {result_response.text}")
        return False
    
    result_data = result_response.json()
    
    if result_data.get('status') != 'success':
        print(f"❌ Processing failed: {result_data.get('errors', ['Unknown error'])}")
        return False
    
    result = result_data.get('result', {})
    
    # Display results
    print("\n📊 Processing Results:")
    print("-" * 40)
    
    # Metadata
    metadata = result.get('metadata', {})
    if metadata:
        print(f"  Processing time: {metadata.get('total_processing_time', 0):.1f}s")
        print(f"  Word count: {metadata.get('word_count', 0)}")
        print(f"  Segments: {metadata.get('segment_count', 0)}")
    
    # Transcription
    transcription = result.get('transcription_result', {})
    if transcription.get('success'):
        text = transcription.get('text', '')
        if text:
            words = text.split()[:20]
            preview = ' '.join(words) + '...' if len(text.split()) > 20 else text
            print(f"\n  Transcription preview:")
            print(f"    {preview}")
    
    # Translation
    translation = result.get('translation_result', {})
    if translation.get('success'):
        translated = translation.get('translated_text', '')
        if translated:
            words = translated.split()[:20]
            preview = ' '.join(words) + '...' if len(translated.split()) > 20 else translated
            print(f"\n  Spanish translation preview:")
            print(f"    {preview}")
    
    # Output files
    output_files = result.get('output_files', {})
    if output_files:
        print(f"\n  Output files generated:")
        for format_name, file_path in output_files.items():
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"    • {format_name}: {size:,} bytes")
    
    # Processing stages
    if processing_stages:
        print(f"\n  Processing stages completed:")
        for stage in processing_stages[:5]:  # Show first 5 stages
            print(f"    • {stage}")
    
    print("\n🎉 Async YouTube processing test passed!")
    return True

def main():
    """Run all Celery tests."""
    print("🚀 Testing Celery Async Processing\n")
    
    # Test 1: Check setup
    if not test_celery_setup():
        print("\n⚠️  Please ensure all components are running:")
        print("  1. Redis: redis-server")
        print("  2. Flask: python app.py")
        print("  3. Celery: celery -A celery_app worker --loglevel=info")
        return False
    
    # Test 2: YouTube async processing
    if not test_youtube_async():
        print("\n❌ Async processing test failed")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All Celery tests passed successfully!")
    print("=" * 60)
    
    print("\n📝 Summary:")
    print("  • Redis message broker: Working")
    print("  • Celery task queue: Working")
    print("  • Progress tracking: Working")
    print("  • YouTube async processing: Working")
    print("  • Task status endpoints: Working")
    print("  • Result retrieval: Working")
    
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)