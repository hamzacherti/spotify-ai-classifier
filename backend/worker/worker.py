import asyncio, logging
from backend.config import get_settings
from backend.database import SessionLocal
from backend.models import User
from backend.services.track_service import process_user

settings = get_settings()
log = logging.getLogger(__name__)

async def worker_loop():
    while True:
        db = SessionLocal()
        try:
            users = db.query(User).filter(User.active.is_(True)).all()
            log.info("[WORKER] Vérification de %s utilisateur(s)", len(users))
            for user in users:
                try:
                    await process_user(user, db)
                except Exception:
                    log.exception("[ERROR] utilisateur %s", user.id)
        finally:
            db.close()
        await asyncio.sleep(settings.poll_interval_seconds)
