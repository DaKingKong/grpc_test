from flask import Flask, send_file, render_template_string, request, jsonify
import os
import glob

app = Flask(__name__)

# Directory where audio files are stored
AUDIO_DIR = os.path.join(os.getcwd(), "saved_audio")

# Ensure the directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)

# HTML template for the web page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Audio Player</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            border: 1px solid #ddd;
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 4px;
        }
        audio {
            width: 100%;
        }
        .timestamp {
            color: #666;
            font-size: 0.8em;
        }
    </style>
</head>
<body>
    <h1>Audio Recordings</h1>
    
    <ul>
    {% for file in files %}
        <li>
            <div>{{ file }}</div>
            <div class="timestamp">Recorded: {{ timestamps[loop.index0] }}</div>
            <audio controls>
                <source src="/audio/{{ file }}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
        </li>
    {% endfor %}
    </ul>
    
    {% if not files %}
    <p>No audio recordings found.</p>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    """Display a list of available audio files with players"""
    # Get all WAV files in the directory
    audio_files = [os.path.basename(f) for f in glob.glob(os.path.join(AUDIO_DIR, "*.wav"))]
    audio_files.sort(reverse=True)  # Most recent first
    
    # Extract timestamps from filenames for display
    timestamps = []
    for file in audio_files:
        # Try to extract timestamp from typical format session_YYYYMMDD_HHMMSS.wav
        try:
            parts = file.split('_')
            date_part = parts[1]
            time_part = parts[2].split('.')[0]
            formatted = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            timestamps.append(formatted)
        except:
            timestamps.append("Unknown date")
    
    return render_template_string(HTML_TEMPLATE, files=audio_files, timestamps=timestamps)

@app.route('/audio/<filename>')
def serve_audio(filename):
    """Stream an audio file to the client"""
    file_path = os.path.join(AUDIO_DIR, filename)
    
    if not os.path.exists(file_path):
        return "File not found", 404
        
    return send_file(file_path, mimetype="audio/wav")

@app.route('/api/files')
def list_files():
    """API endpoint to list all audio files"""
    audio_files = [os.path.basename(f) for f in glob.glob(os.path.join(AUDIO_DIR, "*.wav"))]
    return jsonify({"files": audio_files})

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.environ.get("WEB_PORT", 8080))
    host = '0.0.0.0'  # Listen on all interfaces
    
    print(f"Starting web server at http://{host}:{port}")
    print(f"Audio files directory: {AUDIO_DIR}")
    
    # Run the server
    app.run(host=host, port=port, debug=True) 