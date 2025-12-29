# Replay - Spotify Playlist Manager

A web application that creates and maintains auto-updating Spotify playlists with your recently played tracks.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up Spotify App:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Set redirect URI to `http://localhost:8000/callback`
   - Copy Client ID and Client Secret

4. Set environment variables:
   Copy `.env.example` to `.env` and fill in your Spotify credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```
   
   Make sure the `SPOTIFY_REDIRECT_URI` matches exactly what you set in your Spotify app dashboard.

5. Initialize the database:
   ```bash
   python init_db.py
   ```

## Running the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

**Important**: Make sure your Spotify app's redirect URI is set to `http://localhost:8000/callback` (exactly matching the `SPOTIFY_REDIRECT_URI` in your `.env` file).

## Features

- Login with Spotify
- Create auto-updating playlists
- Background job updates playlists hourly with recently played tracks