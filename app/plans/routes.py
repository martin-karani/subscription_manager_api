from flask import Blueprint, request, current_app

from app.services import (
    create_plan_service,
    get_all_plans_service,
    get_plan_by_id_service,
    update_plan_service,
    delete_plan_service,
)
from app.utils import (
    success_response,
    error_response,
    validate_json_payload,
    admin_required,
)
from app.exceptions import (
    APIResourceNotFoundError,
    APIBadRequestError,
    APIDatabaseError,
    APIValidationError,
)

plans_bp = Blueprint("plans_bp", __name__)


@plans_bp.route("", methods=["POST"])
@admin_required  # Only admins can create plans
@validate_json_payload(
    required_fields=["name", "price", "duration_days"],
    optional_fields=["description", "features", "is_active"],
)
def create_plan_route(json_data):
    try:
        new_plan = create_plan_service(**json_data)
        current_app.logger.info(
            f"Admin created new plan '{new_plan.name}' (ID: {new_plan.id})."
        )
        return success_response(
            data=new_plan.to_dict(),
            message="Subscription plan created successfully.",
            status_code=201,
        )
    except (APIBadRequestError, APIValidationError, APIDatabaseError) as e:
        current_app.logger.warning(
            f"Plan creation failed: {e.message} - Data: {json_data}"
        )
        return error_response(e.message, e.status_code, error_details=e.payload)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error creating plan: {str(e)}", exc_info=True
        )
        return error_response(
            "Could not create plan due to an internal server error.", 500
        )


@plans_bp.route("", methods=["GET"])
def get_all_plans_route():

    active_filter_str = request.args.get("active", "true").lower()

    if active_filter_str == "all":
        plans = get_all_plans_service(active_only=None)

        log_msg = "all subscription plans"
    else:
        active_only = active_filter_str == "true"
        plans = get_all_plans_service(active_only=active_only)
        log_msg = f"{'active' if active_only else 'inactive'} subscription plans"

    current_app.logger.info(f"Retrieved {log_msg}.")
    return success_response(data=[plan.to_dict() for plan in plans])


@plans_bp.route("/<int:plan_id>", methods=["GET"])
def get_plan_route(plan_id: int):
    try:
        plan = get_plan_by_id_service(plan_id)
        current_app.logger.info(f"Retrieved plan ID {plan_id}: '{plan.name}'.")
        return success_response(data=plan.to_dict())
    except APIResourceNotFoundError as e:
        current_app.logger.warning(
            f"Attempt to retrieve non-existent plan ID {plan_id}."
        )
        return error_response(e.message, e.status_code)
    except Exception as e:
        current_app.logger.error(
            f"Error retrieving plan {plan_id}: {str(e)}", exc_info=True
        )
        return error_response("Could not retrieve plan details.", 500)


@plans_bp.route("/<int:plan_id>", methods=["PUT"])
@admin_required
@validate_json_payload(
    optional_fields=[
        "name",
        "description",
        "price",
        "duration_days",
        "features",
        "is_active",
    ]
)
def update_plan_route(plan_id: int, json_data):
    if not json_data:
        return error_response("No update data provided.", status_code=400)
    try:
        updated_plan = update_plan_service(plan_id, **json_data)
        current_app.logger.info(
            f"Admin updated plan ID {plan_id} ('{updated_plan.name}')."
        )
        return success_response(
            data=updated_plan.to_dict(),
            message="Subscription plan updated successfully.",
        )
    except (
        APIResourceNotFoundError,
        APIBadRequestError,
        APIValidationError,
        APIDatabaseError,
    ) as e:
        current_app.logger.warning(
            f"Plan update failed for ID {plan_id}: {e.message} - Data: {json_data}"
        )
        return error_response(e.message, e.status_code, error_details=e.payload)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error updating plan {plan_id}: {str(e)}", exc_info=True
        )
        return error_response(
            "Could not update plan due to an internal server error.", 500
        )


@plans_bp.route("/<int:plan_id>", methods=["DELETE"])
@admin_required  # Only admins can delete plans
def delete_plan_route(plan_id: int):

    try:
        delete_plan_service(plan_id)
        current_app.logger.info(f"Admin deleted plan ID {plan_id}.")

        return success_response(
            message="Subscription plan deleted successfully.", status_code=200
        )
    except (
        APIResourceNotFoundError,
        APIBadRequestError,
        APIDatabaseError,
    ) as e:
        current_app.logger.warning(
            f"Plan deletion failed for ID {plan_id}: {e.message}"
        )
        return error_response(e.message, e.status_code)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error deleting plan {plan_id}: {str(e)}", exc_info=True
        )
        return error_response(
            "Could not delete plan due to an internal server error.", 500
        )
