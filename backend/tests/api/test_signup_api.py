## pytest tests/integration/test_signup_api.py -v

from app.db.models import User
def test_signup_creates_user(client, db_session):
    response = client.post(
        "/users/signup",
        json={
            "username": "newuser_tc01",
            "email": "newuser_tc01@example.com",
            "password": "Password123",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["username"] == "newuser_tc01"
    assert data["email"] == "newuser_tc01@example.com"
    assert "user_id" in data
    assert "password_hash" not in data
    assert "password" not in data

    db_user = (
        db_session.query(User)
        .filter(User.email == "newuser_tc01@example.com")
        .first()
    )

    assert db_user is not None
    assert db_user.password_hash != "Password123"