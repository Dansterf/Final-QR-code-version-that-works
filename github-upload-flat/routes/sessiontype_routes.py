from flask import Blueprint, jsonify
from models.models import SessionType

sessiontype_bp = Blueprint('sessiontype_bp', __name__)

@sessiontype_bp.route("/api/session-types", methods=["GET"])
def get_session_types():
    """Get all session types"""
    try:
        session_types = SessionType.query.all()
        result = []
        
        for st in session_types:
            result.append({
                "id": st.id,
                "name": st.name,
                "price": float(st.price)
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to get session types: {str(e)}")
        return jsonify({"error": "Failed to retrieve session types"}), 500
