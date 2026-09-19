from backend.spotify.client import spotify_request


async def create_playlist(user, db, genre, public):
    from backend.models import Playlist

    # 1. Chercher d'abord dans PostgreSQL
    existing = (
        db.query(Playlist)
        .filter(
            Playlist.user_id == user.id,
            Playlist.genre == genre,
        )
        .first()
    )

    if existing:
        return existing.spotify_playlist_id

    # 2. Si absente de PostgreSQL, chercher sur Spotify
    response = await spotify_request(
        user,
        db,
        "GET",
        "/me/playlists?limit=50",
    )

    spotify_playlists = response.json().get("items", [])

    for playlist in spotify_playlists:
        if playlist.get("name") == genre:
            playlist_id = playlist["id"]

            db_playlist = Playlist(
                user_id=user.id,
                genre=genre,
                spotify_playlist_id=playlist_id,
            )

            db.add(db_playlist)
            db.commit()

            return playlist_id

    # 3. Si elle n'existe nulle part, la créer
    response = await spotify_request(
        user,
        db,
        "POST",
        "/me/playlists",
        json={
            "name": genre,
            "public": public,
            "collaborative": False,
            "description": "Created by Spotify AI Classifier",
        },
    )

    playlist_id = response.json()["id"]

    db_playlist = Playlist(
        user_id=user.id,
        genre=genre,
        spotify_playlist_id=playlist_id,
    )

    db.add(db_playlist)
    db.commit()

    return playlist_id


async def add_track(user, db, playlist_id, track_id):
    response = await spotify_request(
        user,
        db,
        "POST",
        f"/playlists/{playlist_id}/items",
        json={
            "uris": [f"spotify:track:{track_id}"]
        },
    )

    return response.json()