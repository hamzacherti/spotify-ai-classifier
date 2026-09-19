import logging
from datetime import datetime

from httpx import HTTPStatusError
from sqlalchemy import select

from backend.models import ProcessedTrack, Playlist
from backend.spotify.client import get_saved_tracks
from backend.spotify.playlists import create_playlist, add_track
from backend.ai.genre_classifier import classify
from backend.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


async def process_user(user, db):
    items = await get_saved_tracks(user, db)

    existing = [
        x[0]
        for x in db.execute(
            select(Playlist.genre).where(
                Playlist.user_id == user.id
            )
        ).all()
    ]

    for item in reversed(items):
        track = item.get("track") or {}
        track_id = track.get("id")

        if not track_id:
            continue

        done = db.scalar(
            select(ProcessedTrack).where(
                ProcessedTrack.user_id == user.id,
                ProcessedTrack.spotify_track_id == track_id,
            )
        )

        if done:
            continue

        title = track.get("name", "Unknown")

        artist = ", ".join(
            a.get("name", "")
            for a in track.get("artists", [])
        )

        try:
            # =========================
            # CLASSIFICATION GEMINI
            # =========================

            genre = await classify(
                title,
                artist,
                existing,
            )

            # =========================
            # RECHERCHE PLAYLIST
            # =========================

            playlist = db.scalar(
                select(Playlist).where(
                    Playlist.user_id == user.id,
                    Playlist.genre == genre,
                )
            )

            # =========================
            # CRÉATION SI ABSENTE
            # =========================

            if playlist is None:
                playlist_id = await create_playlist(
                    user,
                    db,
                    genre,
                    settings.playlist_public,
                )

                playlist = Playlist(
                    user_id=user.id,
                    genre=genre,
                    spotify_playlist_id=playlist_id,
                )

                db.add(playlist)
                db.commit()

                log.info(
                    "[PLAYLIST] Nouvelle playlist créée : %s -> %s",
                    genre,
                    playlist_id,
                )

            # =========================
            # AJOUT DU MORCEAU
            # =========================

            try:
                await add_track(
                    user,
                    db,
                    playlist.spotify_playlist_id,
                    track_id,
                )

            except HTTPStatusError as exc:

                if exc.response.status_code == 404:

                    old_playlist_id = playlist.spotify_playlist_id

                    log.warning(
                        "[PLAYLIST] Playlist Spotify introuvable : %s",
                        old_playlist_id,
                    )

                    # Supprime l'ancien enregistrement local
                    db.delete(playlist)
                    db.commit()

                    # Crée une nouvelle playlist Spotify
                    new_playlist_id = await create_playlist(
                        user,
                        db,
                        genre,
                        settings.playlist_public,
                    )

                    new_playlist = Playlist(
                        user_id=user.id,
                        genre=genre,
                        spotify_playlist_id=new_playlist_id,
                    )

                    db.add(new_playlist)
                    db.commit()

                    playlist = new_playlist

                    log.info(
                        "[PLAYLIST] Playlist recréée : %s -> %s",
                        genre,
                        new_playlist_id,
                    )

                    # Réessaie l'ajout
                    await add_track(
                        user,
                        db,
                        playlist.spotify_playlist_id,
                        track_id,
                    )

                else:
                    raise

            # =========================
            # ENREGISTREMENT DU MORCEAU
            # =========================

            added_at = item.get("added_at")

            parsed = (
                datetime.fromisoformat(
                    added_at.replace("Z", "+00:00")
                )
                if added_at
                else None
            )

            db.add(
                ProcessedTrack(
                    user_id=user.id,
                    spotify_track_id=track_id,
                    title=title,
                    artist=artist,
                    genre=genre,
                    spotify_added_at=parsed,
                )
            )

            db.commit()

            if genre not in existing:
                existing.append(genre)

            log.info(
                "[OK] %s - %s -> %s",
                artist,
                title,
                genre,
            )

        except Exception:
            db.rollback()

            log.exception(
                "[ERROR] user=%s track=%s",
                user.id,
                track_id,
            )