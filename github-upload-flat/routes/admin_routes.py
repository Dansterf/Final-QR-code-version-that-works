from flask import Blueprint, request, jsonify
from db import db
from models.models import SessionType

admin_bp = Blueprint("admin_bp", __name__)

# Predefined services to import
PREDEFINED_SERVICES = [
    {"name": "Absence Motivée", "duration_minutes": 60, "price": 21.00},
    {"name": "Absence non motivée", "duration_minutes": 60, "price": 21.00},
    {"name": "Cours annulé", "duration_minutes": 60, "price": 0.00},
    {"name": "Cours de Batterie", "duration_minutes": 60, "price": 27.00},
    {"name": "Cours de chant", "duration_minutes": 60, "price": 27.00},
    {"name": "Cours de Guitare", "duration_minutes": 60, "price": 27.00},
    {"name": "Cours de piano", "duration_minutes": 60, "price": 27.00},
    {"name": "Groupe Français", "duration_minutes": 60, "price": 21.00},
    {"name": "Groupe Mathématiques", "duration_minutes": 60, "price": 21.00},
    {"name": "Groupe mathématiques et Français", "duration_minutes": 60, "price": 21.00},
    {"name": "Heures", "duration_minutes": 60, "price": 0.00},
    {"name": "Individuel (En ligne)", "duration_minutes": 60, "price": 40.00},
    {"name": "Individuel (présentiel)", "duration_minutes": 60, "price": 40.00}
]

@admin_bp.route("/services", methods=["GET"])
def get_all_services():
    """Get all services"""
    services = SessionType.query.order_by(SessionType.name).all()
    return jsonify([{
        "id": s.id,
        "name": s.name,
        "duration": s.duration,
        "price": float(s.price)
    } for s in services]), 200

@admin_bp.route("/services", methods=["POST"])
def create_service():
    """Create a new service"""
    data = request.get_json()
    
    name = data.get("name")
    duration_minutes = data.get("duration_minutes", 60)
    price = data.get("price", 0.0)
    
    if not name:
        return jsonify({"error": "Service name is required"}), 400
    
    # Check if service already exists
    existing = SessionType.query.filter_by(name=name).first()
    if existing:
        return jsonify({"error": "Service with this name already exists"}), 400
    
    new_service = SessionType(
        name=name,
        duration_minutes=duration_minutes,
        price=price
    )
    
    db.session.add(new_service)
    db.session.commit()
    
    print(f"[ADMIN] ✓ Service created: {name} - ${price}")
    
    return jsonify({
        "id": new_service.id,
        "name": new_service.name,
        "duration_minutes": new_service.duration_minutes,
        "price": float(new_service.price)
    }), 201

@admin_bp.route("/services/<int:service_id>", methods=["PUT"])
def update_service(service_id):
    """Update an existing service"""
    service = SessionType.query.get(service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404
    
    data = request.get_json()
    
    if "name" in data:
        # Check if new name conflicts with another service
        existing = SessionType.query.filter_by(name=data["name"]).first()
        if existing and existing.id != service_id:
            return jsonify({"error": "Service with this name already exists"}), 400
        service.name = data["name"]
    
    if "duration_minutes" in data:
        service.duration_minutes = data["duration_minutes"]
    
    if "price" in data:
        service.price = data["price"]
    
    db.session.commit()
    
    print(f"[ADMIN] ✓ Service updated: {service.name} - ${service.price}")
    
    return jsonify({
        "id": service.id,
        "name": service.name,
        "duration_minutes": service.duration_minutes,
        "price": float(service.price)
    }), 200

@admin_bp.route("/services/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):
    """Delete a service"""
    service = SessionType.query.get(service_id)
    if not service:
        return jsonify({"error": "Service not found"}), 404
    
    service_name = service.name
    db.session.delete(service)
    db.session.commit()
    
    print(f"[ADMIN] ✓ Service deleted: {service_name}")
    
    return jsonify({"message": "Service deleted successfully"}), 200

@admin_bp.route("/services/import", methods=["POST"])
def import_predefined_services():
    """Import all predefined services"""
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    
    for service_data in PREDEFINED_SERVICES:
        service_name = service_data["name"]
        
        # Check if service already exists
        existing_service = SessionType.query.filter_by(name=service_name).first()
        
        if existing_service:
            # Update existing service
            existing_service.duration_minutes = service_data["duration_minutes"]
            existing_service.price = service_data["price"]
            updated_count += 1
            print(f"[ADMIN] ✓ Updated: {service_name} - ${service_data['price']:.2f}")
        else:
            # Create new service
           new_service = SessionType(
    name=service["name"],
    duration_minutes=service["duration"],
    price=service["price"]
)
            db.session.add(new_service)
            imported_count += 1
            print(f"[ADMIN] ✓ Imported: {service_name} - ${service_data['price']:.2f}")
    
    db.session.commit()
    
    total_services = SessionType.query.count()
    
    print(f"[ADMIN] Import complete: {imported_count} new, {updated_count} updated, {total_services} total")
    
    return jsonify({
        "success": True,
        "imported": imported_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "total": total_services
    }), 200

