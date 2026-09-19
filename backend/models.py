from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    spotify_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(String(2048))
    refresh_token: Mapped[str] = mapped_column(String(2048))
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    processed_tracks = relationship("ProcessedTrack", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship("Playlist", back_populates="user", cascade="all, delete-orphan")

class ProcessedTrack(Base):
    __tablename__ = "processed_tracks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    spotify_track_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(500))
    artist: Mapped[str] = mapped_column(String(500))
    genre: Mapped[str] = mapped_column(String(255))
    spotify_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user = relationship("User", back_populates="processed_tracks")
    __table_args__ = (UniqueConstraint("user_id", "spotify_track_id", name="uq_user_track"),)

class Playlist(Base):
    __tablename__ = "playlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    genre: Mapped[str] = mapped_column(String(255))
    spotify_playlist_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user = relationship("User", back_populates="playlists")
    __table_args__ = (UniqueConstraint("user_id", "genre", name="uq_user_genre"),)
