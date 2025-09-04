#!/usr/bin/env python3
"""
Create a simple test audio file for transcription testing.
"""

import numpy as np
import soundfile as sf
import os

def create_test_audio():
    """Create a simple test audio file with a sine wave tone."""
    
    print("🎵 Creating test audio file...")
    
    # Audio parameters
    duration = 3.0  # 3 seconds
    sample_rate = 16000  # 16kHz (optimal for Whisper)
    frequency = 440  # A4 note
    
    # Generate time array
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Create a simple sine wave with envelope
    audio = np.sin(2 * np.pi * frequency * t)
    
    # Add envelope to make it more natural (fade in/out)
    fade_samples = int(0.1 * sample_rate)  # 0.1 second fade
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    
    audio[:fade_samples] *= fade_in
    audio[-fade_samples:] *= fade_out
    
    # Reduce volume to reasonable level
    audio *= 0.3
    
    # Ensure temp directory exists
    os.makedirs('./temp', exist_ok=True)
    
    # Save the audio file
    output_path = './temp/test_tone.wav'
    sf.write(output_path, audio, sample_rate)
    
    file_size = os.path.getsize(output_path)
    print(f"✓ Test audio created: {output_path}")
    print(f"  Duration: {duration}s")
    print(f"  Sample rate: {sample_rate} Hz") 
    print(f"  File size: {file_size} bytes")
    
    return output_path

if __name__ == "__main__":
    create_test_audio()