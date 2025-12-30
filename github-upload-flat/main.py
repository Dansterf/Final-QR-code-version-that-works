
from routes.session_routes import session_bp
from auto_migrate import auto_migrate
from routes.pages_routes import pages_bp  # Import
from routes.sessiontype_routes import sessiontype_bp  # Avec les imports



import os

# Environment variables will be loaded from Railway or .env file
# No hardcoded credentials for security
if not os.environ.get("QB_ENVIRONMENT"):
    os.environ["QB_ENVIRONMENT"] = "production"

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from db import db

# Try to load environment variables from .env file (optional, will override defaults above)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not available, using environment variables

# Create Flask app with explicit instance_path to avoid conflicts
app = Flask(__name__, 
            static_folder="static", 
            static_url_path="/",
            instance_path="/tmp/flask_instance")
CORS(app)

# Configure the database - PostgreSQL for Railway
# Railway automatically provides DATABASE_URL when you add a PostgreSQL database
database_url = os.environ.get("DATABASE_URL")

if database_url:
    # Railway provides DATABASE_URL - use PostgreSQL
    # Fix for SQLAlchemy 1.4+ which requires postgresql:// instead of postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    print(f"Using PostgreSQL database")
else:
    # Fallback to SQLite for local development
    database_path = "/tmp/data"
    if not os.path.exists(database_path):
        os.makedirs(database_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(database_path, 'app.db')}"
    print(f"Using SQLite database at: {os.path.join(database_path, 'app.db')}")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
db.init_app(app)

# Import models after db is defined to avoid circular imports
from models.models import Customer, SessionType, CheckIn, QuickBooksToken

# Register blueprints
from routes.customer_routes import customer_bp
from routes.session_routes import session_bp
from routes.checkin_routes import checkin_bp
from routes.quickbooks_routes import quickbooks_bp
from routes.admin_routes import admin_bp
from routes.email_routes_improved import email_improved_bp
from routes.simple_checkin_route import simple_checkin_bp



app.register_blueprint(session_bp)
app.register_blueprint(customer_bp, url_prefix="/api/customers")
app.register_blueprint(checkin_bp, url_prefix="/api/checkins")
app.register_blueprint(quickbooks_bp, url_prefix="/api/quickbooks")
app.register_blueprint(admin_bp, url_prefix="/api/admin")
app.register_blueprint(email_improved_bp, url_prefix="/api/email")
app.register_blueprint(simple_checkin_bp)
app.register_blueprint(pages_bp)  # Register
app.register_blueprint(sessiontype_bp)  # Avec les register_blueprint

def create_tables_and_initial_data():
    db.create_all()
    # Add initial session types if they don't exist
    if not SessionType.query.first():
        initial_session_types = [
            SessionType(name="French Tutoring", duration=60, price=50.00),
SessionType(name="Math Tutoring", duration=60, price=45.00),
SessionType(name="Piano Lesson", duration=30, price=35.00),

        ]
        db.session.add_all(initial_session_types)
        db.session.commit()

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, "index.html")

with app.app_context():
    create_tables_and_initial_data()

if __name__ == "__main__":
        # Run auto-migration on startup
    auto_migrate()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)

