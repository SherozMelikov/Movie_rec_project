from app.db.models import User
from app.core.security import hash_password


def test_login_with_valid_credentials(client, db_session):
    db_user = User(
        username="login_user_tc02",
        email="login_user_tc02@example.com",
        password_hash=hash_password("Password123!"),
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)

    response = client.post(
        "/users/login",
        json={
            "username": "login_user_tc02",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"


def test_login_rejects_invalid_password(client, db_session):
    db_user = User(
        username="login_user_tc03",
        email="login_user_tc03@example.com",
        password_hash=hash_password("Password123!"),
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)

    response = client.post(
        "/users/login",
        json={
            "username": "login_user_tc03",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"]["code"] == "INVALID_CREDENTIALS"