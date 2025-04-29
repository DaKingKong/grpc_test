import os
import grpc
import logging
import argparse
import ringcx_streaming_pb2_grpc
import threading
import wave
from pathlib import Path
from concurrent import futures
from google.protobuf.empty_pb2 import Empty
from flask import Flask, send_file, Response, render_template_string, jsonify
import time
import ringcx_streaming_pb2
import audioop
# Google Cloud Speech imports
from google.cloud import speech
import queue
import io
import glob
from datetime import datetime

app = Flask(__name__)
OUTPUT_FOLDER = 'saved_audio'

# HTML template for the web page
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Audio Recordings</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3 {
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
        .session {
            margin-bottom: 30px;
            border: 1px solid #eee;
            padding: 15px;
            border-radius: 8px;
            background-color: #f9f9f9;
        }
    </style>
</head>
<body>
    <h1>Recorded Audio Files</h1>
    
    {% if sessions %}
        {% for session_id, files in sessions.items() %}
            <div class="session">
                <h2>Session: {{ session_id }}</h2>
                
                {% if files.wav_files %}
                    <h3>WAV Files (Playable)</h3>
                    <ul>
                    {% for file_path in files.wav_files %}
                        {% set file_name = file_path.split('/')[-1] %}
                        <li>
                            <div>{{ file_name }}</div>
                            <audio controls>
                                <source src="/files/{{ file_path }}" type="audio/wav">
                                Your browser does not support the audio element.
                            </audio>
                        </li>
                    {% endfor %}
                    </ul>
                {% endif %}
                
                {% if files.bin_files %}
                    <h3>Raw Binary Files</h3>
                    <ul>
                    {% for file_path in files.bin_files %}
                        {% set file_name = file_path.split('/')[-1] %}
                        <li>
                            <a href="/files/{{ file_path }}">{{ file_name }}</a>
                        </li>
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
        {% endfor %}
    {% else %}
        <p>No audio recordings found.</p>
    {% endif %}
</body>
</html>
"""

class StreamingService(ringcx_streaming_pb2_grpc.StreamingServicer):
    def __init__(self):
        self.segments = {}  # Dictionary to track all active segments
        self.speech_client = speech.SpeechClient()

    def Stream(self, request_iterator, context):
        
        # Create output directory
        Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
        
        for event in request_iterator:
            session_id = event.session_id
            
            if event.HasField('dialog_init'):
                dialog_id = event.dialog_init.dialog.id
                logger.info(f"{session_id}: DialogInit, dialog_id: {dialog_id}")
                create_session_dir(session_id)
                write_session_logs(session_id, f"DialogInit: {event}")
                
            elif event.HasField('segment_start'):
                segment_id = event.segment_start.segment_id
                logger.info(f"{session_id}: SegmentStart, segment_id: {segment_id}")
                write_session_logs(session_id, f"SegmentStart: {event}")
                
                # Create entry for this segment
                segment_key = f"{session_id}_{segment_id}"
                self.segments[segment_key] = {
                    'session_id': session_id,
                    'segment_id': segment_id,
                    'audio_format': {},
                    'audio_buffer': queue.Queue(),
                    'transcription_thread': None
                }
                
                # Extract audio format from segment_start if available
                if event.segment_start.HasField('audio_format'):
                    fmt = event.segment_start.audio_format
                    codec_name = ringcx_streaming_pb2.Codec.Name(fmt.codec)
                    # logger.info(f"Audio format from segment_start: codec={codec_name}, rate={fmt.rate}Hz")
                    
                    # Store audio format for this specific segment
                    self.segments[segment_key]['audio_format'] = {
                        'encoding': codec_name,
                        'sample_rate': fmt.rate,
                        'channels': 1  # Default to mono
                    }
                    
                    # Set sample width based on codec
                    if codec_name in ['PCMA', 'PCMU']:  # A-law and μ-law are 8-bit
                        self.segments[segment_key]['audio_format']['sample_width'] = 1
                    elif codec_name in ['L16', 'LINEAR16']:  # 16-bit PCM
                        self.segments[segment_key]['audio_format']['sample_width'] = 2
                    
                    # Start transcription thread for this segment
                    transcription_thread = threading.Thread(
                        target=self.stream_transcript,
                        args=(segment_key,)
                    )
                    transcription_thread.daemon = True
                    transcription_thread.start()
                    self.segments[segment_key]['transcription_thread'] = transcription_thread
                
            elif event.HasField('segment_media'):
                segment_id = event.segment_media.segment_id
                payload = event.segment_media.audio_content.payload
                seq = event.segment_media.audio_content.seq
                duration = event.segment_media.audio_content.duration
                
                segment_key = f"{session_id}_{segment_id}"
                logger.info(f"{session_id}: SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                write_session_logs(session_id, f"SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                
                # Add audio data to the segment's buffer for transcription
                if segment_key in self.segments:
                    self.segments[segment_key]['audio_buffer'].put(payload)
                
            elif event.HasField('segment_stop'):
                segment_id = event.segment_stop.segment_id
                logger.info(f"{session_id}: SegmentStop, segment_id: {segment_id}")
                write_session_logs(session_id, f"SegmentStop: {event}")
                
                # Signal end of audio stream for transcription
                segment_key = f"{session_id}_{segment_id}"
                if segment_key in self.segments:
                    self.segments[segment_key]['audio_buffer'].put(None)  # Signal end of stream
                    
                    # Wait for transcription to complete
                    if self.segments[segment_key]['transcription_thread']:
                        self.segments[segment_key]['transcription_thread'].join(timeout=5)
                    
                    # Clean up
                    del self.segments[segment_key]
            
            logger.debug(f"Event: {event}")
        
        # Signal end of stream for any remaining segments
        segments_to_remove = []
        for segment_key, segment_data in self.segments.items():
            segment_data['audio_buffer'].put(None)  # Signal end of stream
            
            # Wait for transcription to complete
            if segment_data['transcription_thread']:
                segment_data['transcription_thread'].join(timeout=5)
            
            segments_to_remove.append(segment_key)
        
        # Clean up processed segments
        for key in segments_to_remove:
            del self.segments[key]
            
        return Empty()
    
    def stream_transcript(self, segment_key):
        """Stream audio data to Google Speech-to-Text and print transcripts"""
        if segment_key not in self.segments:
            logger.error(f"Segment {segment_key} not found for transcription")
            return
        
        segment_data = self.segments[segment_key]
        audio_format = segment_data['audio_format']
        audio_buffer = segment_data['audio_buffer']
        session_id = segment_data['session_id']
        segment_id = segment_data['segment_id']
        
        # Get audio format parameters
        sample_rate = audio_format.get('sample_rate', 8000)
        encoding = audio_format.get('encoding', 'PCMU')
        
        # Configure speech recognition
        config = speech.RecognitionConfig(
            encoding=self._get_google_encoding(encoding),
            sample_rate_hertz=sample_rate,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="phone_call"  # Use phone_call model for better handling of telephony audio
        )
        
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )
        
        # Audio stream generator
        def audio_stream_generator():
            while True:
                chunk = audio_buffer.get()
                if chunk is None:  # End of stream
                    break
                
                # Convert audio format if needed
                if encoding == 'PCMA':  # A-law
                    chunk = audioop.alaw2lin(chunk, 2)
                elif encoding == 'PCMU':  # μ-law
                    chunk = audioop.ulaw2lin(chunk, 2)
                
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
        
        # Start streaming recognition
        try:
            streaming_responses = self.speech_client.streaming_recognize(
                config=streaming_config,
                requests=audio_stream_generator()
            )
            
            logger.info(f"Started transcription for {segment_key}")
            
            # Process streaming responses
            for response in streaming_responses:
                if not response.results:
                    continue
                
                for result in response.results:
                    transcript = result.alternatives[0].transcript if result.alternatives else ""
                    
                    if result.is_final:
                        logger.info(f"Transcript [{segment_key}]: {transcript}")
                        print(f"FINAL TRANSCRIPT [{segment_key}]: {transcript}")
                    else:
                        logger.debug(f"Interim [{segment_key}]: {transcript}")
                        print(f"INTERIM [{segment_key}]: {transcript}")
            
            logger.info(f"Completed transcription for {segment_key}")
            
        except Exception as e:
            logger.error(f"Error in transcription for {segment_key}: {e}")
    
    def _get_google_encoding(self, encoding):
        """Convert internal encoding names to Google Speech-to-Text encoding enum values"""
        if encoding == 'LINEAR16' or encoding == 'L16':
            return speech.RecognitionConfig.AudioEncoding.LINEAR16
        elif encoding == 'PCMA':
            return speech.RecognitionConfig.AudioEncoding.MULAW  # Google doesn't have A-law, convert to PCM
        elif encoding == 'PCMU':
            return speech.RecognitionConfig.AudioEncoding.MULAW
        else:
            # Default to LINEAR16
            logger.warning(f"Unsupported encoding {encoding} for Google STT, using LINEAR16")
            return speech.RecognitionConfig.AudioEncoding.LINEAR16


def serve(server_ip, grpc_port, grpc_secure_port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ringcx_streaming_pb2_grpc.add_StreamingServicer_to_server(StreamingService(), server)
    
    # Insecure port
    server_address = f'{server_ip}:{grpc_port}'
    server.add_insecure_port(server_address)
    logger.info(f'gRPC server started at {server_address} (insecure)')
    
    # Secure port if SSL certificates are available
    cert_file = os.environ.get('SSL_CERT_FILE')
    key_file = os.environ.get('SSL_KEY_FILE')
    
    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        secure_address = f'{server_ip}:{grpc_secure_port}'
        with open(cert_file, 'rb') as f:
            cert_data = f.read()
        with open(key_file, 'rb') as f:
            key_data = f.read()
            
        server_credentials = grpc.ssl_server_credentials([(key_data, cert_data)])
        server.add_secure_port(secure_address, server_credentials)
        logger.info(f'gRPC server started with SSL at {secure_address}')
    
    server.start()
    return server

def configure_logger(log_level, log_filename):
    _logger = logging.getLogger(__name__)
    _logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(log_level)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    _logger.addHandler(console_handler)
    _logger.addHandler(file_handler)
    return _logger


def create_session_dir(session_id):
    output_folder_path = Path(f"{OUTPUT_FOLDER}/{session_id}")
    output_folder_path.mkdir(parents=True, exist_ok=True)

def write_session_logs(session_id, msg):
    with open(f'{OUTPUT_FOLDER}/{session_id}/session.log', 'a') as file:
        file.write(f"{msg}\n")

def write_audio_content(session_id, segment_id, payload):
    with open(f'{OUTPUT_FOLDER}/{session_id}/{segment_id}.bin', 'ab') as file:
        file.write(payload)

def convert_bin_to_wav(session_id, segment_id, audio_format):
    """Convert binary audio file to WAV format"""
    bin_file = f'{OUTPUT_FOLDER}/{session_id}/{segment_id}.bin'
    wav_file = f'{OUTPUT_FOLDER}/{session_id}_{segment_id}.wav'
    
    # Check if binary file exists and has content
    if not os.path.exists(bin_file) or os.path.getsize(bin_file) == 0:
        logger.warning(f"Binary file {bin_file} is empty or doesn't exist")
        return
    
    # Ensure we have the minimum required audio format parameters
    if not audio_format or 'sample_rate' not in audio_format:
        logger.warning(f"Missing audio format information for {session_id}_{segment_id}")
        return
    
    # Set default values if not provided
    channels = audio_format.get('channels', 1)  # Default to mono
    sample_width = audio_format.get('sample_width', 1)  # Default to 8-bit
    sample_rate = audio_format.get('sample_rate', 8000)  # Default to 8kHz
    encoding = audio_format.get('encoding', 'PCMU')  # Default to PCM
    
    try:
        # Read binary data
        with open(bin_file, 'rb') as f:
            audio_data = f.read()
        
        # Convert based on codec type
        if encoding == 'PCMA':  # A-law
            # Convert A-law to PCM (2 bytes per sample)
            audio_data = audioop.alaw2lin(audio_data, 2)
            sample_width = 2  # A-law conversion results in 16-bit PCM
        
        elif encoding == 'PCMU':  # μ-law
            # Convert μ-law to PCM (2 bytes per sample)
            audio_data = audioop.ulaw2lin(audio_data, 2)
            sample_width = 2  # μ-law conversion results in 16-bit PCM
            
        elif encoding not in ['L16', 'LINEAR16']:
            logger.warning(f"Unsupported codec: {encoding}, using raw data")
        
        # Create WAV file
        with wave.open(wav_file, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        
        logger.info(f"Converted {bin_file} to WAV format: {wav_file}, format: codec={encoding}, channels={channels}, sample_width={sample_width}, rate={sample_rate}Hz")
    except Exception as e:
        logger.error(f"Error converting {bin_file} to WAV: {e}")


def get_all_files(directory):
    if not os.path.exists(directory):
        return []
        
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            creation_time = os.path.getctime(file_path)
            file_list.append((file_path, creation_time))

    file_list.sort(reverse=True, key=lambda x: x[1])
    return [file[0] for file in file_list]


def run_flask(http_port):
    logger.info(f"Starting Flask server on port {http_port}")
    app.run(host="0.0.0.0", port=http_port, threaded=True)

@app.route('/health')
def healthcheck():
    return '', 200

@app.route('/')
def list_files():
    # Group files by session ID
    sessions = {}
    
    # Get all files
    all_files = get_all_files(OUTPUT_FOLDER)
    
    for file_path in all_files:
        # Skip session log files from the main listing
        if file_path.endswith('/session.log'):
            continue
            
        parts = file_path.split('/')
        file_name = parts[-1]
        
        if '_' in file_name:
            # For session_segment named files
            session_segment = file_name.split('.')[0]  # Remove extension
            if session_segment:
                parts = session_segment.split('_')
                if len(parts) >= 2:
                    session_id = parts[0]
                    if session_id not in sessions:
                        sessions[session_id] = {'wav_files': [], 'bin_files': []}
                    
                    if file_name.endswith('.wav'):
                        sessions[session_id]['wav_files'].append(file_path)
                    elif file_name.endswith('.bin'):
                        sessions[session_id]['bin_files'].append(file_path)
        elif len(parts) > 2:
            # For files organized in session directories
            session_id = parts[-2]
            if session_id not in sessions:
                sessions[session_id] = {'wav_files': [], 'bin_files': []}
                
            if file_name.endswith('.wav'):
                sessions[session_id]['wav_files'].append(file_path)
            elif file_name.endswith('.bin'):
                sessions[session_id]['bin_files'].append(file_path)
    
    # Sort sessions and files
    sorted_sessions = {}
    for session_id in sorted(sessions.keys(), reverse=True):
        sorted_sessions[session_id] = {
            'wav_files': sorted(sessions[session_id]['wav_files']),
            'bin_files': sorted(sessions[session_id]['bin_files'])
        }
    
    return render_template_string(HTML_TEMPLATE, sessions=sorted_sessions)

@app.route('/files/<path:filename>')
def download_file(filename):
    if filename.endswith('.log'):
        with open(filename, 'r') as f:
            file_content = f.read()
        return Response(file_content, content_type='text/plain')
    return send_file(filename)

@app.route('/api/files')
def api_list_files():
    """API endpoint to list all audio files"""
    wav_files = []
    for root, _, files in os.walk(OUTPUT_FOLDER):
        for file in files:
            if file.endswith('.wav'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, OUTPUT_FOLDER)
                wav_files.append(relative_path)
                
    return jsonify({"files": wav_files})

def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Streaming Server")
    parser.add_argument('--log_level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Set the logging level")
    parser.add_argument('--log_filename', type=str, default="server.log", help="Log filename")
    parser.add_argument('--server_ip', type=str, default='0.0.0.0', help="IP address for server")
    parser.add_argument('--grpc_port', type=int, default=10080, help="Port for gRPC server")
    parser.add_argument('--grpc_secure_port', type=int, default=443, help="Port for gRPC server with ssl")
    parser.add_argument('--http_port', type=int, default=8080, help="Port for http server to download outputs")

    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    logger = configure_logger(args.log_level, args.log_filename)
    
    # Create output folders if they don't exist
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    
    # Start gRPC server
    grpc_server = serve(args.server_ip, args.grpc_port, args.grpc_secure_port)
    
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask, args=(args.http_port,))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Keep the main thread running
    try:
        while True:
            time.sleep(86400)  # Sleep for a day
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated")
        grpc_server.stop(0)