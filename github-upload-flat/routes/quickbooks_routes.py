from flask import Blueprint, request, jsonify
import requests
import os
import json
from datetime import datetime, timedelta
from db import db
from models.models import QuickBooksToken
from utils.token_storage import save_token_to_file, load_token_from_file, delete_token_file, is_token_valid

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
    """Get the latest QuickBooks token from database"""
    return QuickBooksToken.query.order_by(QuickBooksToken.updated_at.desc()).first()

def save_qb_token(access_token, refresh_token, realm_id, expires_in):
    """Save QuickBooks token to file (persistent across requests)"""
    try:
        print(f"Saving token for realm {realm_id}")
        success = save_token_to_file(access_token, refresh_token, realm_id, expires_in)
        if success:
            print(f"Token saved successfully for realm {realm_id}")
            # Verify it was saved
            verify_token = load_token_from_file()
            if verify_token:
                print(f"Verification: Token exists in file with realm {verify_token.get('realm_id')}")
            else:
                print("WARNING: Token not found after save!")
            return verify_token
        else:
            raise Exception("Failed to save token to file")
    except Exception as e:
        print(f"ERROR saving token: {str(e)}")
        raise

@quickbooks_bp.route("/connect", methods=["GET"])
def connect_quickbooks():
    """Initiate QuickBooks OAuth flow"""
    # Get the current host from the request to build dynamic redirect URI
    from flask import request as flask_request, redirect
    current_host = flask_request.host
    
    # Use the public manus.space URL (replace wasmer.app with manus.space)
    if 'wasmer.app' in current_host:
        current_host = current_host.replace('.id.wasmer.app', '.manus.space')
    
    dynamic_redirect_uri = f"https://{current_host}/api/quickbooks/callback"
    
    auth_url = f"{QB_AUTH_URL}?client_id={QB_CLIENT_ID}&response_type=code&scope=com.intuit.quickbooks.accounting&redirect_uri={dynamic_redirect_uri}&state=security_token"
    return jsonify({"auth_url": auth_url, "redirect_uri": dynamic_redirect_uri}), 200

@quickbooks_bp.route("/auth/redirect", methods=["GET"])
def redirect_to_quickbooks():
    """Redirect directly to QuickBooks OAuth page"""
    from flask import request as flask_request, redirect
    current_host = flask_request.host
    
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
            print(f"Received tokens from QuickBooks for realm {realm_id}")
            # Save tokens to database instead of memory
            try:
                saved_token = save_qb_token(
                    access_token=tokens.get("access_token"),
                    refresh_token=tokens.get("refresh_token"),
                    realm_id=realm_id,
                    expires_in=tokens.get("expires_in", 3600)
                )
                print(f"Token saved with ID: {saved_token.id if saved_token else 'None'}")
            except Exception as save_error:
                print(f"CRITICAL ERROR saving token: {str(save_error)}")
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
    token_data = load_token_from_file()
    if token_data and token_data.get('access_token'):
        if is_token_valid(token_data):
            return jsonify({
                "status": "connected",
                "message": "QuickBooks is connected and active",
                "realm_id": token_data.get('realm_id'),
                "environment": QB_ENVIRONMENT
            }), 200
        else:
            return jsonify({
                "status": "expired",
                "message": "QuickBooks token expired. Please reconnect."
            }), 200
    else:
        return jsonify({
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
    token_data = load_token_from_file()
    if not token_data or not token_data.get('access_token'):
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    # Check if token is expired
    if not is_token_valid(token_data):
        return jsonify({"error": "QuickBooks token expired. Please reconnect."}), 401
    
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
    """Create an invoice in QuickBooks"""
    token_data = load_token_from_file()
    if not token_data or not token_data.get('access_token'):
        return jsonify({"error": "Not connected to QuickBooks"}), 401
    
    data = request.get_json()
    customer_name = data.get("customer_name")
    amount = data.get("amount")
    description = data.get("description")
    
    if not all([customer_name, amount, description]):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        # Create invoice in QuickBooks
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
        
        response = requests.post(
            f"{QB_API_URL}/v3/company/{token_data.get('realm_id')}/invoice",
            headers={
                "Authorization": f"Bearer {token_data.get('access_token')}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=invoice_data
        )
        
        if response.status_code in [200, 201]:
            return jsonify({
                "message": "Invoice created successfully",
                "invoice": response.json()
            }), 200
        else:
            return jsonify({
                "error": "Failed to create invoice",
                "details": response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500
