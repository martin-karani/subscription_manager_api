# Subscription Management API - SQL Query Optimizations

This document outlines the SQL query optimization strategies employed in the Subscription Management API, particularly focusing on areas where raw SQL queries were used to override default SQLAlchemy ORM behavior for performance and scalability.

## 1. Rationale for Using Raw SQL

While SQLAlchemy ORM provides a convenient and Pythonic way to interact with the database, there are scenarios where its abstractions can lead to less efficient queries or make it harder to express complex SQL logic optimally. For critical read operations, especially those involving joins, specific column selection, and ordering/limiting for dashboards or history views, raw SQL offers:

-   **Precise Control:** Directly write the exact SQL query the database should execute.
-   **Reduced Overhead:** Bypass some of the ORM's object hydration спортсменов, which can be costly for large result sets or when only a few columns are needed.
-   **Leveraging Database-Specific Features:** Easier to use specific SQL functions or indexing hints if necessary (though not heavily used in this project to maintain portability).

The ORM is still used for most Create, Update, Delete (CUD) operations and simple Read operations (e.g., fetching an entity by its primary key), where its benefits in terms of development speed and safety (like handling relationships) outweigh the micro-optimization concerns.

## 2. Optimized Queries and Indexing

### a. Retrieving a User's Active Subscription

-   **Service Function:** `get_user_active_subscription_service(user_id)`
-   **Use Case:** Frequently called to check a user's current subscription status, often for authorizing access to features.
-   **Raw SQL Query:**
    ```sql
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
    ```
-   **Optimization Details:**
    1.  **Specific Column Selection:** Only necessary columns from `user_subscriptions` and `subscription_plans` are selected, reducing data transfer and processing.
    2.  **Direct Join:** A simple `JOIN` is used to fetch plan details alongside the subscription.
    3.  **Filtering (`WHERE` clause):** Filters directly for `user_id` and `status = 'active'`.
    4.  **Ordering and Limiting (`ORDER BY ... LIMIT 1`):** Efficiently finds the single, most recent active subscription if multiple were somehow created (though business logic aims to prevent this).
    5.  **Bypassing ORM Hydration:** The result is returned as a dictionary-like mapping, avoiding the cost of creating full ORM objects if only data display is needed.

-   **Supporting Indexes:**
    -   `idx_user_sub_user_id_status` on `user_subscriptions (user_id, status)`: This composite index is crucial for quickly finding active subscriptions for a given user.
    -   Primary keys on `users (id)` and `subscription_plans (id)` are used for joins.

### b. Retrieving a User's Subscription History

-   **Service Function:** `get_user_subscription_history_service(user_id, page, per_page)`
-   **Use Case:** Displaying a paginated list of all past and current subscriptions for a user.
-   **Raw SQL Queries:**
    -   For items:
        ```sql
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
        ```
    -   For total count:
        ```sql
        SELECT COUNT(id) FROM user_subscriptions WHERE user_id = :user_id;
        ```
-   **Optimization Details:**
    1.  **Pagination via `LIMIT` and `OFFSET`:** Efficiently fetches only the required slice of data for the current page.
    2.  **Ordering (`ORDER BY us.start_date DESC`):** Sorts subscriptions chronologically, which is standard for history views.
    3.  **Separate Count Query:** A dedicated, simpler query is used to get the total number of subscriptions for pagination metadata. This is often more efficient than trying to count and fetch data in a single query with window functions, especially for large tables.
    4.  **Specific Column Selection & Bypassing ORM Hydration:** Similar to the active subscription query, this reduces overhead.

-   **Supporting Indexes:**
    -   `idx_user_sub_user_id_start_date` on `user_subscriptions (user_id, start_date)`: This composite index is vital for efficiently filtering by `user_id` and then ordering by `start_date` for pagination.
    -   The count query also benefits from an index on `user_subscriptions (user_id)`.

## 3. General Indexing 

Beyond the specific queries above, the following indexes are defined in `app/models.py` to support various operations:

-   **`users` table:**
    -   `username` (unique index): For login and registration checks.
    -   `email` (unique index): For registration checks and potentially communication.
-   **`subscription_plans` table:**
    -   `name` (unique index): To ensure plan names are unique.
    -   `is_active`: To quickly filter active/inactive plans.
-   **`user_subscriptions` table (additional indexes):**
    -   `idx_user_sub_end_date_status (end_date, status)`: Useful for background jobs that might need to process subscriptions based on their end date and status (e.g., expiring subscriptions).
    -   `idx_user_sub_plan_id_status (plan_id, status)`: Useful for queries related to a specific plan, such as finding all active subscriptions for a plan before attempting to delete or modify it.

