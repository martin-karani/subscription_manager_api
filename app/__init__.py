from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
import logging
from datetime import datetime

from config import get_config_by_name
from .extensions import db, migrate, bcrypt, jwt
from .exceptions import (
    APIError,
    APIValidationError,
    APIAuthError,
)
from .cli import register_cli_commands


def create_app(config_name="default"):
    """
    Application factory for creating the Flask app.
    """
    app = Flask(__name__)

    app_config = get_config_by_name(config_name)
    app.config.from_object(app_config)

    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)

    logging.basicConfig(
        level=app.config.get("LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(module)s.%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    app.logger.info(
        f"App '{app.config.get('APP_NAME')}' created with '{config_name}' config."
    )
    app.logger.debug(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    from .auth.routes import auth_bp
    from .plans.routes import plans_bp
    from .subscriptions.routes import subscriptions_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(plans_bp, url_prefix="/api/v1/plans")
    app.register_blueprint(subscriptions_bp, url_prefix="/api/v1/subscriptions")

    register_cli_commands(app)

    # Global Error Handlers

    @app.errorhandler(APIValidationError)
    def handle_validation_error(error: APIValidationError):
        app.logger.warning(
            f"Validation Error: {error.message} - Details: {error.payload}"
        )
        response_data = {"status": "error", "message": error.message}
        if error.payload:
            response_data["details"] = error.payload
        return jsonify(response_data), error.status_code

    @app.errorhandler(APIAuthError)
    def handle_auth_error(error: APIAuthError):
        app.logger.warning(f"Authentication/Authorization Error: {error.message}")
        return jsonify({"status": "error", "message": error.message}), error.status_code

    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        app.logger.error(
            f"API Error: {error.message}",
            exc_info=True if error.status_code >= 500 else False,
        )
        return jsonify({"status": "error", "message": error.message}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        app.logger.warning(
            f"HTTP Exception: {error.code} {error.name} - {error.description} for {request.url}"
        )
        response = {"status": "error", "message": error.name}
        if error.description and app.config.get("DEBUG"):
            response["details"] = error.description
        return jsonify(response), error.code or 500

    @app.errorhandler(Exception)
    def handle_generic_exception(error: Exception):
        app.logger.error(
            f"Unhandled Exception: {str(error)} for {request.url}", exc_info=True
        )
        message = "An unexpected internal server error occurred."
        if app.config.get("DEBUG"):
            message = f"{message} Details: {str(error)}"
        return jsonify({"status": "error", "message": message}), 500

    @app.route("/health", methods=["GET"])
    def health_check():
        app.logger.debug("Health check endpoint was called.")
        return (
            jsonify(
                {
                    "status": "ok",
                    "message": f"{app.config.get('APP_NAME')} is healthy!",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    return app
