# app/db/models.py
from sqlalchemy import Column, Integer, String
from app.db.database import Base

#Databse tables structure :

# CREATE TABLE movies (
#     movie_id INT PRIMARY KEY,
#     title TEXT,
#     genres TEXT
# );

# CREATE TABLE links (
#     movie_id INT PRIMARY KEY,
#     imdb_id TEXT,
#     tmdb_id TEXT
# );

#CREATE TABLE users (
#     user_id SERIAL PRIMARY KEY,
#     username TEXT UNIQUE,
#     email TEXT UNIQUE,
#     password_hash TEXT,
#     created_at TIMESTAMP DEFAULT NOW()
# );

# CREATE TABLE ratings (
#     user_id INT REFERENCES users(user_id),
#     movie_id INT REFERENCES movies(movie_id),
#     rating FLOAT,
#     rated_at TIMESTAMP DEFAULT NOW(),
#     PRIMARY KEY (user_id, movie_id)
# );

# CREATE TABLE likes (
#     user_id INT REFERENCES users(user_id),
#     movie_id INT REFERENCES movies(movie_id),
#     liked_at TIMESTAMP DEFAULT NOW(),
#     PRIMARY KEY (user_id, movie_id)
# );

# CREATE TABLE user_preferences (
#     user_id INT REFERENCES users(user_id),
#     favorite_genres TEXT,
#     created_at TIMESTAMP DEFAULT NOW(),
#     PRIMARY KEY (user_id)
# );

# CREATE TABLE movie_metadata (
#     movie_id INT PRIMARY KEY REFERENCES movies(movie_id),
#     year INT,
#     poster_url TEXT,
#     backdrop_url TEXT,
#     plot TEXT
# );

# app/db/models.py
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Movie(Base):
    __tablename__ = "movies"
    movie_id = Column(Integer, primary_key=True)
    title = Column(Text)
    genres = Column(Text)

class Link(Base):
    __tablename__ = "links"
    movie_id = Column(Integer, primary_key=True)
    imdb_id = Column(Text)
    tmdb_id = Column(Text)

class MovieMetadata(Base):
    __tablename__ = "movie_metadata"
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), primary_key=True)
    year = Column(Integer)
    poster_url = Column(Text)
    backdrop_url = Column(Text)
    plot = Column(Text)

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(Text, unique=True)
    email = Column(Text, unique=True)
    password_hash = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Rating(Base):
    __tablename__ = "ratings"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), primary_key=True)
    rating = Column(Float)
    rated_at = Column(TIMESTAMP, server_default=func.now())

class Like(Base):
    __tablename__ = "likes"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    movie_id = Column(Integer, ForeignKey("movies.movie_id"), primary_key=True)
    liked_at = Column(TIMESTAMP, server_default=func.now())

class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    favorite_genres = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())
