from flask import Blueprint, request, jsonify
import os
import requests
import json

email_bp = Blueprint("email_bp", __name__)

def send_email_with_sendgrid_http(to_email, subject, html_content):
    """
    Send an email using SendGrid HTTP API (no SDK required)
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
                "type": "text/html",
                "value": html_content
            }]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201, 202]:
            return True, f"Email sent successfully via SendGrid (status: {response.status_code})"
        else:
            return False, f"SendGrid returned status code: {response.status_code} - {response.text}"
            
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def simulate_email(to_email, subject, html_content):
    """Simulate email sending by printing to console"""
    print("=" * 80)
    print("SIMULATED EMAIL")
    print("=" * 80)
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print(f"Content: {html_content[:200]}...")
    print("=" * 80)
    return True, "Email simulated (printed to console)"

@email_bp.route("/send-qr-code", methods=["POST"])
def send_qr_code_email():
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
        # Fallback to simulated email
        success, message = simulate_email(recipient_email, "Your QR Code for Doulos Education", html_content)
        return jsonify({"message": message, "simulated": True}), 200
    
    # Try to send real email via SendGrid HTTP API
    success, message = send_email_with_sendgrid_http(
        recipient_email,
        "Your QR Code for Doulos Education",
        html_content
    )
    
    if success:
        return jsonify({"message": message, "simulated": False}), 200
    else:
        # If SendGrid fails, fall back to simulation
        success, sim_message = simulate_email(recipient_email, "Your QR Code for Doulos Education", html_content)
        return jsonify({
            "message": f"SendGrid failed ({message}), email simulated instead",
            "simulated": True
        }), 200

@email_bp.route("/test", methods=["GET"])
def test_email():
    """Test endpoint to verify email configuration"""
    sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL")
    
    if not sendgrid_api_key:
        return jsonify({
            "configured": False,
            "message": "SendGrid API key not set"
        }), 200
    
    return jsonify({
        "configured": True,
        "from_email": from_email,
        "api_key_present": bool(sendgrid_api_key),
        "api_key_preview": sendgrid_api_key[:10] + "..." if sendgrid_api_key else None
    }), 200
