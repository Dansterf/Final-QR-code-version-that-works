from flask import Blueprint, request, jsonify
from models.models import Customer
from db import db
import uuid

customer_bp = Blueprint('customers', __name__, url_prefix='/api/customers')

@customer_bp.route('/register', methods=['POST'])
def register_customer():
    """Register a new customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('firstName') or not data.get('lastName') or not data.get('email'):
            return jsonify({"error": "First name, last name, and email are required"}), 400
        
        # Check if customer already exists
        existing_customer = Customer.query.filter_by(email=data['email']).first()
        if existing_customer:
            return jsonify({"error": "Customer with this email already exists"}), 400
        
        # Generate QR code data
        qr_code_data = str(uuid.uuid4())
        
        # Create new customer
        new_customer = Customer(
            firstName=data['firstName'],
            lastName=data['lastName'],
            email=data['email'],
            phone=data.get('phone'),
            address=data.get('address'),
            customer_type=data.get('customer_type', 'in-person'),
            qr_code_data=qr_code_data
        )
        
        db.session.add(new_customer)
        db.session.commit()
        
        return jsonify({
            "message": "Customer registered successfully",
            "customer": new_customer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@customer_bp.route('/by-qr-data', methods=['GET'])
def get_customer_by_qr_data():
    """Get customer by QR code data"""
    try:
        qr_data = request.args.get('qrData')
        if not qr_data:
            return jsonify({"error": "QR data is required"}), 400
        
        customer = Customer.query.filter_by(qr_code_data=qr_data).first()
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
        return jsonify(customer.to_dict()), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customer_bp.route('/', methods=['GET'])
def get_all_customers():
    """Get all customers"""
    try:
        customers = Customer.query.all()
        return jsonify([c.to_dict() for c in customers]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """Get a specific customer"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
        return jsonify(customer.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """Update a customer"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
        data = request.get_json()
        
        # Update fields if provided
        if 'firstName' in data:
            customer.firstName = data['firstName']
        if 'lastName' in data:
            customer.lastName = data['lastName']
        if 'email' in data:
            customer.email = data['email']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'address' in data:
            customer.address = data['address']
        if 'customer_type' in data:
            customer.customer_type = data['customer_type']
        
        db.session.commit()
        
        return jsonify({
            "message": "Customer updated successfully",
            "customer": customer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """Delete a customer"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
        db.session.delete(customer)
        db.session.commit()
        
        return jsonify({"message": "Customer deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
