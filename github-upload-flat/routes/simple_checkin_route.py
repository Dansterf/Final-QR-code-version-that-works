from flask import Blueprint, send_from_directory
import os

simple_checkin_bp = Blueprint("simple_checkin_bp", __name__)

@simple_checkin_bp.route("/check-in", methods=["GET"])
def simple_checkin_page():
    """Serve the simple check-in HTML page"""
    # Get the static folder path
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_folder, 'checkin_simple.html')
