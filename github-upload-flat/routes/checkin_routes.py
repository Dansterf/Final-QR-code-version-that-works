
from flask import Blueprint, request, jsonify
from db import db
from models.models import CheckIn, Customer, SessionType
from datetime import datetime
import requests
import os
from utils.token_storage import load_token_from_file, is_token_valid

checkin_bp = Blueprint("checkin_bp", __name__)

# QuickBooks Configuration
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "sandbox")
if QB_ENVIRONMENT == "production":
    QB_API_URL = "https://quickbooks.api.intuit.com"
else:
    QB_API_URL = "https://sandbox-quickbooks.api.intuit.com"

def create_or_update_monthly_invoice(customer, session_type, checkin_id, checkin_date):
    """Create a new invoice or update existing monthly invoice for a customer"""
    try:
        # Load QuickBooks token
        token_data = load_token_from_file()
        if not token_data or not token_data.get('access_token'):
            print("[QUICKBOOKS] Not connected to QuickBooks - skipping invoice creation")
            return None
        
        if not is_token_valid(token_data):
            print("[QUICKBOOKS] Token expired - skipping invoice creation")
            return None
        
        realm_id = token_data.get('realm_id')
        access_token = token_data.get('access_token')
        
        print(f"[QUICKBOOKS] Processing invoice for customer: {customer.firstName} {customer.lastName}")
        
        # Step 1: Find or create customer in QuickBooks
        customer_ref = find_or_create_qb_customer(customer, access_token, realm_id)
        if not customer_ref:
            print("[QUICKBOOKS] Failed to find/create customer")
            return None
        
        # Step 2: Find or create service item in QuickBooks
        item_ref = find_or_create_qb_item(session_type, access_token, realm_id)
        if not item_ref:
            print("[QUICKBOOKS] Failed to find/create service item")
            return None
        
        # Step 3: Check if there's an existing invoice for this customer in the same month
        existing_invoice = find_monthly_invoice(customer_ref, checkin_date, access_token, realm_id)
        
        if existing_invoice:
            # Update existing invoice by adding a new line
            print(f"[QUICKBOOKS] Found existing invoice for this month: ID {existing_invoice['Id']}")
            updated_invoice_id = add_line_to_invoice(existing_invoice, item_ref, session_type, checkin_id, access_token, realm_id)
            return updated_invoice_id
        else:
            # Create new invoice
            print(f"[QUICKBOOKS] No existing invoice for this month - creating new invoice")
            new_invoice_id = create_new_invoice(customer_ref, item_ref, session_type, checkin_id, checkin_date, access_token, realm_id)
            return new_invoice_id
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error processing invoice: {str(e)}")
        return None

def find_monthly_invoice(customer_ref, checkin_date, access_token, realm_id):
    """Find an existing unpaid invoice for the customer in the same month/year"""
    try:
        # Get the first and last day of the month
        year = checkin_date.year
        month = checkin_date.month
        first_day = f"{year}-{month:02d}-01"
        
        # Calculate last day of month
        if month == 12:
            last_day = f"{year}-12-31"
        else:
            import calendar
            last_day_num = calendar.monthrange(year, month)[1]
            last_day = f"{year}-{month:02d}-{last_day_num:02d}"
        
        # Query for invoices for this customer in this month
        customer_id = customer_ref['value']
        query = f"SELECT * FROM Invoice WHERE CustomerRef = '{customer_id}' AND TxnDate >= '{first_day}' AND TxnDate <= '{last_day}' AND Balance > '0'"
        
        print(f"[QUICKBOOKS] Searching for existing invoice: {query}")
        
        response = requests.get(
            f"{QB_API_URL}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": query}
        )
        
        if response.status_code == 200:
            query_response = response.json().get("QueryResponse", {})
            invoices = query_response.get("Invoice", [])
            
            if invoices:
                # Return the first unpaid invoice found
                invoice = invoices[0]
                print(f"[QUICKBOOKS] ✓ Found existing invoice: ID {invoice['Id']} for {year}-{month:02d}")
                return invoice
        
        print(f"[QUICKBOOKS] No existing invoice found for {year}-{month:02d}")
        return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error finding monthly invoice: {str(e)}")
        return None

def add_line_to_invoice(existing_invoice, item_ref, session_type, checkin_id, access_token, realm_id):
    """Add a new line item to an existing invoice"""
    try:
        invoice_id = existing_invoice['Id']
        sync_token = existing_invoice['SyncToken']
        
        # Get existing lines
        existing_lines = existing_invoice.get('Line', [])
        
        # Create new line
        new_line = {
            "Amount": float(session_type.price),
            "DetailType": "SalesItemLineDetail",
            "SalesItemLineDetail": {
                "ItemRef": item_ref,
                "Qty": 1,
                "UnitPrice": float(session_type.price)
            },
            "Description": f"{session_type.name} - Check-in #{checkin_id}"
        }
        
        # Add new line to existing lines
        updated_lines = existing_lines + [new_line]
        
        # Prepare update payload
        update_data = {
            "Id": invoice_id,
            "SyncToken": sync_token,
            "Line": updated_lines,
            "sparse": True  # Only update specified fields
        }
        
        print(f"[QUICKBOOKS] Adding line to invoice {invoice_id}: {session_type.name} - ${session_type.price}")
        
        response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/invoice",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=update_data
        )
        
        if response.status_code in [200, 201]:
            updated_invoice = response.json().get("Invoice", {})
            print(f"[QUICKBOOKS] ✓ Line added successfully to invoice {invoice_id}")
            return invoice_id
        else:
            print(f"[QUICKBOOKS] Failed to update invoice: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error adding line to invoice: {str(e)}")
        return None

def create_new_invoice(customer_ref, item_ref, session_type, checkin_id, checkin_date, access_token, realm_id):
    """Create a new invoice"""
    try:
        invoice_data = {
            "Line": [{
                "Amount": float(session_type.price),
                "DetailType": "SalesItemLineDetail",
                "SalesItemLineDetail": {
                    "ItemRef": item_ref,
                    "Qty": 1,
                    "UnitPrice": float(session_type.price)
                },
                "Description": f"{session_type.name} - Check-in #{checkin_id}"
            }],
            "CustomerRef": customer_ref,
            "TxnDate": checkin_date.strftime("%Y-%m-%d"),
            "DueDate": checkin_date.strftime("%Y-%m-%d")
        }
        
        print(f"[QUICKBOOKS] Creating new invoice for {checkin_date.strftime('%Y-%m')}")
        
        response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/invoice",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=invoice_data
        )
        
        if response.status_code in [200, 201]:
            invoice = response.json().get("Invoice", {})
            invoice_id = invoice.get("Id")
            print(f"[QUICKBOOKS] ✓ New invoice created successfully! ID: {invoice_id}")
            return invoice_id
        else:
            print(f"[QUICKBOOKS] Failed to create invoice: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error creating invoice: {str(e)}")
        return None

def find_or_create_qb_customer(customer, access_token, realm_id):
    """Find or create a customer in QuickBooks"""
    try:
        # Search for existing customer by display name
        display_name = f"{customer.firstName} {customer.lastName}"
        
        # Query for existing customer
        query = f"SELECT * FROM Customer WHERE DisplayName = '{display_name}'"
        response = requests.get(
            f"{QB_API_URL}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": query}
        )
        
        if response.status_code == 200:
            query_response = response.json().get("QueryResponse", {})
            customers = query_response.get("Customer", [])
            
            if customers:
                # Customer exists
                customer_id = customers[0].get("Id")
                print(f"[QUICKBOOKS] Found existing customer: {display_name} (ID: {customer_id})")
                return {"value": customer_id, "name": display_name}
        
        # Customer doesn't exist, create new one
        print(f"[QUICKBOOKS] Creating new customer: {display_name}")
        customer_data = {
            "DisplayName": display_name,
            "GivenName": customer.firstName,
            "FamilyName": customer.lastName,
            "PrimaryEmailAddr": {
                "Address": customer.email
            }
        }
        
        if customer.phone:
            customer_data["PrimaryPhone"] = {
                "FreeFormNumber": customer.phone
            }
        
        create_response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/customer",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=customer_data
        )
        
        if create_response.status_code in [200, 201]:
            new_customer = create_response.json().get("Customer", {})
            customer_id = new_customer.get("Id")
            print(f"[QUICKBOOKS] ✓ Customer created: {display_name} (ID: {customer_id})")
            return {"value": customer_id, "name": display_name}
        else:
            print(f"[QUICKBOOKS] Failed to create customer: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating customer: {str(e)}")
        return None

def find_or_create_qb_item(session_type, access_token, realm_id):
    """Find or create a service item in QuickBooks"""
    try:
        # Search for existing item by name
        item_name = session_type.name
        
        # Query for existing item
        query = f"SELECT * FROM Item WHERE Name = '{item_name}'"
        response = requests.get(
            f"{QB_API_URL}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": query}
        )
        
        if response.status_code == 200:
            query_response = response.json().get("QueryResponse", {})
            items = query_response.get("Item", [])
            
            if items:
                # Item exists
                item_id = items[0].get("Id")
                print(f"[QUICKBOOKS] Found existing item: {item_name} (ID: {item_id})")
                return {"value": item_id, "name": item_name}
        
        # Item doesn't exist, create new one
        print(f"[QUICKBOOKS] Creating new service item: {item_name}")
        
        # First, get the income account (we'll use the default one)
        account_query = "SELECT * FROM Account WHERE AccountType = 'Income' MAXRESULTS 1"
        account_response = requests.get(
            f"{QB_API_URL}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": account_query}
        )
        
        income_account_id = "1"  # Default
        if account_response.status_code == 200:
            accounts = account_response.json().get("QueryResponse", {}).get("Account", [])
            if accounts:
                income_account_id = accounts[0].get("Id")
        
        item_data = {
            "Name": item_name,
            "Type": "Service",
            "IncomeAccountRef": {
                "value": income_account_id
            },
            "UnitPrice": float(session_type.price)
        }
        
        create_response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/item",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=item_data
        )
        
        if create_response.status_code in [200, 201]:
            new_item = create_response.json().get("Item", {})
            item_id = new_item.get("Id")
            print(f"[QUICKBOOKS] ✓ Service item created: {item_name} (ID: {item_id})")
            return {"value": item_id, "name": item_name}
        else:
            print(f"[QUICKBOOKS] Failed to create item: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating item: {str(e)}")
        return None

@checkin_bp.route("/", methods=["POST"])
def create_checkin():
    data = request.get_json()
    qrCodeValue = data.get("qrCodeValue")
    sessionTypeId = data.get("sessionTypeId")
    notes = data.get("notes")

    if not all([qrCodeValue, sessionTypeId]):
        return jsonify({"error": "Missing required fields"}), 400

    customer = Customer.query.filter_by(qr_code_data=qrCodeValue).first()

    if not customer:
        return jsonify({"error": "Customer not found for this QR code"}), 404

    session_type = SessionType.query.get(sessionTypeId)
    if not session_type:
        return jsonify({"error": "Session type not found"}), 404
    checkin_time = datetime.utcnow()
    new_checkin = CheckIn(
    customer_id=customer.id,
    session_type=session_type.name,
    notes=notes,
    check_in_time=checkin_time
)

    db.session.add(new_checkin)
    db.session.commit()
    
    # Create or update QuickBooks invoice (monthly grouping)
    print(f"[CHECK-IN] Check-in successful for {customer.firstName} {customer.lastName} on {checkin_time.strftime('%Y-%m-%d')}")
    invoice_id = create_or_update_monthly_invoice(customer, session_type, new_checkin.id, checkin_time)
    
    response_data = {
        "message": "Check-in successful",
        "checkin": {
            "id": new_checkin.id,
            "customer_id": new_checkin.customer_id,
            "session_type_id": new_checkin.session_type_id,
            "check_in_time": new_checkin.check_in_time.isoformat(),
            "notes": new_checkin.notes
        }
    }
    
    if invoice_id:
        response_data["quickbooks_invoice_id"] = invoice_id
        response_data["message"] = "Check-in successful and invoice created/updated in QuickBooks"
        print(f"[CHECK-IN] ✓ QuickBooks invoice processed: {invoice_id}")
    else:
        response_data["message"] = "Check-in successful (QuickBooks invoice not created - check connection)"
        print("[CHECK-IN] ⚠ QuickBooks invoice not created")

    return jsonify(response_data), 201

@checkin_bp.route("/", methods=["GET"])
def get_checkins():
    checkins = CheckIn.query.all()
    result = []
    for checkin in checkins:
        customer = Customer.query.get(checkin.customer_id)
        session_type = SessionType.query.get(checkin.session_type_id)
        result.append({
            "id": checkin.id,
            "customerName": f"{customer.firstName} {customer.lastName}" if customer else "Unknown",
            "sessionType": session_type.name if session_type else "Unknown",
            "checkInTime": checkin.check_in_time.isoformat(),
            "notes": checkin.notes,
            "price": session_type.price if session_type else 0.0
        })
    return jsonify(result), 200
@checkin_bp.route("/history", methods=["GET"])
def get_checkin_history():
    """Get check-in history with customer and session details"""
    try:
        checkins = CheckIn.query.order_by(CheckIn.check_in_time.desc()).all()
        result = []
        
        for checkin in checkins:
            customer = Customer.query.get(checkin.customer_id)
            session_type = SessionType.query.get(checkin.session_type_id)
            
            result.append({
                "id": checkin.id,
                "customer_id": checkin.customer_id,
                "customer_name": f"{customer.firstName} {customer.lastName}" if customer else "Unknown",
                "customer_email": customer.email if customer else None,
                "session_type_id": checkin.session_type_id,
                "session_type_name": session_type.name if session_type else "Unknown",
                "price": float(session_type.price) if session_type else 0.0,
                "check_in_time": checkin.check_in_time.isoformat(),
                "notes": checkin.notes
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to get check-in history: {str(e)}")
        return jsonify({"error": "Failed to retrieve check-in history"}), 500
