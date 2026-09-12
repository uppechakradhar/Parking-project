"""
app.py
Main Flask application entrypoint & routing for the
Smart Parking Management System with ANPR and Automated Timer-Based Billing.
"""
import os
import io
import csv
import uuid
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, jsonify, send_file, Response, redirect, url_for
)
from werkzeug.utils import secure_filename

from models import db, Vehicle, ParkingSlot, Payment, PricingRule
from database import init_db
import billing_service
import anpr_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png"}
ALLOWED_VIDEO_EXT = {"mp4", "avi", "mov"}

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'parking.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB uploads
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"

db.init_app(app)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def allowed_file(filename, allowed_ext):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext


def get_pricing_for(vehicle_type):
    rule = PricingRule.query.filter_by(vehicle_type=vehicle_type).first()
    if not rule:
        rule = PricingRule.query.first()  # fallback
    return rule


# ---------------------------------------------------------------------------------
# PAGE ROUTES
# ---------------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/entry")
def entry_gate():
    return render_template("entry_gate.html")


@app.route("/exit")
def exit_gate():
    return render_template("exit_gate.html")


@app.route("/slots")
def slots_page():
    return render_template("slots.html")


@app.route("/records")
def records_page():
    return render_template("records.html")


# ---------------------------------------------------------------------------------
# API: ENTRY
# ---------------------------------------------------------------------------------
@app.route("/api/entry/process", methods=["POST"])
def api_entry_process():
    """
    Accepts:
      - multipart file upload (field 'media', image or video), OR
      - JSON/form field 'plate_number' for manual entry
      - form field 'vehicle_type' (CAR/BIKE/TRUCK-EV), default CAR
    """
    payload = request.get_json(silent=True) or {}
    vehicle_type = request.form.get("vehicle_type") or payload.get("vehicle_type") or "CAR"
    manual_plate = request.form.get("plate_number") or payload.get("plate_number")

    plate_text = ""
    confidence = 0.0
    saved_image_rel = None

    if "media" in request.files and request.files["media"].filename:
        file = request.files["media"]
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        unique_name = f"entry_{uuid.uuid4().hex[:10]}.{ext or 'jpg'}"
        temp_path = os.path.join(UPLOAD_DIR, unique_name)
        file.save(temp_path)

        if ext in ALLOWED_IMAGE_EXT:
            result = anpr_engine.process_image_file(temp_path)
        elif ext in ALLOWED_VIDEO_EXT:
            result = anpr_engine.process_video_file(temp_path)
        else:
            return jsonify({"success": False, "message": "Unsupported file type"}), 400

        plate_text = result.get("plate_text", "")
        confidence = result.get("confidence", 0.0)
        if result.get("annotated_frame") is not None:
            anpr_engine.save_annotated_frame(result["annotated_frame"], UPLOAD_DIR, unique_name)
        saved_image_rel = f"uploads/{unique_name}"

    if not plate_text and manual_plate:
        plate_text = anpr_engine.normalize_plate_text(manual_plate)
        confidence = 100.0  # manually entered

    if not plate_text:
        return jsonify({"success": False, "message": "Could not detect a license plate. Try manual entry."}), 422

    # Prevent duplicate active entry
    existing = Vehicle.query.filter_by(vehicle_number=plate_text, status="PARKED").first()
    if existing:
        return jsonify({"success": False, "message": f"Vehicle {plate_text} is already parked in slot "
                                                        f"{ParkingSlot.query.get(existing.slot_id).slot_number}."}), 409

    slot_type_map = {"CAR": "CAR", "BIKE": "BIKE", "TRUCK/EV": "EV", "EV": "EV"}
    target_slot_type = slot_type_map.get(vehicle_type.upper(), "CAR")

    slot = ParkingSlot.query.filter_by(status="AVAILABLE", slot_type=target_slot_type).first()
    if not slot:
        return jsonify({"success": False, "message": f"No available {target_slot_type} slots."}), 409

    vehicle = Vehicle(
        vehicle_number=plate_text,
        vehicle_type=vehicle_type.upper(),
        entry_time=datetime.utcnow(),
        slot_id=slot.id,
        status="PARKED",
        entry_image=saved_image_rel,
    )
    db.session.add(vehicle)
    db.session.flush()

    slot.status = "OCCUPIED"
    slot.vehicle_id = vehicle.id
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Entry recorded. Gate opening.",
        "gate": "OPEN",
        "vehicle": vehicle.to_dict(),
        "slot": slot.to_dict(),
        "confidence": confidence,
    })


# ---------------------------------------------------------------------------------
# API: EXIT
# ---------------------------------------------------------------------------------
@app.route("/api/exit/process", methods=["POST"])
def api_exit_process():
    payload = request.get_json(silent=True) or {}
    manual_plate = request.form.get("plate_number") or payload.get("plate_number")
    payment_mode = request.form.get("payment_mode") or payload.get("payment_mode") or "CASH"

    plate_text = ""
    confidence = 0.0

    if "media" in request.files and request.files["media"].filename:
        file = request.files["media"]
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
        unique_name = f"exit_{uuid.uuid4().hex[:10]}.{ext or 'jpg'}"
        temp_path = os.path.join(UPLOAD_DIR, unique_name)
        file.save(temp_path)

        if ext in ALLOWED_IMAGE_EXT:
            result = anpr_engine.process_image_file(temp_path)
        elif ext in ALLOWED_VIDEO_EXT:
            result = anpr_engine.process_video_file(temp_path)
        else:
            return jsonify({"success": False, "message": "Unsupported file type"}), 400

        plate_text = result.get("plate_text", "")
        confidence = result.get("confidence", 0.0)
        if result.get("annotated_frame") is not None:
            anpr_engine.save_annotated_frame(result["annotated_frame"], UPLOAD_DIR, unique_name)
        exit_image_rel = f"uploads/{unique_name}"
    else:
        exit_image_rel = None

    if not plate_text and manual_plate:
        plate_text = anpr_engine.normalize_plate_text(manual_plate)
        confidence = 100.0

    if not plate_text:
        return jsonify({"success": False, "message": "Could not detect a license plate. Try manual entry."}), 422

    vehicle = Vehicle.query.filter_by(vehicle_number=plate_text, status="PARKED").first()
    if not vehicle:
        return jsonify({"success": False, "message": f"No active parked vehicle found for plate {plate_text}."}), 404

    pricing = get_pricing_for(vehicle.vehicle_type)
    exit_time = datetime.utcnow()
    bill = billing_service.calculate_bill(vehicle.entry_time, exit_time, pricing)

    vehicle.exit_time = exit_time
    vehicle.duration_minutes = bill["duration_minutes"]
    vehicle.amount = bill["amount"]
    vehicle.status = "COMPLETED"
    if exit_image_rel:
        vehicle.exit_image = exit_image_rel

    slot = ParkingSlot.query.get(vehicle.slot_id)
    if slot:
        slot.status = "AVAILABLE"
        slot.vehicle_id = None

    payment = Payment(
        vehicle_id=vehicle.id,
        amount=bill["amount"],
        payment_mode=payment_mode.upper(),
        payment_status="PAID",
        payment_time=exit_time,
        transaction_id=f"TXN{uuid.uuid4().hex[:12].upper()}",
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Exit processed. Gate opening.",
        "gate": "OPEN",
        "vehicle": vehicle.to_dict(),
        "bill": bill,
        "payment": payment.to_dict(),
        "confidence": confidence,
    })


# ---------------------------------------------------------------------------------
# API: SLOTS / ACTIVE VEHICLES / ANALYTICS / RECORDS
# ---------------------------------------------------------------------------------
@app.route("/api/slots")
def api_slots():
    slots = ParkingSlot.query.order_by(ParkingSlot.slot_number).all()
    return jsonify([s.to_dict() for s in slots])


@app.route("/api/vehicles/active")
def api_vehicles_active():
    vehicles = Vehicle.query.filter_by(status="PARKED").all()
    out = []
    for v in vehicles:
        pricing = get_pricing_for(v.vehicle_type)
        estimate = billing_service.live_estimate(v.entry_time, pricing)
        d = v.to_dict()
        d["live_duration"] = estimate["duration"]["formatted"]
        d["live_amount"] = estimate["amount"]
        out.append(d)
    return jsonify(out)


@app.route("/api/analytics")
def api_analytics():
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    today_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
        Payment.payment_time >= today_start
    ).scalar() or 0.0

    total_slots = ParkingSlot.query.count()
    occupied_slots = ParkingSlot.query.filter_by(status="OCCUPIED").count()
    occupancy_rate = round((occupied_slots / total_slots) * 100, 1) if total_slots else 0

    type_breakdown = db.session.query(
        Vehicle.vehicle_type, db.func.count(Vehicle.id)
    ).group_by(Vehicle.vehicle_type).all()

    # Peak hours: count entries by hour-of-day across all history
    all_entries = db.session.query(Vehicle.entry_time).all()
    hour_counts = [0] * 24
    for (entry_time,) in all_entries:
        if entry_time:
            hour_counts[entry_time.hour] += 1

    # Weekly revenue trend (last 7 days)
    weekly = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        rev = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_time >= day_start, Payment.payment_time < day_end
        ).scalar() or 0.0
        weekly.append({"date": day.isoformat(), "revenue": round(rev, 2)})

    return jsonify({
        "today_revenue": round(today_revenue, 2),
        "total_slots": total_slots,
        "occupied_slots": occupied_slots,
        "available_slots": total_slots - occupied_slots,
        "occupancy_rate": occupancy_rate,
        "vehicle_type_breakdown": [{"type": t, "count": c} for t, c in type_breakdown],
        "peak_hours": hour_counts,
        "weekly_revenue": weekly,
    })


@app.route("/api/records")
def api_records():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    search = request.args.get("search", "").strip().upper()
    status_filter = request.args.get("status", "").strip().upper()
    export_csv = request.args.get("export", "") == "csv"

    query = Vehicle.query.order_by(Vehicle.entry_time.desc())
    if search:
        query = query.filter(Vehicle.vehicle_number.like(f"%{search}%"))
    if status_filter in ("PARKED", "COMPLETED"):
        query = query.filter_by(status=status_filter)

    if export_csv:
        rows = query.all()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "Vehicle Number", "Type", "Entry Time", "Exit Time",
                          "Slot", "Duration (min)", "Amount", "Status"])
        for v in rows:
            slot = ParkingSlot.query.get(v.slot_id)
            writer.writerow([
                v.id, v.vehicle_number, v.vehicle_type,
                v.entry_time.isoformat() if v.entry_time else "",
                v.exit_time.isoformat() if v.exit_time else "",
                slot.slot_number if slot else "",
                v.duration_minutes or "", v.amount or "", v.status,
            ])
        mem = io.BytesIO(buf.getvalue().encode("utf-8"))
        return send_file(mem, mimetype="text/csv", as_attachment=True,
                          download_name="parking_records.csv")

    total = query.count()
    records = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "records": [r.to_dict() for r in records],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page else 1,
    })


@app.route("/api/pricing")
def api_pricing():
    rules = PricingRule.query.all()
    return jsonify([r.to_dict() for r in rules])


# ---------------------------------------------------------------------------------
# LIVE VIDEO STREAMING (webcam / RTSP / sample video)
# ---------------------------------------------------------------------------------
@app.route("/video_feed/<gate_type>")
def video_feed(gate_type):
    """
    Streams MJPEG frames with live ANPR bounding boxes.
    Query param ?source=0 for webcam index 0, or ?source=<rtsp_url>, or
    ?source=static/uploads/sample_video1.mp4 for a sample file.
    Defaults to webcam index 0.
    """
    source_param = request.args.get("source", "0")
    try:
        source = int(source_param)
    except ValueError:
        source = source_param  # RTSP URL or file path
        if not os.path.isabs(source) and not source.startswith("rtsp"):
            source = os.path.join(BASE_DIR, source)

    return Response(
        anpr_engine.generate_mjpeg_stream(source),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


if __name__ == "__main__":
    init_db(app)
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)
