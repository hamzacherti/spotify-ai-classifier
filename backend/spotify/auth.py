import secrets
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import User
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/auth")
settings = get_settings()
SCOPES = "user-library-read playlist-modify-private playlist-modify-public user-read-private"

@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {"response_type":"code","client_id":settings.spotify_client_id,
              "scope":SCOPES,"redirect_uri":settings.spotify_redirect_uri,"state":state}
    return RedirectResponse("https://accounts.spotify.com/authorize?" + urlencode(params))

@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state or not secrets.compare_digest(state, request.session.pop("oauth_state", "")):
        return RedirectResponse("/?error=oauth")
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post("https://accounts.spotify.com/api/token", data={
            "grant_type":"authorization_code","code":code,"redirect_uri":settings.spotify_redirect_uri},
            auth=(settings.spotify_client_id, settings.spotify_client_secret))
        token_resp.raise_for_status()
        tokens = token_resp.json()
        profile = await client.get("https://api.spotify.com/v1/me",
                                   headers={"Authorization":f"Bearer {tokens['access_token']}"})
        profile.raise_for_status()
        me = profile.json()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.spotify_id == me["id"]))
        expires = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
        if user is None:
            user = User(spotify_id=me["id"], display_name=me.get("display_name") or me["id"],
                        access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token",""),
                        token_expires_at=expires)
            db.add(user)
        else:
            user.display_name = me.get("display_name") or user.display_name
            user.access_token = tokens["access_token"]
            user.refresh_token = tokens.get("refresh_token") or user.refresh_token
            user.token_expires_at = expires
            user.active = True
        db.commit()
        request.session["user_id"] = user.id
    finally:
        db.close()
    return RedirectResponse("/")
