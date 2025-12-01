from db import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(100), nullable=False)
    lastName = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.String(200))
    customer_type = db.Column(db.String(20), default='in-person')  # 'in-person' or 'remote'
    qr_code_data = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    check_ins = db.relationship('CheckIn', backref='customer', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'firstName': self.firstName,
            'lastName': self.lastName,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'customer_type': self.customer_type,
            'qr_code_data': self.qr_code_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CheckIn(db.Model):
    __tablename__ = 'check_ins'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)
    session_type = db.Column(db.String(100))
    notes = db.Column(db.Text)
    qb_invoice_id = db.Column(db.String(50))  # QuickBooks invoice ID
    is_manual = db.Column(db.Boolean, default=False)  # Track if session was manually entered
    
    def to_dict(self):
        customer = Customer.query.get(self.customer_id)
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': f"{customer.firstName} {customer.lastName}" if customer else "Unknown",
            'customer_type': customer.customer_type if customer else "in-person",
            'check_in_time': self.check_in_time.isoformat() if self.check_in_time else None,
            'session_type': self.session_type,
            'notes': self.notes,
            'qb_invoice_id': self.qb_invoice_id,
            'is_manual': self.is_manual
        }

class SessionType(db.Model):
    __tablename__ = 'session_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, default=60)  # in minutes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'duration': self.duration,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
