"""
Standalone script to update playlists with recently played tracks.
Can be run via cron job.
"""

import logging
from datetime import datetime, timedelta
import spotipy
from config import sp_oauth, setup_logging
from models import SessionLocal, User, Playlist

setup_logging()
logger = logging.getLogger(__name__)

MAX_PLAYLIST_CAPACITY = 100


def refresh_user_token_if_expired(db, user):
    """Refresh user's Spotify token if it has expired."""
    if user.token_expires_at and user.token_expires_at < datetime.utcnow():
        logger.debug(f"Token expired for user {user.id}, refreshing")
        token_info = sp_oauth.refresh_access_token(user.refresh_token)
        user.access_token = token_info['access_token']
        user.refresh_token = token_info.get('refresh_token', user.refresh_token)
        user.token_expires_at = datetime.utcnow() + timedelta(seconds=token_info['expires_in'])
        db.commit()
        logger.debug(f"Token refreshed for user {user.id}")


def get_current_track_id(sp):
    """Get the currently playing track ID, or None if no track is playing."""
    logger.debug("Fetching currently playing track")
    current_track = sp.current_user_playing_track()

    if current_track and current_track.get('item') and current_track['item'].get('id'):
        track_id = current_track['item']['id']
        track_name = current_track['item'].get('name', 'Unknown')
        logger.debug(f"Currently playing: {track_name} (id={track_id})")
        return track_id

    logger.debug("No track currently playing")
    return None


def get_recently_played_track_ids(sp, limit=50):
    """Get recently played track IDs."""
    logger.debug(f"Fetching recently played tracks (limit={limit})")
    recently_played = sp.current_user_recently_played(limit=limit)
    track_ids = [item['track']['id'] for item in recently_played['items']]
    logger.debug(f"Found {len(track_ids)} recently played tracks")
    return track_ids


def get_playlist_track_ids(sp, playlist_id):
    """Get all track IDs in a playlist, handling pagination."""
    logger.debug(f"Fetching tracks from playlist {playlist_id}")
    current_tracks_result = sp.playlist_tracks(playlist_id)
    track_ids = [item['track']['id'] for item in current_tracks_result['items']]

    # Handle pagination for playlists with more than 100 tracks
    while current_tracks_result.get('next'):
        current_tracks_result = sp.next(current_tracks_result)
        track_ids.extend([item['track']['id'] for item in current_tracks_result['items']])

    logger.debug(f"Playlist has {len(track_ids)} current tracks")
    return track_ids


def get_new_track_ids(current_track_id, recently_played_ids, existing_playlist_ids):
    """Determine which new tracks to add to the playlist."""
    new_track_ids = []

    # Add currently playing track first if it's not already in the playlist
    if current_track_id and current_track_id not in existing_playlist_ids:
        logger.debug(f"Will add currently playing track to top: {current_track_id}")
        new_track_ids.append(current_track_id)

    # Add recently played tracks that aren't already in the playlist
    for track_id in recently_played_ids:
        if track_id not in existing_playlist_ids and track_id not in new_track_ids:
            new_track_ids.append(track_id)

    return new_track_ids


def maintain_playlist_capacity(sp, playlist_id, current_track_ids, num_new_tracks):
    """Remove oldest tracks if adding new tracks would exceed capacity."""
    total_tracks = len(current_track_ids) + num_new_tracks

    if total_tracks > MAX_PLAYLIST_CAPACITY:
        tracks_to_remove = total_tracks - MAX_PLAYLIST_CAPACITY
        logger.debug(
            f"Playlist would exceed {MAX_PLAYLIST_CAPACITY} tracks, "
            f"removing {tracks_to_remove} oldest tracks"
        )

        # Remove the oldest tracks (from the end of the current list)
        track_ids_to_remove = current_track_ids[-tracks_to_remove:]
        sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids_to_remove)


def add_tracks_to_playlist(sp, playlist_id, track_ids):
    """Add tracks to the top of the playlist."""
    if not track_ids:
        return

    logger.debug(f"Adding {len(track_ids)} new tracks to top of playlist")
    sp.playlist_add_items(playlist_id, track_ids, position=0)
    logger.info(f"Successfully added {len(track_ids)} tracks to playlist")


def update_user_playlists(db, user):
    """Update all playlists for a user."""
    refresh_user_token_if_expired(db, user)

    sp = spotipy.Spotify(auth=user.access_token)

    # Get user's track data
    current_track_id = get_current_track_id(sp)
    recently_played_ids = get_recently_played_track_ids(sp)

    # Update each of user's playlists
    playlists = db.query(Playlist).filter(Playlist.user_id == user.id).all()
    logger.debug(f"User {user.id} has {len(playlists)} playlists")

    for playlist in playlists:
        logger.debug(
            f"Updating playlist: {playlist.playlist_name} "
            f"({playlist.spotify_playlist_id})"
        )

        # Get current tracks in this playlist
        playlist_track_ids = get_playlist_track_ids(sp, playlist.spotify_playlist_id)

        # Determine which new tracks to add
        new_track_ids = get_new_track_ids(
            current_track_id,
            recently_played_ids,
            playlist_track_ids
        )

        if new_track_ids:
            logger.debug(f"Found {len(new_track_ids)} new tracks to add")

            # Maintain capacity and add tracks
            maintain_playlist_capacity(
                sp,
                playlist.spotify_playlist_id,
                playlist_track_ids,
                len(new_track_ids)
            )
            add_tracks_to_playlist(sp, playlist.spotify_playlist_id, new_track_ids)
        else:
            logger.debug(f"No new tracks to add to playlist {playlist.playlist_name}")


def update_playlists():
    """Main function to update all user playlists."""
    db = SessionLocal()
    try:
        logger.info("Starting playlist update job")
        users = db.query(User).all()
        logger.debug(f"Found {len(users)} users to update")

        for user in users:
            try:
                logger.debug(f"Processing user: id={user.id}, spotify_id={user.spotify_id}")
                update_user_playlists(db, user)
            except Exception as e:
                logger.exception(f"Error updating playlists for user {user.id}: {e}")

        logger.info("Playlist update job completed")
    except Exception as e:
        logger.exception(f"Error in playlist update job: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    update_playlists()
