"""
HCI Report → PDF
================
Turns the SAME canonical report page (hci-report-page.html) into a downloadable
PDF, with zero second source of truth for the visuals.

Why a headless browser (Chromium/Playwright) and not WeasyPrint/wkhtmltopdf:
the report's charts are HTML/CSS <div>s drawn by the page's own JavaScript
(renderReport) from the report data. Nothing renders them server-side. Only a
real browser runs that JS, so Chromium reproduces the live page exactly and
stays in sync automatically whenever the template changes.

How it stays single-source:
render_report_html() does NOT hand-maintain a separate print layout. It reads
the canonical template file, injects the already-generated report object inline
(base64 -> JSON.parse), swaps the page's network bootstrap (init() -> a direct
renderReport call), and disables animations so the PDF captures the final state.
Point template_path at the same hci-report-page.html the site serves.

Deploy dependency (Railway):
    pip install playwright
    playwright install --with-deps chromium
"""

import base64
import json
import os

# The exact network bootstrap at the end of the page's IIFE. We replace this so
# the page renders the injected report directly instead of fetching /premium.
_INIT_BOOTSTRAP = """if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',init);
}else{
  init();
}"""

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
    if _INIT_BOOTSTRAP not in html:
        raise ValueError(
            'report template bootstrap not found — the init() block changed; '
            'update _INIT_BOOTSTRAP in report_pdf.py to match the template.'
        )
    html = html.replace(_INIT_BOOTSTRAP, _PRINT_BOOTSTRAP, 1)

    return html


def generate_report_pdf(report_html, wait_ms=700):
    """Render self-contained report HTML to PDF bytes via headless Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            page = browser.new_page()
            page.set_content(report_html, wait_until='load')
            page.wait_for_timeout(wait_ms)  # let renderReport finish drawing
            pdf_bytes = page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '14mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'},
            )
        finally:
            browser.close()
    return pdf_bytes


def build_report_pdf(report, template_path=DEFAULT_TEMPLATE_PATH, demographics=None):
    """
    One safe call for the API: render + PDF. Returns PDF bytes, or None on any
    failure (logged). None simply means the email goes out as summary + web link
    with no attachment — delivery is never blocked by a PDF problem.
    """
    try:
        html = render_report_html(report, template_path, demographics)
        return generate_report_pdf(html)
    except Exception as e:
        print(f'PDF build failed (non-fatal, sending email without attachment): {e}')
        return None
