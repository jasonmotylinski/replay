from fastapi import FastAPI, Depends, HTTPException, Request, Query, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import spotipy
from models import get_db, User, Playlist
from datetime import datetime, timedelta
import logging
from config import sp_oauth, setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
async def login():
    logger.info("Login initiated")
    auth_url = sp_oauth.get_authorize_url()
    logger.debug(f"Redirecting to auth_url: {auth_url}")
    return RedirectResponse(auth_url)

@app.get("/callback")
async def callback(code: str = Query(...), db: Session = Depends(get_db)):
    logger.info("Callback received from Spotify")
    try:
        logger.debug(f"Exchanging code for access token")
        token_info = sp_oauth.get_access_token(code)

        if token_info:
            logger.debug(f"Access token obtained, fetching user info")
            sp = spotipy.Spotify(auth=token_info['access_token'])
            user_info = sp.current_user()
            logger.debug(f"User info retrieved: spotify_id={user_info['id']}")

            # Check if user exists
            user = db.query(User).filter(User.spotify_id == user_info['id']).first()
            if not user:
                logger.info(f"Creating new user: spotify_id={user_info['id']}")
                user = User(
                    spotify_id=user_info['id'],
                    access_token=token_info['access_token'],
                    refresh_token=token_info.get('refresh_token'),
                    token_expires_at=datetime.utcnow() + timedelta(seconds=token_info['expires_in'])
                )
                db.add(user)
            else:
                logger.info(f"Updating existing user: spotify_id={user_info['id']}")
                user.access_token = token_info['access_token']
                user.refresh_token = token_info.get('refresh_token')
                user.token_expires_at = datetime.utcnow() + timedelta(seconds=token_info['expires_in'])

            db.commit()
            logger.info(f"User saved to database: user_id={user.id}")

            # Redirect to playlist creation page
            return RedirectResponse(f"/create_playlist?user_id={user.id}")

        logger.error("No token_info received from Spotify")
        raise HTTPException(status_code=400, detail="Authentication failed")
    except Exception as e:
        logger.exception(f"Error in callback: {e}")
        raise

@app.get("/create_playlist", response_class=HTMLResponse)
async def create_playlist_page(
    request: Request,
    user_id: int = Query(...),
    db: Session = Depends(get_db)
):
    logger.debug(f"create_playlist_page called with user_id={user_id}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User not found with id={user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    logger.debug(f"Fetching Spotify username for user {user_id}")
    sp = spotipy.Spotify(auth=user.access_token)
    user_info = sp.current_user()
    spotify_username = user_info.get('display_name') or user_info.get('id', 'User')
    logger.debug(f"Spotify username: {spotify_username}")

    default_playlist_name = f"{spotify_username}'s Replay"

    # Check if user already has a playlist
    existing_playlist = db.query(Playlist).filter(Playlist.user_id == user_id).first()
    if existing_playlist:
        logger.debug(f"Existing playlist found for user {user_id}: {existing_playlist.playlist_name}")
        return templates.TemplateResponse(
            "create_playlist.html",
            {
                "request": request,
                "user_id": user_id,
                "playlist_name": existing_playlist.playlist_name,
                "is_update": True
            }
        )

    logger.debug(f"No existing playlist for user {user_id}")
    return templates.TemplateResponse(
        "create_playlist.html",
        {
            "request": request,
            "user_id": user_id,
            "playlist_name": default_playlist_name,
            "is_update": False
        }
    )

@app.post("/playlist")
async def create_or_update_playlist(
    playlist_name: str = Form(...),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"create_or_update_playlist called with playlist_name={playlist_name}, user_id={user_id}")

    try:
        logger.debug(f"Querying user with id={user_id}")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found with id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        logger.debug(f"Found user: spotify_id={user.spotify_id}")

        logger.debug(f"Creating Spotify client with access token")
        sp = spotipy.Spotify(auth=user.access_token)

        # Check if user already has a playlist
        existing_playlist = db.query(Playlist).filter(Playlist.user_id == user_id).first()

        if existing_playlist:
            logger.info(f"Updating existing playlist: id={existing_playlist.spotify_playlist_id}")
            # Update playlist name on Spotify
            logger.debug(f"Updating playlist name on Spotify: {existing_playlist.spotify_playlist_id} -> {playlist_name}")
            sp.playlist_change_details(
                existing_playlist.spotify_playlist_id,
                name=playlist_name,
                description="Auto-updated playlist with recently played tracks"
            )

            # Update in database
            existing_playlist.playlist_name = playlist_name
            db.commit()
            logger.info(f"Playlist updated successfully: id={existing_playlist.spotify_playlist_id}")

            return {"message": "Playlist updated successfully", "playlist_id": existing_playlist.spotify_playlist_id}
        else:
            logger.info(f"Creating new playlist: name={playlist_name}")
            # Create new playlist on Spotify
            logger.debug(f"Creating playlist on Spotify: name={playlist_name}, user={user.spotify_id}")
            playlist = sp.user_playlist_create(
                user.spotify_id,
                playlist_name,
                public=False,
                description="Auto-updated playlist with recently played tracks"
            )
            logger.debug(f"Spotify playlist created: id={playlist['id']}")

            # Save to database
            logger.debug(f"Saving playlist to database: user_id={user.id}, name={playlist_name}, spotify_id={playlist['id']}")
            db_playlist = Playlist(
                user_id=user.id,
                playlist_name=playlist_name,
                spotify_playlist_id=playlist['id']
            )
            db.add(db_playlist)
            db.commit()
            logger.info(f"Playlist created successfully: id={playlist['id']}")

            return {"message": "Playlist created successfully", "playlist_id": playlist['id']}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating or updating playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/playlist-success", response_class=HTMLResponse)
async def playlist_success(
    request: Request,
    playlist_id: str = Query(...),
    action: str = Query(default="create")
):
    logger.debug(f"playlist_success called with playlist_id={playlist_id}, action={action}")

    # Build Spotify playlist URL
    spotify_playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
    logger.debug(f"Generated Spotify URL: {spotify_playlist_url}")

    return templates.TemplateResponse(
        "playlist_success.html",
        {
            "request": request,
            "spotify_playlist_url": spotify_playlist_url,
            "action": action
        }
    )

@app.get("/user")
async def get_user(user_id: int = Query(...), db: Session = Depends(get_db)):
    logger.info(f"get_user called with user_id={user_id}")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User not found with id={user_id}")
        raise HTTPException(status_code=404, detail="User not found")

    logger.debug(f"Querying playlists for user_id={user_id}")
    playlists = db.query(Playlist).filter(Playlist.user_id == user.id).all()
    logger.debug(f"Found {len(playlists)} playlists for user_id={user_id}")
    return {
        "spotify_id": user.spotify_id,
        "playlists": [{"name": p.playlist_name, "spotify_id": p.spotify_playlist_id} for p in playlists]
    }

