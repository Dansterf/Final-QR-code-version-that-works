"""
Token storage utility using JSON file for persistence
This ensures tokens survive across requests within the same deployment
"""
import json
import os
from datetime import datetime, timedelta
from threading import Lock

# File path for token storage
TOKEN_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'qb_token.json')
token_lock = Lock()

def save_token_to_file(access_token, refresh_token, realm_id, expires_in):
    """Save token to JSON file"""
    with token_lock:
        token_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'realm_id': realm_id,
            'expires_at': (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        try:
            with open(TOKEN_FILE, 'w') as f:
                json.dump(token_data, f)
            print(f"Token saved to file: {TOKEN_FILE}")
            return True
        except Exception as e:
            print(f"Error saving token to file: {e}")
            return False

def load_token_from_file():
    """Load token from JSON file"""
    with token_lock:
        try:
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                # Convert ISO format string back to datetime
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
                token_data['updated_at'] = datetime.fromisoformat(token_data['updated_at'])
                print(f"Token loaded from file for realm: {token_data.get('realm_id')}")
                return token_data
            else:
                print(f"Token file not found: {TOKEN_FILE}")
                return None
        except Exception as e:
            print(f"Error loading token from file: {e}")
            return None

def delete_token_file():
    """Delete token file"""
    with token_lock:
        try:
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
                print(f"Token file deleted: {TOKEN_FILE}")
                return True
        except Exception as e:
            print(f"Error deleting token file: {e}")
            return False

def is_token_valid(token_data):
    """Check if token is still valid"""
    if not token_data:
        return False
    expires_at = token_data.get('expires_at')
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    return datetime.utcnow() < expires_at

