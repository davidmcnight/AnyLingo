# AnyLingo Startup Guide

## Prerequisites
- Python 3.9+ with virtual environment activated
- Redis installed (`brew install redis` on macOS)
- FFmpeg installed (`brew install ffmpeg` on macOS)

## Starting the Application

Open **3 separate terminal windows** and run the following commands in order:

### Terminal 1: Redis Server
```bash
redis-server
```
✅ **Success indicator**: You should see the Redis ASCII art logo and "Ready to accept connections"

### Terminal 2: Celery Worker
```bash
cd /Users/davidmcnight/Documents/Github/AnyLingo
source venv/bin/activate
PYTHONPATH=/Users/davidmcnight/Documents/Github/AnyLingo celery -A celery_app worker --loglevel=info --concurrency=1 --pool=solo
```
✅ **Success indicator**: You should see "celery@Davids-Elastic-Mac ready"

### Terminal 3: Flask Application
```bash
cd /Users/davidmcnight/Documents/Github/AnyLingo
source venv/bin/activate
python app.py
```
✅ **Success indicator**: You should see "Running on http://127.0.0.1:5001"

## Verify Everything is Running

In a new terminal, test the health endpoint:
```bash
curl http://localhost:5001/health
```

Expected response:
```json
{"status": "healthy", "message": "AnyLingo API is running"}
```

## Processing a YouTube Video

### Short video test (recommended first):
```bash
curl -X POST http://localhost:5001/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=YE7VzlLtp-4", "target_language": "es"}'
```

### Monitor task progress:
```bash
python monitor_task.py <task_id>
```

## Stopping the Application

Kill all processes:
```bash
pkill -f "python app.py"
pkill -f "celery.*worker"
pkill -f redis-server
```

## Troubleshooting

### Port 5001 already in use:
```bash
lsof -i :5001 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Redis already running:
```bash
pkill -f redis-server
```

### Memory issues with long videos:
The `--concurrency=1 --pool=solo` flags in the Celery command prevent memory crashes but process slower.

## Configuration

### Environment Variables (optional):
Create a `.env` file:
```bash
YOUTUBE_MAX_DURATION=7200  # 2 hours in seconds
WHISPER_MODEL_SIZE=base    # tiny, base, small, medium, large
```

### For longer videos (2+ hours):
Edit `config.py` and increase `YOUTUBE_MAX_DURATION`

## Important Notes

1. **Start services in order**: Redis → Celery → Flask
2. **Memory optimization**: The single worker (`--pool=solo`) prevents crashes with 75+ minute videos
3. **Processing time**: Long videos (1+ hour) may take 10-20 minutes to process
4. **Whisper models**: 
   - `tiny` = fastest, less accurate
   - `base` = balanced (default)
   - `large` = slowest, most accurate

## Web Interface

Once running, open your browser to:
```
http://localhost:5001
```

You can:
- Upload audio/video files
- Process YouTube videos
- View results with side-by-side transcription/translation
- Download results in multiple formats (TXT, SRT, VTT, JSON, PDF)