import pytest
import sys
import os
from datetime import (
    timedelta,
)  # Make sure timedelta is imported if used in TestingConfig directly here

# Add the project root directory for proper module imports if needed
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db as _db  # aliasing to _db is a common convention
from app.models import User, SubscriptionPlan, UserSubscription  # Import all models


@pytest.fixture(scope="session")
def app():
    """Session-wide test Flask application."""
    _app = create_app(config_name="testing")
    # You might want to ensure TestingConfig is loaded here explicitly if there's any doubt
    # For example, by directly creating config object:
    # from config import TestingConfig
    # _app.config.from_object(TestingConfig())
    return _app


@pytest.fixture(scope="session")
def _db_setup_teardown(app):
    """
    Handles session-wide DB setup (table creation) and teardown (table drop).
    Requires the app fixture to ensure app context.
    """
    with app.app_context():
        _db.create_all()  # Create tables once per test session
    yield  # Nothing to yield, just setup/teardown
    with app.app_context():
        _db.session.remove()  # Clean up main session
        _db.drop_all()  # Drop tables once per test session


@pytest.fixture(scope="function")
def db_session(_db_setup_teardown, app):  # Depends on tables being created
    """
    Provides a function-scoped, transaction-isolated database session.
    """
    with app.app_context():  # Ensure app context for db.session
        _db.session.begin_nested()  # Start a SAVEPOINT
        yield _db.session  # Provide the session to the test
        _db.session.rollback()  # Rollback the SAVEPOINT


@pytest.fixture
def client(app):
    """A test client for the app."""
    # _db_setup_teardown dependency isn't strictly needed here if all DB interactions
    # in tests use the db_session fixture. Client itself doesn't directly use DB.
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def auth_tokens(client, db_session):  # Changed to db_session
    """Creates a test user and returns auth tokens."""

    def _auth_tokens(username_suffix="", email_suffix="", is_admin=False):
        from app.services import register_user_service  # Import locally

        # Create unique usernames/emails for each call to avoid conflicts
        # even if somehow data leaks between tests (though db_session should prevent this)
        username = f"testuser{username_suffix}"
        email = f"test{email_suffix}@example.com"
        password = "password"

        user = User.query.with_session(db_session).filter_by(email=email).first()
        if not user:
            user = register_user_service(username, email, password, is_admin=is_admin)
            # register_user_service already calls db.session.commit() which will be part of the nested transaction
        else:
            # This branch should ideally not be hit if db_session isolation works perfectly
            user.set_password(password)
            db_session.add(
                user
            )  # ensure it's part of the current session if re-fetched
            # db_session.commit() # Not strictly needed if set_password doesn't require immediate flush for login

        login_data = {"username": username, "password": password}
        response = client.post("/auth/login", json=login_data)

        assert (
            response.status_code == 200
        ), f"Login failed for {username}: {response.get_data(as_text=True)}"

        tokens_data = response.get_json()
        assert (
            tokens_data["status"] == "success"
        ), f"Login response status not success for {username}"
        assert (
            "data" in tokens_data and "access_token" in tokens_data["data"]
        ), f"Token data missing for {username}"

        return tokens_data["data"], user.id

    return _auth_tokens


@pytest.fixture
def regular_user_tokens(auth_tokens):
    """Provides tokens for a regular (non-admin) user."""
    # Using suffixes to ensure uniqueness if this fixture is called multiple times indirectly
    tokens, user_id = auth_tokens(
        username_suffix="_reg", email_suffix="_reg", is_admin=False
    )
    return tokens["access_token"], user_id


@pytest.fixture
def admin_user_tokens(auth_tokens):
    """Provides tokens for an admin user."""
    tokens, user_id = auth_tokens(
        username_suffix="_admin", email_suffix="_admin", is_admin=True
    )
    return tokens["access_token"], user_id
