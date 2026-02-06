from flask import Blueprint, request, jsonify
import os
import requests
import qrcode
import io
import base64

email_improved_bp = Blueprint("email_improved_bp", __name__)

def generate_qr_code_base64(data_string):
    """Generate QR code and return as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    
    return img_base64

def send_email_with_generated_qr(to_email, customer_name, qr_code_data):
    """
    Generate QR code on backend and send as attachment via Mailgun
    Returns (success: bool, message: str)
    """
    mailgun_api_key = os.environ.get("MAILGUN_API_KEY")
    mailgun_domain = os.environ.get("MAILGUN_DOMAIN")
    from_email = os.environ.get("FROM_EMAIL", "Doulos Education <noreply@doulos.education>")
    
    if not mailgun_api_key:
        return False, "Mailgun API key not configured"
    
    if not mailgun_domain:
        return False, "Mailgun domain not configured"
    
    try:
        # Point to homepage - student will click "Start Check-In" to scan
        base_url = os.environ.get('BASE_URL', 'https://final-qr-code-version-that-works-production.up.railway.app')
        qr_url = base_url
        
        # Generate QR code with homepage URL
        print(f"[EMAIL] Generating QR code for URL: {qr_url}")
        qr_base64 = generate_qr_code_base64(qr_url)
        print(f"[EMAIL] QR code generated, base64 length: {len(qr_base64)}")
        
        # Mailgun API endpoint
        url = f"https://api.mailgun.net/v3/{mailgun_domain}/messages"
        
        # Plain text content
        text_content = f"""Dear {customer_name},

Thank you for registering with Doulos Education Tutoring Program!

Your registration is complete and your unique QR code is attached to this email.

IMPORTANT: Please save the attached QR code image to your phone or print it out. You will need to show this QR code to check in for each tutoring session.

How to use your QR code:
1. Save the attached image to your phone's photo gallery
2. When arriving for your session, scan the QR code with your phone's camera
3. Your phone will open our check-in website automatically
4. Click "Start Check-In" and scan your QR code again to complete check-in
5. Or print the QR code and scan it at the check-in station

Direct check-in link:
{qr_url}

If you have any questions or need assistance, please do not hesitate to contact us.

Best regards,
The Doulos Education Team

---
This is an automated message. Please do not reply to this email.
"""
        
        # Decode base64 to binary for Mailgun
        qr_image_binary = base64.b64decode(qr_base64)
        
        # Prepare multipart form data for Mailgun
        files = {
            'attachment': (f"{customer_name.replace(' ', '_')}_QRCode.png", qr_image_binary, 'image/png')
        }
        
        data = {
            'from': from_email,
            'to': to_email,
            'subject': 'Your QR Code for Doulos Education Tutoring',
            'text': text_content
        }
        
        print(f"[EMAIL] Sending email to {to_email} via Mailgun...")
        response = requests.post(
            url,
            auth=('api', mailgun_api_key),
            files=files,
            data=data,
            timeout=10
        )
        print(f"[EMAIL] Mailgun response: {response.status_code}")
        
        if response.status_code == 200:
            print(f"[EMAIL] Email sent successfully via Mailgun")
            return True, f"Email sent successfully via Mailgun (status: {response.status_code})"
        else:
            error_msg = f"Mailgun returned status code: {response.status_code} - {response.text}"
            print(f"[EMAIL] ERROR: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        print(f"[EMAIL] EXCEPTION: {error_msg}")
        return False, error_msg

def handle_qr_email_request():
    """Common handler for all QR email routes"""
    data = request.get_json()
    
    # Support multiple field name variations
    recipient_email = data.get("recipient_email") or data.get("email")
    customer_name = data.get("customer_name") or data.get("name")
    qr_code_data = data.get("qr_code_data") or data.get("qrCodeData") or data.get("qr_data")

    print(f"[EMAIL] Request received - To: {recipient_email}, Name: {customer_name}, QR Data: {qr_code_data}")

    if not all([recipient_email, customer_name, qr_code_data]):
        return jsonify({"error": "Missing required email data"}), 400

    # Check if Mailgun is configured
    mailgun_api_key = os.environ.get("MAILGUN_API_KEY")
    
    if not mailgun_api_key:
        return jsonify({"message": "Mailgun not configured", "simulated": True}), 200
    
    # Generate QR code and send email
    success, message = send_email_with_generated_qr(
        recipient_email,
        customer_name,
        qr_code_data
    )
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        return jsonify({"error": message, "simulated": False}), 500

# CREATE ALL POSSIBLE ROUTES - so any frontend call will work!
@email_improved_bp.route("/send-qr", methods=["POST"])
def send_qr_code_email_1():
    """Send QR code email - Route 1"""
    return handle_qr_email_request()

@email_improved_bp.route("/send-qr-email", methods=["POST"])
def send_qr_code_email_2():
    """Send QR code email - Route 2"""
    return handle_qr_email_request()

@email_improved_bp.route("/send-qr-code", methods=["POST"])
def send_qr_code_email_3():
    """Send QR code email - Route 3"""
    return handle_qr_email_request()

@email_improved_bp.route("/send-qr-code-v2", methods=["POST"])
def send_qr_code_email_4():
    """Send QR code email - Route 4"""
    return handle_qr_email_request()

@email_improved_bp.route("/send", methods=["POST"])
def send_qr_code_email_5():
    """Send QR code email - Route 5"""
    return handle_qr_email_request()
