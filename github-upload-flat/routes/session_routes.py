
from flask import Blueprint, jsonify
from db import db
from models.models import SessionType

session_bp = Blueprint("session_bp", __name__)

@session_bp.route("/", methods=["GET"])
def get_session_types():
    session_types = SessionType.query.all()
    return jsonify([
        {
            "id": st.id,
            "name": st.name,
            "duration_minutes": st.duration_minutes,
            "price": st.price,
        }
        for st in session_types
    ]), 200

