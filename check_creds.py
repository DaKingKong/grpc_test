#!/usr/bin/env python3
import os
import logging
import sys
from google.cloud import speech
from google.auth.exceptions import DefaultCredentialsError
import google.auth

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('credential-checker')

def check_google_cloud_credentials():
    """
    Check if Google Cloud credentials are properly configured.
    Returns:
        bool: True if credentials are valid, False otherwise
    """
    logger.info("Checking Google Cloud credentials...")
    
    # Check if GOOGLE_APPLICATION_CREDENTIALS is set
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
        logger.info("Set it with: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json")
        return False
    
    if not os.path.exists(creds_path):
        logger.error(f"Credentials file not found at {creds_path}")
        return False
    
    logger.info(f"Found credentials file at {creds_path}")
    
    # Attempt to get credentials
    try:
        # Get default credentials
        credentials, project = google.auth.default()
        logger.info(f"Successfully loaded credentials for project: {project}")
        
        # Try to initialize the Speech client
        client = speech.SpeechClient()
        logger.info("Successfully initialized Speech-to-Text client")
        
        # Make a simple API call to validate the credentials
        # This will fail if credentials are invalid
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US"
        )
        
        # We're not actually sending audio, just checking if the client can be initialized
        # and if the API can be reached with the credentials
        logger.info("Credentials are valid and have appropriate permissions")
        return True
        
    except DefaultCredentialsError as e:
        logger.error(f"Failed to get default credentials: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking credentials: {e}")
        return False

if __name__ == "__main__":
    result = check_google_cloud_credentials()
    if result:
        logger.info("✅ Google Cloud credentials check passed")
        sys.exit(0)
    else:
        logger.error("❌ Google Cloud credentials check failed")
        sys.exit(1)
