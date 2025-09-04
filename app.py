from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import json
from datetime import datetime
from utils.file_handler import FileHandler
from utils.media_processor import MediaProcessor
from celery_app import celery
from celery.result import AsyncResult

app = Flask(__name__)
app.config.from_object('config.Config')
CORS(app)

# Initialize file handler and media processor
file_handler = FileHandler(app.config)
media_processor = MediaProcessor(app.config, whisper_model_size='base')

# Create folders (now handled by FileHandler)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    """Main upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload with validation."""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        is_valid, message = file_handler.validate_file(file)
        
        if not is_valid:
            return jsonify({'error': message}), 400
        
        # Save file
        success, filepath, file_id = file_handler.save_file(file)
        
        if not success:
            return jsonify({'error': filepath}), 500
        
        # Get file info
        file_info = file_handler.get_file_info(filepath)
        
        # Start async processing task using send_task to avoid import
        task = celery.send_task(
            'tasks.media_tasks.process_media_file_task',
            args=[filepath],
            kwargs={
                'target_language': request.form.get('target_language'),
                'output_formats': ['text', 'srt', 'json']
            }
        )
        
        return jsonify({
            'status': 'success',
            'message': 'File uploaded and processing started',
            'file_id': file_id,
            'filename': file.filename,
            'size_mb': file_info.get('size_mb', 0),
            'task_id': task.id,
            'task_status_url': f'/task/{task.id}/status',
            'task_result_url': f'/task/{task.id}/result'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/youtube', methods=['POST'])
def process_youtube():
    """Process YouTube video - download, transcribe, and translate."""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        youtube_url = data.get('url', '').strip()
        target_language = data.get('target_language', 'en')
        
        # Validate YouTube URL
        if not media_processor.is_youtube_url(youtube_url):
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        # Get video info first
        video_info = media_processor.youtube_handler.get_video_info(youtube_url)
        
        if not video_info.get('success'):
            return jsonify({
                'error': video_info.get('error', 'Failed to get video information'),
                'error_type': video_info.get('error_type', 'unknown')
            }), 400
        
        # Check duration limit (configurable, default 2 hours)
        duration = video_info.get('duration', 0)
        max_duration = app.config.get('YOUTUBE_MAX_DURATION', 7200)  # 2 hours default
        max_duration_hours = max_duration / 3600
        if duration > max_duration:
            return jsonify({
                'error': f"Video too long ({duration}s > {max_duration}s). Maximum duration is {max_duration_hours:.1f} hours.",
                'video_info': {
                    'title': video_info.get('title', 'Unknown'),
                    'duration': duration,
                    'duration_string': video_info.get('duration_string', '')
                }
            }), 400
        
        # Start async YouTube processing task using send_task to avoid import
        task = celery.send_task(
            'tasks.media_tasks.process_youtube_task',
            args=[youtube_url],
            kwargs={
                'target_language': target_language if target_language != 'none' else None,
                'output_formats': ['text', 'srt', 'json']
            }
        )
        
        return jsonify({
            'status': 'success',
            'message': 'YouTube processing started',
            'task_id': task.id,
            'video_info': {
                'video_id': video_info.get('video_id'),
                'title': video_info.get('title', 'Unknown'),
                'duration': duration,
                'duration_string': video_info.get('duration_string', ''),
                'uploader': video_info.get('uploader', 'Unknown'),
                'view_count': video_info.get('view_count', 0)
            },
            'task_status_url': f'/task/{task.id}/status',
            'task_result_url': f'/task/{task.id}/result'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/status')
def task_status(task_id):
    """Get status of a processing task."""
    try:
        task = AsyncResult(task_id, app=celery)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task pending...',
                'progress': 0
            }
        elif task.state == 'PROGRESS':
            response = {
                'state': task.state,
                'current': task.info.get('current', 0),
                'total': task.info.get('total', 100),
                'percent': task.info.get('percent', 0),
                'status': task.info.get('message', ''),
                'timestamp': task.info.get('timestamp', '')
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'status': 'Task completed successfully',
                'progress': 100,
                'result_available': True
            }
        else:  # FAILURE
            response = {
                'state': task.state,
                'status': str(task.info),
                'progress': 0,
                'error': True
            }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/result')
def task_result(task_id):
    """Get result of a completed task."""
    try:
        task = AsyncResult(task_id, app=celery)
        
        if task.state == 'SUCCESS':
            result = task.result
            if result.get('success'):
                return jsonify({
                    'status': 'success',
                    'result': result
                })
            else:
                return jsonify({
                    'status': 'error',
                    'errors': result.get('errors', ['Processing failed'])
                }), 500
        elif task.state == 'FAILURE':
            return jsonify({
                'status': 'error',
                'error': str(task.info)
            }), 500
        else:
            return jsonify({
                'status': 'processing',
                'state': task.state,
                'message': 'Task is still processing'
            }), 202
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/task/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """Cancel a running task."""
    try:
        task = AsyncResult(task_id, app=celery)
        task.revoke(terminate=True)
        
        return jsonify({
            'status': 'success',
            'message': 'Task cancellation requested'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results')
def results_page():
    """Display results page."""
    return render_template('results.html')

@app.route('/download/<task_id>/<format>')
def download_result(task_id, format):
    """Download results in specified format."""
    try:
        # Get task result
        task = AsyncResult(task_id, app=celery)
        
        if task.state != 'SUCCESS':
            return jsonify({'error': 'Task not completed or failed'}), 404
        
        result = task.result
        if not result.get('success'):
            return jsonify({'error': 'Processing failed'}), 500
        
        # Get the appropriate content based on format
        if format == 'text':
            # Plain text transcription
            content = result.get('transcription_result', {}).get('text', '')
            mimetype = 'text/plain'
            filename = f'transcription_{task_id}.txt'
            
        elif format == 'srt':
            # SRT subtitles
            content = result.get('outputs', {}).get('srt', '')
            if not content:
                # Generate SRT from segments
                segments = result.get('transcription_result', {}).get('segments', [])
                content = generate_srt(segments)
            mimetype = 'text/srt'
            filename = f'subtitles_{task_id}.srt'
            
        elif format == 'vtt':
            # WebVTT subtitles
            content = result.get('outputs', {}).get('vtt', '')
            if not content:
                # Generate VTT from segments
                segments = result.get('transcription_result', {}).get('segments', [])
                content = generate_vtt(segments)
            mimetype = 'text/vtt'
            filename = f'subtitles_{task_id}.vtt'
            
        elif format == 'json':
            # Full JSON data
            content = json.dumps(result, indent=2)
            mimetype = 'application/json'
            filename = f'data_{task_id}.json'
            
        elif format == 'pdf':
            # Generate PDF report (requires additional implementation)
            from io import BytesIO
            pdf_buffer = generate_pdf_report(result, task_id)
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'report_{task_id}.pdf'
            )
            
        else:
            return jsonify({'error': 'Invalid format'}), 400
        
        # Create response with file download
        from flask import Response
        response = Response(
            content,
            mimetype=mimetype,
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_srt(segments):
    """Generate SRT format from segments."""
    srt_content = []
    for i, segment in enumerate(segments, 1):
        start = format_srt_time(segment.get('start', 0))
        end = format_srt_time(segment.get('end', 0))
        text = segment.get('text', '').strip()
        srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")
    return '\n'.join(srt_content)

def generate_vtt(segments):
    """Generate WebVTT format from segments."""
    vtt_content = ['WEBVTT\n']
    for segment in segments:
        start = format_vtt_time(segment.get('start', 0))
        end = format_vtt_time(segment.get('end', 0))
        text = segment.get('text', '').strip()
        vtt_content.append(f"{start} --> {end}\n{text}\n")
    return '\n'.join(vtt_content)

def format_srt_time(seconds):
    """Format time for SRT (00:00:00,000)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_vtt_time(seconds):
    """Format time for WebVTT (00:00:00.000)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def generate_pdf_report(result, task_id):
    """Generate PDF report of results."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#667eea')
    )
    story.append(Paragraph("AnyLingo Transcription Report", title_style))
    story.append(Spacer(1, 12))
    
    # Metadata
    metadata = result.get('metadata', {})
    meta_data = [
        ['Document ID:', task_id],
        ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['Duration:', f"{metadata.get('audio_duration', 0):.1f} seconds"],
        ['Words:', str(metadata.get('word_count', 0))],
        ['Language:', result.get('transcription_result', {}).get('language', 'Unknown')]
    ]
    
    if metadata.get('youtube_title'):
        meta_data.insert(0, ['Video Title:', metadata.get('youtube_title', '')])
    
    meta_table = Table(meta_data)
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#667eea')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))
    
    # Transcription
    story.append(Paragraph("Transcription", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    transcription_text = result.get('transcription_result', {}).get('text', 'No transcription available')
    para = Paragraph(transcription_text, styles['BodyText'])
    story.append(para)
    story.append(Spacer(1, 20))
    
    # Translation (if available)
    translation = result.get('translation_result', {})
    if translation.get('success') and translation.get('translated_text'):
        story.append(Paragraph("Translation", styles['Heading2']))
        story.append(Spacer(1, 12))
        trans_para = Paragraph(translation.get('translated_text', ''), styles['BodyText'])
        story.append(trans_para)
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'AnyLingo API is running'})

@app.route('/supported-languages')
def supported_languages():
    """Get list of supported languages - stub for now"""
    languages = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'ja': 'Japanese',
        'ko': 'Korean',
        'zh': 'Chinese (Simplified)',
        'ar': 'Arabic',
        'hi': 'Hindi'
    }
    return jsonify(languages)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)