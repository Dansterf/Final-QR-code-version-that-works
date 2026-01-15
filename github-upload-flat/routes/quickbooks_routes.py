"""
QuickBooks Routes - VERSION CORRIGÉE
Handles QuickBooks OAuth flow and API calls with AUTOMATIC TOKEN REFRESH

CHANGEMENTS PRINCIPAUX:
- Utilise get_valid_token() au lieu de load_token_from_file()
- Gestion automatique du rafraîchissement des jetons
- Amélioration de la gestion des erreurs 401
- Retry automatique après rafraîchissement
"""

from flask import Blueprint, request, jsonify, redirect
import requests
import os
import json
from datetime import datetime, timedelta
from db import db
from models.models import QuickBooksToken
from utils.token_storage import (
    save_token_to_file, 
    load_token_from_file, 
    delete_token_file, 
    is_token_valid,
    get_valid_token,  # NOUVEAU: Fonction qui rafraîchit automatiquement
    refresh_access_token  # NOUVEAU: Pour rafraîchissement manuel si nécessaire
)

quickbooks_bp = Blueprint("quickbooks_bp", __name__)

# QuickBooks OAuth Configuration
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID", "AB32rXJy5ipKKQaRgwX0ci4v770Ja9B3hvHTRERj25XTsQr5g8")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET", "wmDRQCodu34KTwgeD6DQT3UTLqU3qAwsmPKl6GD1")
QB_REDIRECT_URI = os.environ.get("QB_REDIRECT_URI", "https://y0h0i3c80qd9.manus.space/api/quickbooks/callback")
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "sandbox")  # 'sandbox' or 'production'

# QuickBooks OAuth URLs
if QB_ENVIRONMENT == "production":
    QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_URL = "https://quickbooks.api.intuit.com"
else:
    QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
    QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
    QB_API_URL = "https://sandbox-quickbooks.api.intuit.com"

def get_qb_token():
    """Get the latest QuickBooks token from database (legacy function)"""
    return QuickBooksToken.query.order_by(QuickBooksToken.updated_at.desc()).first()

def save_qb_token(access_token, refresh_token, realm_id, expires_in):
    """Save QuickBooks token to file (persistent across requests)"""
    try:
        print(f"Saving token for realm {realm_id}")
        success = save_token_to_file(access_token, refresh_token, realm_id, expires_in)
        if success:
            print(f"✓ Token saved successfully for realm {realm_id}")
            # Verify it was saved
            verify_token = load_token_from_file()
            if verify_token:
                print(f"✓ Verification: Token exists in file with realm {verify_token.get('realm_id')}")
            else:
                print("✗ WARNING: Token not found after save!")
            return verify_token
        else:
            raise Exception("Failed to save token to file")
    except Exception as e:
        print(f"✗ ERROR saving token: {str(e)}")
        raise

def make_qb_api_call(endpoint, method="GET", data=None, token_data=None):
    """
    Make a QuickBooks API call with automatic token refresh on 401 errors
    
    Args:
        endpoint (str): API endpoint (e.g., "/v3/company/{realmId}/invoice")
        method (str): HTTP method (GET, POST, etc.)
        data (dict): Request body for POST/PUT requests
        token_data (dict): Token data (if None, will get valid token automatically)
    
    Returns:
        tuple: (response_data, status_code) or (None, error_code)
    """
    # Get valid token (will refresh if needed)
    if not token_data:
        token_data = get_valid_token()
    
    if not token_data:
        return {"error": "Not connected to QuickBooks"}, 401
    
    # Build full URL
    url = f"{QB_API_URL}{endpoint}"
    if "{realmId}" in url:
        url = url.replace("{realmId}", token_data.get('realm_id'))
    
    headers = {
        "Authorization": f"Bearer {token_data.get('access_token')}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # Make API call
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=10)
        else:
            return {"error": f"Unsupported HTTP method: {method}"}, 400
        
        # Handle 401 Unauthorized - token might be expired
        if response.status_code == 401:
            print("⚠ Received 401 Unauthorized. Attempting token refresh...")
            
            # Try to refresh token
            new_token_data = refresh_access_token()
            if new_token_data:
                print("✓ Token refreshed. Retrying API call...")
                # Retry the call with new token
                headers["Authorization"] = f"Bearer {new_token_data.get('access_token')}"
                
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, timeout=10)
                elif method.upper() == "POST":
                    response = requests.post(url, headers=headers, json=data, timeout=10)
                elif method.upper() == "PUT":
                    response = requests.put(url, headers=headers, json=data, timeout=10)
                
                if response.status_code in [200, 201]:
                    print("✓ Retry successful after token refresh")
            else:
                print("✗ Token refresh failed. User must reconnect.")
                return {"error": "Token expired and refresh failed. Please reconnect to QuickBooks."}, 401
        
        # Return response
        if response.status_code in [200, 201]:
            return response.json(), response.status_code
        else:
            return {"error": response.text}, response.status_code
            
    except requests.exceptions.Timeout:
        return {"error": "QuickBooks API request timeout"}, 504
    except Exception as e:
        return {"error": str(e)}, 500

@quickbooks_bp.route("/connect", methods=["GET"])
def connect_quickbooks():
    """Initiate QuickBooks OAuth flow"""
    # Get the current host from the request to build dynamic redirect URI
    current_host = request.host
    
    # Use the public manus.space URL (replace wasmer.app with manus.space)
    if 'wasmer.app' in current_host:
        current_host = current_host.replace('.id.wasmer.app', '.manus.space')
    
    dynamic_redirect_uri = f"https://{current_host}/api/quickbooks/callback"
    
    auth_url = f"{QB_AUTH_URL}?client_id={QB_CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting&redirect_uri={dynamic_redirect_uri}&state=security_token"
    return jsonify({"auth_url": auth_url, "redirect_uri": dynamic_redirect_uri}), 200

@quickbooks_bp.route("/auth/redirect", methods=["GET"])
def redirect_to_quickbooks():
    """Redirect directly to QuickBooks OAuth page"""
    current_host = request.host
    
    # Use the public manus.space URL (replace wasmer.app with manus.space)
    if 'wasmer.app' in current_host:
        current_host = current_host.replace('.id.wasmer.app', '.manus.space')
    
    dynamic_redirect_uri = f"https://{current_host}/api/quickbooks/callback"
    
    auth_url = f"{QB_AUTH_URL}?client_id={QB_CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting&redirect_uri={dynamic_redirect_uri}&state=security_token"
    
    return redirect(auth_url, code=302)

@quickbooks_bp.route("/callback", methods=["GET"])
def quickbooks_callback():
    """Handle OAuth callback from QuickBooks"""
    code = request.args.get("code")
    realm_id = request.args.get("realmId")
    error = request.args.get("error")
    
    if error:
        return f"<html><body><h1>Error connecting to QuickBooks</h1><p>{error}</p><a href='/'>Go back</a></body></html>", 400
    
    if not code or not realm_id:
        return "<html><body><h1>Error: Missing authorization code or realm ID</h1><a href='/'>Go back</a></body></html>", 400
    
    # Get the current host to build dynamic redirect URI (must match what was used in authorization)
    current_host = request.host
    if 'wasmer.app' in current_host:
        current_host = current_host.replace('.id.wasmer.app', '.manus.space')
    dynamic_redirect_uri = f"https://{current_host}/api/quickbooks/callback"
    
    # Exchange authorization code for access token
    try:
        token_response = requests.post(
            QB_TOKEN_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            auth=(QB_CLIENT_ID, QB_CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": dynamic_redirect_uri  # Use dynamic URI to match authorization request
            }
        )
        
        if token_response.status_code == 200:
            tokens = token_response.json()
            print(f"✓ Received tokens from QuickBooks for realm {realm_id}")
            # Save tokens to file
            try:
                saved_token = save_qb_token(
                    access_token=tokens.get("access_token"),
                    refresh_token=tokens.get("refresh_token"),
                    realm_id=realm_id,
                    expires_in=tokens.get("expires_in", 3600)
                )
                print(f"✓ Token saved successfully for realm: {realm_id}")
            except Exception as save_error:
                print(f"✗ CRITICAL ERROR saving token: {str(save_error)}")
                return f"<html><body><h1>Error saving token</h1><p>{str(save_error)}</p></body></html>", 500
            
            return """
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #4CAF50;">✓ Successfully Connected to QuickBooks!</h1>
                <p>You can now close this window and return to the application.</p>
                <p style="font-size: 12px; color: #666;">Please refresh the QuickBooks page to see the updated status.</p>
                <script>
                    setTimeout(function() {
                        window.close();
                    }, 3000);
                </script>
            </body>
            </html>
            """, 200
        else:
            return f"<html><body><h1>Error getting access token</h1><p>{token_response.text}</p></body></html>", 400
            
    except Exception as e:
        return f"<html><body><h1>Error during OAuth</h1><p>{str(e)}</p></body></html>", 500

@quickbooks_bp.route("/status", methods=["GET"])
def get_quickbooks_status():
    """Check QuickBooks connection status"""
    # Use get_valid_token which will refresh if needed
    token_data = get_valid_token()
    
    if token_data and token_data.get('access_token'):
        return jsonify({
            "connected": True,
            "status": "connected",
            "message": "QuickBooks is connected and active",
            "realm_id": token_data.get('realm_id'),
            "environment": QB_ENVIRONMENT,
            "company_name": "QuickBooks Company",  # Could be fetched from QB API
            "expires_at": token_data.get('expires_at')
        }), 200
    else:
        return jsonify({
            "connected": False,
            "status": "disconnected",
            "message": "QuickBooks not connected. Please connect to QuickBooks Online."
        }), 200

@quickbooks_bp.route("/disconnect", methods=["POST"])
def disconnect_quickbooks():
    """Disconnect from QuickBooks"""
    delete_token_file()
    return jsonify({"message": "Disconnected from QuickBooks"}), 200

@quickbooks_bp.route("/sync", methods=["POST"])
def sync_quickbooks():
    """Sync check-in data to QuickBooks"""
    # Use get_valid_token which will refresh if needed
    token_data = get_valid_token()
    
    if not token_data:
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    data = request.get_json()
    
    # This is a placeholder for actual sync logic
    # In a real implementation, you would:
    # 1. Fetch check-in data from database
    # 2. Create invoices or sales receipts in QuickBooks
    # 3. Handle errors and retries
    
    return jsonify({
        "message": "QuickBooks sync initiated successfully",
        "status": "connected",
        "realm_id": token_data.get('realm_id'),
        "note": "Sync functionality is a placeholder. Implement actual invoice/sales receipt creation as needed."
    }), 200

@quickbooks_bp.route("/create-invoice", methods=["POST"])
def create_invoice():
    """Create an invoice in QuickBooks with automatic token refresh"""
    # Use get_valid_token which will refresh if needed
    token_data = get_valid_token()
    
    if not token_data:
        return jsonify({"error": "Not connected to QuickBooks. Please reconnect."}), 401
    
    data = request.get_json()
    customer_name = data.get("customer_name")
    amount = data.get("amount")
    description = data.get("description")
    
    if not all([customer_name, amount, description]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Create invoice data
    invoice_data = {
        "Line": [{
            "Amount": amount,
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": "1",  # Default item, should be configured
                    "name": "Services"
                }
            },
            "Description": description
        }],
        "CustomerRef": {
            "value": "1"  # This should be looked up or created
        }
    }
    
    # Use the new make_qb_api_call function which handles refresh automatically
    response_data, status_code = make_qb_api_call(
        endpoint=f"/v3/company/{token_data.get('realm_id')}/invoice",
        method="POST",
        data=invoice_data,
        token_data=token_data
    )
    
    if status_code in [200, 201]:
        return jsonify({
            "message": "Invoice created successfully",
            "invoice": response_data
        }), 200
    else:
        return jsonify(response_data), status_code

@quickbooks_bp.route("/test-refresh", methods=["GET"])
def test_token_refresh():
    """
    Test endpoint to manually trigger token refresh
    Useful for debugging and verification
    """
    print("\n" + "="*60)
    print("MANUAL TOKEN REFRESH TEST")
    print("="*60 + "\n")
    
    # Load current token
    current_token = load_token_from_file()
    if not current_token:
        return jsonify({
            "error": "No token found",
            "message": "Please connect to QuickBooks first"
        }), 404
    
    # Show current token info
    print(f"Current token realm: {current_token.get('realm_id')}")
    print(f"Expires at: {current_token.get('expires_at')}")
    print(f"Is valid: {is_token_valid(current_token)}")
    
    # Try to refresh
    new_token = refresh_access_token()
    
    if new_token:
        return jsonify({
            "success": True,
            "message": "Token refreshed successfully",
            "old_expires_at": current_token.get('expires_at'),
            "new_expires_at": new_token.get('expires_at'),
            "realm_id": new_token.get('realm_id')
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": "Token refresh failed",
            "error": "Unable to refresh token. User may need to reconnect."
        }), 500
