import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import User, ProcessedTrack, Playlist


SOURCE_DB = "sqlite:///./spotify_ai.db"

TARGET_DB = os.environ.get("DATABASE_PUBLIC_URL")

if not TARGET_DB:
    raise RuntimeError(
        "DATABASE_PUBLIC_URL n'est pas définie dans les variables d'environnement."
    )

print("Connexion à PostgreSQL...")

source_engine = create_engine(
    SOURCE_DB,
    connect_args={"check_same_thread": False},
)

target_engine = create_engine(
    TARGET_DB,
    pool_pre_ping=True,
)

SourceSession = sessionmaker(bind=source_engine)
TargetSession = sessionmaker(bind=target_engine)

print("Création des tables PostgreSQL...")
Base.metadata.create_all(bind=target_engine)

source = SourceSession()
target = TargetSession()


def utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


try:
    users = source.query(User).all()
    tracks = source.query(ProcessedTrack).all()
    playlists = source.query(Playlist).all()

    print(f"Utilisateurs trouvés : {len(users)}")
    print(f"Morceaux trouvés : {len(tracks)}")
    print(f"Playlists trouvées : {len(playlists)}")

    # Nettoyage uniquement de PostgreSQL.
    # La base SQLite locale n'est jamais modifiée.
    target.query(ProcessedTrack).delete()
    target.query(Playlist).delete()
    target.query(User).delete()
    target.commit()

    # Users
    for u in users:
        target.add(
            User(
                id=u.id,
                spotify_id=u.spotify_id,
                display_name=u.display_name,
                access_token=u.access_token,
                refresh_token=u.refresh_token,
                token_expires_at=utc(u.token_expires_at),
                active=u.active,
                created_at=utc(u.created_at),
                updated_at=utc(u.updated_at),
            )
        )

    target.commit()

    # Playlists
    for p in playlists:
        target.add(
            Playlist(
                id=p.id,
                user_id=p.user_id,
                genre=p.genre,
                spotify_playlist_id=p.spotify_playlist_id,
                created_at=utc(p.created_at),
            )
        )

    target.commit()

    # Processed tracks
    for t in tracks:
        target.add(
            ProcessedTrack(
                id=t.id,
                user_id=t.user_id,
                spotify_track_id=t.spotify_track_id,
                title=t.title,
                artist=t.artist,
                genre=t.genre,
                spotify_added_at=utc(t.spotify_added_at),
                processed_at=utc(t.processed_at),
            )
        )

    target.commit()

    # Remettre les séquences PostgreSQL correctement.
    for table in ["users", "processed_tracks", "playlists"]:
        target.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1),
                    true
                )
                """
            )
        )

    target.commit()

    print()
    print("========================================")
    print("MIGRATION TERMINÉE")
    print("========================================")
    print(f"Utilisateurs : {target.query(User).count()}")
    print(f"Morceaux : {target.query(ProcessedTrack).count()}")
    print(f"Playlists : {target.query(Playlist).count()}")
    print("========================================")

finally:
    source.close()
    target.close()