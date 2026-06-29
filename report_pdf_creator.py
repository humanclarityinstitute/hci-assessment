"""
report_pdf_creator.py

Converts premium report HTML to PDF using PDFShift API.

Takes the rendered HTML report (with data injected) and converts to PDF for:
- Email attachment
- Download link
- Archival

Main entry point: build_report_pdf(rendering_dict, demographics)

Dependencies:
- requests (for PDFShift API calls)
- PDFSHIFT_API_KEY environment variable

Note: PDFShift requires raw HTML (not base64-encoded) for rendering accuracy.
      Wait-for-JS option ensures charts and distributions render correctly.
"""

import logging
import os
import requests
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

PDFSHIFT_API_ENDPOINT = 'https://api.pdfshift.io/v3/convert/html'

# PDFShift configuration
PDFSHIFT_TIMEOUT = 120  # 2 minutes
PDFSHIFT_RETRY_COUNT = 2
PDFSHIFT_RETRY_DELAY = 2  # seconds

# ============================================================
# PDF GENERATION
# ============================================================

def build_report_pdf(
    rendering_dict: Dict[str, Any],
    demographics: Optional[Dict[str, Any]] = None,
    pdfshift_api_key: Optional[str] = None
) -> Optional[bytes]:
    """
    Convert report HTML to PDF using PDFShift API.
    
    Process:
    1. Render report HTML with data injection (from render_report_html)
    2. Send to PDFShift API with wait-for-JS enabled
    3. Return PDF bytes
    
    Args:
        rendering_dict (dict): Output from report_page_builder.build_report_html()
                              (or final HTML string with data injection)
        demographics (dict, optional): User demographics (used for metadata)
        pdfshift_api_key (str, optional): PDFShift API key (uses env var if not provided)
    
    Returns:
        bytes: PDF binary data, or None if conversion failed
    
    Note:
        - rendering_dict should be the final HTML (already has data injected)
        - If rendering_dict is a dict, will fail (expects HTML string)
        - PDFShift renders JavaScript, so charts/distributions will render
    """
    
    try:
        # Get API key
        if not pdfshift_api_key:
            pdfshift_api_key = os.environ.get('PDFSHIFT_API_KEY')
        
        if not pdfshift_api_key:
            logger.error('[PDF] PDFSHIFT_API_KEY not configured')
            return None
        
        # Validate input
        if isinstance(rendering_dict, dict):
            logger.error('[PDF] build_report_pdf expects HTML string, not dict')
            logger.error('[PDF] Did you pass rendering_dict instead of final HTML?')
            return None
        
        if not isinstance(rendering_dict, str):
            logger.error(f'[PDF] Invalid input type: {type(rendering_dict)}')
            return None
        
        html_content = rendering_dict.strip()
        if not html_content:
            logger.error('[PDF] HTML content is empty')
            return None
        
        if len(html_content) > 10_000_000:  # 10MB limit
            logger.error(f'[PDF] HTML too large ({len(html_content)} bytes)')
            return None
        
        logger.info('[PDF] Converting report to PDF via PDFShift...')
        
        # Prepare PDFShift request
        payload = {
            'source': html_content,  # Raw HTML, not base64
            'options': {
                'wait_for_js': True,       # Wait for JavaScript to render charts
                'wait_for_js_delay': 3000, # 3 seconds max wait
                'margin': {
                    'top': 0.5,      # inches
                    'right': 0.75,
                    'bottom': 0.5,
                    'left': 0.75
                },
                'page_size': 'letter',      # 8.5" x 11"
                'orientation': 'portrait',
                'format': 'pdf',
                'media': 'print',           # Use print styles
                'timeout': 120              # seconds
            }
        }
        
        # Add demographics to request (for tracking/logging)
        if demographics:
            demographics_str = ', '.join([
                f'{k}={v}' for k, v in demographics.items()
                if k in ['age_group', 'country', 'ai_tool_use_frequency']
            ])
            if demographics_str:
                payload['options']['header_html'] = f'<!-- {demographics_str} -->'
        
        headers = {
            'Authorization': f'Bearer {pdfshift_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Make request with retry logic
        pdf_bytes = None
        for attempt in range(1, PDFSHIFT_RETRY_COUNT + 1):
            try:
                logger.info(f'[PDF] PDFShift API call (attempt {attempt}/{PDFSHIFT_RETRY_COUNT})')
                
                response = requests.post(
                    PDFSHIFT_API_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=PDFSHIFT_TIMEOUT
                )
                
                # Success
                if response.status_code == 200:
                    pdf_bytes = response.content
                    logger.info(f'[PDF] ✓ PDF generated ({len(pdf_bytes)} bytes)')
                    return pdf_bytes
                
                # Rate limited - retry with backoff
                elif response.status_code == 429:
                    if attempt < PDFSHIFT_RETRY_COUNT:
                        wait_time = PDFSHIFT_RETRY_DELAY * attempt
                        logger.warning(f'[PDF] Rate limited, waiting {wait_time}s before retry...')
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f'[PDF] Rate limited after {PDFSHIFT_RETRY_COUNT} attempts')
                        return None
                
                # Client error
                elif 400 <= response.status_code < 500:
                    error_text = response.text[:200]
                    logger.error(f'[PDF] PDFShift client error {response.status_code}: {error_text}')
                    return None
                
                # Server error - retry
                elif 500 <= response.status_code < 600:
                    if attempt < PDFSHIFT_RETRY_COUNT:
                        logger.warning(f'[PDF] Server error {response.status_code}, retrying...')
                        time.sleep(PDFSHIFT_RETRY_DELAY)
                        continue
                    else:
                        logger.error(f'[PDF] Server error {response.status_code} after {PDFSHIFT_RETRY_COUNT} attempts')
                        return None
                
                else:
                    logger.error(f'[PDF] Unexpected status code: {response.status_code}')
                    return None
            
            except requests.Timeout:
                if attempt < PDFSHIFT_RETRY_COUNT:
                    logger.warning('[PDF] Timeout, retrying...')
                    time.sleep(PDFSHIFT_RETRY_DELAY)
                    continue
                else:
                    logger.error('[PDF] Timeout after all retries')
                    return None
            
            except requests.RequestException as e:
                if attempt < PDFSHIFT_RETRY_COUNT:
                    logger.warning(f'[PDF] Request error: {e}, retrying...')
                    time.sleep(PDFSHIFT_RETRY_DELAY)
                    continue
                else:
                    logger.error(f'[PDF] Request error after all retries: {e}')
                    return None
        
        return pdf_bytes
    
    except Exception as e:
        logger.error(f'[PDF] build_report_pdf failed: {e}')
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# VALIDATION HELPERS
# ============================================================

def validate_html_for_pdf(html_content: str) -> tuple[bool, str]:
    """
    Validate HTML before sending to PDFShift.
    
    Args:
        html_content: HTML string
    
    Returns:
        (is_valid, error_message)
    """
    
    if not html_content:
        return False, 'HTML content is empty'
    
    if len(html_content) > 10_000_000:
        return False, f'HTML too large ({len(html_content)} bytes, max 10MB)'
    
    if not html_content.strip().startswith('<'):
        return False, 'HTML does not start with opening tag'
    
    if 'window.hciRenderingData' not in html_content:
        return False, 'HTML missing data injection (window.hciRenderingData)'
    
    if '<html' not in html_content.lower():
        return False, 'HTML missing <html> tag'
    
    if '<body' not in html_content.lower():
        return False, 'HTML missing <body> tag'
    
    return True, ''


# ============================================================
# FOR TESTING
# ============================================================

if __name__ == '__main__':
    print('report_pdf_creator.py loaded successfully')
    print('Entry point: build_report_pdf(html_string, demographics)')
    print('\nFunctions:')
    print('  ✓ build_report_pdf() - Convert HTML to PDF via PDFShift')
    print('  ✓ validate_html_for_pdf() - Validate HTML before conversion')
    print('\nRequired environment variable:')
    print('  PDFSHIFT_API_KEY - API key from pdfshift.io')
    print('\nUsage:')
    print('  pdf_bytes = build_report_pdf(')
    print('      rendering_dict=final_html_string,  # Must be HTML string, not dict')
    print('      demographics={"age_group": "25-34"},')
    print('      pdfshift_api_key="sk_xxx"')
    print('  )')
    print('  if pdf_bytes:')
    print('      with open("report.pdf", "wb") as f:')
    print('          f.write(pdf_bytes)')
    print('\nNote:')
    print('  - Input must be FINAL HTML (already has window.hciRenderingData injected)')
    print('  - PDFShift renders JavaScript (charts, distributions will render)')
    print('  - Retry logic: 2 attempts with exponential backoff on 429/5xx errors')
