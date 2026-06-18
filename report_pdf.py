"""
HCI Report -> PDF  (PDFShift edition)
=====================================
Turns the SAME canonical report page (hci-report-page.html) into a downloadable
PDF, with zero second source of truth for the visuals.

Why PDFShift (and not Playwright/Chromium, WeasyPrint, or wkhtmltopdf):
the report's charts are HTML/CSS <div>s drawn by the page's own JavaScript
(renderReport) from the report data. Nothing renders them server-side. Only a
real browser runs that JS. PDFShift is a hosted headless-Chrome service, so it
reproduces the live page exactly and stays in sync automatically whenever the
template changes — without needing Chromium installed in the container (the
previous Playwright approach failed because Chromium was never installed).

How it stays single-source:
render_report_html() does NOT hand-maintain a separate print layout. It reads
the canonical template file, injects the already-generated report object inline
(base64 -> JSON.parse), swaps the page's network bootstrap (init() -> a direct
renderReport call), and disables animations so the PDF captures the final state.
Point template_path at the same hci-report-page.html the site serves.

The bootstrap swap is whitespace-tolerant (regex), so ordinary edits to the
report page's init() block do not silently break PDF generation. If the block
genuinely cannot be found, render_report_html() raises and the caller treats
that as "no PDF" — the summary email still sends.

Deploy dependencies (Railway):
    PDFSHIFT_API_KEY   (required)  your PDFShift API key
    PDFSHIFT_SANDBOX   (optional)  "true" to render free watermarked test PDFs;
                                   unset/"false" for real (billed) PDFs.
No system packages, no Chromium install required.
"""

import base64
import json
import os
import re
import urllib.request

PDFSHIFT_ENDPOINT = 'https://api.pdfshift.io/v3/convert/pdf'

# The page's network bootstrap, matched flexibly (any whitespace between tokens).
# This is the block at the end of the report page IIFE that wires init() to the
# DOM. We replace it so the PDF renders the injected report directly instead of
# fetching /premium.
_INIT_BOOTSTRAP_RE = re.compile(
    r"if\s*\(\s*document\.readyState\s*===\s*'loading'\s*\)\s*\{\s*"
    r"document\.addEventListener\s*\(\s*'DOMContentLoaded'\s*,\s*init\s*\)\s*;?\s*"
    r"\}\s*else\s*\{\s*"
    r"init\s*\(\s*\)\s*;?\s*"
    r"\}",
    re.DOTALL,
)

# Replacement bootstrap — stays INSIDE the IIFE, so renderReport is in scope.
# Also snaps every animated bar/marker to its final position immediately.
_PRINT_BOOTSTRAP = """function __hciPrintInit(){
  try{
    var e=document.getElementById('hci-error'); if(e){e.style.display='none';}
    renderReport(window.__HCI_REPORT__);
    document.querySelectorAll('[data-fill]').forEach(function(el){el.style.width=el.dataset.fill+'%';});
    document.querySelectorAll('[data-pos]').forEach(function(el){el.style.left=el.dataset.pos+'%';});
  }catch(err){console.error('print render failed',err);}
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',__hciPrintInit);
}else{
  __hciPrintInit();
}"""

_PRINT_STYLE = (
    '<style id="hci-print-overrides">'
    '*{transition:none !important;animation:none !important}'
    '#hci-generating,#hci-error,.hci-print-bar{display:none !important}'
    '#hci-report{display:block !important}'
    '</style>'
)

DEFAULT_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'hci-report-page.html')


def render_report_html(report, template_path=DEFAULT_TEMPLATE_PATH, demographics=None):
    """
    Transform the canonical report template into a self-contained print HTML
    with the report data baked in. Raises if the template doesn't contain the
    expected anchors (so a silently-broken PDF can never go out — the caller
    treats a raise as "no PDF" and still sends the summary email).
    """
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Make sure the header meta has demographics to render.
    if demographics:
        report = dict(report)
        meta = dict(report.get('metadata') or {})
        if not meta.get('demographics'):
            meta['demographics'] = demographics
        report['metadata'] = meta

    # ensure_ascii keeps the payload pure-ASCII so base64 -> atob -> JSON.parse
    # round-trips any unicode (em dashes, smart quotes) safely.
    payload = base64.b64encode(
        json.dumps(report, ensure_ascii=True).encode('utf-8')
    ).decode('ascii')
    inject = f'<script>window.__HCI_REPORT__=JSON.parse(atob("{payload}"));</script>'

    # 1) Inject the report payload right after <body> (runs before the IIFE).
    if '<body>' not in html:
        raise ValueError('report template missing <body> anchor')
    html = html.replace('<body>', '<body>\n' + inject, 1)

    # 2) Inject print overrides before </head>.
    if '</head>' not in html:
        raise ValueError('report template missing </head> anchor')
    html = html.replace('</head>', _PRINT_STYLE + '\n</head>', 1)

    # 3) Swap the network bootstrap for the direct-render bootstrap.
    #    Whitespace-tolerant so ordinary edits to the page don't break this.
    html, n = _INIT_BOOTSTRAP_RE.subn(_PRINT_BOOTSTRAP, html, count=1)
    if n == 0:
        raise ValueError(
            'report template bootstrap not found — the init() block changed '
            'beyond what the whitespace-tolerant matcher handles; update '
            '_INIT_BOOTSTRAP_RE in report_pdf.py to match the template.'
        )

    return html


def generate_report_pdf(report_html, wait_ms=1200, css=None):
    """
    Render self-contained report HTML to PDF bytes via PDFShift (hosted headless
    Chrome). Runs the page's JavaScript so renderReport draws the charts.

    Env:
      PDFSHIFT_API_KEY  (required) — raises if missing.
      PDFSHIFT_SANDBOX  (optional) — "true"/"1"/"yes" renders a free, watermarked
                        test PDF; anything else renders a real (billed) PDF.

    wait_ms: how long PDFShift waits after load for renderReport to finish
             drawing before printing (the charts are JS-drawn).
    """
    api_key = os.environ.get('PDFSHIFT_API_KEY')
    if not api_key:
        raise ValueError('PDFSHIFT_API_KEY not set — cannot render PDF')

    sandbox = os.environ.get('PDFSHIFT_SANDBOX', '').strip().lower() in ('1', 'true', 'yes')

    payload = {
        'source': report_html,        # raw HTML (Option B — self-contained)
        'landscape': False,
        'use_print': False,           # use screen styles, not @media print
        'format': 'A4',
        'margin': {'top': '14mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'},
        # The report charts are drawn by the page's own JS after load, so give
        # the browser time to finish before capturing.
        'delay': wait_ms,
        'sandbox': sandbox,
    }
    if css:
        payload['css'] = css

    body = json.dumps(payload).encode('utf-8')

    # PDFShift auth: X-API-Key header (per the dashboard's request example).
    req = urllib.request.Request(
        PDFSHIFT_ENDPOINT,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
            'User-Agent': 'HCI-Reports/1.0',
        },
        method='POST',
    )

    # Generous timeout: hosted render of a JS page can take a few seconds.
    response = urllib.request.urlopen(req, timeout=60)
    pdf_bytes = response.read()
    if not pdf_bytes:
        raise ValueError('PDFShift returned an empty response')
    return pdf_bytes


def build_report_pdf(report, template_path=DEFAULT_TEMPLATE_PATH, demographics=None):
    """
    One safe call for the API: render + PDF. Returns PDF bytes, or None on any
    failure (logged). None simply means the email goes out as summary + web link
    with no attachment — delivery is never blocked by a PDF problem.

    Signature unchanged from the previous (Playwright) version, so api.py,
    the Supabase upload, and the email all keep working untouched.
    """
    try:
        html = render_report_html(report, template_path, demographics)
        return generate_report_pdf(html)
    except urllib.error.HTTPError as e:
        # Surface PDFShift's error body — it explains auth/credit/format issues.
        try:
            detail = e.read().decode('utf-8', 'replace')[:500]
        except Exception:
            detail = ''
        print(f'PDF build failed (non-fatal): PDFShift HTTP {e.code} {detail}')
        return None
    except Exception as e:
        print(f'PDF build failed (non-fatal, sending email without attachment): {e}')
        return None
