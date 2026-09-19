from backend.spotify.client import spotify_request


async def create_playlist(user, db, genre, public):
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

    return response.json()["id"]


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