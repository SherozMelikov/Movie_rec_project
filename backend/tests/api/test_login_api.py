##pytest tests/integration/test_login_api.py -v

from app.db.models import User
from app.core.security import hash_password


def test_login_with_valid_credentials(client, db_session):
    # Arrange: create a registered user in the test DB
    db_user = User(
        username="login_user_tc02",
        email="login_user_tc02@example.com",
        password_hash=hash_password("Password123"),
    )
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)

    # Act: attempt login with valid credentials
    response = client.post(
        "/users/login",
        json={
            "username": "login_user_tc02",
            "password": "Password123",
        },
    )

    # Assert: successful authentication
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["access_token"] is not None
    assert data["token_type"] == "bearer"