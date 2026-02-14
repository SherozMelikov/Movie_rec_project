# app/db/models.py
import enum
from sqlalchemy import (
    Column, Date, DateTime, Enum, ForeignKey,
    Integer, BigInteger, SmallInteger, Text, String, func
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from app.db.database import Base


class Movie(Base):
    __tablename__ = "movies"

    movie_id = Column(Integer, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    genres = Column(Text)  # or Text[] if you want array

    ratings = relationship("Rating", back_populates="movie")
    likes = relationship("Like", back_populates="movie")
    tags = relationship("Tag", back_populates="movie")

    # ✅ FIX: add metadata relationship to match MovieMetadata(back_populates="movie")
    tmdb_metadata = relationship("MovieMetadata", back_populates="movie", uselist=False)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ratings = relationship("Rating", back_populates="user")
    likes = relationship("Like", back_populates="user")
    tags = relationship("Tag", back_populates="user")


class Rating(Base):
    __tablename__ = "ratings"

    rating_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), nullable=False)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ratings")
    movie = relationship("Movie", back_populates="ratings")


class Like(Base):
    __tablename__ = "likes"

    like_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="likes")
    movie = relationship("Movie", back_populates="likes")


class Tag(Base):
    __tablename__ = "tags"

    tag_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), nullable=False)
    tag = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="tags")
    movie = relationship("Movie", back_populates="tags")


class EventType(str, enum.Enum):
    view = "view"
    like = "like"
    rate = "rate"


class Event(Base):
    __tablename__ = "events"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(EventType, name="event_type"), nullable=False)
    rating_value = Column(SmallInteger, nullable=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserOnboarding(Base):
    __tablename__ = "user_onboarding"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    favorite_genres = Column(ARRAY(Text), nullable=False, server_default="{}")
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserOnboardingMovie(Base):
    __tablename__ = "user_onboarding_movies"

    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MovieMetadata(Base):
    __tablename__ = "movie_metadata"

    movie_id = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"), primary_key=True)
    tmdb_id = Column(Integer, unique=True, index=True, nullable=True)

    overview = Column(Text, nullable=True)
    poster_path = Column(Text, nullable=True)
    backdrop_path = Column(Text, nullable=True)
    release_date = Column(Date, nullable=True)

    status = Column(String, nullable=False, default="pending")  # pending|found|not_found|error
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    movie = relationship("Movie", back_populates="tmdb_metadata", uselist=False)














