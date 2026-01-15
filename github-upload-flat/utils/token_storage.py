""
QuickBooks Token Storage Utilities - VERSION CORRIGÉE
Handles saving, loading, validating, and REFRESHING QuickBooks OAuth tokens

CHANGEMENTS PRINCIPAUX:
- Ajout de refresh_access_token() pour rafraîchir automatiquement les jetons
- Ajout de get_valid_token() pour obtenir un jeton valide (rafraîchit si nécessaire)
- Amélioration de la gestion des erreurs
"""

import json
import os
import requests
from datetime import datetime, timedelta

# Token file path - store in persistent location
TOKEN_FILE_PATH = os.environ.get("QB_TOKEN_FILE", "/tmp/data/qb_token.json")

# QuickBooks OAuth Configuration (needed for refresh)
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID", "AB32rXJy5ipKKQaRgwX0ci4v770Ja9B3hvHTRERj25XTsQr5g8")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET", "wmDRQCodu34KTwgeD6DQT3UTLqU3qAwsmPKl6GD1")
QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

def save_token_to_file(access_token, refresh_token, realm_id, expires_in):
    """
    Save QuickBooks token to a JSON file
    
    Args:
        access_token (str): OAuth access token
        refresh_token (str): OAuth refresh token
        realm_id (str): QuickBooks company/realm ID
        expires_in (int): Token expiration time in seconds
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        # Ensure directory exists
        token_dir = os.path.dirname(TOKEN_FILE_PATH)
        if not os.path.exists(token_dir):
            os.makedirs(token_dir, exist_ok=True)
        
        # Calculate expiration timestamp
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "realm_id": realm_id,
            "expires_in": expires_in,
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Write to file
        with open(TOKEN_FILE_PATH, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"✓ Token saved to file: {TOKEN_FILE_PATH}")
        return True
        
    except Exception as e:
        print(f"✗ ERROR saving token to file: {str(e)}")
        return False

def load_token_from_file():
    """
    Load QuickBooks token from JSON file
    
    Returns:
        dict: Token data if file exists and is valid, None otherwise
    """
    try:
        if not os.path.exists(TOKEN_FILE_PATH):
            print(f"Token file not found: {TOKEN_FILE_PATH}")
            return None
        
        with open(TOKEN_FILE_PATH, 'r') as f:
            token_data = json.load(f)
        
        print(f"✓ Token loaded from file for realm: {token_data.get('realm_id')}")
        return token_data
        
    except Exception as e:
        print(f"✗ ERROR loading token from file: {str(e)}")
        return None

def is_token_valid(token_data, buffer_minutes=10):
    """
    Check if a token is still valid (not expired)
    
    Args:
        token_data (dict): Token data dictionary
        buffer_minutes (int): Minutes before expiration to consider token invalid (default: 10)
    
    Returns:
        bool: True if token is valid, False if expired or invalid
    """
    try:
        if not token_data or not token_data.get('expires_at'):
            return False
        
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        now = datetime.utcnow()
        
        # Add buffer to avoid edge cases (refresh proactively)
        is_valid = expires_at > (now + timedelta(minutes=buffer_minutes))
        
        if is_valid:
            time_remaining = expires_at - now
            print(f"✓ Token is valid. Expires in {time_remaining}")
        else:
            print(f"⚠ Token has expired or will expire soon (within {buffer_minutes} minutes)")
        
        return is_valid
        
    except Exception as e:
        print(f"✗ ERROR checking token validity: {str(e)}")
        return False

def refresh_access_token():
    """
    Refresh the access token using the refresh_token
    
    IMPORTANT: This function uses the refresh_token to get a NEW access_token
    and a NEW refresh_token. Both must be saved!
    
    Returns:
        dict: New token data if refresh was successful, None otherwise
    """
    print("🔄 Attempting to refresh access token...")
    
    token_data = load_token_from_file()
    if not token_data or not token_data.get('refresh_token'):
        print("✗ No refresh token available. User must reconnect.")
        return None
    
    try:
        # Call QuickBooks token endpoint with refresh_token
        response = requests.post(
            QB_TOKEN_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            auth=(QB_CLIENT_ID, QB_CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": token_data.get('refresh_token')
            },
            timeout=10
        )
        
        if response.status_code == 200:
            tokens = response.json()
            print("✓ Successfully refreshed access token")
            
            # CRITICAL: Save BOTH the new access_token AND the new refresh_token
            # QuickBooks returns a NEW refresh_token with each refresh
            success = save_token_to_file(
                access_token=tokens.get("access_token"),
                refresh_token=tokens.get("refresh_token"),  # NEW refresh_token!
                realm_id=token_data.get('realm_id'),
                expires_in=tokens.get("expires_in", 3600)
            )
            
            if success:
                return load_token_from_file()
            else:
                print("✗ Failed to save refreshed token")
                return None
        else:
            print(f"✗ Failed to refresh token. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("✗ Timeout while refreshing token")
        return None
    except Exception as e:
        print(f"✗ ERROR refreshing token: {str(e)}")
        return None

def get_valid_token():
    """
    Get a valid QuickBooks token, refreshing it automatically if needed
    
    This is the main function to use when you need a token for API calls.
    It will automatically refresh the token if it's expired or about to expire.
    
    Returns:
        dict: Valid token data, or None if unable to get/refresh token
    """
    token_data = load_token_from_file()
    
    if not token_data:
        print("✗ No token found. User must connect to QuickBooks.")
        return None
    
    # Check if token is valid (with 10-minute buffer)
    if not is_token_valid(token_data, buffer_minutes=10):
        print("⚠ Token expired or expiring soon. Attempting refresh...")
        token_data = refresh_access_token()
        
        if not token_data:
            print("✗ Failed to refresh token. User must reconnect.")
            return None
        
        print("✓ Token refreshed successfully")
    
    return token_data

def delete_token_file():
    """
    Delete the token file (used for disconnecting)
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        if os.path.exists(TOKEN_FILE_PATH):
            os.remove(TOKEN_FILE_PATH)
            print(f"✓ Token file deleted: {TOKEN_FILE_PATH}")
            return True
        else:
            print(f"Token file not found (already deleted?): {TOKEN_FILE_PATH}")
            return True
        
    except Exception as e:
        print(f"✗ ERROR deleting token file: {str(e)}")
        return False

def get_token_info():
    """
    Get information about the current token without full validation
    
    Returns:
        dict: Token info or None if no token exists
    """
    token_data = load_token_from_file()
    if not token_data:
        return None
    
    return {
        "realm_id": token_data.get("realm_id"),
        "created_at": token_data.get("created_at"),
        "expires_at": token_data.get("expires_at"),
        "is_valid": is_token_valid(token_data, buffer_minutes=10)
    }

# Test function for debugging
def test_token_refresh():
    """
    Test function to verify token refresh works correctly
    Can be called manually for debugging
    """
    print("\n" + "="*60)
    print("TESTING TOKEN REFRESH FUNCTIONALITY")
    print("="*60 + "\n")
    
    # Load current token
    token_data = load_token_from_file()
    if not token_data:
        print("✗ No token found. Please connect to QuickBooks first.")
        return False
    
    print(f"Current token realm: {token_data.get('realm_id')}")
    print(f"Expires at: {token_data.get('expires_at')}")
    print(f"Is valid: {is_token_valid(token_data)}")
    
    # Try to get valid token (will refresh if needed)
    print("\nAttempting to get valid token...")
    valid_token = get_valid_token()
    
    if valid_token:
        print("✓ Successfully obtained valid token")
        print(f"New expires at: {valid_token.get('expires_at')}")
        return True
    else:
        print("✗ Failed to obtain valid token")
        return False

if __name__ == "__main__":
    # Run test if executed directly
    test_token_refresh()
