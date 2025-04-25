# gRPC Audio Stream Server

A gRPC server for audio streaming and transcription using Google Cloud Speech API.

## Deployment to Heroku

1. Create a Heroku app:
   ```
   heroku create
   ```

2. Add buildpacks:
   ```
   heroku buildpacks:clear
   heroku buildpacks:add heroku/python
   ```

3. Set up Google Cloud credentials:
   ```
   heroku config:set GOOGLE_APPLICATION_CREDENTIALS=path/to/your/credentials.json
   ```

4. Upload your Google Cloud credentials file:
   - Place your Google Cloud credentials JSON file in the project directory
   - Make sure to add the file path to .gitignore to avoid committing sensitive data

5. Deploy to Heroku:
   ```
   git push heroku main
   ```

## Local Development

1. Install dependencies:
   ```
   # Install system dependencies (only required for source builds)
   sudo apt-get install portaudio19-dev libasound2-dev  # For Ubuntu/Debian
   # OR
   sudo yum install portaudio-devel alsa-lib-devel      # For CentOS/RHEL

   # Install Python dependencies
   pip install -r requirements.txt
   ```

2. Run the server:
   ```
   python server.py
   ```

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