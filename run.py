import os
from app import create_app


config_name = os.getenv("FLASK_CONFIG", "development")
app = create_app(config_name)

if __name__ == "__main__":

    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))

    debug_mode = app.config.get("DEBUG", False)

    app.logger.info(f"Starting Subscription API on http://{host}:{port}")
    app.logger.info(f"Configuration: '{config_name}', Debug mode: {debug_mode}")

    app.run(host=host, port=port, debug=debug_mode)
