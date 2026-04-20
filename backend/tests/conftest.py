import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("SECRET_KEY", "test_secret_key")

from app.main import app
from app.db.database import get_db
from app.db.models import User,Movie, MovieMetadata, Like, Rating, UserOnboardingMovie

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="function")
def db_session():
    User.__table__.create(bind=engine, checkfirst=True)
    Movie.__table__.create(bind=engine, checkfirst=True)
    MovieMetadata.__table__.create(bind=engine, checkfirst=True)
    Like.__table__.create(bind=engine, checkfirst=True)
    Rating.__table__.create(bind=engine, checkfirst=True)
    UserOnboardingMovie.__table__.create(bind=engine, checkfirst=True)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Rating.__table__.drop(bind=engine, checkfirst=True)
        Like.__table__.drop(bind=engine, checkfirst=True)
        MovieMetadata.__table__.drop(bind=engine, checkfirst=True)
        Movie.__table__.drop(bind=engine, checkfirst=True)
        User.__table__.drop(bind=engine, checkfirst=True)
        UserOnboardingMovie.__table__.drop(bind=engine, checkfirst=True)
    

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()