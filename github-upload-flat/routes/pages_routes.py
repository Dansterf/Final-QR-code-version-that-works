from flask import Blueprint, send_from_directory
import os

pages_bp = Blueprint("pages_bp", __name__)

@pages_bp.route("/register-customer", methods=["GET"])
def register_customer_page():
    """Serve the customer registration HTML page"""
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_folder, 'register_customer.html')

@pages_bp.route("/history", methods=["GET"])
def history_page():
    """Serve the check-in history HTML page"""
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_folder, 'history.html')

@pages_bp.route("/quickbooks", methods=["GET"])
def quickbooks_page():
    """Serve the QuickBooks sync HTML page"""
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    return send_from_directory(static_folder, 'quickbooks.html')
