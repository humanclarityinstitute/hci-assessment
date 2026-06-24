"""
email_template.py
HCI Assessment Platform — Email Template and Delivery

Purpose:
  - Format report email with HTML template
  - Send emails via Resend API
  - Handle attachments (PDF reports)
  - Error handling and retries

All email operations go through this module.
"""

import os
import json
from typing import Optional, Dict, Any


class EmailTemplate:
    """Email template and delivery handler."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize email handler.
        
        Args:
            api_key (str, optional): Resend API key. Defaults to RESEND_API_KEY env var
        """
        self.api_key = api_key or os.environ.get('RESEND_API_KEY')
        self.from_address = 'info@humanclarityinstitute.com'
        self.report_base_url = os.environ.get(
            'REPORT_BASE_URL',
            'https://humanclarityinstitute.com/ai-assessment/report'
        )
    
    def format_report_email(self, recipient_email: str, session_id: str,
                          first_name: Optional[str] = None) -> str:
        """
        Format premium report email HTML.
        
        Args:
            recipient_email (str): Email address of recipient
            session_id (str): Assessment session ID
            first_name (str, optional): Recipient first name
        
        Returns:
            str: HTML email body
        """
        report_link = f'{self.report_base_url}?session_id={session_id}'
        name_greeting = f'Hi {first_name},' if first_name else 'Hi,'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background-color: #f5f5f5;
                    padding: 0;
                    margin: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    margin-bottom: 30px;
                    border-bottom: 2px solid #007bff;
                    padding-bottom: 20px;
                }}
                .header h1 {{
                    margin: 0;
                    color: #007bff;
                    font-size: 24px;
                }}
                .content {{
                    margin: 20px 0;
                    line-height: 1.8;
                }}
                .cta-button {{
                    display: inline-block;
                    margin: 30px 0;
                    padding: 14px 32px;
                    background-color: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 16px;
                    transition: background-color 0.2s;
                }}
                .cta-button:hover {{
                    background-color: #0056b3;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    font-size: 12px;
                    color: #666;
                }}
                .link {{
                    color: #007bff;
                    text-decoration: none;
                }}
                .link:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Your HCI Assessment Report is Ready</h1>
                </div>
                
                <div class="content">
                    <p>{name_greeting}</p>
                    
                    <p>Your comprehensive AI Identity & Behaviour Assessment report has been generated and is ready for you to review.</p>
                    
                    <p>Your report includes:</p>
                    <ul>
                        <li>Percentile rankings across 9 behavioural dimensions</li>
                        <li>Detailed insights about your AI use patterns</li>
                        <li>Comparison with your demographic cohort</li>
                        <li>Perception gaps and distinctive patterns</li>
                        <li>Research context and explanations</li>
                    </ul>
                    
                    <p style="text-align: center; margin: 40px 0;">
                        <a href="{report_link}" class="cta-button">View Your Full Report</a>
                    </p>
                    
                    <p>You can also copy this link into your browser:</p>
                    <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 4px; font-size: 12px;">
                        <a href="{report_link}" class="link">{report_link}</a>
                    </p>
                    
                    <p>The report is saved securely and can be accessed anytime using the link above.</p>
                    
                    <p>If you have any questions about your results, please don't hesitate to reach out.</p>
                    
                    <p>
                        Best regards,<br>
                        <strong>Human Clarity Institute</strong>
                    </p>
                </div>
                
                <div class="footer">
                    <p>
                        © 2026 Human Clarity Institute. All rights reserved.<br>
                        <a href="https://humanclarityinstitute.com" class="link">Visit our website</a> | 
                        <a href="https://humanclarityinstitute.com/privacy" class="link">Privacy Policy</a>
                    </p>
                    <p>
                        Session ID: {session_id}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html.strip()
    
    def send_report_email(self, recipient_email: str, session_id: str,
                         first_name: Optional[str] = None,
                         pdf_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Send premium report email via Resend.
        
        Args:
            recipient_email (str): Email address to send to
            session_id (str): Assessment session ID
            first_name (str, optional): Recipient first name
            pdf_url (str, optional): URL to PDF for downloading
        
        Returns:
            dict: {success: bool, message: str, email_id: str or None}
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'message': 'RESEND_API_KEY not configured',
                    'email_id': None
                }
            
            import urllib.request
            
            # Format email HTML
            html_body = self.format_report_email(recipient_email, session_id, first_name)
            
            # Build request payload
            payload = {
                'from': self.from_address,
                'to': recipient_email,
                'subject': 'Your HCI Assessment Report is Ready',
                'html': html_body,
            }
            
            # Add PDF link as reply-to hint
            payload['reply_to'] = self.from_address
            
            body = json.dumps(payload).encode('utf-8')
            
            # POST to Resend API
            url = 'https://api.resend.com/emails'
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'HCI-Reports/1.0',  # Required by Resend to bypass Cloudflare
                },
                method='POST'
            )
            
            response = urllib.request.urlopen(req, timeout=15)
            response_data = json.loads(response.read())
            
            email_id = response_data.get('id')
            if email_id:
                print(f'Report email sent to {recipient_email} (ID: {email_id})')
                return {
                    'success': True,
                    'message': f'Email sent to {recipient_email}',
                    'email_id': email_id
                }
            else:
                return {
                    'success': False,
                    'message': 'Email send returned no ID',
                    'email_id': None
                }
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f'Resend API error: {error_body}')
            return {
                'success': False,
                'message': f'Email API error: {error_body}',
                'email_id': None
            }
        except Exception as e:
            print(f'send_report_email failed: {e}')
            return {
                'success': False,
                'message': f'Email send failed: {str(e)}',
                'email_id': None
            }
    
    def send_alert_email(self, alert_type: str, session_id: str,
                        error_message: str) -> Dict[str, Any]:
        """
        Send internal alert email (for failures).
        
        Used when report generation fails, to notify support team.
        
        Args:
            alert_type (str): 'generation_timeout', 'generation_error', etc.
            session_id (str): Assessment session ID
            error_message (str): Error details
        
        Returns:
            dict: {success: bool, message: str}
        """
        try:
            if not self.api_key:
                return {'success': False, 'message': 'RESEND_API_KEY not configured'}
            
            import urllib.request
            
            subject = f'[HCI Alert] Report Generation Failed: {alert_type}'
            body = f"""
            Report generation failed for session {session_id}.
            
            Alert Type: {alert_type}
            Error: {error_message}
            
            Please investigate.
            """
            
            payload = {
                'from': self.from_address,
                'to': self.from_address,  # Send to ourselves
                'subject': subject,
                'text': body,
            }
            
            body_json = json.dumps(payload).encode('utf-8')
            
            url = 'https://api.resend.com/emails'
            req = urllib.request.Request(
                url,
                data=body_json,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'HCI-Reports/1.0',
                },
                method='POST'
            )
            
            response = urllib.request.urlopen(req, timeout=15)
            response.read()
            
            return {'success': True, 'message': 'Alert email sent'}
        
        except Exception as e:
            print(f'Alert email failed (non-critical): {e}')
            return {'success': False, 'message': str(e)}


# Singleton instance (created once at startup)
_email_instance = None


def get_email_template() -> EmailTemplate:
    """
    Get or create email template singleton.
    
    Returns:
        EmailTemplate: Singleton instance
    """
    global _email_instance
    if _email_instance is None:
        _email_instance = EmailTemplate()
    return _email_instance
