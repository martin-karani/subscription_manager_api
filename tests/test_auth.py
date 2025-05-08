import pytest
from app.models import User


def test_register_user(client, db_session, _db_setup_teardown):
    """Test user registration."""
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser_auth_test",
            "email": "newuser_auth_test@example.com",
            "password": "password123",
        },
    )
    assert (
        response.status_code == 201
    ), f"Registration failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["data"]["username"] == "newuser_auth_test"
    assert "id" in json_data["data"]

    user_in_db = (
        db_session.query(User).filter_by(email="newuser_auth_test@example.com").first()
    )
    assert user_in_db is not None
    assert user_in_db.username == "newuser_auth_test"

    response_dup_uname = client.post(
        "/auth/register",
        json={
            "username": "newuser_auth_test",
            "email": "another_auth_test@example.com",
            "password": "password123",
        },
    )
    assert response_dup_uname.status_code == 400

    # Test duplicate email
    response_dup_email = client.post(
        "/auth/register",
        json={
            "username": "anotheruser_auth_test",
            "email": "newuser_auth_test@example.com",  # Duplicate email
            "password": "password123",
        },
    )
    assert response_dup_email.status_code == 400


def test_login_user(client, db_session, _db_setup_teardown):
    """Test user login."""
    from app.services import register_user_service  # Import locally

    # Use unique credentials for this test
    username = "loginuser_auth_test"
    email = "login_auth_test@example.com"
    password = "testpassword"

    # Ensure user exists for login
    user = db_session.query(User).filter_by(email=email).first()
    if not user:
        user = register_user_service(username, email, password)
        # register_user_service commits, which is fine within this test's transaction

    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert (
        response.status_code == 200
    ), f"Login failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert "access_token" in json_data["data"]
    assert "refresh_token" in json_data["data"]
    assert json_data["data"]["user"]["username"] == username

    # Test login with wrong password
    response_wrong_pass = client.post(
        "/auth/login", json={"username": username, "password": "wrongpassword"}
    )
    assert response_wrong_pass.status_code == 401


def test_get_me(
    client, regular_user_tokens, _db_setup_teardown
):  # regular_user_tokens depends on auth_tokens which uses db_session
    """Test the /auth/me endpoint."""
    access_token, user_id_from_token_fixture = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}

    response = client.get("/auth/me", headers=headers)
    assert (
        response.status_code == 200
    ), f"/auth/me failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()
    assert json_data["status"] == "success"
    assert json_data["data"]["id"] == user_id_from_token_fixture
    # Username in token fixture is "testuser_reg"
    assert json_data["data"]["username"] == "testuser_reg"
    assert "email" in json_data["data"]


def test_refresh_token(
    client, db_session, _db_setup_teardown
):  # Using db_session to create user directly for this test
    """Test token refresh functionality."""
    from app.services import register_user_service

    username = "refreshuser_auth_test"
    email = "refresh_auth_test@example.com"
    password = "password"

    user = db_session.query(User).filter_by(email=email).first()
    if not user:
        user = register_user_service(username, email, password)

    login_resp = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert login_resp.status_code == 200, "Login failed before refresh test"

    login_json_data = login_resp.get_json()
    assert "data" in login_json_data and "refresh_token" in login_json_data["data"]
    refresh_token = login_json_data["data"]["refresh_token"]
    access_token_old = login_json_data["data"]["access_token"]

    headers_refresh = {"Authorization": f"Bearer {refresh_token}"}
    response_refresh = client.post("/auth/refresh", headers=headers_refresh)

    assert (
        response_refresh.status_code == 200
    ), f"Refresh failed: {response_refresh.get_data(as_text=True)}"
    json_data_refresh = response_refresh.get_json()
    assert json_data_refresh["status"] == "success"
    assert "access_token" in json_data_refresh["data"]
    assert (
        json_data_refresh["data"]["access_token"] != access_token_old
    )  # Ensure new token is different

    # Test using an access token for refresh (should fail)
    headers_invalid_type = {"Authorization": f"Bearer {access_token_old}"}
    response_invalid_type = client.post("/auth/refresh", headers=headers_invalid_type)
    # Flask-JWT-Extended might return 401 (if token type check is strict early) or 422 (if it processes it as wrong type)
    assert response_invalid_type.status_code in [
        401,
        422,
    ], "Refresh with access token did not fail as expected."
