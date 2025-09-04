#!/usr/bin/env python3
"""
Simple test to verify Celery is working.
"""

from celery import Celery
import time

# Create a simple Celery app
app = Celery('test', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@app.task
def add(x, y):
    """Simple add task for testing."""
    time.sleep(2)  # Simulate work
    return x + y

if __name__ == "__main__":
    print("Testing basic Celery functionality...")
    
    # Send task
    result = add.delay(4, 6)
    print(f"Task ID: {result.id}")
    print("Waiting for result...")
    
    # Get result
    try:
        final_result = result.get(timeout=10)
        print(f"Result: 4 + 6 = {final_result}")
        print("✅ Celery is working!")
    except Exception as e:
        print(f"❌ Celery test failed: {e}")