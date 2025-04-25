# gRPC Audio Transcription System

This project implements a simple gRPC-based system where a client captures audio from a microphone and sends it to a server for real-time transcription using Google Cloud Speech-to-Text API.

## Features

- Client captures audio from the microphone and streams it to the server via gRPC
- Server receives the audio stream and transcribes it using Google Cloud Speech-to-Text streaming API
- Real-time transcription of audio
- Minimal logging - only shows start, end, and transcribed text

## Prerequisites

- Python 3.7+
- Google Cloud account with Speech-to-Text API enabled
- Google Cloud credentials set up

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set up Google Cloud credentials:
   ```
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-file.json"
   ```
   On Windows:
   ```
   set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\service-account-file.json
   ```

## Usage

1. Start the server:
   ```
   python server.py
   ```

2. In a separate terminal, start the client to begin capturing audio:
   ```
   python client.py
   ```

3. Speak into your microphone. The audio will be streamed to the server and transcribed in real-time.

4. Press `Ctrl+C` to stop the client and terminate the audio capture.

## Architecture

- **Client**: Captures audio from the microphone, packages it according to the defined protocol, and streams it to the server.
- **Server**: Receives the audio stream, processes it through Google Cloud Speech-to-Text API, and outputs transcription results.

## Protocol

The system uses gRPC with protocol buffers for communication. The audio stream follows a specific format defined in `audio_stream.proto`.

## How It Works

The system uses the following components:

1. **Protocol Buffers**: Defines the message structure for communication between client and server (audio_stream.proto)
2. **gRPC**: Handles the bidirectional streaming communication
3. **PyAudio**: Captures audio from the microphone on the client side
4. **Google Cloud Speech-to-Text API**: Performs the streaming speech recognition on the server side

## Troubleshooting

- If you encounter microphone issues, check your system's audio settings and ensure PyAudio can access your microphone.
- For authentication errors with Google Cloud, verify your credentials are correctly set up.
- For network issues, check that the server is running and accessible from the client machine.

## Project Structure

- `audio_stream.proto`: The protocol definition
- `audio_stream_pb2.py`: Generated protocol buffer code
- `audio_stream_pb2_grpc.py`: Generated gRPC service code
- `server.py`: Server implementation with Google Cloud Speech integration
- `client.py`: Client implementation with microphone support
- `ngrok_setup.py`: Helper script for setting up ngrok
- `README.md`: This file

## Audio Capture Details

The client uses PyAudio to capture audio from the default microphone device. Audio is captured with the following parameters:
- Sample rate: 8000 Hz (telephone quality)
- Format: 16-bit PCM
- Channels: 1 (mono)
- Chunk size: 160 samples (20ms at 8000 Hz)

The audio is then sent in real-time to the gRPC server using the streaming API.

## Speech Recognition Details

The server uses Google Cloud Speech-to-Text API to transcribe the audio it receives in real-time. Key features:

- Audio codec conversion: Converts PCMA/PCMU to LINEAR16 format required by Google Cloud
- Streams audio to Google Cloud Speech API in real-time
- Uses the "phone_call" model which is optimized for telephone quality audio
- Returns both interim (in-progress) and final transcription results
- Handles multiple simultaneous audio streams (from different segments)

## License

[MIT License] 