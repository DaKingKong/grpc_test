# gRPC Audio Stream Server

A gRPC server for audio streaming and transcription using Google Cloud Speech API.

## Deployment to Render

### Option 1: Deploy from Dashboard

1. Create an account on [Render](https://render.com) if you don't have one

2. In the Render dashboard, click "New" and select "Web Service"

3. Connect your GitHub repository

4. Configure the service:
   - **Name**: grpc-audio-service (or your preferred name)
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
   - **Plan**: Free (or select a paid plan for production use)
   - **Advanced** → **Health Check Path**: `/health`
   - **Advanced** → **Health Check Port**: `8081`

5. Set up environment variables for Google Cloud credentials:
   ```
   GCP_PROJECT_ID=audio-streaming-456807
   GCP_CLIENT_EMAIL=audiostreaming@audio-streaming-456807.iam.gserviceaccount.com
   GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
   GCP_CLIENT_ID=101353014334693255163
   GCP_PRIVATE_KEY_ID=your-private-key-id
   ```

6. Click "Create Web Service"

### Option 2: Deploy via render.yaml (Blueprint)

1. Push the included `render.yaml` file to your GitHub repository

2. In the Render dashboard, click "New" and select "Blueprint"

3. Connect your GitHub repository

4. Configure the environment variables for Google Cloud credentials that are marked as manual in the render.yaml file:
   - `GCP_PRIVATE_KEY`
   - `GCP_PRIVATE_KEY_ID`

5. Click "Apply Blueprint"

## Connecting to the Deployed Service

When your service is deployed on Render, clients should connect to:
```
grpc-audio-service.onrender.com:443
```

The client needs to use a secure channel with SSL credentials:
```python
channel_credentials = grpc.ssl_channel_credentials()
with grpc.secure_channel('grpc-audio-service.onrender.com:443', channel_credentials) as channel:
    # Use the channel for gRPC requests
```

## Local Development

1. Install server dependencies:
   ```
   pip install -r requirements.txt
   ```

2. For client development (if using audio recording), install PyAudio:
   ```
   # Install system dependencies for PyAudio (client-side only)
   sudo apt-get install portaudio19-dev libasound2-dev  # For Ubuntu/Debian
   # OR
   sudo yum install portaudio-devel alsa-lib-devel      # For CentOS/RHEL

   # Install PyAudio
   pip install pyaudio==0.2.14
   ```

3. Set up Google Cloud credentials locally (choose one option):
   
   Option A: Using individual environment variables (recommended for security)
   ```
   export GCP_PROJECT_ID="audio-streaming-456807"
   export GCP_CLIENT_EMAIL="audiostreaming@audio-streaming-456807.iam.gserviceaccount.com"
   export GCP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
   # Optional parameters
   export GCP_CLIENT_ID="101353014334693255163"
   export GCP_PRIVATE_KEY_ID="your-private-key-id"
   ```
   
   Option B: Using the credential JSON directly
   ```
   export GOOGLE_CREDENTIALS_JSON='{"type":"service_account","project_id":"audio-streaming-456807","private_key_id":"...","private_key":"...","client_email":"audiostreaming@audio-streaming-456807.iam.gserviceaccount.com","client_id":"101353014334693255163","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/audiostreaming%40audio-streaming-456807.iam.gserviceaccount.com","universe_domain":"googleapis.com"}'
   ```
   
   Option C: Using a credential file (traditional approach)
   ```
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-file.json"
   ```

4. Run the server:
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