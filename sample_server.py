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
from flask import Flask, send_file, Response
import time
import ringcx_streaming_pb2

app = Flask(__name__)
OUTPUT_FOLDER = 'saved_audio'

class StreamingService(ringcx_streaming_pb2_grpc.StreamingServicer):
    def __init__(self):
        self.segments = {}  # Dictionary to track all active segments

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
                    'audio_format': {}
                }
                
                # Extract audio format from segment_start if available
                if event.segment_start.HasField('audio_format'):
                    fmt = event.segment_start.audio_format
                    codec_name = ringcx_streaming_pb2.Codec.Name(fmt.codec)
                    logger.info(f"Audio format from segment_start: codec={codec_name}, rate={fmt.rate}Hz")
                    
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
                
            elif event.HasField('segment_media'):
                segment_id = event.segment_media.segment_id
                payload = event.segment_media.audio_content.payload
                seq = event.segment_media.audio_content.seq
                duration = event.segment_media.audio_content.duration
                
                logger.info(f"{session_id}: SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                write_session_logs(session_id, f"SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                write_audio_content(session_id, segment_id, payload)
                
            elif event.HasField('segment_stop'):
                segment_id = event.segment_stop.segment_id
                logger.info(f"{session_id}: SegmentStop, segment_id: {segment_id}")
                write_session_logs(session_id, f"SegmentStop: {event}")
                
                # When a segment stops, convert the binary file to WAV
                segment_key = f"{session_id}_{segment_id}"
                if segment_key in self.segments:
                    audio_format = self.segments[segment_key]['audio_format']
                    convert_bin_to_wav(session_id, segment_id, audio_format)
                    # Clean up after conversion
                    del self.segments[segment_key]
            
            logger.debug(f"Event: {event}")
        
        # Convert any remaining segments when stream ends
        segments_to_remove = []
        for segment_key, segment_data in self.segments.items():
            session_id = segment_data['session_id']
            segment_id = segment_data['segment_id']
            audio_format = segment_data['audio_format']
            convert_bin_to_wav(session_id, segment_id, audio_format)
            segments_to_remove.append(segment_key)
        
        # Clean up processed segments
        for key in segments_to_remove:
            del self.segments[key]
            
        return Empty()


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
        import audioop
        
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
    
    # Generate HTML output
    html_output = "<h1>Recorded Audio Files</h1>"
    
    for session_id, files in sorted(sessions.items()):
        html_output += f"<h2>Session: {session_id}</h2>"
        
        if files['wav_files']:
            html_output += "<h3>WAV Files (Playable)</h3><ul>"
            for file in sorted(files['wav_files']):
                file_name = file.split('/')[-1]
                html_output += f'<li><a href="/files/{file}">{file_name}</a> <audio controls><source src="/files/{file}" type="audio/wav"></audio></li>'
            html_output += "</ul>"
            
        if files['bin_files']:
            html_output += "<h3>Raw Binary Files</h3><ul>"
            for file in sorted(files['bin_files']):
                file_name = file.split('/')[-1]
                html_output += f'<li><a href="/files/{file}">{file_name}</a></li>'
            html_output += "</ul>"
    
    return html_output

@app.route('/files/<path:filename>')
def download_file(filename):
    if filename.endswith('.log'):
        with open(filename, 'r') as f:
            file_content = f.read()
        return Response(file_content, content_type='text/plain')
    return send_file(filename)


def parse_args():
    parser = argparse.ArgumentParser(description="gRPC Streaming Server")
    parser.add_argument('--log_level', type=str, default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Set the logging level")
    parser.add_argument('--log_filename', type=str, default="server.log", help="Log filename")
    parser.add_argument('--server_ip', type=str, default='0.0.0.0', help="IP address for server")
    parser.add_argument('--grpc_port', type=int, default=10080, help="Port for gRPC server")
    parser.add_argument('--grpc_secure_port', type=int, default=443, help="Port for gRPC server with ssl")
    parser.add_argument('--http_port', type=int, default=8000, help="Port for http server to download outputs")

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