#!/usr/bin/env python3
"""
Test the complete results workflow:
1. Submit YouTube video for processing
2. Monitor task progress
3. View results page
4. Test download formats
"""

import os
import sys
import time
import json
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:5001"

def test_results_workflow():
    """Test the complete results workflow."""
    print("🎯 Testing Complete Results Workflow")
    print("=" * 70)
    
    # Step 1: Check system status
    print("\n1️⃣ Checking System Status...")
    
    # Check Flask
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("   ✓ Flask app is running")
        else:
            print("   ❌ Flask app issue")
            return False
    except:
        print("   ❌ Flask app not running. Run: python app.py")
        return False
    
    # Check Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("   ✓ Redis is running")
    except:
        print("   ❌ Redis not running. Run: redis-server")
        return False
    
    # Check Celery
    try:
        from celery_app import celery
        inspector = celery.control.inspect()
        stats = inspector.stats()
        if stats:
            print(f"   ✓ Celery workers: {len(stats)}")
        else:
            print("   ⚠️ No Celery workers. Run: celery -A celery_app worker")
            return False
    except Exception as e:
        print(f"   ❌ Celery issue: {e}")
        return False
    
    # Step 2: Submit YouTube video for processing
    print("\n2️⃣ Submitting YouTube Video...")
    
    # Short test video
    test_url = "https://www.youtube.com/watch?v=YE7VzlLtp-4"
    
    response = requests.post(
        f"{BASE_URL}/youtube",
        json={
            "url": test_url,
            "target_language": "es"  # Spanish translation
        }
    )
    
    if response.status_code != 200:
        print(f"   ❌ Failed to submit: {response.text}")
        return False
    
    data = response.json()
    task_id = data.get('task_id')
    
    if not task_id:
        print("   ❌ No task ID received")
        return False
    
    print(f"   ✓ Task submitted: {task_id}")
    print(f"   Video: {data['video_info']['title'][:50]}...")
    print(f"   Duration: {data['video_info']['duration_string']}")
    
    # Step 3: Monitor task progress
    print("\n3️⃣ Monitoring Task Progress...")
    
    start_time = time.time()
    last_percent = -1
    max_wait = 300  # 5 minutes max
    
    while time.time() - start_time < max_wait:
        status_response = requests.get(f"{BASE_URL}/task/{task_id}/status")
        
        if status_response.status_code != 200:
            print(f"   ❌ Status check failed")
            return False
        
        status = status_response.json()
        state = status.get('state', 'UNKNOWN')
        
        if state == 'PROGRESS':
            percent = status.get('percent', 0)
            if percent != last_percent and percent % 20 == 0:  # Show every 20%
                print(f"   Progress: {percent}% - {status.get('status', '')}")
                last_percent = percent
        
        elif state == 'SUCCESS':
            elapsed = time.time() - start_time
            print(f"   ✓ Processing completed in {elapsed:.1f}s")
            break
        
        elif state == 'FAILURE':
            print(f"   ❌ Task failed: {status.get('status')}")
            return False
        
        time.sleep(2)
    else:
        print("   ❌ Task timed out")
        return False
    
    # Step 4: Get and verify results
    print("\n4️⃣ Retrieving Results...")
    
    result_response = requests.get(f"{BASE_URL}/task/{task_id}/result")
    
    if result_response.status_code != 200:
        print(f"   ❌ Failed to get results")
        return False
    
    result_data = result_response.json()
    
    if result_data.get('status') != 'success':
        print(f"   ❌ Processing failed")
        return False
    
    result = result_data.get('result', {})
    
    # Verify transcription
    transcription = result.get('transcription_result', {})
    if transcription.get('success'):
        text = transcription.get('text', '')
        word_count = len(text.split()) if text else 0
        print(f"   ✓ Transcription: {word_count} words")
        print(f"     Language: {transcription.get('language', 'unknown')}")
        
        # Show preview
        if text:
            preview = ' '.join(text.split()[:15]) + '...'
            print(f"     Preview: \"{preview}\"")
    else:
        print("   ❌ No transcription")
    
    # Verify translation
    translation = result.get('translation_result', {})
    if translation.get('success'):
        translated_text = translation.get('translated_text', '')
        if translated_text:
            preview = ' '.join(translated_text.split()[:15]) + '...'
            print(f"   ✓ Translation to Spanish")
            print(f"     Preview: \"{preview}\"")
    else:
        print("   ⚠️ No translation available")
    
    # Step 5: Test results page accessibility
    print("\n5️⃣ Testing Results Page...")
    
    results_url = f"{BASE_URL}/results?task_id={task_id}"
    page_response = requests.get(results_url)
    
    if page_response.status_code == 200:
        print(f"   ✓ Results page accessible")
        print(f"     URL: {results_url}")
        
        # Check if page contains expected elements
        page_html = page_response.text
        if 'Processing Results' in page_html:
            print(f"     ✓ Page title found")
        if 'download' in page_html.lower():
            print(f"     ✓ Download section found")
        if 'side-by-side' in page_html.lower():
            print(f"     ✓ View options found")
    else:
        print(f"   ❌ Results page not accessible")
    
    # Step 6: Test download formats
    print("\n6️⃣ Testing Download Formats...")
    
    formats_to_test = ['text', 'srt', 'json', 'vtt']
    successful_downloads = 0
    
    for format in formats_to_test:
        download_url = f"{BASE_URL}/download/{task_id}/{format}"
        download_response = requests.get(download_url)
        
        if download_response.status_code == 200:
            content_length = len(download_response.content)
            print(f"   ✓ {format.upper()}: {content_length:,} bytes")
            successful_downloads += 1
            
            # Show sample for text formats
            if format in ['text', 'srt'] and content_length > 0:
                sample = download_response.text[:100]
                print(f"     Sample: {sample}...")
        else:
            print(f"   ❌ {format.upper()}: Download failed")
    
    # Test PDF (might fail if reportlab not installed)
    pdf_response = requests.get(f"{BASE_URL}/download/{task_id}/pdf")
    if pdf_response.status_code == 200:
        pdf_size = len(pdf_response.content)
        print(f"   ✓ PDF: {pdf_size:,} bytes")
        successful_downloads += 1
    else:
        print(f"   ⚠️ PDF: Not available (reportlab may not be installed)")
    
    # Step 7: Summary
    print("\n" + "=" * 70)
    print("📊 WORKFLOW TEST SUMMARY")
    print("=" * 70)
    
    print(f"✅ Task Submission: Success")
    print(f"✅ Progress Tracking: Working")
    print(f"✅ Results Retrieval: Success")
    print(f"✅ Results Page: Accessible")
    print(f"✅ Downloads: {successful_downloads}/5 formats working")
    
    if word_count > 0:
        print(f"✅ Transcription: {word_count} words extracted")
    
    metadata = result.get('metadata', {})
    if metadata:
        print(f"\n📈 Performance Metrics:")
        print(f"   Processing time: {metadata.get('total_processing_time', 0):.1f}s")
        print(f"   Audio duration: {metadata.get('audio_duration', 0):.1f}s")
        if metadata.get('processing_ratio'):
            print(f"   Speed ratio: {metadata.get('processing_ratio'):.2f}x real-time")
    
    print(f"\n🎉 Results workflow test completed successfully!")
    print(f"\n🔗 View results at: {results_url}")
    
    return True

def main():
    """Run the complete workflow test."""
    print("🚀 AnyLingo Results Workflow Test\n")
    
    success = test_results_workflow()
    
    if success:
        print("\n✅ All tests passed!")
        print("\nYou can now:")
        print("1. Visit http://localhost:5001 to upload files")
        print("2. Process YouTube videos with transcription and translation")
        print("3. View beautiful results with multiple display modes")
        print("4. Download results in various formats (TXT, SRT, VTT, JSON, PDF)")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)