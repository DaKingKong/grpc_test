import grpc
import concurrent.futures
import signal
import sys
import traceback
import os
from google.cloud import speech
import ringcx_streaming_pb2_grpc
from google.protobuf.empty_pb2 import Empty
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('speech-server')

class StreamingService(ringcx_streaming_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        logger.info("Server started, waiting for audio stream...")
        
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MULAW,
            sample_rate_hertz=8000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True,
        )
        
        def audio_generator():
            for stream_event in request_iterator:
                if stream_event.HasField('segment_media'):
                    yield speech.StreamingRecognizeRequest(
                        audio_content=stream_event.segment_media.audio_content.payload
                    )
        
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
                    logger.info(f"Transcription: {transcript}")
            
            logger.info("Transcription completed.")
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Transcription error: {str(e)}")
            
        return Empty()

def serve():
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    ringcx_streaming_pb2_grpc.add_StreamingServicer_to_server(
        StreamingService(), server
    )
    
    port = int(os.environ.get("PORT", 443)) # We only support 443 port at the moment
    host = '0.0.0.0'
    server_address = f'{host}:{port}'
    
    cert_file = os.environ.get('SSL_CERT_FILE')
    key_file = os.environ.get('SSL_KEY_FILE')
    
    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        with open(cert_file, 'rb') as f:
            cert_data = f.read()
        with open(key_file, 'rb') as f:
            key_data = f.read()
            
        server_credentials = grpc.ssl_server_credentials([(key_data, cert_data)])
        server.add_secure_port(server_address, server_credentials)
        logger.info(f"Server started with SSL at {server_address}")
    else:
        server.add_insecure_port(server_address)
        logger.info(f"Server started without SSL at {server_address} (insecure)")
    
    server.start()
    
    def graceful_shutdown(signum, frame):
        logger.info("Received signal to terminate. Shutting down server gracefully...")
        server.stop(grace=5)
        logger.info("Server stopped successfully")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down server gracefully...")
        server.stop(grace=5)
        logger.info("Server stopped successfully")
    except Exception as e:
        logger.error(f"Server error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    try:
        logger.info("Starting server")
        serve()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}")
        traceback.print_exc()
        sys.exit(1) 