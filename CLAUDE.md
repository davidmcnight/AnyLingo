# CLAUDE.md - AnyLingo Project Context

## Project Overview
AnyLingo is a comprehensive web application for video/audio transcription and translation using OpenAI Whisper and multiple translation APIs. This Flask-based application allows users to upload media files or provide YouTube URLs for automatic transcription and translation into 50+ languages.

## Quick Start Commands

### Initial Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (macOS)
brew install ffmpeg redis

# Install system dependencies (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install ffmpeg redis-server
```

### Running the Application
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A celery_app worker --loglevel=info

# Terminal 3: Start Flask app
python app.py

# Access at: http://localhost:5000
```

## Project Structure
```
anylingo/
├── app.py                      # Main Flask application & routes
├── celery_app.py              # Celery configuration
├── celeryconfig.py            # Celery settings
├── tasks.py                   # Background processing tasks
├── config.py                  # Application configuration
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (create from .env.example)
├── static/
│   ├── css/
│   │   └── styles.css        # Custom CSS styles
│   ├── js/
│   │   └── main.js          # Frontend JavaScript
│   └── uploads/             # Temporary file storage
├── templates/
│   ├── base.html            # Base template with navigation
│   ├── index.html           # Upload interface
│   └── results.html         # Results display page
├── utils/
│   ├── __init__.py
│   ├── audio_processor.py   # FFmpeg audio extraction
│   ├── transcription.py     # Whisper integration
│   ├── translation.py       # Multi-provider translation
│   ├── file_handler.py     # File upload validation
│   └── youtube_handler.py  # YouTube download with yt-dlp
└── tests/
    └── test_basic.py       # Basic unit tests
```

## Key Features

### 1. File Processing
- **Supported Formats**: MP4, MP3, WAV, MOV, AVI, WebM, MKV, FLAC, M4A, OGG
- **Max File Size**: 500MB
- **Audio Extraction**: Automatic extraction from video files using FFmpeg
- **Quality Enhancement**: Audio preprocessing for better transcription

### 2. Transcription (OpenAI Whisper)
- **Models**: tiny, base, small, medium, large
- **Language Detection**: Automatic with confidence scores
- **Timestamp Generation**: For subtitle files
- **Segment Processing**: Chunked processing for long files

### 3. Translation Services
- **Primary**: Azure Translator API
- **Secondary**: Google Translate API
- **Tertiary**: LibreTranslate (self-hosted option)
- **Fallback**: Google Translate free tier
- **Languages**: 50+ major world languages

### 4. YouTube Integration
- **URL Processing**: Direct YouTube video processing
- **Quality Selection**: Automatic best audio quality
- **Metadata Extraction**: Title, duration, uploader info
- **Caption Download**: Existing YouTube captions if available

### 5. Output Formats
- **Text Files**: Plain text (.txt)
- **Subtitles**: SRT and WebVTT formats
- **PDF Report**: Side-by-side comparison
- **JSON Export**: Complete data with metadata

## Environment Variables (.env)

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
MAX_FILE_SIZE=524288000
UPLOAD_FOLDER=./static/uploads
TEMP_FOLDER=./temp

# Whisper Model (tiny, base, small, medium, large)
WHISPER_MODEL_SIZE=base

# Azure Translator (Primary)
AZURE_TRANSLATOR_KEY=your_azure_key
AZURE_TRANSLATOR_REGION=your_region

# Google Translate API (Secondary)
GOOGLE_TRANSLATE_API_KEY=your_google_key

# LibreTranslate (Optional)
LIBRETRANSLATE_URL=https://libretranslate.com

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_HOUR=100
```

## API Endpoints

### Core Routes
- `GET /` - Main upload interface
- `POST /upload` - File upload handler
- `POST /youtube` - YouTube URL processor
- `GET /status/<task_id>` - Check processing status
- `GET /results/<task_id>` - Display results
- `GET /download/<task_id>/<type>` - Download files

### Utility Routes
- `GET /supported-languages` - List available languages
- `GET /health` - Health check endpoint

## Common Development Tasks

### Adding a New Language
1. Update `utils/translation.py` language dictionary
2. Add option to language selects in `templates/index.html`
3. Test translation API support

### Changing Whisper Model
1. Update `WHISPER_MODEL_SIZE` in `.env`
2. Models: tiny (39M), base (74M), small (244M), medium (769M), large (1550M)
3. Restart application

### Debugging Processing Issues
1. Check Celery worker logs for errors
2. Verify Redis is running: `redis-cli ping`
3. Check `/temp` folder for intermediate files
4. Review task status at `/status/<task_id>`

### Testing File Upload
```bash
# Test with curl
curl -X POST -F "file=@test.mp3" -F "target_language=es" http://localhost:5000/upload

# Test YouTube processing
curl -X POST -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=...", "target_language":"fr"}' \
  http://localhost:5000/youtube
```

## Performance Optimization

### For Production
1. **Use GPU**: Install CUDA and pytorch-cuda for faster Whisper processing
2. **Increase Workers**: `celery -A celery_app worker --concurrency=4`
3. **Add Caching**: Implement Redis caching for repeated translations
4. **Use CDN**: Serve static files through CDN
5. **Database**: Add PostgreSQL for persistent result storage

### Memory Management
- Large files are automatically chunked (5-minute segments)
- Temporary files are cleaned up after processing
- Use smaller Whisper models for limited memory

## Troubleshooting

### Common Issues and Solutions

#### FFmpeg Not Found
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows: Download from https://ffmpeg.org
```

#### Whisper Model Download Fails
- Models download on first use (~1-2GB for large model)
- Ensure stable internet connection
- Models are cached in `~/.cache/whisper`

#### Redis Connection Error
```bash
# Check Redis status
redis-cli ping

# Start Redis
redis-server

# Or as service
sudo service redis-server start
```

#### Translation API Errors
1. Verify API keys in `.env`
2. Check API quotas and limits
3. Fallback chain: Azure → Google → LibreTranslate → Free Google

#### Out of Memory
- Use smaller Whisper model (tiny or base)
- Reduce chunk size in `audio_processor.py`
- Increase system swap space

## Testing

### Run Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test
python tests/test_basic.py

# Run with coverage
pytest --cov=utils tests/
```

### Manual Testing Checklist
- [ ] File upload (various formats)
- [ ] YouTube URL processing
- [ ] Large file handling (>100MB)
- [ ] Translation accuracy
- [ ] Download all output formats
- [ ] Error handling (invalid files, API failures)
- [ ] Rate limiting
- [ ] Concurrent processing

## Security Considerations

1. **File Validation**: MIME type checking, extension validation
2. **Rate Limiting**: Per-IP limits to prevent abuse
3. **Input Sanitization**: All user inputs sanitized
4. **Secure File Storage**: Unique IDs, automatic cleanup
5. **API Key Security**: Never exposed to frontend
6. **CORS Configuration**: Restricted to specific origins in production

## Deployment Notes

### Production Checklist
- [ ] Set `FLASK_ENV=production`
- [ ] Generate secure `SECRET_KEY`
- [ ] Configure production Redis
- [ ] Set up SSL/TLS
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Set up monitoring (logs, metrics)
- [ ] Configure backup strategy
- [ ] Set API rate limits
- [ ] Test failover scenarios

### Recommended Production Setup
```
Internet → Nginx (reverse proxy) → Gunicorn (WSGI) → Flask App
                                 → Static files (CDN)
         → Redis (cache/queue)
         → Celery Workers (background tasks)
```

## Future Enhancements

### Phase 2
- User accounts and history
- Batch processing for multiple files
- Custom vocabulary management
- Speaker diarization
- Real-time streaming transcription

### Phase 3
- Mobile applications
- REST API for third-party integration
- Advanced subtitle editor
- Translation memory
- Multi-language output support

## Code Examples

### Processing a File Programmatically
```python
from utils.audio_processor import AudioProcessor
from utils.transcription import TranscriptionService
from utils.translation import TranslationService
from config import Config

config = Config()

# Initialize services
audio_processor = AudioProcessor(config)
transcription_service = TranscriptionService(config)
translation_service = TranslationService(config)

# Process audio
success, audio_path, msg = audio_processor.extract_audio('video.mp4')

# Transcribe
result = transcription_service.transcribe(audio_path)

# Translate
translation = translation_service.translate(result['text'], 'es', result['language'])
```

### Adding Custom Translation Provider
```python
# In utils/translation.py
def _translate_custom(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> Dict:
    """Custom translation provider"""
    try:
        # Your API call here
        response = requests.post('https://api.custom.com/translate', ...)
        return {
            'success': True,
            'translated_text': response['translation'],
            'service': 'custom'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

## Useful Commands

```bash
# Monitor Celery tasks
celery -A celery_app flower

# Clear Redis cache
redis-cli FLUSHALL

# Check disk usage
du -sh static/uploads temp

# Clean old files
find static/uploads -type f -mtime +1 -delete
find temp -type f -mtime +1 -delete

# Test Whisper model
python -c "import whisper; model = whisper.load_model('base'); print('Model loaded')"

# Check API connectivity
curl -X POST https://api.cognitive.microsofttranslator.com/detect?api-version=3.0 \
  -H "Ocp-Apim-Subscription-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d "[{'Text':'Hello'}]"
```

## Support & Documentation

### External Documentation
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Azure Translator](https://docs.microsoft.com/en-us/azure/cognitive-services/translator/)
- [Google Translate API](https://cloud.google.com/translate/docs)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/documentation.html)
- [Celery](https://docs.celeryproject.org/)
- [Flask](https://flask.palletsprojects.com/)

### Project Maintenance
- Update dependencies monthly: `pip list --outdated`
- Monitor API deprecations
- Test with new Whisper model releases
- Review security advisories
- Update translation language support

## Contact & Contributing

For issues, improvements, or questions about the AnyLingo project:
1. Check existing issues in project repository
2. Review this documentation thoroughly
3. Test in development environment first
4. Include error logs and reproduction steps

Remember: This is a production-ready application designed for reliability, scalability, and user-friendliness. Always prioritize security and performance in any modifications.