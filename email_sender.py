"""
email_sender.py

Sends premium AI assessment reports via Resend email service.

Sends email with:
- Formatted HTML report
- PDF attachment (optional)
- Branded header with HCI logo
- Call-to-action to view report online

Main entry point: send_report_email(to_email, report_html, pdf_bytes, ...)

Dependencies:
- requests (for Resend API calls)
- RESEND_API_KEY environment variable
"""

import logging
import base64
import requests
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

RESEND_API_ENDPOINT = 'https://api.resend.com/emails'

# Email configuration
FROM_EMAIL = 'reports@updates.humanclarityinstitute.com'
FROM_NAME = 'Human Clarity Institute'

# ============================================================
# EMAIL CONTENT TEMPLATES
# ============================================================

def build_email_html(
    report_name: str,
    demographics: Dict[str, Any],
    session_id: str,
    report_url: str
) -> str:
    """
    Build email HTML wrapper for the report.
    
    Creates branded email with:
    - HCI header
    - Opening message
    - Report link
    - Footer with unsubscribe/settings
    
    Args:
        report_name: Name of recipient or "AI Identity Report"
        demographics: Dict with age_group, country, etc.
        session_id: Session ID for link
        report_url: URL to access report
    
    Returns:
        str: HTML email content
    """
    
    age_group = demographics.get('age_group', '')
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #0066cc; color: white; padding: 20px; text-align: center; border-radius: 4px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ background: #fafafa; padding: 30px; margin: 20px 0; border-radius: 4px; }}
        .content p {{ font-size: 14px; line-height: 1.6; color: #333; margin: 0 0 12px 0; }}
        .cta-button {{ 
            display: inline-block; 
            background: #0066cc; 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 4px; 
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{ font-size: 12px; color: #666; text-align: center; padding: 20px 0; }}
        .footer a {{ color: #0066cc; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Your AI Identity Report is Ready</h1>
        </div>
        
        <div class="content">
            <p>Hi there,</p>
            
            <p>Your comprehensive AI behaviour assessment has been completed and analysed. 
            Your report compares your profile across nine dimensions of AI engagement, 
            benchmarked against 10,500+ participants across 21 research datasets.</p>
            
            <p><strong>What you'll discover:</strong></p>
            <ul style="margin: 12px 0; padding-left: 20px;">
                <li>Your unique AI behaviour pattern</li>
                <li>How typical or distinctive you are</li>
                <li>Key areas worth protecting</li>
                <li>What's likely to shift as AI integration accelerates</li>
                <li>Actionable insights for your AI strategy</li>
            </ul>
            
            <p style="text-align: center; margin: 30px 0;">
                <a href="{report_url}" class="cta-button">
                    View Your Report
                </a>
            </p>
            
            <p><strong>Report Details:</strong></p>
            <ul style="margin: 12px 0; padding-left: 20px; font-size: 13px;">
                <li>Assessment ID: {session_id[:8]}...</li>
                <li>Generated: {datetime.utcnow().strftime('%d %B %Y')}</li>
                <li>Benchmark: 10,500+ Prolific-screened participants</li>
            </ul>
            
            <p>Your report remains accessible online whenever you need to reference it. 
            The link above works from any device.</p>
            
            <p style="font-style: italic; font-size: 13px; color: #666; margin-top: 20px;">
                Questions? Reply to this email or visit 
                <a href="https://humanclarityinstitute.com" style="color: #0066cc;">humanclarityinstitute.com</a>
            </p>
        </div>
        
        <div class="footer">
            <p>
                <a href="https://humanclarityinstitute.com">Human Clarity Institute</a> |
                <a href="https://humanclarityinstitute.com/privacy">Privacy</a> |
                <a href="https://humanclarityinstitute.com/terms">Terms</a>
            </p>
            <p style="margin-top: 10px; color: #999;">
                You received this email because you purchased a premium AI Identity Report.
            </p>
        </div>
    </div>
</body>
</html>
"""


# ============================================================
# ATTACHMENT HANDLING
# ============================================================

def create_pdf_attachment(
    pdf_bytes: bytes,
    filename: str = 'HCI-AI-Identity-Report.pdf'
) -> Dict[str, str]:
    """
    Create PDF attachment for email.
    
    Args:
        pdf_bytes: PDF file as bytes
        filename: Filename for attachment
    
    Returns:
        Dict with content (base64) and filename
    """
    try:
        if not pdf_bytes:
            logger.warning('PDF bytes empty, skipping attachment')
            return None
        
        # Encode as base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        return {
            'filename': filename,
            'content': pdf_base64
        }
    
    except Exception as e:
        logger.error(f'Error creating PDF attachment: {e}')
        return None


# ============================================================
# RESEND API CALL
# ============================================================

def send_via_resend(
    to_email: str,
    subject: str,
    html: str,
    attachment: Optional[Dict[str, str]],
    resend_api_key: str
) -> Dict[str, Any]:
    """
    Send email via Resend API.
    
    Args:
        to_email: Recipient email
        subject: Email subject
        html: Email body (HTML)
        attachment: Optional PDF attachment dict
        resend_api_key: Resend API key
    
    Returns:
        Dict with success status and message_id or error
    """
    
    try:
        # Build request payload
        payload = {
            'from': f'{FROM_NAME} <{FROM_EMAIL}>',
            'to': to_email,
            'subject': subject,
            'html': html
        }
        
        # Add attachment if provided
        if attachment:
            payload['attachments'] = [attachment]
        
        # Set headers
        headers = {
            'Authorization': f'Bearer {resend_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Make request
        logger.info(f'[EMAIL] Sending to {to_email} via Resend...')
        
        response = requests.post(
            RESEND_API_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Handle response
        if response.status_code == 200:
            result = response.json()
            message_id = result.get('id', 'unknown')
            logger.info(f'[EMAIL] ✓ Email sent to {to_email} (ID: {message_id})')
            
            return {
                'success': True,
                'message_id': message_id
            }
        
        else:
            error_text = response.text
            logger.error(f'[EMAIL] Resend API error: {response.status_code} - {error_text}')
            
            return {
                'success': False,
                'error': f'Resend API returned {response.status_code}',
                'details': error_text
            }
    
    except requests.Timeout:
        logger.error(f'[EMAIL] Resend API timeout for {to_email}')
        return {
            'success': False,
            'error': 'Resend API timeout'
        }
    
    except requests.RequestException as e:
        logger.error(f'[EMAIL] Resend API request error: {e}')
        return {
            'success': False,
            'error': f'Request failed: {str(e)}'
        }
    
    except Exception as e:
        logger.error(f'[EMAIL] Unexpected error: {e}')
        return {
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        }


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def send_report_email(
    to_email: str,
    report_html: str,
    demographics: Dict[str, Any],
    resend_api_key: str,
    session_id: str,
    pdf_bytes: Optional[bytes] = None,
    pdf_filename: str = 'HCI-AI-Identity-Report.pdf'
) -> Dict[str, Any]:
    """
    Send premium report email via Resend.
    
    Sends branded email with:
    - HTML email wrapper (header + CTA)
    - Report link (to view online)
    - PDF attachment (optional)
    - Footer with company info
    
    Args:
        to_email (str): Recipient email address
        report_html (str): Complete report HTML from render_report_html()
        demographics (dict): User demographics {age_group, country, ...}
        resend_api_key (str): Resend API key
        session_id (str): Assessment session ID
        pdf_bytes (bytes, optional): PDF binary data for attachment
        pdf_filename (str): Filename for PDF attachment
    
    Returns:
        dict: {
            'success': True/False,
            'message_id': 'msg_...' (if success),
            'error': 'error message' (if failed)
        }
    
    Example:
        >>> result = send_report_email(
        ...     to_email='user@example.com',
        ...     report_html=final_html,
        ...     demographics={'age_group': '25-34'},
        ...     resend_api_key='re_xxx',
        ...     session_id='uuid-123',
        ...     pdf_bytes=pdf_data
        ... )
        >>> if result['success']:
        ...     print(f"Email sent: {result['message_id']}")
    """
    
    try:
        # Validate inputs
        if not to_email:
            logger.error('[EMAIL] No recipient email provided')
            return {'success': False, 'error': 'No recipient email'}
        
        if not resend_api_key:
            logger.error('[EMAIL] RESEND_API_KEY not configured')
            return {'success': False, 'error': 'Resend API key not configured'}
        
        if not report_html:
            logger.error('[EMAIL] Report HTML is empty')
            return {'success': False, 'error': 'Report HTML is empty'}
        
        # Build report URL
        report_url = f'https://humanclarityinstitute.com/ai-assessment/report/?session_id={session_id}'
        
        # Build email HTML wrapper
        email_html = build_email_html(
            report_name='AI Identity Report',
            demographics=demographics,
            session_id=session_id,
            report_url=report_url
        )
        
        # Prepare PDF attachment if provided
        attachment = None
        if pdf_bytes:
            attachment = create_pdf_attachment(pdf_bytes, pdf_filename)
            if attachment:
                logger.info(f'[EMAIL] PDF attachment prepared ({len(pdf_bytes)} bytes)')
            else:
                logger.warning('[EMAIL] PDF attachment creation failed, sending without')
        
        # Send via Resend
        result = send_via_resend(
            to_email=to_email,
            subject='Your AI Identity Report is Ready',
            html=email_html,
            attachment=attachment,
            resend_api_key=resend_api_key
        )
        
        return result
    
    except Exception as e:
        logger.error(f'[EMAIL] send_report_email failed: {e}')
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': f'Email sending failed: {str(e)}'
        }


# ============================================================
# FOR TESTING
# ============================================================

if __name__ == '__main__':
    print('email_sender.py loaded successfully')
    print('Entry point: send_report_email(to_email, report_html, demographics, resend_api_key, session_id)')
    print('\nFunctions:')
    print('  ✓ build_email_html() - Create branded email wrapper')
    print('  ✓ create_pdf_attachment() - Prepare PDF for attachment')
    print('  ✓ send_via_resend() - Call Resend API')
    print('  ✓ send_report_email() - Main function')
    print('\nRequired environment variable:')
    print('  RESEND_API_KEY - API key from resend.com')
    print('\nUsage:')
    print('  result = send_report_email(')
    print('      to_email="user@example.com",')
    print('      report_html=final_html_string,')
    print('      demographics={"age_group": "25-34"},')
    print('      resend_api_key="re_xxx",')
    print('      session_id="uuid-123",')
    print('      pdf_bytes=pdf_binary_data')
    print('  )')
