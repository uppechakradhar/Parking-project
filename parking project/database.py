"""
database.py
Handles DB initialization and seeding of default parking slots + pricing rules.
"""
from werkzeug.security import generate_password_hash
from models import db, ParkingSlot, PricingRule, User

DEFAULT_PRICING = [
    {"vehicle_type": "CAR", "base_rate": 20.0, "base_hours": 1, "hourly_rate": 10.0, "grace_period_mins": 15},
    {"vehicle_type": "BIKE", "base_rate": 10.0, "base_hours": 1, "hourly_rate": 5.0, "grace_period_mins": 15},
    {"vehicle_type": "TRUCK/EV", "base_rate": 40.0, "base_hours": 1, "hourly_rate": 20.0, "grace_period_mins": 10},
]


def seed_slots():
    """Create A01-A10 (CAR), B01-B10 (BIKE), C01-C05 (EV) if not already present."""
    if ParkingSlot.query.count() > 0:
        return
    slots = []
    for i in range(1, 11):
        slots.append(ParkingSlot(slot_number=f"A{i:02d}", slot_type="CAR", status="AVAILABLE"))
    for i in range(1, 11):
        slots.append(ParkingSlot(slot_number=f"B{i:02d}", slot_type="BIKE", status="AVAILABLE"))
    for i in range(1, 6):
        slots.append(ParkingSlot(slot_number=f"C{i:02d}", slot_type="EV", status="AVAILABLE"))
    db.session.bulk_save_objects(slots)
    db.session.commit()


def seed_pricing():
    if PricingRule.query.count() > 0:
        return
    for rule in DEFAULT_PRICING:
        db.session.add(PricingRule(**rule))
    db.session.commit()


def seed_admin_user():
    if User.query.filter_by(username="admin").first():
        return
    admin = User(
        username="admin",
        password_hash=generate_password_hash("admin123"),
        role="admin",
    )
    db.session.add(admin)
    db.session.commit()


def init_db(app):
    """Create all tables and seed initial data. Call within app context."""
    with app.app_context():
        db.create_all()
        seed_slots()
        seed_pricing()
        seed_admin_user()
