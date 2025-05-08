
## Getting Started

### Prerequisites

*   Git
*   Python 3.9+ and Pip
*   MySQL Server (if running locally without Docker)
*   Docker and Docker Compose (if using Docker setup)

### Option 1: Running Locally (Development)

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd subscription_manager_api
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
   
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
  
4.  **Set up environment variables:**
    ```bash
    cp .env.example .env
    ```

5.  **Create your MySQL database:**
    Log into MySQL and create the database specified in your `.env` file (e.g., `subscription_api_dev`).

6.  **Initialize and apply database migrations:**
    ```bash
    flask db init  # Run only once if 'migrations' folder doesn't exist
    flask db migrate -m "Initial migration"
    flask db upgrade
    ```

7.  **Seed the database (optional):**
    ```bash
    flask seed_db
    ```

8.  **Run the application:**
    ```bash
    flask run
    ```
    The API will typically be available at `http://127.0.0.1:5000`.

### Option 2: Running with Docker Compose

1.  **Clone the repository:** (Same as above)

2.  **Set up environment variables for Docker:**
    ```bash
    cp .env.example .env
    ```
    Edit `.env`. Key variables for Docker Compose: `SECRET_KEY`, `JWT_SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_ROOT_PASSWORD`.
    `FLASK_CONFIG` can be `production` (default) or `development`.

3.  **Build and start services:**
    ```bash
    docker-compose up --build
    ```

4.  **Initialize and apply database migrations (in a separate terminal):**
    ```bash
    docker-compose exec web flask db init  # Only if 'migrations' folder doesn't exist
    docker-compose exec web flask db migrate -m "Initial migration for Docker"
    docker-compose exec web flask db upgrade
    ```

5.  **Seed the database (optional, in a separate terminal):**
    ```bash
    docker-compose exec web flask seed_db
    ```
    The API will typically be available at `http://localhost:5000` (or the port configured in `FLASK_RUN_PORT`).

## API Endpoints

Refer to the `app/*/routes.py` files for detailed endpoint definitions. Key base URLs:

*   `/auth/` - Authentication
*   `/api/v1/plans/` - Subscription Plans
*   `/api/v1/subscriptions/` - User Subscriptions
*   `/health` - Health check

**Authentication:**
Requests to protected endpoints require a JWT access token in the `Authorization` header:
`Authorization: Bearer <your_access_token>`

## Running Tests

1.  Ensure you have a testing configuration (e.g., `TestingConfig` in `config.py` often uses SQLite for speed).
2.  Set `FLASK_CONFIG=testing` in your environment or ensure your test runner sets it.
3.  From the project root:
    ```bash
    pytest
    ```

## SQL Optimizations

For details on SQL query optimizations and indexing strategies, please refer to the [OPTIMIZATIONS.md](./OPTIMIZATIONS.md) file.

## Environment Variables

The application uses a `.env` file to manage environment variables. See `.env.example` for a template. Key variables include:

*   `FLASK_APP`: Set to `run.py`.
*   `FLASK_CONFIG`: `development`, `testing`, or `production`.
*   `SECRET_KEY`: A strong secret key for Flask session security.
*   `JWT_SECRET_KEY`: A strong secret key for JWT signing.
*   `DATABASE_URL`: Full database connection string (especially for production/Docker).
*   `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`: Individual database connection parameters (for local development).
*   `LOG_LEVEL`: Logging level (e.g., `INFO`, `DEBUG`).

