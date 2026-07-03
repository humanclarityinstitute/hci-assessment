"""
HCI Report -> PDF  (PDFShift edition)
=====================================
Turns the SAME canonical report page (hci-report-page.html) into a downloadable
PDF, with zero second source of truth for the visuals.

Why PDFShift (and not Playwright/Chromium, WeasyPrint, or wkhtmltopdf):
the report's charts are HTML/CSS <div>s drawn by the page's own JavaScript
(renderReport/render) from the report data. Nothing renders them server-side. Only a
real browser runs that JS. PDFShift is a hosted headless-Chrome service, so it
reproduces the live page exactly and stays in sync automatically whenever the
template changes — without needing Chromium installed in the container (the
previous Playwright approach failed because Chromium was never installed).

How it stays single-source:
render_report_html() does NOT hand-maintain a separate print layout. It reads
the canonical template file, injects the already-generated report object inline
(base64 -> JSON.parse), swaps the page's network bootstrap (init() -> a direct
renderReport/render call), and disables animations so the PDF captures the final state.
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

# Replacement bootstrap — stays INSIDE the page IIFE, so render/renderReport is in scope.
# It supports both versions of the report template:
#   - the Railway/backend template with renderReport(...)
#   - the WordPress wrapper template with render(...)
# It also applies PDF mode after rendering, including inside Shadow DOM if the
# WordPress wrapper injects the finished report into a shadow root.
_PRINT_BOOTSTRAP = """function __hciApplyPdfModeStyles(root){
  try{
    root = root || document;
    if(!root.getElementById || root.getElementById('hci-pdf-mode-style')){return;}
    var style = root.createElement('style');
    style.id = 'hci-pdf-mode-style';
    style.textContent = window.__HCI_PDF_CSS__ || '';
    var target = root.head || root;
    target.appendChild(style);
  }catch(err){console.error('pdf style injection failed', err);}
}

function __hciPrintInit(){
  try{
    document.documentElement.classList.add('hci-pdf-mode');
    if(document.body){document.body.classList.add('hci-pdf-mode');}
    __hciApplyPdfModeStyles(document);

    var report = window.__HCI_REPORT__;
    var rendered = false;

    if(typeof renderReport === 'function'){
      renderReport(report);
      rendered = true;
    }else if(typeof render === 'function'){
      render(report);
      rendered = true;
    }else{
      console.error('print render failed: no renderReport() or render() function was found');
    }

    ['hci-generating','hci-error','loading','error'].forEach(function(id){
      var el = document.getElementById(id);
      if(el){el.style.display='none'; el.classList.add('hidden');}
    });
    ['hci-report','report'].forEach(function(id){
      var el = document.getElementById(id);
      if(el){el.style.display='block'; el.classList.remove('hidden');}
    });

    document.querySelectorAll('[data-fill]').forEach(function(el){el.style.width=el.dataset.fill+'%';});
    document.querySelectorAll('[data-pos]').forEach(function(el){el.style.left=el.dataset.pos+'%';});

    document.querySelectorAll('*').forEach(function(el){
      if(el.shadowRoot){__hciApplyPdfModeStyles(el.shadowRoot);}
    });

    window.__HCI_PDF_READY__ = rendered;
  }catch(err){
    console.error('print render failed',err);
    window.__HCI_PDF_READY__ = true;
  }
}
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',__hciPrintInit);
}else{
  __hciPrintInit();
}"""

_PDF_MODE_CSS = r"""
*{transition:none !important;animation:none !important;scroll-behavior:auto !important;}
html.hci-pdf-mode,
body.hci-pdf-mode{background:#fff !important;overflow:visible !important;}
body.hci-pdf-mode{font-size:15px !important;}
#hci-generating,#hci-error,#loading,#error,.hci-print-bar{display:none !important;}
#hci-report,#report{display:block !important;width:100% !important;}
.hidden{display:none !important;}
#report.hidden,#hci-report.hidden{display:block !important;}

.page,
.hci-report,
main.hci-report,
#hci-report,
#report .hci-report{max-width:1080px !important;margin-left:auto !important;margin-right:auto !important;}

.grid,
.dimension-grid,
.evidence-grid,
.distinctive-grid,
.question-grid,
.human-capital-grid,
.capability-grid,
.priority-grid,
.forward-grid,
.looking-forward-grid,
.trajectory-grid{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;gap:18px !important;}
.grid.two,
.two-col,
.profile-shape-layout,
.human-capital-layout,
.perception-card-grid,
.perception-grid,
.comparison-list{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:18px !important;}

.dimension{display:grid !important;grid-template-columns:220px 1fr !important;gap:28px !important;}
.question-group,
.question-card,
.dimension-card,
.evidence-card,
.distinctive-card,
.split-card,
.card,
.shape-panel,
.profile-shape-summary,
.perception-card,
.human-capital-card,
.capability-card,
.priority-card,
.forward-card,
.trajectory-card{break-inside:avoid !important;page-break-inside:avoid !important;}
.page-section,
.section,
.report-opening,
.dashboard-section,
.profile-shape-section,
.questions-section,
.distinctive-section,
.perception-section,
.human-capital-section,
.trajectory-section,
.looking-forward-section,
.closing-reflection-section{break-inside:auto !important;page-break-inside:auto !important;}
h1,h2,h3,h4{break-after:avoid !important;page-break-after:avoid !important;}
p{orphans:3 !important;widows:3 !important;}

.inner{padding:52px 64px !important;}
.topline{padding-left:64px !important;padding-right:64px !important;}
.section,
.page-section{padding-left:64px !important;padding-right:64px !important;}
.footer,
.report-footer{padding-left:64px !important;padding-right:64px !important;}
h1{font-size:64px !important;}
h2{font-size:38px !important;}
.card,
.dimension-card,
.evidence-card,
.question-card,
.split-card{padding:20px !important;}

.percentile-track,
.mini-track,
.perception-scale-track,
.bar{border-style:solid !important;background-image:none !important;}
.percentile-fill,
.bar span{display:block !important;}
"""

_PRINT_STYLE = (
    '<style id="hci-print-overrides">' + _PDF_MODE_CSS + '</style>'
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
    inject = (
        f'<script>window.__HCI_REPORT__=JSON.parse(atob("{payload}"));'
        f'window.__HCI_PDF_CSS__={json.dumps(_PDF_MODE_CSS)};</script>'
    )

    # 1) Inject the report payload right after <body> (runs before the IIFE),
    #    and mark the document as PDF mode. This leaves the live desktop and
    #    mobile HTML untouched; only the generated PDF receives these rules.
    body_re = re.compile(r'<body([^>]*)>', re.IGNORECASE)
    match = body_re.search(html)
    if not match:
        raise ValueError('report template missing <body> anchor')
    attrs = match.group(1) or ''
    if re.search(r'class\s*=', attrs, re.IGNORECASE):
        attrs = re.sub(
            r"class=([\"\'])(.*?)\1",
            lambda m: f'class={m.group(1)}{m.group(2)} hci-pdf-mode{m.group(1)}',
            attrs,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        attrs = attrs + ' class="hci-pdf-mode"'
    html = html[:match.start()] + f'<body{attrs}>\n' + inject + html[match.end():]

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
        # Give the content more usable paper width without changing the live web report.
        'margin': {'top': '10mm', 'bottom': '10mm', 'left': '8mm', 'right': '8mm'},
        # Force a desktop browser viewport before PDFShift prints to A4, so the
        # report does not trip the template's mobile/tablet responsive breakpoint.
        'viewport': '1440x1600',
        # Slightly reduce PDF scale for better density and fewer awkward breaks.
        'zoom': 0.94,
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
