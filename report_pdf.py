"""
report_pdf.py
HCI Assessment Platform — PDF Generation and Storage

Purpose:
  - Convert HTML reports to PDF via PDFShift API
  - Upload PDFs to Supabase Storage (public bucket)
  - Handle retries and error cases

All PDF operations go through this module.
"""

import os
import json
import time
from typing import Optional, Dict, Any, Tuple


class ReportPDF:
    """PDF generation and storage handler."""
    
    def __init__(self, pdfshift_key: Optional[str] = None):
        """
        Initialize PDF handler.
        
        Args:
            pdfshift_key (str, optional): PDFShift API key. Defaults to PDFSHIFT_API_KEY env var
        """
        self.pdfshift_key = pdfshift_key or os.environ.get('PDFSHIFT_API_KEY')
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = os.environ.get('SUPABASE_KEY')
        self.storage_bucket = os.environ.get('REPORT_PDF_BUCKET', 'reports')
        self.max_retries = 3
        self.retry_delay = 2  # seconds
    
    def build_report_pdf(self, html_content: str, session_id: str) -> Optional[bytes]:
        """
        Convert HTML report to PDF via PDFShift.
        
        Args:
            html_content (str): Full HTML report
            session_id (str): Assessment session ID (for logging)
        
        Returns:
            bytes: PDF content, or None if failed
        """
        if not self.pdfshift_key:
            print('PDFSHIFT_API_KEY not configured — skipping PDF generation')
            return None
        
        try:
            import urllib.request
            import base64
            
            # PDFShift API expects base64-encoded HTML
            html_b64 = base64.b64encode(html_content.encode()).decode()
            
            # Build PDFShift request
            payload = {
                'source': html_b64,
                'filename': f'hci-report-{session_id}.pdf',
                'format': 'A4',
                'margins': {
                    'top': 0.5,
                    'right': 0.5,
                    'bottom': 0.5,
                    'left': 0.5,
                    'unit': 'in'
                },
                'prints_background': True,
            }
            
            body = json.dumps(payload).encode('utf-8')
            
            # POST to PDFShift API with retries
            url = 'https://api.pdfshift.io/v3/convert/html'
            headers = {
                'Authorization': f'Bearer {self.pdfshift_key}',
                'Content-Type': 'application/json',
            }
            
            for attempt in range(self.max_retries):
                try:
                    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
                    response = urllib.request.urlopen(req, timeout=30)
                    pdf_bytes = response.read()
                    
                    if pdf_bytes:
                        print(f'PDF generated for session {session_id} ({len(pdf_bytes)} bytes)')
                        return pdf_bytes
                
                except urllib.error.HTTPError as e:
                    if e.code >= 500:  # Server error, retry
                        if attempt < self.max_retries - 1:
                            print(f'PDFShift server error (attempt {attempt + 1}/{self.max_retries}), retrying...')
                            time.sleep(self.retry_delay)
                            continue
                    raise
            
            return None
        
        except Exception as e:
            print(f'PDF generation failed: {e}')
            return None
    
    def upload_to_supabase(self, pdf_bytes: bytes, session_id: str) -> Optional[str]:
        """
        Upload PDF to Supabase Storage bucket.
        
        Args:
            pdf_bytes (bytes): PDF content
            session_id (str): Assessment session ID
        
        Returns:
            str: Public URL to PDF, or None if failed
        """
        if not self.supabase_url or not self.supabase_key:
            print('Supabase credentials not configured — cannot upload PDF')
            return None
        
        if not pdf_bytes:
            print('No PDF bytes provided')
            return None
        
        try:
            import urllib.request
            import base64
            
            # Upload to Supabase Storage
            file_path = f'{session_id}.pdf'
            url = f'{self.supabase_url}/storage/v1/object/{self.storage_bucket}/{file_path}'
            
            # Supabase Storage expects file content directly (not JSON)
            req = urllib.request.Request(
                url,
                data=pdf_bytes,
                headers={
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Content-Type': 'application/pdf',
                },
                method='POST'
            )
            
            response = urllib.request.urlopen(req, timeout=30)
            response_data = json.loads(response.read())
            
            if 'name' in response_data:
                # Build public URL (Supabase Storage public bucket)
                public_url = f'{self.supabase_url}/storage/v1/object/public/{self.storage_bucket}/{file_path}'
                print(f'PDF uploaded for session {session_id}: {public_url}')
                return public_url
            else:
                print(f'Upload response missing name field: {response_data}')
                return None
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f'Supabase upload failed: {error_body}')
            return None
        except Exception as e:
            print(f'PDF upload failed: {e}')
            return None
    
    def generate_and_upload(self, html_content: str, session_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate PDF and upload in one operation.
        
        Args:
            html_content (str): Full HTML report
            session_id (str): Assessment session ID
        
        Returns:
            tuple: (pdf_bytes, public_url) — either or both can be None
        """
        try:
            # Generate PDF
            pdf_bytes = self.build_report_pdf(html_content, session_id)
            if not pdf_bytes:
                return None, None
            
            # Upload to Supabase
            pdf_url = self.upload_to_supabase(pdf_bytes, session_id)
            
            return pdf_bytes, pdf_url
        
        except Exception as e:
            print(f'PDF generation and upload failed: {e}')
            return None, None


# Singleton instance (created once at startup)
_pdf_instance = None


def get_report_pdf() -> ReportPDF:
    """
    Get or create PDF handler singleton.
    
    Returns:
        ReportPDF: Singleton instance
    """
    global _pdf_instance
    if _pdf_instance is None:
        _pdf_instance = ReportPDF()
    return _pdf_instance
