#!/usr/bin/env python3
"""
Script to import all services into the database
Run this script once to populate the SessionType table
"""

from main import app
from db import db
from models.models import SessionType

# List of all services from QuickBooks
SERVICES = [
    {
        "name": "Absence Motivée",
        "duration_minutes": 60,
        "price": 21.00,
        "category": "Tutorat"
    },
    {
        "name": "Absence non motivée",
        "duration_minutes": 60,
        "price": 21.00,
        "category": "Tutorat"
    },
    {
        "name": "Cours annulé",
        "duration_minutes": 60,
        "price": 0.00,
        "category": "Tutorat"
    },
    {
        "name": "Cours de Batterie",
        "duration_minutes": 60,
        "price": 27.00,
        "category": "Musique"
    },
    {
        "name": "Cours de chant",
        "duration_minutes": 60,
        "price": 27.00,
        "category": "Musique"
    },
    {
        "name": "Cours de Guitare",
        "duration_minutes": 60,
        "price": 27.00,
        "category": "Musique"
    },
    {
        "name": "Cours de piano",
        "duration_minutes": 60,
        "price": 27.00,
        "category": "Musique"
    },
    {
        "name": "Groupe Français",
        "duration_minutes": 60,
        "price": 21.00,
        "category": "Tutorat"
    },
    {
        "name": "Groupe Mathématiques",
        "duration_minutes": 60,
        "price": 21.00,
        "category": "Tutorat"
    },
    {
        "name": "Groupe mathématiques et Français",
        "duration_minutes": 60,
        "price": 21.00,
        "category": "Tutorat"
    },
    {
        "name": "Heures",
        "duration_minutes": 60,
        "price": 0.00,
        "category": "Général"
    },
    {
        "name": "Individuel (En ligne)",
        "duration_minutes": 60,
        "price": 40.00,
        "category": "Tutorat"
    },
    {
        "name": "Individuel (présentiel)",
        "duration_minutes": 60,
        "price": 40.00,
        "category": "Tutorat"
    }
]

def import_services():
    """Import all services into the database"""
    with app.app_context():
        print("=" * 60)
        print("IMPORTING SERVICES INTO DATABASE")
        print("=" * 60)
        print()
        
        imported_count = 0
        skipped_count = 0
        updated_count = 0
        
        for service_data in SERVICES:
            service_name = service_data["name"]
            
            # Check if service already exists
            existing_service = SessionType.query.filter_by(name=service_name).first()
            
            if existing_service:
                # Update existing service
                existing_service.duration_minutes = service_data["duration_minutes"]
                existing_service.price = service_data["price"]
                print(f"✓ Updated: {service_name} - ${service_data['price']:.2f}")
                updated_count += 1
            else:
                # Create new service
                new_service = SessionType(
                    name=service_name,
                    duration_minutes=service_data["duration_minutes"],
                    price=service_data["price"]
                )
                db.session.add(new_service)
                print(f"✓ Imported: {service_name} - ${service_data['price']:.2f}")
                imported_count += 1
        
        # Commit all changes
        db.session.commit()
        
        print()
        print("=" * 60)
        print("IMPORT COMPLETE!")
        print("=" * 60)
        print(f"✓ New services imported: {imported_count}")
        print(f"✓ Existing services updated: {updated_count}")
        print(f"✓ Total services in database: {SessionType.query.count()}")
        print()
        
        # Display all services
        print("=" * 60)
        print("ALL SERVICES IN DATABASE:")
        print("=" * 60)
        all_services = SessionType.query.order_by(SessionType.name).all()
        for service in all_services:
            print(f"  • {service.name} - ${service.price:.2f} ({service.duration_minutes} min)")
        print()

if __name__ == "__main__":
    import_services()

