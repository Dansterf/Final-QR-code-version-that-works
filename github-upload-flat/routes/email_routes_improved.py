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
    Generate QR code on backend and send as attachment
    Returns (success: bool, message: str)
    """
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@qrcheckin.app")
    
    if not sendgrid_api_key:
        return False, "SendGrid API key not configured"
    
    try:
        # Generate QR code on backend
        print(f"[EMAIL] Generating QR code for: {qr_code_data}")
        qr_base64 = generate_qr_code_base64(qr_code_data)
        print(f"[EMAIL] QR code generated, base64 length: {len(qr_base64)}")
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        
        # Plain text content
        text_content = f"""Dear {customer_name},

Thank you for registering with Doulos Education Tutoring Program!

Your registration is complete and your unique QR code is attached to this email.

IMPORTANT: Please save the attached QR code image to your phone or print it out. You will need to show this QR code to check in for each tutoring session.

How to use your QR code:
1. Save the attached image to your phone's photo gallery
2. Show the QR code on your phone screen when checking in
3. Or print the QR code and bring it to each session

If you have any questions or need assistance, please don't hesitate to contact us.

Best regards,
The Doulos Education Team

---
This is an automated message. Please do not reply to this email.
"""
        
        payload = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "subject": "Your QR Code for Doulos Education Tutoring"
            }],
            "from": {"email": from_email},
            "content": [{
                "type": "text/plain",
                "value": text_content
            }],
            "attachments": [{
                "content": qr_base64,
                "type": "image/png",
                "filename": f"{customer_name.replace(' ', '_')}_QRCode.png",
                "disposition": "attachment"
            }]
        }
        
        print(f"[EMAIL] Sending email to {to_email}...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"[EMAIL] SendGrid response: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:
            return True, f"Email sent successfully via SendGrid (status: {response.status_code})"
        else:
            error_msg = f"SendGrid returned status code: {response.status_code} - {response.text}"
            print(f"[EMAIL] ERROR: {error_msg}")
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        print(f"[EMAIL] EXCEPTION: {error_msg}")
        return False, error_msg

@email_improved_bp.route("/send-qr-email", methods=["POST"])
def send_qr_code_email():
    """Send QR code email - backend generates QR code from customer data"""
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    customer_name = data.get("customer_name")
    qr_code_data = data.get("qr_code_data")  # The text data to encode in QR code

    print(f"[EMAIL] Request received - To: {recipient_email}, Name: {customer_name}, QR Data: {qr_code_data}")

    if not all([recipient_email, customer_name, qr_code_data]):
        return jsonify({"error": "Missing required email data"}), 400

    # Check if SendGrid is configured
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        return jsonify({"message": "SendGrid not configured", "simulated": True}), 200
    
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

