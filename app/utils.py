from functools import wraps
from flask import request, jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from .exceptions import APIValidationError, APIAuthError

#  Response Helpers


def success_response(data=None, message=None, status_code=200, pagination_info=None):
    payload = {"status": "success"}
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if pagination_info:
        payload["pagination"] = pagination_info
    return jsonify(payload), status_code


def error_response(message, status_code=400, error_details=None):
    payload = {"status": "error", "message": message}
    if error_details:
        payload["details"] = error_details
    return jsonify(payload), status_code


#  Decorators
def validate_json_payload(required_fields=None, optional_fields=None):

    if required_fields is None:
        required_fields = []
    if optional_fields is None:
        optional_fields = []

    all_expected_fields = set(required_fields + optional_fields)

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                current_app.logger.warning(
                    f"Invalid request to {request.path}: Content-Type must be application/json."
                )
                raise APIValidationError(
                    "Invalid request: Content-Type must be application/json.",
                    status_code=415,
                )

            try:
                data = request.get_json()
                if data is None:
                    raise APIValidationError(
                        "Invalid JSON: Request body is empty or malformed."
                    )
            except Exception as e:
                current_app.logger.error(f"Error parsing JSON for {request.path}: {e}")
                raise APIValidationError("Invalid JSON: Could not parse request body.")

            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                details = {"missing_fields": missing_fields}
                raise APIValidationError(
                    f"Missing required fields: {', '.join(missing_fields)}",
                    payload=details,
                )

            # Extract only the specified fields  avoid unexpected data
            extracted_data = {}
            for field in all_expected_fields:
                if field in data:
                    extracted_data[field] = data[field]

            kwargs["json_data"] = extracted_data
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("is_admin", False) is True:
            return fn(*args, **kwargs)
        else:
            current_user_id = claims.get("sub")
            current_app.logger.warning(
                f"Admin access denied for user '{current_user_id}' to '{request.path}'."
            )
            raise APIAuthError(
                "Forbidden: Administrator access required for this resource.",
                status_code=403,
            )

    return wrapper
