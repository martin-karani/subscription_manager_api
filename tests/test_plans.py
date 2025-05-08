import pytest
from decimal import Decimal
from app.models import SubscriptionPlan
from app.services import create_plan_service  # For direct creation if needed

# Ensure tests that need the DB to be set up have _db_setup_teardown
# Tests using client for DB interaction will rely on the app context.
# Tests directly using db_session for setup/verification need db_session.


def test_create_plan_admin(client, admin_user_tokens, db_session, _db_setup_teardown):
    """Test plan creation by an admin."""
    access_token, _ = admin_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}

    plan_name = "Test Gold Plan Admin"  # Unique name
    plan_data = {
        "name": plan_name,
        "price": "49.99",
        "duration_days": 30,
        "description": "A shiny gold plan for testing.",
        "features": "Feature X, Feature Y",
    }
    response = client.post("/api/v1/plans", json=plan_data, headers=headers)
    assert (
        response.status_code == 201
    ), f"Plan creation failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()["data"]
    assert json_data["name"] == plan_name
    assert json_data["price"] == "49.99"

    plan_in_db = (
        db_session.query(SubscriptionPlan).filter_by(id=json_data["id"]).first()
    )
    assert plan_in_db is not None
    assert plan_in_db.name == plan_name


def test_create_plan_non_admin(client, regular_user_tokens, _db_setup_teardown):
    """Test plan creation attempt by a non-admin."""
    access_token, _ = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}

    plan_data = {
        "name": "Unauthorized Plan by RegUser",
        "price": "1.00",
        "duration_days": 7,
    }
    response = client.post("/api/v1/plans", json=plan_data, headers=headers)
    assert (
        response.status_code == 403
    ), f"Non-admin plan creation status: {response.status_code}"


def test_get_all_plans(client, db_session, _db_setup_teardown):
    """Test retrieving all plans (public endpoint)."""
    # Create plans directly for this test's scope to ensure they exist.
    # Use unique names to avoid conflict if other tests create similar plans.
    plan1_name = "Public Plan Test 1"
    plan2_name = "Public Plan Test 2"
    inactive_plan_name = "Inactive Plan Test"

    # Clear existing plans with these names if any (defensive)
    db_session.query(SubscriptionPlan).filter(
        SubscriptionPlan.name.in_([plan1_name, plan2_name, inactive_plan_name])
    ).delete(synchronize_session=False)
    db_session.commit()

    create_plan_service(
        name=plan1_name, price="10.00", duration_days=30, is_active=True
    )
    create_plan_service(
        name=plan2_name, price="20.00", duration_days=30, is_active=True
    )
    create_plan_service(
        name=inactive_plan_name, price="5.00", duration_days=30, is_active=False
    )
    # create_plan_service commits within its own transaction scope, which is part of db_session's nested transaction

    # Test getting active plans (default)
    response = client.get("/api/v1/plans")
    assert response.status_code == 200
    json_data = response.get_json()["data"]

    found_plan1 = any(p["name"] == plan1_name and p["is_active"] for p in json_data)
    found_plan2 = any(p["name"] == plan2_name and p["is_active"] for p in json_data)
    found_inactive = any(p["name"] == inactive_plan_name for p in json_data)

    assert found_plan1
    assert found_plan2
    assert not found_inactive

    # Test getting all plans (including inactive)
    response_all = client.get("/api/v1/plans?active=all")
    assert response_all.status_code == 200
    json_data_all = response_all.get_json()["data"]
    assert any(
        p["name"] == inactive_plan_name and not p["is_active"] for p in json_data_all
    )
    assert len(json_data_all) >= 3  # Check based on what you created


def test_get_specific_plan(client, db_session, _db_setup_teardown):
    """Test retrieving a specific plan by ID."""
    plan_name = "Specific Plan Test"
    # Clear existing (defensive)
    db_session.query(SubscriptionPlan).filter_by(name=plan_name).delete(
        synchronize_session=False
    )
    db_session.commit()

    plan = create_plan_service(name=plan_name, price="12.34", duration_days=15)

    response = client.get(f"/api/v1/plans/{plan.id}")
    assert response.status_code == 200
    json_data = response.get_json()["data"]
    assert json_data["id"] == plan.id
    assert json_data["name"] == plan_name
    assert json_data["price"] == "12.34"

    response_not_found = client.get("/api/v1/plans/999999")  # Use a very unlikely ID
    assert response_not_found.status_code == 404


def test_update_plan_admin(client, admin_user_tokens, db_session, _db_setup_teardown):
    """Test updating a plan by an admin."""
    access_token, _ = admin_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    plan_name = "Updatable Plan Test"
    # Clear existing (defensive)
    db_session.query(SubscriptionPlan).filter_by(name=plan_name).delete(
        synchronize_session=False
    )
    db_session.commit()

    plan = create_plan_service(name=plan_name, price="10.00", duration_days=30)

    update_data = {"description": "Updated plan description", "price": "12.50"}
    response = client.put(f"/api/v1/plans/{plan.id}", json=update_data, headers=headers)
    assert (
        response.status_code == 200
    ), f"Update failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()["data"]
    assert json_data["description"] == "Updated plan description"
    assert json_data["price"] == "12.50"

    updated_plan_db = db_session.query(SubscriptionPlan).filter_by(id=plan.id).first()
    assert updated_plan_db.description == "Updated plan description"
    assert updated_plan_db.price == Decimal("12.50")


def test_delete_plan_admin(client, admin_user_tokens, db_session, _db_setup_teardown):
    """Test deleting a plan by an admin."""
    access_token, _ = admin_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    plan_name = "Deletable Plan Test"
    # Clear existing (defensive)
    db_session.query(SubscriptionPlan).filter_by(name=plan_name).delete(
        synchronize_session=False
    )
    db_session.commit()

    plan_to_delete = create_plan_service(name=plan_name, price="5.00", duration_days=10)
    plan_id = plan_to_delete.id

    response = client.delete(f"/api/v1/plans/{plan_id}", headers=headers)
    assert response.status_code == 200  # Or 204 if preferred

    deleted_plan_db = db_session.query(SubscriptionPlan).filter_by(id=plan_id).first()
    assert deleted_plan_db is None
