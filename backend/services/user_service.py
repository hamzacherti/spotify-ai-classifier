from sqlalchemy import select, func
from backend.models import User, ProcessedTrack, Playlist

def get_user_stats(db, user_id):
    user = db.get(User, user_id)
    return {
        "display_name": user.display_name if user else None,
        "processed_tracks": db.scalar(select(func.count()).select_from(ProcessedTrack).where(ProcessedTrack.user_id==user_id)) or 0,
        "playlists": db.scalar(select(func.count()).select_from(Playlist).where(Playlist.user_id==user_id)) or 0,
    }
