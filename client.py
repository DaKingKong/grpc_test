import grpc
import pyaudio
import uuid
import time
import signal
import sys
import audio_stream_pb2
import audio_stream_pb2_grpc

# Audio recording parameters
RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Global flag to control audio streaming
running = True

def signal_handler(signum, frame):
    global running
    print("\nReceived signal to terminate. Stopping audio capture...")
    running = False

def generate_stream_events():
    """
    Generator that captures audio from microphone and yields StreamEvent messages.
    """
    global running
    session_id = str(uuid.uuid4())
    segment_id = str(uuid.uuid4())
    
    # Initialize audio stream from microphone
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    print("Recording audio... Press Ctrl+C to stop")
    
    # First, send a dialog init event
    dialog_init = audio_stream_pb2.DialogInitEvent(
        account=audio_stream_pb2.Account(id="test_account"),
        dialog=audio_stream_pb2.Dialog(id="test_dialog", type=audio_stream_pb2.DialogType.INBOUND)
    )
    yield audio_stream_pb2.StreamEvent(
        session_id=session_id,
        dialog_init=dialog_init
    )
    
    # Then send a segment start event
    segment_start = audio_stream_pb2.SegmentStartEvent(
        segment_id=segment_id,
        participant=audio_stream_pb2.Participant(id="user", type=audio_stream_pb2.ParticipantType.CONTACT),
        audio_format=audio_stream_pb2.AudioFormat(
            codec=audio_stream_pb2.Codec.L16,
            rate=RATE,
            ptime=20  # 20ms chunks
        )
    )
    yield audio_stream_pb2.StreamEvent(
        session_id=session_id,
        segment_start=segment_start
    )
    
    # Start sending audio data
    seq = 0
    try:
        while running:
            audio_chunk = stream.read(CHUNK, exception_on_overflow=False)
            
            # Create audio content message
            audio_content = audio_stream_pb2.AudioContent(
                payload=audio_chunk,
                seq=seq,
                duration=int(CHUNK * 1000 / RATE)  # duration in milliseconds
            )
            
            # Create segment media event
            segment_media = audio_stream_pb2.SegmentMediaEvent(
                segment_id=segment_id,
                audio_content=audio_content
            )
            
            # Create and yield stream event
            yield audio_stream_pb2.StreamEvent(
                session_id=session_id,
                segment_media=segment_media
            )
            
            seq += 1
            
    except KeyboardInterrupt:
        print("Stopping audio capture...")
    finally:
        # Close audio stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Send segment stop event
        segment_stop = audio_stream_pb2.SegmentStopEvent(
            segment_id=segment_id
        )
        yield audio_stream_pb2.StreamEvent(
            session_id=session_id,
            segment_stop=segment_stop
        )
        print("Audio capture stopped and resources released")

def run():
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    # For secure connections, you typically don't need root certificates
    # unless you are using custom or self-signed certificates.
    # gRPC clients usually trust standard CAs by default.
    # If you encounter certificate validation issues, you might need to
    # provide root certificates or disable validation (not recommended for production).
    # For connecting to ngrok, the default should work.
    channel_credentials = grpc.ssl_channel_credentials()
    
    try:
        # Create gRPC channel
        with grpc.secure_channel('sip-bot.labs.ringcentral.com:443', channel_credentials) as channel:
        # with grpc.insecure_channel('localhost:443') as channel:
            # Create stub
            stub = audio_stream_pb2_grpc.StreamingStub(channel)
            
            print("Connecting to server...")
            
            # Call Stream method with the generator
            response = stub.Stream(generate_stream_events())
            
            print("Audio streaming complete")
    except KeyboardInterrupt:
        print("\nClient shutdown initiated")
    except grpc.RpcError as e:
        print(f"\nRPC error occurred: {e.code()} - {e.details()}")
    finally:
        print("Client terminated")

if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Exiting...")
        sys.exit(0) 