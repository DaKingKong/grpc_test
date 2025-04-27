import grpc
import concurrent.futures
import signal
import sys
import time
import threading
import traceback
import os # Import the os module
from google.cloud import speech
import audio_stream_pb2
import audio_stream_pb2_grpc
import logging

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('speech-server')

class StreamingService(audio_stream_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        print("Server started, waiting for audio stream...")
        
        # Configure Google Cloud Speech client
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )
        
        # This generator converts the incoming gRPC audio stream to the format 
        # expected by Google Cloud Speech API
        def audio_generator():
            for stream_event in request_iterator:
                # session_id = stream_event.session_id
                # segment_id = stream_event.segment_media.segment_id
                # payload = stream_event.segment_media.audio_content.payload
                # seq = stream_event.segment_media.audio_content.seq
                # duration = stream_event.segment_media.audio_content.duration
                # logger.info(f"{session_id}: SegmentMedia, segment_id: {segment_id}, payload size: {len(payload)}, seq: {seq}, duration: {duration}")
                if stream_event.HasField('segment_media'):
                    yield speech.StreamingRecognizeRequest(
                        audio_content=stream_event.segment_media.audio_content.payload
                    )
        
        # Start streaming recognition
        try:            
            responses = client.streaming_recognize(
                config=streaming_config,
                requests=audio_generator()
            )
            
            for response in responses:
                if not response.results:
                    continue
                    
                result = response.results[0]
                if result.is_final:
                    transcript = result.alternatives[0].transcript
                    print(f"Transcription: {transcript}")
                    
            print("Transcription completed.")
            
        except Exception as e:
            print(f"Error during transcription: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Transcription error: {str(e)}")
            
        return audio_stream_pb2.google_dot_protobuf_dot_empty__pb2.Empty()

# Global flag to control server restart
should_restart = True

def serve():
    global should_restart
    
    # Health check state
    server_healthy = {'status': True}
    
    # Create the server instance
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    audio_stream_pb2_grpc.add_StreamingServicer_to_server(
        StreamingService(), server
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