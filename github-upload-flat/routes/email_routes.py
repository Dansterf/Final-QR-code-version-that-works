from flask import Blueprint, request, jsonify
import qrcode
import io
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import os

email_bp = Blueprint('email', __name__, url_prefix='/api/email')

@email_bp.route('/send-qr', methods=['POST'])
def send_qr_email():
    """Send QR code email to customer"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('email') or not data.get('name') or not data.get('qrCodeData'):
            return jsonify({"error": "Email, name, and QR code data are required"}), 400
        
        email = data['email']
        name = data['name']
        qr_code_data = data['qrCodeData']
        
        print(f"[EMAIL] Request received - To: {email}, Name: {name}, QR Data: {qr_code_data}")
        
        # Get the base URL from environment or use default
        base_url = os.environ.get('BASE_URL', 'https://final-qr-code-version-that-works-production.up.railway.app')
        
        # Create full URL for QR code
        qr_url = f"{base_url}/checkin?qr={qr_code_data}"
        
        print(f"[EMAIL] QR URL: {qr_url}")
        
        # Generate QR code with full URL
        print(f"[EMAIL] Generating QR code for: {qr_url}")
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        print(f"[EMAIL] QR code generated, base64 length: {len(qr_base64)}")
        
        # Create email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h1 style="color: #333; text-align: center;">Bienvenue {name}!</h1>
                <p style="color: #666; font-size: 16px; line-height: 1.6;">
                    Merci de vous être enregistré(e). Voici votre QR code personnel pour le check-in.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <img src="cid:qrcode" alt="QR Code" style="max-width: 300px; border: 2px solid #ddd; padding: 10px; background: white; border-radius: 10px;">
                </div>
                <div style="background-color: #e3f2fd; padding: 20px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="color: #1976d2; margin-top: 0;">Comment utiliser votre QR code:</h3>
                    <ol style="color: #666; line-height: 1.8;">
                        <li>Scannez ce QR code avec votre téléphone lors de votre arrivée</li>
                        <li>Ou cliquez sur le lien ci-dessous depuis votre téléphone</li>
                        <li>Votre check-in sera enregistré automatiquement</li>
                    </ol>
                </div>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{qr_url}" style="display: inline-block; background-color: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Check-in Direct
                    </a>
                </div>
                <p style="color: #999; font-size: 12px; text-align: center; margin-top: 30px;">
                    Gardez cet email pour vos prochaines visites.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create SendGrid message
        message = Mail(
            from_email=os.environ.get('SENDGRID_FROM_EMAIL', 'noreply@yourdomain.com'),
            to_emails=email,
            subject=f'Votre QR Code - {name}',
            html_content=html_content
        )
        
        # Attach QR code
        attachment = Attachment(
            FileContent(qr_base64),
            FileName('qrcode.png'),
            FileType('image/png'),
            Disposition('inline'),
            content_id='qrcode'
        )
        message.attachment = attachment
        
        # Send email
        print(f"[EMAIL] Sending email to {email}...")
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        
        print(f"[EMAIL] SendGrid response: {response.status_code}")
        
        if response.status_code in [200, 201, 202]:
            return jsonify({
                "message": "Email sent successfully",
                "qr_url": qr_url
            }), 200
        else:
            return jsonify({"error": "Failed to send email"}), 500
            
    except Exception as e:
        print(f"[EMAIL] Error: {str(e)}")
        return jsonify({"error": str(e)}), 500
