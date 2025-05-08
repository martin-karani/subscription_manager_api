from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from decimal import Decimal

from app.services import (
    subscribe_user_to_plan_service,
    get_user_active_subscription_service,
    get_user_subscription_history_service,
    cancel_user_subscription_service,
    upgrade_user_subscription_service,
)
from app.utils import success_response, error_response, validate_json_payload
from app.exceptions import (
    APIResourceNotFoundError,
    APIBadRequestError,
    APIDatabaseError,
    APIValidationError,
)
from app.models import UserSubscription

subscriptions_bp = Blueprint("subscriptions_bp", __name__)


def _serialize_raw_sql_subscription_data(raw_data: dict):

    if not raw_data:
        return None

    serialized = raw_data.copy()

    for key in [
        "start_date",
        "end_date",
        "subscription_created_at",
    ]:
        if key in serialized and isinstance(serialized[key], datetime):
            serialized[key] = serialized[key].isoformat()

    # Convert objects (like price) to strings
    if "plan_price" in serialized and isinstance(serialized["plan_price"], Decimal):
        serialized["plan_price"] = str(serialized["plan_price"])

    return serialized


@subscriptions_bp.route("/subscribe", methods=["POST"])
@jwt_required()
@validate_json_payload(required_fields=["plan_id"])
def subscribe_to_plan_route(json_data):
    current_user_id = get_jwt_identity()
    plan_id = json_data["plan_id"]

    try:
        if not isinstance(plan_id, int) or plan_id <= 0:
            raise APIValidationError("Invalid plan_id provided.")

        subscription = subscribe_user_to_plan_service(
            user_id=current_user_id, plan_id=plan_id
        )
        current_app.logger.info(
            f"User {current_user_id} successfully subscribed to plan {plan_id} (Subscription ID: {subscription.id})."
        )
        return success_response(
            data=subscription.to_dict(),
            message="Successfully subscribed to plan.",
            status_code=201,
        )
    except (
        APIResourceNotFoundError,
        APIBadRequestError,
        APIValidationError,
        APIDatabaseError,
    ) as e:
        current_app.logger.warning(
            f"Subscription failed for user {current_user_id} to plan {plan_id}: {e.message}"
        )
        return error_response(e.message, e.status_code, error_details=e.payload)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error during subscription for user {current_user_id} to plan {plan_id}: {str(e)}",
            exc_info=True,
        )
        return error_response(
            "Could not process subscription due to an internal server error.", 500
        )


@subscriptions_bp.route("/active", methods=["GET"])
@jwt_required()
def get_active_subscription_route():
    current_user_id = get_jwt_identity()
    try:
        active_sub_data = get_user_active_subscription_service(user_id=current_user_id)

        if active_sub_data:
            current_app.logger.info(
                f"Retrieved active subscription for user {current_user_id}."
            )
            return success_response(
                data=_serialize_raw_sql_subscription_data(active_sub_data)
            )
        else:
            current_app.logger.info(
                f"No active subscription found for user {current_user_id}."
            )
            return success_response(data=None, message="No active subscription found.")
    except Exception as e:
        current_app.logger.error(
            f"Error retrieving active subscription for user {current_user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response("Could not retrieve active subscription.", 500)


@subscriptions_bp.route("/history", methods=["GET"])
@jwt_required()
def get_subscription_history_route():
    current_user_id = get_jwt_identity()

    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        if page <= 0:
            page = 1
        if per_page <= 0:
            per_page = 10
        if per_page > 100:
            per_page = 100

        history_data = get_user_subscription_history_service(
            user_id=current_user_id, page=page, per_page=per_page
        )

        serialized_items = [
            _serialize_raw_sql_subscription_data(item)
            for item in history_data.get("items", [])
        ]

        pagination_info = {
            "total_items": history_data["total"],
            "current_page": history_data["page"],
            "items_per_page": history_data["per_page"],
            "total_pages": history_data["pages"],
        }
        current_app.logger.info(
            f"Retrieved subscription history for user {current_user_id} (Page: {page})."
        )
        return success_response(data=serialized_items, pagination_info=pagination_info)
    except Exception as e:
        current_app.logger.error(
            f"Error retrieving subscription history for user {current_user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response("Could not retrieve subscription history.", 500)


@subscriptions_bp.route("/cancel", methods=["POST"])
@jwt_required()
@validate_json_payload(optional_fields=["subscription_id", "reason"])
def cancel_subscription_route(json_data):
    current_user_id = get_jwt_identity()
    subscription_id_to_cancel = json_data.get("subscription_id")
    cancellation_reason = json_data.get("reason")

    try:
        if subscription_id_to_cancel and (
            not isinstance(subscription_id_to_cancel, int)
            or subscription_id_to_cancel <= 0
        ):
            raise APIValidationError("Invalid subscription_id provided.")

        cancelled_sub = cancel_user_subscription_service(
            user_id=current_user_id,
            subscription_id=subscription_id_to_cancel,
            reason=cancellation_reason,
        )
        current_app.logger.info(
            f"Subscription ID {cancelled_sub.id} cancelled for user {current_user_id}."
        )
        return success_response(
            data=cancelled_sub.to_dict(),
            message="Subscription cancelled successfully.",
        )
    except (
        APIResourceNotFoundError,
        APIBadRequestError,
        APIValidationError,
        APIDatabaseError,
    ) as e:
        current_app.logger.warning(
            f"Subscription cancellation failed for user {current_user_id} "
            f"(Sub ID: {subscription_id_to_cancel}): {e.message}"
        )
        return error_response(e.message, e.status_code, error_details=e.payload)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error cancelling subscription for user {current_user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response("Could not process subscription cancellation.", 500)


@subscriptions_bp.route("/upgrade", methods=["POST"])
@jwt_required()
@validate_json_payload(required_fields=["new_plan_id"])
def upgrade_subscription_route(json_data):
    current_user_id = get_jwt_identity()
    new_plan_id = json_data["new_plan_id"]

    try:
        if not isinstance(new_plan_id, int) or new_plan_id <= 0:
            raise APIValidationError("Invalid new_plan_id provided.")

        upgraded_subscription = upgrade_user_subscription_service(
            user_id=current_user_id, new_plan_id=new_plan_id
        )
        current_app.logger.info(
            f"User {current_user_id} successfully upgraded to plan {new_plan_id} "
            f"(New Subscription ID: {upgraded_subscription.id})."
        )
        return success_response(
            data=upgraded_subscription.to_dict(),
            message="Subscription upgraded successfully.",
        )
    except (
        APIResourceNotFoundError,
        APIBadRequestError,
        APIValidationError,
        APIDatabaseError,
    ) as e:
        current_app.logger.warning(
            f"Subscription upgrade failed for user {current_user_id} to new plan {new_plan_id}: {e.message}"
        )
        return error_response(e.message, e.status_code, error_details=e.payload)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error upgrading subscription for user {current_user_id}: {str(e)}",
            exc_info=True,
        )
        return error_response("Could not process subscription upgrade.", 500)
