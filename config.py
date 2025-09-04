import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # Flask Environment
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './static/uploads')
    TEMP_FOLDER = os.environ.get('TEMP_FOLDER', './temp')
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 524288000))  # 500MB default
    ALLOWED_EXTENSIONS = {'mp4', 'mp3', 'wav', 'mov', 'avi', 'webm', 'mkv', 'flac', 'm4a', 'ogg'}
    
    # Whisper Configuration (for later)
    WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')
    
    # YouTube Configuration
    YOUTUBE_MAX_DURATION = int(os.environ.get('YOUTUBE_MAX_DURATION', 7200))  # 2 hours default
    
    # Rate Limiting (for later)
    RATE_LIMIT_PER_MINUTE = int(os.environ.get('RATE_LIMIT_PER_MINUTE', 10))
    RATE_LIMIT_PER_HOUR = int(os.environ.get('RATE_LIMIT_PER_HOUR', 100))