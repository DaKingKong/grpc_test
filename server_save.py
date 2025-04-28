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
import struct

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

# Create directory for raw data
RAW_DATA_DIR = os.path.join(os.getcwd(), "raw_audio")
os.makedirs(RAW_DATA_DIR, exist_ok=True)

class AudioSaverService(audio_stream_pb2_grpc.StreamingServicer):
    def Stream(self, request_iterator, context):
        logger.info("Starting to record 5 seconds of audio...")
        
        # Generate a unique filename using timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        
        # Buffer to collect audio data
        audio_data = bytearray()
        
        # Track audio format information
        audio_format = {
            'codec': None,
            'rate': 16000,  # Default to 16kHz if not specified
            'ptime': 20,    # Default to 20ms if not specified
            'channels': 1   # Mono
        }
        
        # Track segment info
        segment_ids = set()
        
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
                
                # Check if this is a segment start event with format info
                if stream_event.HasField('segment_start'):
                    segment_start = stream_event.segment_start
                    segment_id = segment_start.segment_id
                    segment_ids.add(segment_id)
                    
                    # Extract audio format if available
                    if segment_start.HasField('audio_format'):
                        fmt = segment_start.audio_format
                        audio_format['codec'] = audio_stream_pb2.Codec.Name(fmt.codec)
                        print(f"Audio format: codec={audio_format['codec']}, rate={audio_format['rate']}Hz, ptime={audio_format['ptime']}ms")
                        audio_format['rate'] = fmt.rate
                        audio_format['ptime'] = fmt.ptime
                        logger.info(f"Audio format: codec={audio_format['codec']}, rate={audio_format['rate']}Hz, ptime={audio_format['ptime']}ms")
                
                # Extract audio payload from segment media event
                elif stream_event.HasField('segment_media'):
                    media = stream_event.segment_media
                    segment_id = media.segment_id
                    
                    if segment_id not in segment_ids:
                        segment_ids.add(segment_id)
                        logger.info(f"New segment ID detected: {segment_id}")
                    
                    audio_chunk = media.audio_content.payload
                    audio_data.extend(audio_chunk)
                    
                    # Log current data size
                    if len(audio_data) % (1024 * 10) < 1024:  # Log every ~10KB
                        logger.info(f"Received {len(audio_data)/1024:.2f} KB of audio data")
                
                # Handle segment stop events
                elif stream_event.HasField('segment_stop'):
                    segment_id = stream_event.segment_stop.segment_id
                    logger.info(f"Segment stop received for segment {segment_id}")
            
            # Save the audio to file - both as WAV and raw bytes for diagnosis
            if audio_data:
                # Save raw bytes for debugging
                raw_path = self._save_raw_file(session_id, audio_data)
                logger.info(f"Raw audio bytes saved to {raw_path}")
                
                # Save as WAV
                wav_path = self._save_audio_file(session_id, audio_data, audio_format)
                logger.info(f"Audio saved to {wav_path}")
                
                # Analyze first few bytes to detect potential format issues
                self._analyze_audio_bytes(audio_data[:100])
            else:
                logger.warning("No audio data received during the 5-second window")
                
        except Exception as e:
            logger.error(f"Error during audio recording: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            
        return audio_stream_pb2.google_dot_protobuf_dot_empty__pb2.Empty()
    
    def _save_audio_file(self, session_id, audio_data, audio_format):
        """Save audio data to a WAV file"""
        filename = f"{session_id}.wav"
        filepath = os.path.join(AUDIO_SAVE_DIR, filename)
        
        # Determine sample width based on codec
        sample_width = 2  # Default to 16-bit audio (2 bytes)
        if audio_format['codec'] == 'OPUS':
            # OPUS is variable bitrate, we'll save raw bytes and use ffmpeg later if needed
            sample_width = 2
        elif audio_format['codec'] in ['PCMA', 'PCMU']:
            # A-law and μ-law are 8-bit
            sample_width = 1
        
        # Create WAV file
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(audio_format['channels'])
            wf.setsampwidth(sample_width)
            wf.setframerate(audio_format['rate'])
            wf.writeframes(audio_data)
            
        return filepath
    
    def _save_raw_file(self, session_id, audio_data):
        """Save raw audio bytes for debugging"""
        filename = f"{session_id}.raw"
        filepath = os.path.join(RAW_DATA_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(audio_data)
            
        return filepath
    
    def _analyze_audio_bytes(self, audio_bytes):
        """Analyze first few bytes to detect potential issues"""
        if len(audio_bytes) < 10:
            logger.warning("Audio sample too small to analyze")
            return
            
        # Check first few bytes for patterns
        try:
            logger.info(f"First 10 bytes: {' '.join([f'{b:02x}' for b in audio_bytes[:10]])}")
            
            # Check if it could be 16-bit PCM (look for patterns)
            if len(audio_bytes) >= 4:
                # Try as 16-bit integers (both endianness)
                le_ints = struct.unpack(f"<{len(audio_bytes)//2}h", audio_bytes[:len(audio_bytes)//2*2])
                be_ints = struct.unpack(f">{len(audio_bytes)//2}h", audio_bytes[:len(audio_bytes)//2*2])
                
                logger.info(f"As 16-bit LE: {le_ints[:5]}")
                logger.info(f"As 16-bit BE: {be_ints[:5]}")
                
                # Simple heuristic for detecting correct endianness
                le_variance = sum((x - le_ints[0])**2 for x in le_ints[:5]) / 5
                be_variance = sum((x - be_ints[0])**2 for x in be_ints[:5]) / 5
                
                if le_variance > be_variance:
                    logger.info("Likely big-endian data")
                else:
                    logger.info("Likely little-endian data")
        except Exception as e:
            logger.error(f"Error analyzing audio bytes: {e}")

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