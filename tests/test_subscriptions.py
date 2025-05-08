import pytest
from app.models import (
    SubscriptionPlan,
    UserSubscription,
)  # Added SubscriptionPlan for direct query
from app.services import create_plan_service  # For direct creation

# Using unique names for plans created in fixtures or tests is crucial
# if the database isn't perfectly reset to an empty state before each test function,
# or if fixtures are re-used in a way that causes name clashes.
# The db_session with nested transactions should prevent this for function-scoped data.


@pytest.fixture
def sample_plan_for_sub_tests(db_session):  # Renamed for clarity, uses db_session
    """
    Creates a unique sample plan for each test function that uses this fixture.
    Relies on db_session fixture for transaction management.
    """
    plan_name = "SubTest Plan Alpha"  # A name likely unique to this fixture's use

    # Attempt to find if a plan with this name exists from a previous (failed/unrolled) test run.
    # This is defensive; ideally, db_session rollback handles everything.
    plan = db_session.query(SubscriptionPlan).filter_by(name=plan_name).first()
    if plan:  # If it somehow exists, delete it to ensure a clean state for this test
        active_subs_count = (
            db_session.query(UserSubscription)
            .filter_by(plan_id=plan.id, status="active")
            .count()
        )
        if active_subs_count == 0:
            db_session.delete(plan)
            db_session.commit()  # Commit deletion before trying to recreate
        else:
            # This state should ideally not be reached if tests are isolated
            pytest.skip(
                f"Plan '{plan_name}' exists with active subscriptions, skipping test to avoid conflict."
            )

    new_plan = create_plan_service(
        name=plan_name,
        price="19.99",
        duration_days=30,
        description="A plan for subscription testing.",
        is_active=True,
    )
    # create_plan_service commits; this commit is part of db_session's nested transaction
    return new_plan


def test_subscribe_to_plan(
    client,
    regular_user_tokens,
    sample_plan_for_sub_tests,
    db_session,
    _db_setup_teardown,
):
    access_token, user_id = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    current_plan = sample_plan_for_sub_tests  # Use the correctly scoped and named plan

    response = client.post(
        "/api/v1/subscriptions/subscribe",
        json={"plan_id": current_plan.id},
        headers=headers,
    )
    assert (
        response.status_code == 201
    ), f"Subscription failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()["data"]
    assert json_data["plan_id"] == current_plan.id
    assert json_data["user_id"] == user_id
    assert json_data["status"] == "active"

    sub_in_db = (
        db_session.query(UserSubscription)
        .filter_by(user_id=user_id, plan_id=current_plan.id, status="active")
        .first()
    )
    assert sub_in_db is not None


def test_get_active_subscription(
    client,
    regular_user_tokens,
    sample_plan_for_sub_tests,
    db_session,
    _db_setup_teardown,
):
    access_token, user_id = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    current_plan = sample_plan_for_sub_tests

    # Subscribe the user first
    sub_resp = client.post(
        "/api/v1/subscriptions/subscribe",
        json={"plan_id": current_plan.id},
        headers=headers,
    )
    assert (
        sub_resp.status_code == 201
    ), "Failed to subscribe user before getting active subscription."

    response = client.get("/api/v1/subscriptions/active", headers=headers)
    assert (
        response.status_code == 200
    ), f"Get active sub failed: {response.get_data(as_text=True)}"
    json_data = response.get_json()["data"]
    assert json_data is not None
    assert json_data["plan_id"] == current_plan.id
    assert json_data["user_id"] == user_id
    assert json_data["status"] == "active"
    assert json_data["plan_name"] == current_plan.name


def test_get_subscription_history(
    client,
    regular_user_tokens,
    sample_plan_for_sub_tests,
    db_session,
    _db_setup_teardown,
):
    access_token, user_id = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    plan1 = sample_plan_for_sub_tests  # First plan for this test

    # Subscribe to plan1
    client.post(
        "/api/v1/subscriptions/subscribe", json={"plan_id": plan1.id}, headers=headers
    )

    # Create and subscribe to a second, different plan for history
    plan2_name = "SubTest Plan Bravo"
    db_session.query(SubscriptionPlan).filter_by(name=plan2_name).delete(
        synchronize_session=False
    )  # Defensive clear
    db_session.commit()
    plan2 = create_plan_service(
        name=plan2_name, price="5.00", duration_days=10, is_active=True
    )

    client.post(
        "/api/v1/subscriptions/subscribe", json={"plan_id": plan2.id}, headers=headers
    )
    # The subscribe service should have cancelled the sub to plan1

    response = client.get("/api/v1/subscriptions/history", headers=headers)
    assert response.status_code == 200
    json_response = response.get_json()
    assert json_response["status"] == "success"
    # Should have 2 entries: one cancelled (plan1), one active (plan2)
    assert (
        len(json_response["data"]) == 2
    ), f"Expected 2 history items, got {len(json_response['data'])}"
    assert "total_items" in json_response["pagination"]
    assert json_response["pagination"]["current_page"] == 1

    active_subs_in_history = [
        s for s in json_response["data"] if s["status"] == "active"
    ]
    cancelled_subs_in_history = [
        s for s in json_response["data"] if s["status"] == "cancelled"
    ]
    assert len(active_subs_in_history) == 1
    assert len(cancelled_subs_in_history) == 1
    assert active_subs_in_history[0]["plan_id"] == plan2.id
    assert cancelled_subs_in_history[0]["plan_id"] == plan1.id


def test_cancel_subscription(
    client,
    regular_user_tokens,
    sample_plan_for_sub_tests,
    db_session,
    _db_setup_teardown,
):
    access_token, user_id = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    current_plan = sample_plan_for_sub_tests

    sub_response = client.post(
        "/api/v1/subscriptions/subscribe",
        json={"plan_id": current_plan.id},
        headers=headers,
    )
    assert sub_response.status_code == 201
    subscription_id = sub_response.get_json()["data"]["id"]

    cancel_response = client.post(
        "/api/v1/subscriptions/cancel",
        json={
            "subscription_id": subscription_id,
            "reason": "Test cancellation by user",
        },
        headers=headers,
    )
    assert (
        cancel_response.status_code == 200
    ), f"Cancel failed: {cancel_response.get_data(as_text=True)}"
    json_data = cancel_response.get_json()["data"]
    assert json_data["id"] == subscription_id
    assert json_data["status"] == "cancelled"
    assert json_data["auto_renew"] is False
    assert json_data["cancellation_reason"] == "Test cancellation by user"

    cancelled_sub_db = (
        db_session.query(UserSubscription).filter_by(id=subscription_id).first()
    )
    assert cancelled_sub_db is not None
    assert cancelled_sub_db.status == "cancelled"


def test_upgrade_subscription(
    client,
    regular_user_tokens,
    sample_plan_for_sub_tests,
    db_session,
    _db_setup_teardown,
):
    access_token, user_id = regular_user_tokens
    headers = {"Authorization": f"Bearer {access_token}"}
    initial_plan = sample_plan_for_sub_tests

    # Subscribe to initial plan
    sub_resp = client.post(
        "/api/v1/subscriptions/subscribe",
        json={"plan_id": initial_plan.id},
        headers=headers,
    )
    assert sub_resp.status_code == 201

    # Create a new plan to upgrade to
    upgrade_plan_name = "SubTest Pro Upgrade Plan"
    db_session.query(SubscriptionPlan).filter_by(name=upgrade_plan_name).delete(
        synchronize_session=False
    )  # Defensive
    db_session.commit()
    upgrade_target_plan = create_plan_service(
        name=upgrade_plan_name, price="99.99", duration_days=30, is_active=True
    )

    upgrade_response = client.post(
        "/api/v1/subscriptions/upgrade",
        json={"new_plan_id": upgrade_target_plan.id},
        headers=headers,
    )
    assert (
        upgrade_response.status_code == 200
    ), f"Upgrade failed: {upgrade_response.get_data(as_text=True)}"
    json_data = upgrade_response.get_json()["data"]
    assert json_data["plan_id"] == upgrade_target_plan.id
    assert json_data["status"] == "active"
    assert json_data["user_id"] == user_id

    old_sub = (
        db_session.query(UserSubscription)
        .filter_by(user_id=user_id, plan_id=initial_plan.id)
        .first()
    )
    assert old_sub is not None
    assert old_sub.status == "upgraded"
