from flask import Blueprint, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)

from app.services import (
    register_user_service,
    authenticate_user_service,
    get_user_by_id_service,
)
from app.utils import success_response, error_response, validate_json_payload
from app.exceptions import APIBadRequestError, APIDatabaseError, APIAuthError

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/register", methods=["POST"])
@validate_json_payload(
    required_fields=["username", "email", "password"], optional_fields=["is_admin"]
)
def register_user_route(json_data):

    username = json_data["username"]
    email = json_data["email"]
    password = json_data["password"]

    is_admin_request = False

    try:
        new_user = register_user_service(
            username, email, password, is_admin=is_admin_request
        )
        current_app.logger.info(
            f"User '{username}' registered successfully (ID: {new_user.id})."
        )
        return success_response(
            data=new_user.to_dict(include_email=True),
            message="User registered successfully.",
            status_code=201,
        )
    except (APIBadRequestError, APIDatabaseError) as e:
        current_app.logger.warning(f"Registration failed for '{username}': {e.message}")
        return error_response(e.message, e.status_code)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error during registration for '{username}': {str(e)}",
            exc_info=True,
        )
        return error_response(
            "Could not process registration due to an internal error.", 500
        )


@auth_bp.route("/login", methods=["POST"])
@validate_json_payload(required_fields=["username", "password"])
def login_user_route(json_data):
    username = json_data["username"]
    password = json_data["password"]

    try:
        user = authenticate_user_service(username, password)
        if user:
            access_token = create_access_token(
                identity=user.id, additional_claims={"is_admin": user.is_admin}
            )
            refresh_token = create_refresh_token(identity=user.id)

            login_response_data = {
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            current_app.logger.info(
                f"User '{username}' (ID: {user.id}) logged in successfully."
            )
            return success_response(
                data=login_response_data, message="Login successful."
            )
        else:
            current_app.logger.warning(
                f"Invalid login attempt for username '{username}'."
            )
            return error_response("Invalid username or password.", status_code=401)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error during login for '{username}': {str(e)}", exc_info=True
        )
        return error_response("Could not process login due to an internal error.", 500)


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token_route():
    current_user_id = get_jwt_identity()
    try:
        user = get_user_by_id_service(current_user_id)
        if not user:
            raise APIAuthError("User not found or inactive.", status_code=401)

        new_access_token = create_access_token(
            identity=user.id, additional_claims={"is_admin": user.is_admin}
        )
        current_app.logger.info(
            f"Access token refreshed for user ID '{current_user_id}'."
        )
        return success_response(
            data={"access_token": new_access_token}, message="Access token refreshed."
        )
    except APIAuthError as e:
        current_app.logger.warning(
            f"Token refresh failed for user ID '{current_user_id}': {e.message}"
        )
        return error_response(e.message, e.status_code)
    except Exception as e:
        current_app.logger.error(
            f"Unexpected error during token refresh for user ID '{current_user_id}': {str(e)}",
            exc_info=True,
        )
        return error_response("Could not refresh token due to an internal error.", 500)


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user_route():
    current_user_id = get_jwt_identity()
    try:
        user = get_user_by_id_service(current_user_id)
        current_app.logger.debug(
            f"User profile requested for user ID '{current_user_id}'."
        )
        return success_response(data=user.to_dict(include_email=True))
    except APIAuthError as e:
        return error_response(e.message, e.status_code)
