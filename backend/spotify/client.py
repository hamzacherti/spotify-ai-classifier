from datetime import datetime, timezone, timedelta
import asyncio
import logging
import httpx

from backend.config import get_settings
from backend.models import User

settings = get_settings()
API = "https://api.spotify.com/v1"

log = logging.getLogger(__name__)


class SpotifyError(Exception):
    pass


def ensure_utc(dt):
    """
    Normalise une datetime pour éviter les comparaisons
    entre datetime naive et datetime aware.
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


async def refresh_if_needed(user: User, db):
    expires = ensure_utc(user.token_expires_at)
    now = datetime.now(timezone.utc)

    if expires and expires > now + timedelta(minutes=2):
        return user.access_token

    log.info("[SPOTIFY] Token expiré ou bientôt expiré, refresh...")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": user.refresh_token,
            },
            auth=(
                settings.spotify_client_id,
                settings.spotify_client_secret,
            ),
        )

    if response.status_code in (400, 401):
        user.active = False
        db.commit()
        raise SpotifyError("Spotify refresh rejected")

    response.raise_for_status()

    data = response.json()

    user.access_token = data["access_token"]
    user.refresh_token = (
        data.get("refresh_token") or user.refresh_token
    )

    user.token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(seconds=data.get("expires_in", 3600))
    )

    db.commit()

    log.info("[SPOTIFY] Token rafraîchi avec succès")

    return user.access_token


async def spotify_request(user, db, method, path, **kwargs):
    """
    Effectue une requête Spotify avec :
    - refresh automatique du token ;
    - retry sur 401 ;
    - gestion du rate limit 429 ;
    - affichage du détail de l'erreur Spotify.
    """

    max_attempts = 5

    # IMPORTANT :
    # On récupère les headers UNE SEULE FOIS avant la boucle.
    headers = kwargs.pop("headers", {}).copy()

    for attempt in range(1, max_attempts + 1):

        token = await refresh_if_needed(user, db)

        headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.request(
                method,
                API + path,
                headers=headers,
                **kwargs,
            )

        # ---------------------------------------------------------
        # 401 : token invalide/expiré
        # ---------------------------------------------------------
        if response.status_code == 401:

            log.warning(
                "[SPOTIFY] 401 sur %s %s - renouvellement du token",
                method,
                path,
            )

            user.token_expires_at = datetime.now(timezone.utc)
            db.commit()

            continue

        # ---------------------------------------------------------
        # 429 : rate limit / quota Spotify
        # ---------------------------------------------------------
        if response.status_code == 429:

            retry_after = response.headers.get("Retry-After")

            try:
                error_data = response.json()
            except Exception:
                error_data = {}

            reason = error_data.get("error", {}).get("reason")
            message = error_data.get("error", {}).get("message")

            log.warning(
                "[SPOTIFY 429] %s %s",
                method,
                path,
            )

            log.warning(
                "[SPOTIFY 429] Retry-After=%s | reason=%s | message=%s | body=%s",
                retry_after,
                reason,
                message,
                error_data,
            )

            # -----------------------------------------------------
            # QUOTA_EXCEEDED
            # -----------------------------------------------------
            if reason == "QUOTA_EXCEEDED":

                raise SpotifyError(
                    "Spotify QUOTA_EXCEEDED : "
                    "le quota Development Mode de l'application "
                    "Spotify a été atteint."
                )

            # -----------------------------------------------------
            # Rate limit classique
            # -----------------------------------------------------
            try:
                wait_seconds = int(retry_after) if retry_after else 60
            except (TypeError, ValueError):
                wait_seconds = 60

            # On accepte jusqu'à 120 secondes.
            # Si Spotify fournit Retry-After, on le respecte.
            wait_seconds = max(1, min(wait_seconds, 120))

            if attempt >= max_attempts:

                raise SpotifyError(
                    f"Spotify rate limit toujours actif après "
                    f"{max_attempts} tentatives."
                )

            log.warning(
                "[SPOTIFY] Rate limit actif - "
                "attente de %s seconde(s) avant retry "
                "(tentative %s/%s)",
                wait_seconds,
                attempt,
                max_attempts,
            )

            await asyncio.sleep(wait_seconds)

            continue

        # ---------------------------------------------------------
        # Autres erreurs HTTP
        # ---------------------------------------------------------
        response.raise_for_status()

        return response

    raise SpotifyError("Spotify request failed after retries")


async def get_saved_tracks(user, db):
    tracks = []
    offset = 0

    while True:

        response = await spotify_request(
            user,
            db,
            "GET",
            "/me/tracks",
            params={
                "limit": 50,
                "offset": offset,
            },
        )

        data = response.json()

        items = data.get("items", [])

        tracks.extend(items)

        if not data.get("next") or not items:
            break

        offset += len(items)

    log.info(
        "[SPOTIFY] %s morceau(x) récupéré(s)",
        len(tracks),
    )

    return tracks