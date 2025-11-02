
from flask import Blueprint, request, jsonify
from db import db
from models.models import Customer

customer_bp = Blueprint("customer_bp", __name__)

@customer_bp.route("/register", methods=["POST"])
def register_customer():
    data = request.get_json()
    firstName = data.get("firstName")
    lastName = data.get("lastName")
    email = data.get("email")
    phone = data.get("phone")
    address = data.get("address")
    qrCodeData = data.get("qrCodeData")

    if not all([firstName, lastName, email]):
        return jsonify({"error": "Missing required fields"}), 400

    if Customer.query.filter_by(email=email).first():
        return jsonify({"error": "Customer with this email already exists"}), 409

    new_customer = Customer(
        firstName=firstName,
        lastName=lastName,
        email=email,
        phone=phone,
        address=address,
        qrCodeData=qrCodeData
    )
    db.session.add(new_customer)
    db.session.commit()

    return jsonify({"message": "Customer registered successfully", "customer": {
        "id": new_customer.id,
        "firstName": new_customer.firstName,
        "lastName": new_customer.lastName,
        "email": new_customer.email,
        "qrCodeData": new_customer.qrCodeData
    }}), 201

@customer_bp.route("/by-qr-data", methods=["GET"])
def get_customer_by_qr_data():
    qr_data = request.args.get("qr_data")
    if not qr_data:
        return jsonify({"error": "QR data is required"}), 400

    customer = Customer.query.filter_by(qrCodeData=qr_data).first()
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    return jsonify({
        "id": customer.id,
        "firstName": customer.firstName,
        "lastName": customer.lastName,
        "email": customer.email,
        "qrCodeData": customer.qrCodeData
    }), 200

@customer_bp.route("/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    data = request.get_json()
    customer.firstName = data.get("firstName", customer.firstName)
    customer.lastName = data.get("lastName", customer.lastName)
    customer.email = data.get("email", customer.email)
    customer.phone = data.get("phone", customer.phone)
    customer.address = data.get("address", customer.address)
    customer.qrCodeData = data.get("qrCodeData", customer.qrCodeData)

    db.session.commit()
    return jsonify({"message": "Customer updated successfully", "customer": {
        "id": customer.id,
        "firstName": customer.firstName,
        "lastName": customer.lastName,
        "email": customer.email,
        "qrCodeData": customer.qrCodeData
    }}), 200

