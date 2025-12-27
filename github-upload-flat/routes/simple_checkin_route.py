from flask import Blueprint, send_file
import os

simple_checkin_bp = Blueprint("simple_checkin_bp", __name__)

@simple_checkin_bp.route("/simple-checkin", methods=["GET"])
def simple_checkin_page():
    """Serve the simple check-in HTML page"""
    # Get the path to the HTML file
    html_path = os.path.join(os.path.dirname(__file__), 'static', 'checkin_simple.html')
    return send_file(html_path)
