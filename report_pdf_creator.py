"""report_pdf_creator.py - PDFShift renderer for HCI Option B reports.

Input: complete HTML string from report_renderer.render_report(report_data).
Output: PDF bytes, or None on failure.

This module is intentionally simple: report_renderer.py is the single source of
truth for visuals. We send that final HTML directly to PDFShift.

Required env:
  PDFSHIFT_API_KEY
Optional env:
  PDFSHIFT_SANDBOX=true   # watermarked test PDFs
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional

PDFSHIFT_ENDPOINT = "https://api.pdfshift.io/v3/convert/pdf"


DEFAULT_PDF_CSS = """
* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
body { background: #ffffff !important; }
.hci-report { box-shadow: none !important; }
.page-section, .dimension-card, .question-card, .protect-card, .evidence-card, .split-card {
  break-inside: avoid;
  page-break-inside: avoid;
}
"""


def _is_sandbox() -> bool:
    return os.environ.get("PDFSHIFT_SANDBOX", "").strip().lower() in {"1", "true", "yes", "on"}


def build_report_pdf(
    report_html: str,
    demographics: Optional[dict] = None,
    wait_ms: int = 1200,
    extra_css: Optional[str] = None,
) -> Optional[bytes]:
    """Render final report HTML to PDF bytes using PDFShift.

    Args:
        report_html: Complete standalone HTML from render_report(report_data).
        demographics: Accepted for API compatibility; not required by this renderer.
        wait_ms: Delay before print capture, useful if any visual elements need layout time.
        extra_css: Optional additional CSS appended to default PDF CSS.

    Returns:
        PDF bytes, or None if PDF generation fails. Failure is non-fatal so the
        web report and email can still work.
    """
    try:
        if not report_html or not isinstance(report_html, str):
            print("PDF build skipped: report_html is empty or not a string")
            return None

        api_key = os.environ.get("PDFSHIFT_API_KEY")
        if not api_key:
            print("PDF build skipped: PDFSHIFT_API_KEY not set")
            return None

        css = DEFAULT_PDF_CSS
        if extra_css:
            css += "\n" + extra_css

        payload = {
            "source": report_html,
            "landscape": False,
            "use_print": False,
            "format": "A4",
            "margin": {
                "top": "14mm",
                "bottom": "14mm",
                "left": "12mm",
                "right": "12mm",
            },
            "delay": wait_ms,
            "sandbox": _is_sandbox(),
            "css": css,
        }

        req = urllib.request.Request(
            PDFSHIFT_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key,
                "User-Agent": "HCI-Reports/1.0",
            },
            method="POST",
        )

        response = urllib.request.urlopen(req, timeout=60)
        pdf_bytes = response.read()

        if not pdf_bytes:
            print("PDF build failed: PDFShift returned empty response")
            return None

        print(f"PDF generated successfully ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:1000]
        except Exception:
            detail = ""
        print(f"PDF build failed (non-fatal): PDFShift HTTP {e.code} {detail}")
        return None

    except Exception as e:
        print(f"PDF build failed (non-fatal): {e}")
        return None
