import grpc
import concurrent.futures
import signal
import sys
import traceback
import os
import ringcx_streaming_pb2_grpc
from google.protobuf.empty_pb2 import Empty
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('simple-speech-server')

class StreamingService(ringcx_streaming_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        logger.info("Server started, waiting for audio stream...")
        
        try:
            for stream_event in request_iterator:
                if stream_event.HasField('segment_media'):
                    payload_size = len(stream_event.segment_media.audio_content.payload)
                    logger.info(f"Received segment media with payload size: {payload_size} bytes")
                elif stream_event.HasField('segment_metadata'):
                    logger.info(f"Received segment metadata: {stream_event.segment_metadata}")
                else:
                    logger.info(f"Received other stream event type")
            
            logger.info("Stream completed.")
            
        except Exception as e:
            logger.error(f"Error during stream processing: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Stream processing error: {str(e)}")
            
        return Empty()

should_restart = True

def serve():
    global should_restart
    
    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    ringcx_streaming_pb2_grpc.add_StreamingServicer_to_server(
        StreamingService(), server
    )
    
    port = int(os.environ.get("PORT", 443))
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
        global should_restart
        logger.info("Received signal to terminate. Shutting down server gracefully...")
        should_restart = False
        server.stop(grace=5)
        logger.info("Server stopped successfully")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        should_restart = False
        logger.info("Keyboard interrupt received. Shutting down server gracefully...")
        server.stop(grace=5)
        logger.info("Server stopped successfully")
    except Exception as e:
        logger.error(f"Server error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    try:
        logger.info("Starting simple server")
        serve()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Exiting...")
        should_restart = False
        sys.exit(0)
    except Exception as e:
        logger.error(f"Critical error in main loop: {e}")
        traceback.print_exc()
        sys.exit(1) 