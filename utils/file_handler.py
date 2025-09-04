import os
import uuid
import magic
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from typing import Optional, Tuple
import hashlib

class FileHandler:
    """Handles file upload, validation, and storage."""
    
    def __init__(self, config):
        self.config = config
        self.upload_folder = config.get('UPLOAD_FOLDER', './static/uploads')
        self.temp_folder = config.get('TEMP_FOLDER', './temp')
        self.max_file_size = config.get('MAX_FILE_SIZE', 524288000)
        self.allowed_extensions = config.get('ALLOWED_EXTENSIONS', {'mp4', 'mp3', 'wav', 'mov', 'avi', 'webm', 'mkv', 'flac', 'm4a', 'ogg'})
        
        # Create folders if they don't exist
        os.makedirs(self.upload_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)
        
    def validate_file(self, file: FileStorage) -> Tuple[bool, str]:
        """
        Validate uploaded file.
        Returns (is_valid, message)
        """
        # Check if file exists
        if not file or file.filename == '':
            return False, "No file provided"
        
        # Check file extension
        if not self.allowed_file(file.filename):
            return False, f"Invalid file format. Allowed formats: {', '.join(self.allowed_extensions)}"
        
        # Check file size by reading chunks to avoid memory issues
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > self.max_file_size:
            size_mb = self.max_file_size / (1024 * 1024)
            return False, f"File too large. Maximum size: {size_mb}MB"
        
        # Check MIME type using python-magic
        try:
            mime = magic.Magic(mime=True)
            # Read first 2048 bytes for MIME detection
            file_start = file.read(2048)
            file.seek(0)  # Reset to beginning
            
            file_mime = mime.from_buffer(file_start)
            
            # Allowed MIME types for video and audio
            allowed_mimes = [
                'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/wave', 
                'audio/x-wav', 'audio/flac', 'audio/ogg', 'audio/x-m4a',
                'video/mp4', 'video/quicktime', 'video/x-msvideo', 
                'video/webm', 'video/x-matroska', 'application/ogg'
            ]
            
            if not any(file_mime.startswith(mime_type.split('/')[0]) for mime_type in allowed_mimes):
                if file_mime not in allowed_mimes:
                    return False, f"Invalid file type detected: {file_mime}"
            
        except Exception as e:
            print(f"Warning: MIME type detection failed: {e}")
            # Continue if MIME detection fails but extension is valid
        
        return True, "File is valid"
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def save_file(self, file: FileStorage) -> Tuple[bool, str, str]:
        """
        Save uploaded file with unique identifier.
        Returns (success, filepath_or_error, file_id)
        """
        try:
            # Generate unique filename
            file_id = str(uuid.uuid4())
            extension = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{file_id}.{extension}"
            filepath = os.path.join(self.upload_folder, filename)
            
            # Save file
            file.save(filepath)
            
            # Verify file was saved
            if not os.path.exists(filepath):
                return False, "Failed to save file", ""
            
            return True, filepath, file_id
            
        except Exception as e:
            return False, f"Error saving file: {str(e)}", ""
    
    def cleanup_file(self, filepath: str):
        """Remove file from filesystem."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error removing file {filepath}: {e}")
            return False
    
    def get_file_info(self, filepath: str) -> dict:
        """Get file metadata."""
        if not os.path.exists(filepath):
            return {}
        
        file_stats = os.stat(filepath)
        return {
            'size': file_stats.st_size,
            'size_mb': round(file_stats.st_size / (1024 * 1024), 2),
            'created': file_stats.st_ctime,
            'modified': file_stats.st_mtime,
            'filename': os.path.basename(filepath)
        }
    
    def generate_checksum(self, filepath: str) -> str:
        """Generate SHA256 checksum for file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()