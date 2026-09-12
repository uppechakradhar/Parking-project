"""
models.py
SQLAlchemy ORM models for the Smart Parking Management System.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ParkingSlot(db.Model):
    __tablename__ = "parking_slots"

    id = db.Column(db.Integer, primary_key=True)
    slot_number = db.Column(db.String(10), unique=True, nullable=False)
    slot_type = db.Column(db.String(10), nullable=False, default="CAR")  # CAR, BIKE, EV
    status = db.Column(db.String(15), nullable=False, default="AVAILABLE")  # AVAILABLE, OCCUPIED, RESERVED
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=True)

    def to_dict(self):
        vehicle = None
        if self.status == "OCCUPIED" and self.vehicle_id:
            v = Vehicle.query.get(self.vehicle_id)
            if v:
                vehicle = {
                    "vehicle_number": v.vehicle_number,
                    "vehicle_type": v.vehicle_type,
                    "entry_time": v.entry_time.isoformat() if v.entry_time else None,
                }
        return {
            "id": self.id,
            "slot_number": self.slot_number,
            "slot_type": self.slot_type,
            "status": self.status,
            "vehicle_id": self.vehicle_id,
            "vehicle": vehicle,
        }


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_number = db.Column(db.String(20), index=True, nullable=False)
    vehicle_type = db.Column(db.String(10), nullable=False, default="CAR")  # CAR, BIKE, TRUCK/EV
    entry_time = db.Column(db.DateTime, default=datetime.utcnow)
    exit_time = db.Column(db.DateTime, nullable=True)
    slot_id = db.Column(db.Integer, db.ForeignKey("parking_slots.id"), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(15), nullable=False, default="PARKED")  # PARKED, COMPLETED
    entry_image = db.Column(db.String(255), nullable=True)
    exit_image = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_number": self.vehicle_number,
            "vehicle_type": self.vehicle_type,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "slot_id": self.slot_id,
            "slot_number": ParkingSlot.query.get(self.slot_id).slot_number if self.slot_id else None,
            "duration_minutes": self.duration_minutes,
            "amount": self.amount,
            "status": self.status,
            "entry_image": self.entry_image,
            "exit_image": self.exit_image,
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(10), nullable=False, default="CASH")  # CASH, UPI, CARD
    payment_status = db.Column(db.String(10), nullable=False, default="PAID")  # PAID, PENDING
    payment_time = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_id = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "amount": self.amount,
            "payment_mode": self.payment_mode,
            "payment_status": self.payment_status,
            "payment_time": self.payment_time.isoformat() if self.payment_time else None,
            "transaction_id": self.transaction_id,
        }


class PricingRule(db.Model):
    __tablename__ = "pricing_rules"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(10), nullable=False, unique=True)
    base_rate = db.Column(db.Float, nullable=False, default=20.0)
    base_hours = db.Column(db.Integer, nullable=False, default=1)
    hourly_rate = db.Column(db.Float, nullable=False, default=10.0)
    grace_period_mins = db.Column(db.Integer, nullable=False, default=15)

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_type": self.vehicle_type,
            "base_rate": self.base_rate,
            "base_hours": self.base_hours,
            "hourly_rate": self.hourly_rate,
            "grace_period_mins": self.grace_period_mins,
        }


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="operator")  # admin, operator
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
