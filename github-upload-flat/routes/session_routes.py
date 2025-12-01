from flask import Blueprint, request, jsonify
from db import db
from models.models import Customer, CheckIn, SessionType
from datetime import datetime
import requests
import os
from utils.token_storage import load_token_from_file, is_token_valid

session_bp = Blueprint('sessions', __name__)

@session_bp.route('/api/sessions/manual', methods=['POST'])
def create_manual_session():
    """Create a manual session entry for remote customers"""
    try:
        data = request.json
        customer_id = data.get('customer_id')
        service_id = data.get('service_id')
        session_date = data.get('session_date')  # Format: YYYY-MM-DD
        notes = data.get('notes', '')

        # Validate required fields
        if not customer_id or not service_id or not session_date:
            return jsonify({'error': 'Missing required fields'}), 400

        # Get customer
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # Get service
        service = SessionType.query.get(service_id)
        if not service:
            return jsonify({'error': 'Service not found'}), 404

        # Parse session date
        try:
            session_datetime = datetime.strptime(session_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        # Create check-in record
        check_in = CheckIn(
            customer_id=customer_id,
            check_in_time=session_datetime,
            session_type=service.name,
            notes=notes,
            is_manual=True
        )
        
        db.session.add(check_in)
        db.session.commit()

        print(f"[MANUAL SESSION] Created for {customer.firstName} {customer.lastName} - {service.name}")

        # Try to create QuickBooks invoice
        qb_invoice_id = None
        try:
            qb_invoice_id = create_or_update_quickbooks_invoice(customer, service, session_datetime, check_in.id)
            if qb_invoice_id:
                check_in.qb_invoice_id = qb_invoice_id
                db.session.commit()
                print(f"[MANUAL SESSION] ✓ QuickBooks invoice created/updated: {qb_invoice_id}")
        except Exception as qb_error:
            print(f"[MANUAL SESSION] ⚠ QuickBooks invoice creation failed: {str(qb_error)}")

        return jsonify({
            'success': True,
            'check_in_id': check_in.id,
            'qb_invoice_id': qb_invoice_id,
            'message': 'Session enregistrée avec succès'
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"[MANUAL SESSION] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


def create_or_update_quickbooks_invoice(customer, service, session_date, check_in_id):
    """Create or update QuickBooks invoice for the session"""
    
    # Load QuickBooks token
    token_data = load_token_from_file()
    if not token_data or not is_token_valid(token_data):
        print("[QUICKBOOKS] Not connected to QuickBooks - skipping invoice creation")
        return None

    access_token = token_data.get('access_token')
    realm_id = token_data.get('realm_id')

    # Get month/year for invoice grouping
    invoice_month = session_date.strftime('%Y-%m')
    
    # Search for existing invoice for this customer in this month
    existing_invoice = search_monthly_invoice(access_token, realm_id, customer, invoice_month)
    
    if existing_invoice:
        # Add line to existing invoice
        return add_line_to_invoice(access_token, realm_id, existing_invoice, service, session_date, check_in_id)
    else:
        # Create new invoice
        return create_new_invoice(access_token, realm_id, customer, service, session_date, check_in_id)


def search_monthly_invoice(access_token, realm_id, customer, invoice_month):
    """Search for an existing invoice for this customer in this month"""
    try:
        # First, find or create the customer in QuickBooks
        qb_customer_id = find_or_create_qb_customer(access_token, realm_id, customer)
        if not qb_customer_id:
            return None

        # Search for invoices for this customer
        query = f"SELECT * FROM Invoice WHERE CustomerRef = '{qb_customer_id}' MAXRESULTS 100"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
        response = requests.get(url, headers=headers, params={"query": query})
        
        if response.status_code == 200:
            data = response.json()
            invoices = data.get("QueryResponse", {}).get("Invoice", [])
            
            # Filter invoices by month and unpaid status
            for invoice in invoices:
                invoice_date = invoice.get("TxnDate", "")
                if invoice_date.startswith(invoice_month):
                    balance = float(invoice.get("Balance", 0))
                    if balance > 0:  # Invoice not fully paid
                        print(f"[QUICKBOOKS] ✓ Found existing invoice: ID {invoice['Id']} for {invoice_month}")
                        return invoice
        
        print(f"[QUICKBOOKS] No existing invoice found for {invoice_month}")
        return None
        
    except Exception as e:
        print(f"[QUICKBOOKS] Error searching for invoice: {str(e)}")
        return None


def add_line_to_invoice(access_token, realm_id, invoice, service, session_date, check_in_id):
    """Add a new line to an existing invoice"""
    try:
        invoice_id = invoice['Id']
        sync_token = invoice['SyncToken']
        
        # Find or create the service item in QuickBooks
        qb_item_id = find_or_create_qb_item(access_token, realm_id, service)
        if not qb_item_id:
            print("[QUICKBOOKS] Failed to find/create item")
            return None

        # Prepare new line
        new_line = {
            "DetailType": "SalesItemLineDetail",
            "Amount": service.price,
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": qb_item_id
                },
                "UnitPrice": service.price,
                "Qty": 1
            },
            "Description": f"{service.name} - Check-in #{check_in_id} ({session_date.strftime('%Y-%m-%d')})"
        }

        # Add new line to existing lines
        existing_lines = invoice.get("Line", [])
        # Filter out subtotal lines
        item_lines = [line for line in existing_lines if line.get("DetailType") == "SalesItemLineDetail"]
        item_lines.append(new_line)
        
        # Add subtotal line
        item_lines.append({
            "DetailType": "SubTotalLineDetail",
            "Amount": sum(float(line.get("Amount", 0)) for line in item_lines),
            "SubTotalLineDetail": {}
        })

        # Update invoice
        update_data = {
            "Id": invoice_id,
            "SyncToken": sync_token,
            "Line": item_lines,
            "sparse": True
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/invoice?minorversion=65"
        response = requests.post(url, headers=headers, json=update_data)

        if response.status_code == 200:
            updated_invoice = response.json().get("Invoice", {})
            print(f"[QUICKBOOKS] ✓ Line added successfully to invoice {invoice_id}")
            return invoice_id
        else:
            print(f"[QUICKBOOKS] Error adding line: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"[QUICKBOOKS] Error adding line to invoice: {str(e)}")
        return None


def create_new_invoice(access_token, realm_id, customer, service, session_date, check_in_id):
    """Create a new QuickBooks invoice"""
    try:
        # Find or create customer
        qb_customer_id = find_or_create_qb_customer(access_token, realm_id, customer)
        if not qb_customer_id:
            return None

        # Find or create item
        qb_item_id = find_or_create_qb_item(access_token, realm_id, service)
        if not qb_item_id:
            return None

        # Create invoice
        invoice_data = {
            "CustomerRef": {
                "value": qb_customer_id
            },
            "TxnDate": session_date.strftime('%Y-%m-%d'),
            "Line": [
                {
                    "DetailType": "SalesItemLineDetail",
                    "Amount": service.price,
                    "SalesItemLineDetail": {
                        "ItemRef": {
                            "value": qb_item_id
                        },
                        "UnitPrice": service.price,
                        "Qty": 1
                    },
                    "Description": f"{service.name} - Check-in #{check_in_id}"
                }
            ]
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/invoice?minorversion=65"
        response = requests.post(url, headers=headers, json=invoice_data)

        if response.status_code == 200:
            invoice = response.json().get("Invoice", {})
            invoice_id = invoice.get("Id")
            print(f"[QUICKBOOKS] ✓ New invoice created successfully! ID: {invoice_id}")
            return invoice_id
        else:
            print(f"[QUICKBOOKS] Error creating invoice: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"[QUICKBOOKS] Error creating invoice: {str(e)}")
        return None


def find_or_create_qb_customer(access_token, realm_id, customer):
    """Find or create customer in QuickBooks"""
    try:
        # Search for existing customer
        query = f"SELECT * FROM Customer WHERE DisplayName = '{customer.firstName} {customer.lastName}'"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
        response = requests.get(url, headers=headers, params={"query": query})
        
        if response.status_code == 200:
            data = response.json()
            customers = data.get("QueryResponse", {}).get("Customer", [])
            if customers:
                return customers[0]["Id"]

        # Create new customer
        customer_data = {
            "DisplayName": f"{customer.firstName} {customer.lastName}",
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

        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/customer?minorversion=65"
        response = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=customer_data)

        if response.status_code == 200:
            new_customer = response.json().get("Customer", {})
            return new_customer.get("Id")

        return None

    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating customer: {str(e)}")
        return None


def find_or_create_qb_item(access_token, realm_id, service):
    """Find or create service item in QuickBooks"""
    try:
        # Search for existing item
        query = f"SELECT * FROM Item WHERE Name = '{service.name}'"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/query"
        response = requests.get(url, headers=headers, params={"query": query})
        
        if response.status_code == 200:
            data = response.json()
            items = data.get("QueryResponse", {}).get("Item", [])
            if items:
                return items[0]["Id"]

        # Create new item
        item_data = {
            "Name": service.name,
            "Type": "Service",
            "IncomeAccountRef": {
                "value": "1"  # Default income account
            },
            "UnitPrice": service.price
        }

        url = f"https://quickbooks.api.intuit.com/v3/company/{realm_id}/item?minorversion=65"
        response = requests.post(url, headers={**headers, "Content-Type": "application/json"}, json=item_data)

        if response.status_code == 200:
            new_item = response.json().get("Item", {})
            return new_item.get("Id")

        return None

    except Exception as e:
        print(f"[QUICKBOOKS] Error finding/creating item: {str(e)}")
        return None
