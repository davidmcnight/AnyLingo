#!/usr/bin/env python3
"""
Create a test audio file with actual speech using text-to-speech.
"""

import os
import subprocess
import sys

def create_speech_audio():
    """Create a test audio file with actual speech using macOS say command."""
    
    print("🎙️ Creating speech test audio file...")
    
    # Text to speak
    test_text = "Hello, this is a test of the AnyLingo transcription system. The quick brown fox jumps over the lazy dog. Testing one, two, three."
    
    # Ensure temp directory exists
    os.makedirs('./temp', exist_ok=True)
    
    # Output path
    output_path = './temp/test_speech.wav'
    
    try:
        # Use macOS 'say' command to generate speech
        # -o: output file
        # -v: voice (default system voice)
        # --data-format=LEF32@16000: 16kHz sample rate (optimal for Whisper)
        cmd = [
            'say',
            '-o', output_path,
            '--data-format=LEF32@16000',
            test_text
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Speech audio created: {output_path}")
            print(f"  Text: \"{test_text}\"")
            print(f"  File size: {file_size} bytes")
            return output_path, test_text
        else:
            print(f"❌ Failed to create speech audio")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            return None, None
            
    except Exception as e:
        print(f"❌ Error creating speech audio: {str(e)}")
        return None, None

if __name__ == "__main__":
    audio_path, text = create_speech_audio()
    if audio_path:
        print(f"\n✅ Test audio ready for transcription testing")
        print(f"   Expected transcription: \"{text}\"")
    else:
        print(f"\n❌ Failed to create test audio")
        sys.exit(1)