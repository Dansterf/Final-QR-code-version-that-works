
from db import db
from datetime import datetime

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(80), nullable=False)
    lastName = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    qrCodeData = db.Column(db.String(255), unique=True, nullable=True)
    check_ins = db.relationship("CheckIn", backref="customer", lazy=True)

    def __repr__(self):
        return f"<Customer {self.firstName} {self.lastName}>"

class SessionType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    check_ins = db.relationship("CheckIn", backref="session_type", lazy=True)

    def __repr__(self):
        return f"<SessionType {self.name}>"

class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    session_type_id = db.Column(db.Integer, db.ForeignKey("session_type.id"), nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f"<CheckIn {self.customer_id} at {self.check_in_time}>"



class QuickBooksToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(500), nullable=True)
    refresh_token = db.Column(db.String(500), nullable=True)
    realm_id = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<QuickBooksToken realm_id={self.realm_id}>"

