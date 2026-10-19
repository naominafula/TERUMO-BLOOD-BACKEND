from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, CheckConstraint, ForeignKey, func, Date, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class Donor(Base):
    __tablename__ = "donors"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, index=True)
    phone = Column(String(30), nullable=False)
    blood_group = Column(String(3), nullable=False, index=True)
    location = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    donations = relationship("Donation", back_populates="donor")


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)
    donor_id = Column(Integer, ForeignKey("donors.id"), nullable=False, index=True)
    donor = relationship("Donor", back_populates="donations")

    blood_group = Column(String(3), nullable=False, index=True)
    quantity_ml = Column(Integer, nullable=False)
    donation_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    screening_status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    screening_notes = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("quantity_ml > 0", name="positive_donation_quantity"),
        CheckConstraint(
            "screening_status IN ('pending', 'passed', 'rejected')",
            name="valid_screening_status",
        ),
    )


class BloodInventory(Base):
    __tablename__ = "blood_inventory"

    id = Column(Integer, primary_key=True, index=True)
    blood_group = Column(String(3), nullable=False, index=True)
    component = Column(
        String(30),
        nullable=False,
        default="whole_blood",
        index=True,
    )
    batch_number = Column(String(50), nullable=False, index=True)
    units = Column(Integer, default=0, nullable=False)
    expiry_date = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("units >= 0", name="nonnegative_units"),
        CheckConstraint(
            "component IN ('whole_blood', 'red_cells', 'plasma', 'platelets')",
            name="valid_blood_component",
        ),
        UniqueConstraint(
            "blood_group",
            "component",
            "batch_number",
            name="uix_blood_group_component_batch",
        ),
    )


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True, index=True)
    code = Column(String(30), nullable=False, unique=True, index=True)
    location = Column(String(200), nullable=False)
    contact_phone = Column(String(30), nullable=True)
    email = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    email = Column(String(150), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="staff", index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'staff', 'viewer')",
            name="valid_user_role",
        ),
    )


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    blood_group = Column(String(3), nullable=False, index=True)
    component = Column(
        String(30),
        nullable=False,
        default="whole_blood",
        index=True,
    )
    units_needed = Column(Integer, nullable=False)
    priority = Column(String(20), nullable=False, default="medium", index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    notes = Column(String(500), nullable=True)
    request_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("units_needed > 0", name="positive_request_units"),
        CheckConstraint(
            "component IN ('whole_blood', 'red_cells', 'plasma', 'platelets')",
            name="valid_request_component",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="valid_request_priority",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'fulfilled')",
            name="valid_request_status",
        ),
    )


class BloodDistribution(Base):
    __tablename__ = "blood_distributions"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("blood_requests.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("blood_inventory.id"), nullable=False, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    units_dispatched = Column(Integer, nullable=False)
    dispatch_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="dispatched", index=True)
    recipient_reference = Column(String(100), nullable=True)
    notes = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("units_dispatched > 0", name="positive_distribution_units"),
        CheckConstraint(
            "status IN ('dispatched', 'received', 'rejected')",
            name="valid_distribution_status",
        ),
    )


class InventorySummary(Base):
    __tablename__ = "inventory_summary"

    id = Column(Integer, primary_key=True, index=True)
    blood_group = Column(String(3), nullable=False, index=True)
    total_units = Column(Integer, nullable=False, default=0)
    available_units = Column(Integer, nullable=False, default=0)
    reserved_units = Column(Integer, nullable=False, default=0)
    expired_units = Column(Integer, nullable=False, default=0)
    near_expiry_units = Column(Integer, nullable=False, default=0)
    last_updated = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("blood_group", name="uix_inventory_blood_group"),
    )


class ExpiryAlert(Base):
    __tablename__ = "expiry_alerts"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("blood_inventory.id"), nullable=False, index=True)
    alert_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="active", index=True)
    notes = Column(String(500), nullable=True)

    inventory = relationship("BloodInventory")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'resolved')",
            name="valid_alert_status",
        ),
    )


class StockAlert(Base):
    __tablename__ = "stock_alerts"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("blood_inventory.id"), nullable=False, index=True)
    alert_threshold = Column(Integer, nullable=False, default=5)
    alert_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status = Column(String(20), nullable=False, default="active", index=True)
    notes = Column(String(500), nullable=True)

    inventory = relationship("BloodInventory")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'resolved')",
            name="valid_alert_status",
        ),
    )
