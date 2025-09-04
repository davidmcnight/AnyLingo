#!/usr/bin/env python3
"""Monitor a running task's progress."""
import sys
import time
import requests

def monitor_task(task_id):
    """Monitor task progress until completion."""
    url = f"http://localhost:5001/task/{task_id}/status"
    
    print(f"Monitoring task: {task_id}")
    print("-" * 60)
    
    last_status = None
    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                state = data.get('state', 'UNKNOWN')
                
                if state == 'PROGRESS':
                    status = data.get('status', '')
                    percent = data.get('percent', 0)
                    if status != last_status:
                        print(f"[{percent:3}%] {status}")
                        last_status = status
                        
                elif state == 'SUCCESS':
                    print("\n✅ Task completed successfully!")
                    break
                    
                elif state == 'FAILURE':
                    print(f"\n❌ Task failed: {data.get('status', 'Unknown error')}")
                    break
                    
                elif state == 'PENDING':
                    if last_status != 'PENDING':
                        print("⏳ Task pending...")
                        last_status = 'PENDING'
                        
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
            break
        except Exception as e:
            print(f"Error checking status: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python monitor_task.py <task_id>")
        sys.exit(1)
    
    monitor_task(sys.argv[1])