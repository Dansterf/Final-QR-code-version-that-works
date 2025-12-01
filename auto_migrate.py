"""
Auto-migration script that runs when the app starts
This will automatically add the customer_type and is_manual columns
"""

import os
from sqlalchemy import create_engine, text, inspect

def auto_migrate():
    """
    Automatically migrate the database on app startup
    Only runs if columns don't exist yet
    """
    try:
        # Get database URL
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            print("⚠️  DATABASE_URL not found, skipping migration")
            return
        
        # Fix Railway PostgreSQL URL
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        # Skip if using SQLite (local development)
        if 'sqlite' in database_url:
            print("ℹ️  Using SQLite, skipping PostgreSQL migration")
            return
        
        print("🔄 Checking database schema...")
        
        # Create engine
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Check if tables exist
        if 'customers' not in inspector.get_table_names():
            print("ℹ️  Tables not created yet, skipping migration")
            return
        
        with engine.connect() as connection:
            # Check if customer_type column exists
            columns = [col['name'] for col in inspector.get_columns('customers')]
            
            if 'customer_type' not in columns:
                print("📝 Adding customer_type column...")
                connection.execute(text(
                    "ALTER TABLE customers ADD COLUMN customer_type VARCHAR(20) DEFAULT 'in-person'"
                ))
                connection.commit()
                print("   ✅ customer_type column added")
            else:
                print("   ✓ customer_type column already exists")
            
            # Check if is_manual column exists
            checkin_columns = [col['name'] for col in inspector.get_columns('check_ins')]
            
            if 'is_manual' not in checkin_columns:
                print("📝 Adding is_manual column...")
                connection.execute(text(
                    "ALTER TABLE check_ins ADD COLUMN is_manual BOOLEAN DEFAULT FALSE"
                ))
                connection.commit()
                print("   ✅ is_manual column added")
            else:
                print("   ✓ is_manual column already exists")
            
            # Update existing customers
            connection.execute(text(
                "UPDATE customers SET customer_type = 'in-person' WHERE customer_type IS NULL"
            ))
            connection.commit()
            
        print("✅ Database schema up to date!")
        
    except Exception as e:
        print(f"⚠️  Migration warning: {e}")
        # Don't crash the app if migration fails
        pass

if __name__ == "__main__":
    auto_migrate()
