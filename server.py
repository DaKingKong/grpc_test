import grpc
import concurrent.futures
import signal
import sys
import time
import threading
import traceback
import os # Import the os module
import json
from google.cloud import speech
from google.oauth2 import service_account
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

# Configure Google Cloud credentials
def setup_google_credentials():
    """Set up Google Cloud credentials from environment variables"""
    # Check for credentials in environment variables
    creds = None
    
    # Option 1: Build credentials from individual env vars
    if os.environ.get('GCP_PROJECT_ID') and os.environ.get('GCP_CLIENT_EMAIL') and os.environ.get('GCP_PRIVATE_KEY'):
        logger.info("Using Google credentials from individual environment variables")
        try:
            creds_dict = {
                "type": "service_account",
                "project_id": os.environ.get('GCP_PROJECT_ID'),
                "private_key_id": os.environ.get('GCP_PRIVATE_KEY_ID', ""),
                "private_key": os.environ.get('GCP_PRIVATE_KEY').replace('\\n', '\n'),
                "client_email": os.environ.get('GCP_CLIENT_EMAIL'),
                "client_id": os.environ.get('GCP_CLIENT_ID', ""),
                "auth_uri": os.environ.get('GCP_AUTH_URI', "https://accounts.google.com/o/oauth2/auth"),
                "token_uri": os.environ.get('GCP_TOKEN_URI', "https://oauth2.googleapis.com/token"),
                "auth_provider_x509_cert_url": os.environ.get('GCP_AUTH_PROVIDER_X509_CERT_URL', "https://www.googleapis.com/oauth2/v1/certs"),
                "client_x509_cert_url": os.environ.get('GCP_CLIENT_X509_CERT_URL', ""),
                "universe_domain": os.environ.get('GCP_UNIVERSE_DOMAIN', "googleapis.com")
            }
            creds = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            logger.error(f"Error creating credentials from environment variables: {e}")
            raise
    
    # Option 2: JSON credentials directly in an environment variable
    elif os.environ.get('GOOGLE_CREDENTIALS_JSON'):
        logger.info("Using Google credentials from GOOGLE_CREDENTIALS_JSON environment variable")
        try:
            creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
            creds_dict = json.loads(creds_json)
            creds = service_account.Credentials.from_service_account_info(creds_dict)
        except Exception as e:
            logger.error(f"Error parsing GOOGLE_CREDENTIALS_JSON: {e}")
            raise
    
    # Option 3: Path to credentials file (standard approach)
    elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        logger.info(f"Using Google credentials from file: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
        # The google-cloud libraries will automatically use this environment variable
    
    # No credentials found
    else:
        logger.warning("No Google credentials found in environment variables. Using default authentication method.")
    
    return creds

class StreamingService(audio_stream_pb2_grpc.StreamingServicer):
    def __init__(self, credentials=None):
        self.credentials = credentials
        
    def Stream(self, request_iterator, context):
        print("Server started, waiting for audio stream...")
        
        # Configure Google Cloud Speech client with credentials if provided
        if self.credentials:
            client = speech.SpeechClient(credentials=self.credentials)
        else:
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
    
    # Set up Google credentials
    credentials = setup_google_credentials()
    
    # Health check state
    server_healthy = {'status': True}
    
    # Create the server instance
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    audio_stream_pb2_grpc.add_StreamingServicer_to_server(
        StreamingService(credentials=credentials), server
    )
        
    # Get the port from the environment variable or default to 8080
    port = int(os.environ.get("PORT", 8080))
    
    # For Heroku, we always use 0.0.0.0
    host = '0.0.0.0'
    server_address = f'{host}:{port}'
    
    server.add_insecure_port(server_address)
    server.start()
    logger.info(f"Server started at {server_address}")
    
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