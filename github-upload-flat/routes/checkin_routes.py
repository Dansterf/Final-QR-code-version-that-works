
from flask import Blueprint, request, jsonify
from db import db
from models.models import CheckIn, Customer, SessionType
from datetime import datetime

checkin_bp = Blueprint("checkin_bp", __name__)

@checkin_bp.route("/", methods=["POST"])
def create_checkin():
    data = request.get_json()
    qrCodeValue = data.get("qrCodeValue")
    sessionTypeId = data.get("sessionTypeId")
    notes = data.get("notes")

    if not all([qrCodeValue, sessionTypeId]):
        return jsonify({"error": "Missing required fields"}), 400

    customer = Customer.query.filter_by(qrCodeData=qrCodeValue).first()
    if not customer:
        return jsonify({"error": "Customer not found for this QR code"}), 404

    session_type = SessionType.query.get(sessionTypeId)
    if not session_type:
        return jsonify({"error": "Session type not found"}), 404

    new_checkin = CheckIn(
        customer_id=customer.id,
        session_type_id=session_type.id,
        notes=notes,
        check_in_time=datetime.utcnow()
    )
    db.session.add(new_checkin)
    db.session.commit()

    return jsonify({"message": "Check-in successful", "checkin": {
        "id": new_checkin.id,
        "customer_id": new_checkin.customer_id,
        "session_type_id": new_checkin.session_type_id,
        "check_in_time": new_checkin.check_in_time.isoformat(),
        "notes": new_checkin.notes
    }}), 201

@checkin_bp.route("/", methods=["GET"])
def get_checkins():
    checkins = CheckIn.query.all()
    result = []
    for checkin in checkins:
        customer = Customer.query.get(checkin.customer_id)
        session_type = SessionType.query.get(checkin.session_type_id)
        result.append({
            "id": checkin.id,
            "customerName": f"{customer.firstName} {customer.lastName}" if customer else "Unknown",
            "sessionType": session_type.name if session_type else "Unknown",
            "checkInTime": checkin.check_in_time.isoformat(),
            "notes": checkin.notes,
            "price": session_type.price if session_type else 0.0
        })
    return jsonify(result), 200

