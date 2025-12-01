from flask import Blueprint, request, jsonify
from models.models import SessionType
from db import db

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Get all services
@admin_bp.route('/services', methods=['GET'])
def get_all_services():
    """Get all available services/session types"""
    try:
        services = SessionType.query.all()
        return jsonify([{
            "id": s.id,
            "name": s.name,
            "price": s.price,
            "duration": s.duration,
            "created_at": s.created_at.isoformat() if s.created_at else None
        } for s in services]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add a new service
@admin_bp.route('/services', methods=['POST'])
def add_service():
    """Add a new service/session type"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('price'):
            return jsonify({"error": "Name and price are required"}), 400
        
        # Check if service already exists
        existing_service = SessionType.query.filter_by(name=data['name']).first()
        if existing_service:
            return jsonify({"error": "Service with this name already exists"}), 400
        
        # Create new service
        new_service = SessionType(
            name=data['name'],
            price=float(data['price']),
            duration=int(data.get('duration', 60))
        )
        
        db.session.add(new_service)
        db.session.commit()
        
        return jsonify({
            "message": "Service added successfully",
            "service": {
                "id": new_service.id,
                "name": new_service.name,
                "price": new_service.price,
                "duration": new_service.duration
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Update a service
@admin_bp.route('/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    """Update an existing service"""
    try:
        service = SessionType.query.get(service_id)
        if not service:
            return jsonify({"error": "Service not found"}), 404
        
        data = request.get_json()
        
        # Update fields if provided
        if 'name' in data:
            service.name = data['name']
        if 'price' in data:
            service.price = float(data['price'])
        if 'duration' in data:
            service.duration = int(data['duration'])
        
        db.session.commit()
        
        return jsonify({
            "message": "Service updated successfully",
            "service": {
                "id": service.id,
                "name": service.name,
                "price": service.price,
                "duration": service.duration
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Delete a service
@admin_bp.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """Delete a service"""
    try:
        service = SessionType.query.get(service_id)
        if not service:
            return jsonify({"error": "Service not found"}), 404
        
        db.session.delete(service)
        db.session.commit()
        
        return jsonify({"message": "Service deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Import predefined services
@admin_bp.route('/services/import', methods=['POST'])
def import_predefined_services():
    """Import a predefined list of services"""
    try:
        # Predefined services list
        predefined_services = [
            {"name": "Individuel (En ligne)", "duration": 60, "price": 40.00},
            {"name": "Individuel (En personne)", "duration": 60, "price": 40.00},
            {"name": "Petit groupe (2-3) (En ligne)", "duration": 60, "price": 30.00},
            {"name": "Petit groupe (2-3) (En personne)", "duration": 60, "price": 30.00},
            {"name": "Groupe (4-5) (En ligne)", "duration": 60, "price": 21.00},
            {"name": "Groupe (4-5) (En personne)", "duration": 60, "price": 21.00},
            {"name": "Grand groupe (6+) (En ligne)", "duration": 60, "price": 21.00},
            {"name": "Grand groupe (6+) (En personne)", "duration": 60, "price": 21.00},
            {"name": "Piano", "duration": 30, "price": 27.00},
            {"name": "Guitare", "duration": 30, "price": 27.00},
            {"name": "Chant", "duration": 30, "price": 27.00},
            {"name": "Batterie", "duration": 30, "price": 27.00},
            {"name": "Heures", "duration": 60, "price": 0.00}
        ]
        
        imported_count = 0
        skipped_count = 0
        
        for service_data in predefined_services:
            # Check if service already exists
            existing_service = SessionType.query.filter_by(name=service_data["name"]).first()
            if existing_service:
                skipped_count += 1
                continue
            
            # Create new service
            new_service = SessionType(
                name=service_data["name"],
                duration=service_data["duration"],
                price=service_data["price"]
            )
            db.session.add(new_service)
            imported_count += 1
        
        db.session.commit()
        
        return jsonify({
            "message": f"Import completed: {imported_count} services imported, {skipped_count} skipped (already exist)",
            "imported": imported_count,
            "skipped": skipped_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


