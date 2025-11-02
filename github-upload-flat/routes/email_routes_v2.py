from flask import Blueprint, request, jsonify
import os
import requests
import json
import base64
import re

email_bp_v2 = Blueprint("email_bp_v2", __name__)

def send_email_with_attachment(to_email, subject, html_content, qr_code_data_url):
    """
    Send an email using SendGrid with QR code as attachment
    Returns (success: bool, message: str)
    """
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@qrcheckin.app")
    
    if not sendgrid_api_key:
        return False, "SendGrid API key not configured"
    
    try:
        # Extract base64 data from data URL
        # Format: data:image/png;base64,iVBORw0KGgoAAAANSUh...
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
        
        # Create HTML content that references the attachment
        html_with_cid = html_content.replace(
            qr_code_data_url,
            "cid:qrcode"  # Reference the attachment by Content-ID
        )
        
        payload = {
            "personalizations": [{
                "to": [{"email": to_email}],
                "subject": subject
            }],
            "from": {"email": from_email},
            "content": [{
                "type": "text/html",
                "value": html_with_cid
            }],
            "attachments": [{
                "content": base64_data,
                "type": f"image/{image_type}",
                "filename": "qr-code.png",
                "disposition": "inline",
                "content_id": "qrcode"
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            return True, f"Email sent successfully via SendGrid (status: {response.status_code})"
        else:
            return False, f"SendGrid returned status code: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

@email_bp_v2.route("/send-qr-code-v2", methods=["POST"])
def send_qr_code_email_v2():
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    customer_name = data.get("customer_name")
    qr_code_url = data.get("qr_code_url")

    if not all([recipient_email, customer_name, qr_code_url]):
        return jsonify({"error": "Missing required email data"}), 400

    # Create HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .qr-code {{ text-align: center; margin: 20px 0; }}
            .qr-code img {{ max-width: 300px; border: 2px solid #ddd; padding: 10px; background: white; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to Doulos Education!</h1>
            </div>
            <div class="content">
                <p>Dear {customer_name},</p>
                <p>Thank you for registering with our tutoring program. We're excited to have you!</p>
                <p>Here is your unique QR code for quick and easy check-ins:</p>
                <div class="qr-code">
                    <img src="{qr_code_url}" alt="Your QR Code" />
                </div>
                <p><strong>Important:</strong> Please save this QR code to your phone or print it out. You will need to show it to check in for tutoring sessions.</p>
                <p>If you have any questions, please don't hesitate to contact us.</p>
                <p>Best regards,<br>The Doulos Education Team</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Check if SendGrid is configured
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    
    if not sendgrid_api_key:
        return jsonify({"message": "SendGrid not configured", "simulated": True}), 200
    
    # Send email with QR code as attachment
    success, message = send_email_with_attachment(
        recipient_email,
        "Your QR Code for Doulos Education",
        html_content,
        qr_code_url
    )
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        return jsonify({"error": message, "simulated": False}), 500

