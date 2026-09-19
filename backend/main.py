import asyncio, logging
from pathlib import Path
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from backend.config import get_settings
from backend.database import init_db, get_db
from backend.models import User
from backend.spotify.auth import router as auth_router
from backend.services.user_service import get_user_stats
from backend.worker.worker import worker_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = get_settings()
app = FastAPI(title="Spotify AI Classifier")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=False)
app.include_router(auth_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent.parent / "frontend"), name="static")

@app.on_event("startup")
async def startup():
    init_db()
    app.state.worker_task = asyncio.create_task(worker_loop())

@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "worker_task", None)
    if task:
        task.cancel()

def current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None

@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent.parent / "frontend" / "index.html").read_text(encoding="utf-8")

@app.get("/api/me")
async def me(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"authenticated":False})
    return {"authenticated":True, **get_user_stats(db, user.id)}

@app.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
