from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import (
    Index,
    Column,
    Integer,
    String,
    Text,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .extensions import db, bcrypt


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    subscriptions = relationship(
        "UserSubscription",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self, include_email=False):
        data = {
            "id": self.id,
            "username": self.username,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_email:
            data["email"] = self.email
        return data

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}' admin={self.is_admin}>"


class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    duration_days = Column(Integer, nullable=False)
    features = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user_subscriptions = relationship(
        "UserSubscription", back_populates="plan", lazy="dynamic"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": str(self.price),
            "duration_days": self.duration_days,
            "features": self.features,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<SubscriptionPlan id={self.id} name='{self.name}' price={self.price}>"


class UserSubscription(db.Model):
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)

    start_date = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    end_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    auto_renew = Column(Boolean, default=True, nullable=False)

    payment_intent_id = Column(String(255), nullable=True, index=True)
    cancellation_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="user_subscriptions")

    # Table  specify  indexes for common query patterns
    __table_args__ = (
        Index(
            "idx_user_sub_user_id_status", "user_id", "status"
        ),  # For finding a user's active/specific status subs
        Index(
            "idx_user_sub_user_id_start_date", "user_id", "start_date"
        ),  # For user's subscription history
        Index(
            "idx_user_sub_end_date_status", "end_date", "status"
        ),  # For jobs finding expired/ending subs
        Index(
            "idx_user_sub_plan_id_status", "plan_id", "status"
        ),  # For checking subs on a plan (e.g. before plan deletion)
    )

    def calculate_and_set_end_date(self):
        """
        Calculates and sets the end_date based on the associated plan's duration.
        Assumes self.plan is populated or can be lazy-loaded.
        """
        if self.plan and self.start_date and self.plan.duration_days > 0:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        elif self.plan and self.plan.duration_days == 0:
            self.end_date = None
        else:

            pass
        return self.end_date

    def to_dict(self):
        """Serializes the UserSubscription object to a dictionary."""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status,
            "auto_renew": self.auto_renew,
            "cancellation_reason": self.cancellation_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.plan:
            data["plan_details"] = {
                "name": self.plan.name,
                "price": str(self.plan.price),
                "duration_days": self.plan.duration_days,
            }
        return data

    def __repr__(self):
        return (
            f"<UserSubscription id={self.id} user_id={self.user_id} "
            f"plan_id={self.plan_id} status='{self.status}'>"
        )
