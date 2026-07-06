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
body { background: #ffffff !important; margin: 0 !important; padding: 0 !important; }
.hci-report { box-shadow: none !important; padding: 28px 32px !important; }

/* Preserve grid layouts - force multi-column */
.dimension-grid { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)) !important; gap: 12px !important; }
.evidence-grid { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)) !important; gap: 12px !important; }
.distinctive-grid { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)) !important; gap: 12px !important; }
.protect-grid { display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 14px !important; }
.question-grid { display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 12px !important; }
.human-capital-card-grid { display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 14px !important; }
.standing-grid { display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 14px !important; }
.profile-shape-layout { display: grid !important; gap: 12px !important; }
.cover-grid { display: grid !important; gap: 20px !important; }
.two-col { display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)) !important; gap: 14px !important; }

/* Reduce page section margins */
.page-section { margin: 0 0 32px 0 !important; break-inside: avoid; page-break-inside: avoid; }

/* Reduce card padding */
.dimension-card { padding: 14px 12px 12px !important; font-size: 12px !important; }
.evidence-card { padding: 14px 12px !important; font-size: 13px !important; }
.split-card { padding: 14px 12px !important; font-size: 13px !important; }
.question-card { padding: 14px 12px !important; font-size: 13px !important; }
.protect-card { padding: 14px 12px !important; font-size: 13px !important; }
.distinctive-card { padding: 14px 12px !important; min-height: 160px !important; }
.standing-card { padding: 14px 12px !important; }
.cover-panel { padding: 16px !important; font-size: 12px !important; }

/* Reduce font sizes */
h1 { font-size: 44px !important; line-height: 1.1 !important; }
h2 { font-size: 28px !important; line-height: 1.15 !important; }
h3 { font-size: 15px !important; line-height: 1.3 !important; }
h4 { font-size: 13px !important; }
p { font-size: 13px !important; margin: 0 0 8px !important; }
.lede { font-size: 16px !important; line-height: 1.4 !important; }
.section-intro { font-size: 14px !important; margin-bottom: 16px !important; }
.narrative p { font-size: 14px !important; line-height: 1.45 !important; }

/* Reduce spacing in components */
.percentile-block { margin: 6px 0 !important; }
.percentile-track { height: 4px !important; }
.insight { font-size: 11px !important; margin-top: auto !important; padding-top: 6px !important; }
.dimension-definition { font-size: 11px !important; margin: 0 0 4px !important; }
.dimension-footnote { font-size: 9px !important; margin: 4px 0 0 !important; }
.percentile-context { font-size: 11px !important; }

/* Question-Level Profile: tight continuous flow, no whitespace */
.question-group { margin-top: 12px !important; margin-bottom: 0 !important; break-inside: auto !important; page-break-inside: auto !important; }
.group-definition { margin-bottom: 8px !important; max-width: none !important; }
.question-card { margin-bottom: 12px !important; break-inside: avoid !important; page-break-inside: avoid !important; }
.question-grid { gap: 10px !important; margin-bottom: 0 !important; }

/* Remove excessive margins in question sections */
.question-group h3 { margin-bottom: 8px !important; }
.comparison-note { margin-top: 8px !important; margin-bottom: 0 !important; }

/* Remove shadows for cleaner print */
.cover-panel, .dimension-card, .evidence-card, .split-card, .question-card, .protect-card, .standing-card {
  box-shadow: none !important;
}

/* Reduce brand row spacing */
.brand-row { margin-bottom: 28px !important; gap: 10px !important; }
.brand-mark { width: 32px !important; height: 32px !important; font-size: 11px !important; }
.brand-name { font-size: 11px !important; }
.brand-subtitle { font-size: 10px !important; }

/* Reduce section intro spacing */
.eyebrow, .section-kicker, .card-topline { font-size: 10px !important; margin-bottom: 8px !important; }

/* Links */
a { color: inherit !important; }

/* Ensure all cards respect break rules */
.page-section, .dimension-card, .question-card, .protect-card, .evidence-card, .split-card, .distinctive-card, .standing-card, .shape-panel {
  break-inside: avoid !important;
  page-break-inside: avoid !important;
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
                "top": "8mm",
                "bottom": "8mm",
                "left": "10mm",
                "right": "10mm",
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
