"""
Shared configuration for logging and Spotify OAuth across the application.
"""

import os
import logging
import sys
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Logging Configuration
# ============================================================================

def setup_logging():
    """Configure logging to output to console with consistent formatting."""
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

    # Configure specific loggers for FastAPI/Uvicorn
    logging.getLogger("uvicorn").addHandler(console_handler)
    logging.getLogger("uvicorn.access").addHandler(console_handler)
    logging.getLogger("fastapi").addHandler(console_handler)

    return logging.getLogger(__name__)


# ============================================================================
# Spotify Configuration
# ============================================================================

# Spotify credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/callback")

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables must be set")

# Spotify OAuth scopes
SPOTIFY_SCOPE = "user-read-currently-playing user-read-recently-played playlist-modify-public playlist-modify-private"

# Initialize SpotifyOAuth
sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SPOTIFY_SCOPE
)
