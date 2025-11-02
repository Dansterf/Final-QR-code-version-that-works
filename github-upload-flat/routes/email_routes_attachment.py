from flask import Blueprint, request, jsonify
import os
import requests
import re

email_attachment_bp = Blueprint("email_attachment_bp", __name__)

def send_email_with_qr_attachment(to_email, customer_name, qr_code_data_url):
    """
    Send email with QR code as a downloadable attachment (not inline)
    Returns (success: bool, message: str)
    """
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@qrcheckin.app")
    
    if not sendgrid_api_key:
        return False, "SendGrid API key not configured"
    
    try:
        # Extract base64 data from data URL
        match = re.match(r'data:image/(\w+);base64,(.+)', qr_code_data_url)
        if not match:
            return False, "Invalid QR code data URL format"
        
        image_type = match.group(1)  # png, jpeg, etc.
        base64_data = match.group(2)
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {sendgrid_api_key}",
            "Content-Type": "application/json"
        }
        
        # Plain text content (no HTML to avoid Gmail filtering)
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
                "content": base64_data,
                "type": f"image/{image_type}",
                "filename": f"{customer_name.replace(' ', '_')}_QRCode.png",
                "disposition": "attachment"  # Downloadable attachment, not inline
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            return True, f"Email sent successfully via SendGrid (status: {response.status_code})"
        else:
            return False, f"SendGrid returned status code: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

@email_attachment_bp.route("/send-qr-attachment", methods=["POST"])
def send_qr_code_attachment():
    """Send QR code as downloadable attachment"""
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    customer_name = data.get("customer_name")
    qr_code_url = data.get("qr_code_url")
    
    # Log request details
    print(f"[EMAIL] Request received - To: {recipient_email}, Name: {customer_name}")
    print(f"[EMAIL] QR code URL length: {len(qr_code_url) if qr_code_url else 0} characters")
    if qr_code_url:
        print(f"[EMAIL] QR code URL prefix: {qr_code_url[:50]}...")

    if not all([recipient_email, customer_name, qr_code_url]):
        return jsonify({"error": "Missing required email data"}), 400

    # Check if SendGrid is configured
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        return jsonify({"message": "SendGrid not configured", "simulated": True}), 200
    
    # Send email with QR code as downloadable attachment
    success, message = send_email_with_qr_attachment(
        recipient_email,
        customer_name,
        qr_code_url
    )
    
    print(f"[EMAIL] Send result - Success: {success}, Message: {message}")
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        print(f"[EMAIL] ERROR: {message}")
        return jsonify({"error": message, "simulated": False}), 500

