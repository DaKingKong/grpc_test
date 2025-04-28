import os
import grpc
import logging
import argparse
import audio_stream_pb2_grpc
import threading
import wave
from pathlib import Path
from concurrent import futures
from google.protobuf.empty_pb2 import Empty
from flask import Flask, send_file, Response
import time
import audio_stream_pb2

app = Flask(__name__)
OUTPUT_FOLDER = 'saved_audio'

class StreamingService(audio_stream_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        # Get audio format from metadata if provided
        metadata = dict(context.invocation_metadata())
        audio_encoding = metadata.get('x-audio-encoding', 'LINEAR16')
        sample_rate = int(metadata.get('x-sample-rate', '8000'))
        channels = int(metadata.get('x-channels', '1'))
        logger.info(f"Audio parameters from headers: encoding={audio_encoding}, sample_rate={sample_rate}Hz, channels={channels}")
        
        # Track audio format for this session
        audio_format = {
            'encoding': audio_encoding,
            'sample_rate': sample_rate,
            'channels': channels,
            'sample_width': 2  # Default to 2 bytes (16-bit)
        }
        
        # Create output directory
        Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
        
        current_session_id = None
        current_segment_id = None
        
        for event in request_iterator:
            if event.HasField('dialog_init'):
                session_id = event.session_id
                current_session_id = session_id
                dialog_id = event.dialog_init.dialog.id
                logger.info(f"{session_id}: DialogInit, dialog_id: {dialog_id}")
                create_session_dir(session_id)
                write_session_logs(session_id, f"DialogInit: {event}")
            if event.HasField('segment_start'):
                session_id = event.session_id
                current_session_id = session_id
                segment_id = event.segment_start.segment_id
                current_segment_id = segment_id
                logger.info(f"{session_id}: SegmentStart, segment_id: {segment_id}")
                write_session_logs(session_id, f"SegmentStart: {event}")
                # Extract audio format from segment_start if available
                if event.segment_start.HasField('audio_format'):
                    fmt = event.segment_start.audio_format
                    # Update audio format from segment_start
                    codec_name = audio_stream_pb2.Codec.Name(fmt.codec)
                    logger.info(f"Audio format from segment_start: codec={codec_name}, rate={fmt.rate}Hz")
                    audio_format['encoding'] = codec_name
                    audio_format['sample_rate'] = fmt.rate
                    # Set sample width based on codec
                    if codec_name in ['PCMA', 'PCMU']:  # A-law and μ-law are 8-bit
                        audio_format['sample_width'] = 1
                    elif codec_name in ['L16', 'LINEAR16']:  # 16-bit PCM
                        audio_format['sample_width'] = 2
            elif event.HasField('segment_media'):
                session_id = event.session_id
                current_session_id = session_id
                segment_id = event.segment_media.segment_id
                current_segment_id = segment_id
                payload = event.segment_media.audio_content.payload
                seq = event.segment_media.audio_content.seq
                duration = event.segment_media.audio_content.duration
                logger.info(f"{session_id}: SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                write_session_logs(session_id, f"SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                write_audio_content(session_id, segment_id, payload)
            elif event.HasField('segment_stop'):
                session_id = event.session_id
                segment_id = event.segment_stop.segment_id
                logger.info(f"{session_id}: SegmentStop, segment_id: {segment_id}")
                write_session_logs(session_id, f"SegmentStop: {event}")
                
                # When a segment stops, convert the binary file to WAV
                if current_session_id and current_segment_id:
                    convert_bin_to_wav(current_session_id, current_segment_id, audio_format)
            else:
                pass
            logger.debug(f"Event: {event}")
        
        # Convert any remaining files when the stream ends
        if current_session_id and current_segment_id:
            convert_bin_to_wav(current_session_id, current_segment_id, audio_format)
            
        return Empty()


def serve(server_ip, grpc_port, grpc_secure_port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    audio_stream_pb2_grpc.add_StreamingServicer_to_server(StreamingService(), server)
    
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
    
    try:
        # Read binary data
        with open(bin_file, 'rb') as f:
            audio_data = f.read()
        
        # Create WAV file
        with wave.open(wav_file, 'wb') as wf:
            wf.setnchannels(audio_format['channels'])
            wf.setsampwidth(audio_format['sample_width'])
            wf.setframerate(audio_format['sample_rate'])
            wf.writeframes(audio_data)
        
        logger.info(f"Converted {bin_file} to WAV format: {wav_file}")
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
    # Get all binary files
    bin_files = get_all_files(OUTPUT_FOLDER)
    bin_links = ''.join([f'<li><a href="/files/{file}">{file}</a></li>' for file in bin_files])
    
    # Get all WAV files
    wav_files = get_all_files(OUTPUT_FOLDER)
    wav_links = ''.join([f'<li><a href="/files/{file}">{file}</a> <audio controls><source src="/files/{file}" type="audio/wav"></audio></li>' for file in wav_files])
    
    return f"""
    <h1>Recorded Audio Files</h1>
    <h2>WAV Files (Playable)</h2>
    <ul>{wav_links}</ul>
    <h2>Raw Binary Files</h2>
    <ul>{bin_links}</ul>
    """

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