from flask import Blueprint, request, jsonify
from db import db
from models.models import CheckIn, Customer, SessionType
from datetime import datetime
import requests
import os
import re
from utils.token_storage import load_token_from_file, is_token_valid, get_valid_token
from urllib.parse import urlparse, parse_qs

checkin_bp = Blueprint("checkin_bp", __name__)

# QuickBooks Configuration
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT", "sandbox")
if QB_ENVIRONMENT == "production":
    QB_API_URL = "https://quickbooks.api.intuit.com"
else:
    QB_API_URL = "https://sandbox-quickbooks.api.intuit.com"

def extract_qr_code_from_value(qr_value):
    """
    Extract the actual QR code UUID from various possible formats
    
    Handles:
    1. Direct UUID: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    2. URL with qr parameter: "https://domain.com/checkin?qr=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    3. Just the qr parameter: "qr=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    
    Returns:
        str: The extracted UUID
    """
    if not qr_value:
        return None
    
    # If it's already a clean UUID (no URL parts), return as-is
    if '://' not in qr_value and '=' not in qr_value:
        print(f"[QR_EXTRACT] Direct UUID detected: {qr_value}")
        return qr_value
    
    # If it contains a URL, parse it
    if '://' in qr_value:
        try:
            parsed = urlparse(qr_value)
            query_params = parse_qs(parsed.query)
            
            if 'qr' in query_params:
                extracted = query_params['qr'][0]
                print(f"[QR_EXTRACT] Extracted from URL: {qr_value} → {extracted}")
                return extracted
        except Exception as e:
            print(f"[QR_EXTRACT] Error parsing URL: {str(e)}")
    
    # If it's in format "qr=value"
    if '=' in qr_value and 'qr=' in qr_value:
        try:
            extracted = qr_value.split('qr=')[1].split('&')[0]
            print(f"[QR_EXTRACT] Extracted from parameter: {qr_value} → {extracted}")
            return extracted
        except Exception as e:
            print(f"[QR_EXTRACT] Error parsing parameter: {str(e)}")
    
    # Fallback: return original value
    print(f"[QR_EXTRACT] No extraction needed, using original: {qr_value}")
    return qr_value

def get_next_invoice_number(access_token, realm_id):
    """
    Get the next available invoice number from QuickBooks
    
    ✅ NOUVEAU: Génère automatiquement un numéro de facture unique
    
    Strategy:
    1. Query the most recent invoice to get the last DocNumber
    2. If numeric, increment by 1
    3. If not found or not numeric, generate based on date/time
    
    Returns:
        str: Next invoice number (e.g., "1001" or "INV-1001" or "20260214-001")
    """
    try:
        # Query for the most recent invoice
        query = "SELECT * FROM Invoice ORDERBY DocNumber DESC MAXRESULTS 1"
        
        print(f"[INVOICE_NUMBER] Querying QuickBooks for last invoice number...")
        
        response = requests.get(
            f"{QB_API_URL}/v3/company/{realm_id}/query",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            },
            params={"query": query}
        )
        
        if response.status_code == 200:
            query_response = response.json().get('QueryResponse', {})
            invoices = query_response.get('Invoice', [])
            
            if invoices and len(invoices) > 0:
                last_doc_number = invoices[0].get('DocNumber')
                print(f"[INVOICE_NUMBER] Last invoice number found: {last_doc_number}")
                
                # Try to extract numeric part and increment
                if last_doc_number:
                    # Format 1: Pure number (e.g., "1001")
                    if last_doc_number.isdigit():
                        next_number = int(last_doc_number) + 1
                        print(f"[INVOICE_NUMBER] Generated next number: {next_number}")
                        return str(next_number)
                    
                    # Format 2: Prefix with dash (e.g., "INV-1001")
                    if '-' in last_doc_number:
                        parts = last_doc_number.split('-')
                        if len(parts) >= 2 and parts[-1].isdigit():
                            prefix = '-'.join(parts[:-1])
                            next_number = int(parts[-1]) + 1
                            result = f"{prefix}-{next_number}"
                            print(f"[INVOICE_NUMBER] Generated next number: {result}")
                            return result
                    
                    # Format 3: Try to find any number at the end
                    match = re.search(r'(\d+)$', last_doc_number)
                    if match:
                        number_part = match.group(1)
                        prefix = last_doc_number[:match.start()]
                        next_number = int(number_part) + 1
                        # Preserve leading zeros
                        formatted_number = str(next_number).zfill(len(number_part))
                        result = f"{prefix}{formatted_number}"
                        print(f"[INVOICE_NUMBER] Generated next number: {result}")
                        return result
        
        # Fallback: Generate based on date/time
        now = datetime.now()
        date_prefix = now.strftime("%Y%m%d")
        time_suffix = now.strftime("%H%M%S")
        invoice_number = f"{date_prefix}-{time_suffix}"
        print(f"[INVOICE_NUMBER] Generated fallback number: {invoice_number}")
        return invoice_number
        
    except Exception as e:
        print(f"[INVOICE_NUMBER] Error getting next invoice number: {str(e)}")
        # Fallback: Generate based on timestamp
        now = datetime.now()
        invoice_number = now.strftime("%Y%m%d-%H%M%S")
        print(f"[INVOICE_NUMBER] Using timestamp fallback: {invoice_number}")
        return invoice_number

def create_or_update_monthly_invoice(customer, session_type, checkin_id, checkin_date):
    """Create a new invoice or update existing monthly invoice for a customer"""
    try:
        # ✅ FIXED: Use get_valid_token() which automatically refreshes if expired
        # This replaces the old pattern of load_token_from_file() + is_token_valid()
        # which would skip invoice creation instead of retrying after refresh
        token_data = get_valid_token()
        if not token_data or not token_data.get('access_token'):
            print("[QUICKBOOKS] Not connected to QuickBooks or unable to refresh token - skipping invoice creation")
            return None
        
        realm_id = token_data.get('realm_id')
        access_token = token_data.get('access_token')
        
        print(f"[QUICKBOOKS] Token valid, proceeding with invoice creation...")
        
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
    """
    Create a new invoice
    
    ✅ NOUVEAU: Génère automatiquement un numéro de facture unique
    """
    try:
        # ✅ NOUVEAU: Générer le numéro de facture automatiquement
        invoice_number = get_next_invoice_number(access_token, realm_id)
        print(f"[QUICKBOOKS] Creating invoice with DocNumber: {invoice_number}")
        
        invoice_data = {
            "DocNumber": invoice_number,  # ✅ AJOUTÉ: Numéro de facture automatique
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
            doc_number = invoice.get("DocNumber", invoice_number)
            print(f"[QUICKBOOKS] ✓ New invoice created successfully! ID: {invoice_id}, DocNumber: {doc_number}")
            return invoice_id
        else:
            print(f"[QUICKBOOKS] Failed to create invoice: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error creating invoice: {str(e)}")
        return None

def find_or_create_qb_customer(customer, access_token, realm_id):
    """Find existing customer in QuickBooks or create new one"""
    try:
        # Search for existing customer by display name
        customer_name = f"{customer.firstName} {customer.lastName}"
        query = f"SELECT * FROM Customer WHERE DisplayName = '{customer_name}'"
        
        print(f"[QUICKBOOKS] Searching for customer: {customer_name}")
        
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
                customer_id = customers[0].get("Id")
                print(f"[QUICKBOOKS] Found existing customer: {customer_name} (ID: {customer_id})")
                return {"value": customer_id, "name": customer_name}
        
        # Customer not found, create new one
        print(f"[QUICKBOOKS] Customer not found, creating new: {customer_name}")
        
        customer_data = {
            "DisplayName": customer_name,
            "GivenName": customer.firstName,
            "FamilyName": customer.lastName,
            "PrimaryEmailAddr": {"Address": customer.email} if customer.email else None,
            "PrimaryPhone": {"FreeFormNumber": customer.phone} if customer.phone else None
        }
        
        # Remove None values
        customer_data = {k: v for k, v in customer_data.items() if v is not None}
        
        response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/customer",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=customer_data
        )
        
        if response.status_code in [200, 201]:
            new_customer = response.json().get("Customer", {})
            customer_id = new_customer.get("Id")
            print(f"[QUICKBOOKS] ✓ Customer created: {customer_name} (ID: {customer_id})")
            return {"value": customer_id, "name": customer_name}
        else:
            print(f"[QUICKBOOKS] Failed to create customer: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating customer: {str(e)}")
        return None

def find_or_create_qb_item(session_type, access_token, realm_id):
    """Find existing service item in QuickBooks or create new one"""
    try:
        # Search for existing item by name
        item_name = session_type.name
        query = f"SELECT * FROM Item WHERE Name = '{item_name}'"
        
        print(f"[QUICKBOOKS] Searching for item: {item_name}")
        
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
                item_id = items[0].get("Id")
                print(f"[QUICKBOOKS] Found existing item: {item_name} (ID: {item_id})")
                return {"value": item_id, "name": item_name}
        
        # Item not found, create new one
        print(f"[QUICKBOOKS] Item not found, creating new: {item_name}")
        
        item_data = {
            "Name": item_name,
            "Type": "Service",
            "IncomeAccountRef": {
                "value": "1"  # Default income account - should be configured
            },
            "UnitPrice": float(session_type.price)
        }
        
        response = requests.post(
            f"{QB_API_URL}/v3/company/{realm_id}/item",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json=item_data
        )
        
        if response.status_code in [200, 201]:
            new_item = response.json().get("Item", {})
            item_id = new_item.get("Id")
            print(f"[QUICKBOOKS] ✓ Item created: {item_name} (ID: {item_id})")
            return {"value": item_id, "name": item_name}
        else:
            print(f"[QUICKBOOKS] Failed to create item: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating item: {str(e)}")
        return None

@checkin_bp.route("/", methods=["GET"])
def get_checkins():
    """Get all check-ins with customer and session type details"""
    try:
        # Get query parameters for filtering
        customer_id = request.args.get("customer_id")
        session_type_id = request.args.get("session_type_id")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        # Build query
        query = CheckIn.query
        
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        
        if session_type_id:
            # session_type is stored as string name, need to get the name from ID
            st = SessionType.query.get(session_type_id)
            if st:
                query = query.filter_by(session_type=st.name)
        
        if start_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(CheckIn.check_in_time >= start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.strptime(end_date, "%Y-%m-%d")
                query = query.filter(CheckIn.check_in_time <= end)
            except ValueError:
                pass
        
        # Order by most recent first
        checkins = query.order_by(CheckIn.check_in_time.desc()).all()
        
        # Format response
        result = []
        for checkin in checkins:
            customer = Customer.query.get(checkin.customer_id)
            
            # Find the session type to get the price
            session_type = SessionType.query.filter_by(name=checkin.session_type).first()
            price = session_type.price if session_type else 0.0
            
            result.append({
                "id": checkin.id,
                "customer_id": checkin.customer_id,
                "customer_name": f"{customer.firstName} {customer.lastName}" if customer else "Unknown",
                "session_type": checkin.session_type,  # session_type is stored as string
                "checkin_date": checkin.check_in_time.isoformat(),
                "notes": checkin.notes,
                "qb_invoice_id": checkin.qb_invoice_id,
                "price": float(price)  # Add price for frontend display
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@checkin_bp.route("/", methods=["POST"])
def create_checkin():
    """
    Create a check-in for a customer
    
    ✅ FIXED: Now extracts QR code UUID from URL if needed
    """
    data = request.get_json()
    qrCodeValue = data.get("qrCodeValue")
    sessionTypeId = data.get("sessionTypeId")
    notes = data.get("notes")

    if not all([qrCodeValue, sessionTypeId]):
        return jsonify({"error": "Missing required fields"}), 400

    # ✅ NOUVEAU: Extract the actual UUID from the QR code value
    # Handles both direct UUID and URL formats
    extracted_qr_code = extract_qr_code_from_value(qrCodeValue)
    
    print(f"[CHECK-IN] Original QR value: {qrCodeValue}")
    print(f"[CHECK-IN] Extracted QR code: {extracted_qr_code}")

    # Look up customer using the extracted QR code
    customer = Customer.query.filter_by(qr_code_data=extracted_qr_code).first()
    
    if not customer:
        print(f"[CHECK-IN] ✗ Customer not found with QR code: {extracted_qr_code}")
        print(f"[CHECK-IN] ✗ Original value was: {qrCodeValue}")
        return jsonify({
            "error": "Customer not found with this QR code",
            "qr_value_received": qrCodeValue,
            "qr_value_searched": extracted_qr_code
        }), 404

    print(f"[CHECK-IN] ✓ Customer found: {customer.firstName} {customer.lastName} (ID: {customer.id})")
    
    session_type = SessionType.query.get(sessionTypeId)
    if not session_type:
        return jsonify({"error": "Session type not found"}), 404

    # Create check-in
    checkin = CheckIn(
        customer_id=customer.id,
        session_type=session_type.name,  # Store session type name, not ID
        check_in_time=datetime.now(),
        notes=notes
    )
    
    db.session.add(checkin)
    db.session.commit()
    
    print(f"[CHECK-IN] Check-in successful for {customer.firstName} {customer.lastName} on {checkin.check_in_time.strftime('%Y-%m-%d')}")
    
    # Create or update QuickBooks invoice
    invoice_id = create_or_update_monthly_invoice(customer, session_type, checkin.id, checkin.check_in_time)
    
    if invoice_id:
        print(f"[CHECK-IN] ✓ QuickBooks invoice processed: {invoice_id}")
    else:
        print(f"[CHECK-IN] ⚠ QuickBooks invoice not created (may not be connected)")

    return jsonify({
        "message": "Check-in successful",
        "checkin": {
            "id": checkin.id,
            "customer_name": f"{customer.firstName} {customer.lastName}",
            "session_type": session_type.name,
            "checkin_date": checkin.check_in_time.isoformat(),
            "notes": checkin.notes,
            "quickbooks_invoice_id": invoice_id
        }
    }), 201
