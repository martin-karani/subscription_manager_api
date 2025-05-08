from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text, exc
from typing import Union

from .extensions import db
from .models import User, SubscriptionPlan, UserSubscription
from .exceptions import (
    APIResourceNotFoundError,
    APIBadRequestError,
    APIDatabaseError,
    APIValidationError,
)


# --- User Services ---
def register_user_service(username, email, password, is_admin=False):
    if not username or not email or not password:
        raise APIValidationError("Username, email, and password are required.")

    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing_user:
        raise APIBadRequestError("Username or email already exists.")

    new_user = User(username=username, email=email, is_admin=is_admin)
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error during user registration: {e}")
        raise APIDatabaseError("Could not register user due to a database issue.")
    return new_user


def authenticate_user_service(username, password):
    if not username or not password:
        return None

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        return user
    return None


def get_user_by_id_service(user_id):
    user = db.session.get(User, user_id)
    if not user:
        raise APIResourceNotFoundError(f"User with ID {user_id} not found.")
    return user


# --- Subscription Plan Services ---
def create_plan_service(
    name: str,
    price: Union[str, Decimal],
    duration_days: int,
    description: str = None,
    features: str = None,
    is_active: bool = True,
):
    if SubscriptionPlan.query.filter_by(name=name).first():
        raise APIBadRequestError(f"A plan with name '{name}' already exists.")

    try:
        price_decimal = Decimal(price)
        if price_decimal < Decimal("0.00"):
            raise ValueError("Price cannot be negative.")
    except Exception:
        raise APIValidationError("Invalid price format. Price must be a valid number.")

    if not isinstance(duration_days, int) or duration_days < 0:
        raise APIValidationError("Duration (days) must be a non-negative integer.")

    new_plan = SubscriptionPlan(
        name=name,
        description=description,
        price=price_decimal,
        duration_days=duration_days,
        features=features,
        is_active=is_active,
    )
    try:
        db.session.add(new_plan)
        db.session.commit()
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error creating plan: {str(e)}")
    return new_plan


def get_all_plans_service(active_only=True):
    query = SubscriptionPlan.query
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(SubscriptionPlan.price).all()


def get_plan_by_id_service(plan_id: int):
    plan = db.session.get(SubscriptionPlan, plan_id)
    if not plan:
        raise APIResourceNotFoundError(
            f"Subscription Plan with ID {plan_id} not found."
        )
    return plan


def update_plan_service(plan_id: int, **kwargs):
    plan = get_plan_by_id_service(plan_id)

    allowed_fields = [
        "name",
        "description",
        "price",
        "duration_days",
        "features",
        "is_active",
    ]
    updated_fields_count = 0

    for field, value in kwargs.items():
        if field in allowed_fields and value is not None:
            if field == "price":
                try:
                    price_decimal = Decimal(value)
                    if price_decimal < Decimal("0.00"):
                        raise APIValidationError("Price cannot be negative.")
                    setattr(plan, field, price_decimal)
                except Exception:
                    raise APIValidationError("Invalid price format for update.")
            elif field == "name" and value != plan.name:
                if SubscriptionPlan.query.filter(
                    SubscriptionPlan.id != plan_id, SubscriptionPlan.name == value
                ).first():
                    raise APIBadRequestError(f"Plan name '{value}' already exists.")
                setattr(plan, field, value)
            elif field == "duration_days":
                if not isinstance(value, int) or value < 0:
                    raise APIValidationError(
                        "Duration (days) must be a non-negative integer."
                    )
                setattr(plan, field, value)
            else:
                setattr(plan, field, value)
            updated_fields_count += 1

    if not updated_fields_count:
        return plan

    try:
        db.session.commit()
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error updating plan {plan_id}: {str(e)}")
    return plan


def delete_plan_service(plan_id: int):

    plan = get_plan_by_id_service(plan_id)

    active_subs_count = UserSubscription.query.filter_by(
        plan_id=plan_id, status="active"
    ).count()
    if active_subs_count > 0:
        raise APIBadRequestError(
            f"Cannot delete plan '{plan.name}'. It has {active_subs_count} active subscription(s). "
            "Consider deactivating the plan instead."
        )

    try:
        db.session.delete(plan)
        db.session.commit()
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error deleting plan {plan_id}: {str(e)}")


# --- User Subscription Services ---


def subscribe_user_to_plan_service(user_id: int, plan_id: int):

    user = get_user_by_id_service(user_id)
    plan = get_plan_by_id_service(plan_id)

    if not plan.is_active:
        raise APIBadRequestError(
            f"Plan '{plan.name}' is not active and cannot be subscribed to."
        )

    existing_active_sub = UserSubscription.query.filter_by(
        user_id=user_id, status="active"
    ).first()
    if existing_active_sub:
        existing_active_sub.status = "cancelled"
        existing_active_sub.end_date = datetime.utcnow()
        existing_active_sub.auto_renew = False
        existing_active_sub.cancellation_reason = (
            f"Superseded by new subscription to plan '{plan.name}'."
        )
        db.session.add(existing_active_sub)

    new_sub = UserSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        auto_renew=True,
        start_date=datetime.utcnow(),
    )
    new_sub.plan = plan
    new_sub.calculate_and_set_end_date()

    try:
        db.session.add(new_sub)
        db.session.commit()
        db.session.refresh(new_sub)
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error during subscription: {str(e)}")
    return new_sub


def get_user_active_subscription_service(user_id: int):

    sql = text(
        """
        SELECT 
            us.id AS subscription_id, us.user_id, us.plan_id,
            us.start_date, us.end_date, us.status, us.auto_renew,
            us.created_at AS subscription_created_at,
            p.name AS plan_name, p.price AS plan_price, 
            p.duration_days AS plan_duration_days, p.features AS plan_features
        FROM user_subscriptions us
        JOIN subscription_plans p ON us.plan_id = p.id
        WHERE us.user_id = :user_id AND us.status = 'active'
        ORDER BY us.start_date DESC
        LIMIT 1;
    """
    )
    result = db.session.execute(sql, {"user_id": user_id}).fetchone()

    return result._mapping if result else None


def get_user_subscription_history_service(
    user_id: int, page: int = 1, per_page: int = 10
):

    offset = (page - 1) * per_page

    items_sql = text(
        """
        SELECT 
            us.id AS subscription_id, us.user_id, us.plan_id,
            us.start_date, us.end_date, us.status, us.auto_renew,
            us.created_at AS subscription_created_at,
            p.name AS plan_name, p.price AS plan_price,
            p.duration_days AS plan_duration_days
        FROM user_subscriptions us
        JOIN subscription_plans p ON us.plan_id = p.id
        WHERE us.user_id = :user_id
        ORDER BY us.start_date DESC
        LIMIT :limit OFFSET :offset;
    """
    )
    results = db.session.execute(
        items_sql, {"user_id": user_id, "limit": per_page, "offset": offset}
    ).fetchall()

    count_sql = text(
        "SELECT COUNT(id) FROM user_subscriptions WHERE user_id = :user_id;"
    )
    total_count = db.session.execute(count_sql, {"user_id": user_id}).scalar_one()

    return {
        "items": [row._mapping for row in results],
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "pages": (total_count + per_page - 1) // per_page if total_count > 0 else 0,
    }


def cancel_user_subscription_service(
    user_id: int, subscription_id: int = None, reason: str = None
):
    """
    Cancels a user's subscription.
    If subscription_id is provided, cancels that specific one.
    Otherwise, cancels the latest active subscription.
    """
    sub_to_cancel = None
    if subscription_id:
        sub_to_cancel = UserSubscription.query.filter_by(
            id=subscription_id, user_id=user_id
        ).first()
        if not sub_to_cancel:
            raise APIResourceNotFoundError(
                f"Subscription with ID {subscription_id} not found or does not belong to this user."
            )
    else:
        sub_to_cancel = (
            UserSubscription.query.filter_by(user_id=user_id, status="active")
            .order_by(UserSubscription.start_date.desc())
            .first()
        )

    if not sub_to_cancel:
        raise APIResourceNotFoundError(
            "No active subscription found to cancel for this user."
        )

    if sub_to_cancel.status not in [
        "active",
        "pending_cancellation",
    ]:
        raise APIBadRequestError(
            f"Subscription is already '{sub_to_cancel.status}' and cannot be cancelled."
        )

    sub_to_cancel.status = "cancelled"
    sub_to_cancel.auto_renew = False
    sub_to_cancel.cancellation_reason = (
        reason if reason else "User initiated cancellation."
    )

    try:
        db.session.add(sub_to_cancel)
        db.session.commit()
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error cancelling subscription: {str(e)}")
    return sub_to_cancel


def upgrade_user_subscription_service(user_id: int, new_plan_id: int):

    user = get_user_by_id_service(user_id)
    new_plan = get_plan_by_id_service(new_plan_id)

    if not new_plan.is_active:
        raise APIBadRequestError(
            f"New plan '{new_plan.name}' is not active and cannot be upgraded to."
        )

    active_sub = (
        UserSubscription.query.filter_by(user_id=user_id, status="active")
        .order_by(UserSubscription.start_date.desc())
        .first()
    )

    if not active_sub:
        return subscribe_user_to_plan_service(user_id, new_plan_id)

    if active_sub.plan_id == new_plan_id:
        raise APIBadRequestError("User is already subscribed to this plan.")

    active_sub.status = "upgraded"
    active_sub.end_date = datetime.utcnow()
    active_sub.auto_renew = False
    active_sub.cancellation_reason = f"Upgraded to plan '{new_plan.name}'."
    db.session.add(active_sub)

    upgraded_sub = UserSubscription(
        user_id=user_id,
        plan_id=new_plan_id,
        status="active",
        auto_renew=True,
        start_date=datetime.utcnow(),
    )
    upgraded_sub.plan = new_plan
    upgraded_sub.calculate_and_set_end_date()

    try:
        db.session.add(upgraded_sub)
        db.session.commit()
        db.session.refresh(upgraded_sub)
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        raise APIDatabaseError(f"Database error during subscription upgrade: {str(e)}")
    return upgraded_sub
