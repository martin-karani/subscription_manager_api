import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
if not ENV_FILE.exists():
    ENV_FILE = BASE_DIR / ".." / ".env"
load_dotenv(dotenv_path=ENV_FILE)


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "a-very-secure-default-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "a-secure-jwt-default-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False").lower() in (
        "true",
        "1",
        "yes",
    )
    APP_NAME = os.getenv("APP_NAME", "Subscription Management API")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", 1))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", 30))
    )

    @staticmethod
    def _build_db_uri(driver, user, password, host, port, name):
        return f"mysql+{driver}://{user}:{password}@{host}:{port}/{name}"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = True

    _provided_database_url = os.getenv("DATABASE_URL")
    if _provided_database_url:
        SQLALCHEMY_DATABASE_URI = _provided_database_url
    else:
        DB_USER = os.getenv("DB_USER", "dev_user")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "dev_password")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "3306")
        DB_NAME = os.getenv("DB_NAME", "subscription_api_dev")
        DB_DRIVER = os.getenv("DB_DRIVER", "pymysql")
        SQLALCHEMY_DATABASE_URI = BaseConfig._build_db_uri(
            DB_DRIVER, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
        )


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("TEST_DATABASE_URL") or f"sqlite:///{BASE_DIR / 'test_db.sqlite3'}"
    )
    SQLALCHEMY_ECHO = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=15)


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ECHO = False

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL environment variable is not set for production.")
    if SQLALCHEMY_DATABASE_URI and not SQLALCHEMY_DATABASE_URI.startswith(
        "mysql+pymysql"
    ):
        print(
            "Warning: DATABASE_URL in ProductionConfig does not appear to be using 'pymysql'. Ensure it's correctly formatted."
        )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config_by_name(config_name: str):
    return config_by_name.get(config_name, DevelopmentConfig)
