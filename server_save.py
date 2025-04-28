import grpc
import concurrent.futures
import signal
import sys
import os
import wave
import time
import datetime
import threading
import audio_stream_pb2
import audio_stream_pb2_grpc
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('audio-saver')

# Create directory for saved audio files
AUDIO_SAVE_DIR = os.path.join(os.getcwd(), "saved_audio")
os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)

class AudioSaverService(audio_stream_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        logger.info("Starting to record 5 seconds of audio...")
        
        # Generate a unique filename using timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        
        # Buffer to collect audio data
        audio_data = bytearray()
        
        # Set a 5-second timer to stop recording
        recording_done = threading.Event()
        
        def stop_recording_after_timeout():
            time.sleep(5)  # Sleep for 5 seconds
            recording_done.set()
            logger.info("5-second timer expired, stopping recording")
        
        # Start the timer in a separate thread
        timer_thread = threading.Thread(target=stop_recording_after_timeout)
        timer_thread.daemon = True
        timer_thread.start()
        
        try:
            # Process incoming audio until timer expires
            for stream_event in request_iterator:
                if recording_done.is_set():
                    logger.info("Recording time limit reached, stopping collection")
                    break
                    
                if stream_event.HasField('segment_media'):
                    audio_chunk = stream_event.segment_media.audio_content.payload
                    audio_data.extend(audio_chunk)
                    
                    # Log current data size
                    logger.info(f"Received {len(audio_data)/1024:.2f} KB of audio data")
            
            # Save the audio to file
            if audio_data:
                filepath = self._save_audio_file(session_id, audio_data)
                logger.info(f"Audio saved to {filepath}")
            else:
                logger.warning("No audio data received during the 5-second window")
                
        except Exception as e:
            logger.error(f"Error during audio recording: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
        return audio_stream_pb2.google_dot_protobuf_dot_empty__pb2.Empty()
    
    def _save_audio_file(self, session_id, audio_data):
        """Save audio data to a WAV file"""
        filename = f"{session_id}.wav"
        filepath = os.path.join(AUDIO_SAVE_DIR, filename)
        
        # Create WAV file (LINEAR16 format, 16kHz, mono)
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit audio (2 bytes)
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(audio_data)
            
        return filepath

def serve():
    # Create and configure the gRPC server
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=5))
    audio_stream_pb2_grpc.add_StreamingServicer_to_server(
        AudioSaverService(), server
    )
    
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 443))
    host = '0.0.0.0'  # Listen on all interfaces
    server_address = f'{host}:{port}'
    
    # Configure SSL if certificates are available
    cert_file = os.environ.get('SSL_CERT_FILE')
    key_file = os.environ.get('SSL_KEY_FILE')
    
    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        # Use secure connection with SSL
        with open(cert_file, 'rb') as f:
            cert_data = f.read()
        with open(key_file, 'rb') as f:
            key_data = f.read()
            
        server_credentials = grpc.ssl_server_credentials([(key_data, cert_data)])
        server.add_secure_port(server_address, server_credentials)
        logger.info(f"Server started with SSL at {server_address}")
    else:
        # Fall back to insecure connection
        server.add_insecure_port(server_address)
        logger.info(f"Server started without SSL at {server_address} (insecure)")
    
    # Start server
    server.start()
    
    # Handle graceful shutdown
    def handle_shutdown(signum, frame):
        logger.info("Shutting down server...")
        server.stop(grace=2)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        handle_shutdown(None, None)

if __name__ == '__main__':
    logger.info("Starting 5-second audio recording server")
    serve() 