import click
from flask.cli import with_appcontext
from decimal import Decimal

from .extensions import db
from .models import (
    SubscriptionPlan,
    User,
)


@click.command(name="seed_db")
@with_appcontext
def seed_db_command():
    click.echo("Seeding database...")

    # Seed Subscription Plans
    click.echo("  Checking and seeding subscription plans...")
    default_plans = [
        {
            "name": "Free Tier",
            "price": "0.00",
            "duration_days": 36500,
            "description": "Basic access, free forever.",
            "features": "Limited access to core features, Community support",
            "is_active": True,
        },
        {
            "name": "Basic Monthly",
            "price": "9.99",
            "duration_days": 30,
            "description": "Standard features for individual users, billed monthly.",
            "features": "All core features, Standard email support, Access to basic content",
            "is_active": True,
        },
        {
            "name": "Pro Monthly",
            "price": "29.99",
            "duration_days": 30,
            "description": "Advanced features and priority support, billed monthly.",
            "features": "All core features, Advanced analytics, Priority email support, Access to premium content",
            "is_active": True,
        },
        {
            "name": "Basic Annual",
            "price": "99.99",
            "duration_days": 365,
            "description": "Standard features, billed annually (save ~17%).",
            "features": "All core features, Standard email support, Access to basic content",
            "is_active": True,
        },
    ]

    plans_added_count = 0
    for plan_data in default_plans:
        existing_plan = SubscriptionPlan.query.filter_by(name=plan_data["name"]).first()
        if not existing_plan:
            try:
                plan = SubscriptionPlan(
                    name=plan_data["name"],
                    price=Decimal(plan_data["price"]),
                    duration_days=plan_data["duration_days"],
                    description=plan_data.get("description"),
                    features=plan_data.get("features"),
                    is_active=plan_data.get("is_active", True),
                )
                db.session.add(plan)
                plans_added_count += 1
                click.echo(f"    Added plan: {plan_data['name']}")
            except Exception as e:
                click.echo(f"    Error adding plan {plan_data['name']}: {str(e)}")
        else:
            click.echo(f"    Plan '{plan_data['name']}' already exists. Skipped.")

    if plans_added_count > 0:
        click.echo(f"  Added {plans_added_count} new subscription plans.")
    else:
        click.echo(
            "  No new subscription plans were added (they likely exist already)."
        )

    # Seed Admin User
    click.echo("\n  Checking and seeding default admin user...")
    admin_username = "admin"
    admin_email = "admin@example.com"
    admin_password = "SecurePassword123!"

    if (
        not User.query.filter_by(username=admin_username).first()
        and not User.query.filter_by(email=admin_email).first()
    ):
        try:
            admin_user = User(username=admin_username, email=admin_email, is_admin=True)
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            click.echo(
                f"    Admin user '{admin_username}' created. "
                "IMPORTANT: Change the default password and email immediately if this is a production-like environment."
            )
        except Exception as e:
            click.echo(f"    Error creating admin user '{admin_username}': {str(e)}")
    else:
        click.echo(
            f"    Admin user '{admin_username}' or email '{admin_email}' already exists. Skipped."
        )

    try:
        db.session.commit()
        click.echo("\nSeed data committed successfully.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"\nError committing seed data to database: {e}")


def register_cli_commands(app):
    app.cli.add_command(seed_db_command)
