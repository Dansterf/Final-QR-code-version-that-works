from flask import Blueprint, request, jsonify
import os
import requests

email_simple_bp = Blueprint("email_simple_bp", __name__)

def send_simple_text_email(to_email, subject, text_content):
    """
    Send a simple plain text email (no HTML, no attachments)
    Returns (success: bool, message: str)
    """
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@qrcheckin.app")
    
    if not sendgrid_api_key:
        return False, "SendGrid API key not configured"
    
    try:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "subject": subject
            }],
            "from": {"email": from_email},
            "content": [{
                "type": "text/plain",
                "value": text_content
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            return True, f"Email sent successfully via SendGrid (status: {response.status_code})"
        else:
            return False, f"SendGrid returned status code: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

@email_simple_bp.route("/send-simple-test", methods=["POST"])
def send_simple_test_email():
    """Send a simple plain text test email"""
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    customer_name = data.get("customer_name", "Customer")

    if not recipient_email:
        return jsonify({"error": "Missing recipient email"}), 400

    text_content = f"""
Hello {customer_name},

This is a test email from Doulos Education QR Check-In System.

If you receive this email, it means plain text emails are working correctly.

Your QR code has been generated and is available in the system.
Please log in to download your QR code, or contact us for assistance.

Best regards,
The Doulos Education Team

---
This is an automated message from the QR Check-In System.
    """

    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        return jsonify({"message": "SendGrid not configured", "simulated": True}), 200
    
    success, message = send_simple_text_email(
        recipient_email,
        "Test Email from Doulos Education",
        text_content
    )
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        return jsonify({"error": message, "simulated": False}), 500

@email_simple_bp.route("/send-qr-link", methods=["POST"])
def send_qr_link_email():
    """Send email with link to view QR code (no attachment)"""
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    customer_name = data.get("customer_name")
    customer_id = data.get("customer_id")
    qr_code_data = data.get("qr_code_data")

    if not all([recipient_email, customer_name, customer_id]):
        return jsonify({"error": "Missing required data"}), 400

    text_content = f"""
Dear {customer_name},

Thank you for registering with Doulos Education Tutoring Program!

Your registration is complete and your unique QR code has been generated.

QR Code ID: {qr_code_data}

To access your QR code:
1. Visit the check-in system
2. Your QR code is saved in your account
3. You can download it anytime

For check-in, please show this QR code at each tutoring session.

If you have any questions, please contact us.

Best regards,
The Doulos Education Team

---
This is an automated message. Please do not reply to this email.
    """

    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        return jsonify({"message": "SendGrid not configured", "simulated": True}), 200
    
    success, message = send_simple_text_email(
        recipient_email,
        "Your Doulos Education Registration Confirmation",
        text_content
    )
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        return jsonify({"error": message, "simulated": False}), 500

