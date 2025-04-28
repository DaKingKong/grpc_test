import grpc
import concurrent.futures
import signal
import sys
import time
import threading
import traceback
import os
import wave
import datetime
import audio_stream_pb2
import audio_stream_pb2_grpc
import logging

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('audio-saver-server')

# Create audio save directory if it doesn't exist
AUDIO_SAVE_DIR = os.path.join(os.getcwd(), "saved_audio")
os.makedirs(AUDIO_SAVE_DIR, exist_ok=True)

class AudioSaverService(audio_stream_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        logger.info("Server started, waiting for audio stream...")
        
        # Create a unique session ID for this stream
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = None
        audio_data = bytearray()
        
        try:
            for stream_event in request_iterator:
                # Get session ID from first event
                if session_id is None and stream_event.session_id:
                    session_id = stream_event.session_id
                    
                # If no session ID was provided, use timestamp
                if session_id is None:
                    session_id = f"session_{timestamp}"
                    
                # Extract and save audio payload
                if stream_event.HasField('segment_media'):
                    audio_chunk = stream_event.segment_media.audio_content.payload
                    audio_data.extend(audio_chunk)
                    
                    # Log progress
                    if len(audio_data) % (1024 * 10) < 1024:  # Log every ~10KB
                        logger.info(f"Session {session_id}: Received {len(audio_data)/1024:.2f} KB of audio data")
            
            # Save the complete audio file when the stream ends
            if audio_data:
                self._save_audio_file(session_id, audio_data)
                
            logger.info(f"Audio saving completed for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error during audio saving: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Audio saving error: {str(e)}")
            
        return audio_stream_pb2.google_dot_protobuf_dot_empty__pb2.Empty()
    
    def _save_audio_file(self, session_id, audio_data):
        """Save the audio data to a WAV file"""
        # Create a filename with session ID and timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.wav"
        filepath = os.path.join(AUDIO_SAVE_DIR, filename)
        
        # Create a WAV file (assuming LINEAR16 format, 16kHz, mono)
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes for 16-bit audio
            wf.setframerate(16000)
            wf.writeframes(audio_data)
            
        logger.info(f"Saved audio file: {filepath} ({len(audio_data)/1024:.2f} KB)")
        return filepath

# Global flag to control server restart
should_restart = True

def serve():
    global should_restart
    
    # Health check state
    server_healthy = {'status': True}
    
    # Create the server instance
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    audio_stream_pb2_grpc.add_StreamingServicer_to_server(
        AudioSaverService(), server
    )
        
    # Get the port from the environment variable or default to 8080
    port = int(os.environ.get("PORT", 443))
    
    # For Cloud Run, use 0.0.0.0 instead of [::]
    host = '0.0.0.0' if os.environ.get("K_SERVICE") else '[::]'
    server_address = f'{host}:{port}'
    
    # Check if SSL certificates are available
    cert_file = os.environ.get('SSL_CERT_FILE')
    key_file = os.environ.get('SSL_KEY_FILE')
    
    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        # Use secure connection with SSL certificates
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
    
    server.start()
    
    # Setup server health monitoring thread
    def health_monitor():
        consecutive_failures = 0
        
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            try:
                # Add health check logic here
                # Example: Check for external dependencies
                # If an issue is detected:
                if not server_healthy['status']:
                    consecutive_failures += 1
                    print(f"Health check failed {consecutive_failures} time(s) in a row")
                    
                    if consecutive_failures >= 3:
                        print("Critical health check failure detected. Initiating server restart...")
                        restart_server()
                        break
                else:
                    consecutive_failures = 0
                    
            except Exception as e:
                print(f"Error in health monitoring: {e}")
                traceback.print_exc()
    
    # Start the health monitor in a background thread
    monitor_thread = threading.Thread(target=health_monitor, daemon=True)
    monitor_thread.start()
    
    # Setup graceful shutdown
    def graceful_shutdown(signum, frame):
        global should_restart
        print("\nReceived signal to terminate. Shutting down server gracefully...")
        # Prevent auto-restart on shutdown signal
        should_restart = False
        # Stop server (if not already stopped)
        server.stop(grace=5)
        print("Server stopped successfully")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        should_restart = False
        print("\nKeyboard interrupt received. Shutting down server gracefully...")
        server.stop(grace=5)
        print("Server stopped successfully")
    except Exception as e:
        print(f"Server error: {e}")
        traceback.print_exc()
        # Let the restart logic handle this

def restart_server():
    """Function to restart the server"""
    global should_restart
    
    if not should_restart:
        print("Server restart disabled. Exiting...")
        return
        
    print("Restarting server in 5 seconds...")
    time.sleep(5)
    
    # Re-execute the current script
    os.execv(sys.executable, ['python'] + sys.argv)

if __name__ == '__main__':
    # Keep track of failures for exponential backoff
    failures = 0
    max_failures = 10
    
    while should_restart:
        try:
            # Reset connection pools or other resources that might be stale
            # Connection pools are often implemented by client libraries
            
            print(f"Starting server (attempt {failures+1})")
            serve()
            
            # If we get here and should_restart is still True, it means
            # the server exited unexpectedly
            failures += 1
            
            # Implement exponential backoff
            if failures >= max_failures:
                print(f"Too many failures ({failures}). Giving up.")
                sys.exit(1)
                
            # Calculate backoff time with jitter
            backoff_seconds = min(30, (2 ** failures) + (failures % 3))
            print(f"Server will restart in {backoff_seconds} seconds...")
            time.sleep(backoff_seconds)
            
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received. Exiting...")
            should_restart = False
            sys.exit(0)
        except Exception as e:
            print(f"Critical error in main loop: {e}")
            traceback.print_exc()
            failures += 1
            time.sleep(5) 