"""
HCI Premium Report Email — v2.1 (lightweight summary + PDF attachment)

Design decision (locked): the email is a SHORT, scannable summary that mirrors
the free results page voice — positional language + plain-English, no bare
percentiles, no charts. The full experience lives in two places:
  1. the interactive web report (CTA button -> report_url), and
  2. a downloadable PDF of the full report, attached to this email.

v2.1 rules honoured here:
  - NO bare "Xth percentile" anywhere (cards or prose). We render only the
    positional word + plain-English string that the generator produces.
  - No archetypes, no "tensions" language.
  - British English. Brand: navy #1B2A4A, brand blue #4054B2, cream #F9F7F2.

------------------------------------------------------------------------------
FIELD MAP — CONFIRM AGAINST report_generator.py BEFORE DEPLOY
------------------------------------------------------------------------------
This template reads the v2.1 report object. The exact key names below are the
ONLY thing tying it to the generator, so they are isolated here on purpose.
Everything is read with a safe default: a missing key degrades to blank, never
to a wrong number (that is what produced the old "0th percentile" bug).
"""

import base64
import json
import urllib.request
from datetime import datetime


# Nine dimensions, v2.1 report order.
DIM_ORDER = [
    'reliance', 'trust', 'verification', 'decision_delegation',
    'human_agency', 'disclosure', 'emotional_regulation',
    'thought_partnership', 'social_transparency',
]


def _first_paragraph(text):
    """Lightweight: show only the opening paragraph of a longer section."""
    if not text:
        return ''
    return text.split('\n\n')[0].replace('\n', ' ').strip()


def _dim_summary_row(dim):
    """
    One compact dimension row: label + subtitle, positional word, plain-English.
    No percentile number, no chart, no full narrative — those live in the
    PDF / web report.

    Reads report_generator's dimension_profiles fields:
      label, subtitle, position (the Section-3 positional word), plain_english.
    We render the positional word + plain-English string only — never a bare
    percentile (v2.1).
    """
    label = dim.get('label', '')
    subtitle = dim.get('subtitle', '')
    position = (dim.get('position') or '').strip()
    if position:
        position = position[0].upper() + position[1:]  # "notably high" -> "Notably high"
    plain = dim.get('plain_english', '')

    position_pill = (
        f'<span style="display:inline-block;background:#EDEBFB;color:#3D2B8C;'
        f'font-size:11px;font-weight:700;padding:3px 11px;border-radius:20px;'
        f'letter-spacing:0.02em;">{position}</span>'
    ) if position else ''

    return f"""
    <tr><td style="padding:0 0 12px;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#F8F9FC;border-radius:8px;border-left:3px solid #4054B2;">
        <tr><td style="padding:16px 18px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:top;">
                <p style="margin:0;color:#1B2A4A;font-size:15px;font-weight:700;">{label}</p>
                <p style="margin:2px 0 0;color:#6B7280;font-size:12px;">{subtitle}</p>
              </td>
              <td align="right" style="vertical-align:top;">{position_pill}</td>
            </tr>
          </table>
          <p style="margin:10px 0 0;color:#4054B2;font-size:13px;font-weight:600;line-height:1.5;">{plain}</p>
        </td></tr>
      </table>
    </td></tr>"""


def generate_report_email(report, demographics, report_url='https://humanclarityinstitute.com', pdf_url=None):
    """Generate the lightweight HTML summary email (PDF carries the full report).

    pdf_url: optional durable link to the stored PDF, shown as a fallback so a
    stripped attachment or a lost inbox never loses the report.
    """

    age_group = demographics.get('age_group', '')
    country = demographics.get('country', '')
    frequency = demographics.get('ai_tool_use_frequency', '')
    date_str = datetime.utcnow().strftime('%d %B %Y')

    # Most surprising finding -> short opener. In report_generator this is the
    # 'opening' field (generate_opening). 'overview' is the separate AI-Identity
    # overview, used only as a fallback.
    surprising = _first_paragraph(
        report.get('opening')
        or report.get('overview')
        or ''
    )

    # Methodology stays the fixed verbatim "10,000+" text from the generator.
    methodology = report.get('methodology_note') or report.get('methodology') or ''

    # Build the nine compact dimension rows in v2.1 order.
    profiles = report.get('dimension_profiles', {}) or {}
    dim_rows = ''.join(
        _dim_summary_row(profiles[k]) for k in DIM_ORDER if profiles.get(k)
    )

    # Durable PDF download link (fallback if the attachment is stripped/lost).
    pdf_link_html = (
        f'<p style="margin:14px 0 0;color:#6B7280;font-size:12px;">'
        f'Prefer a direct download? <a href="{pdf_url}" style="color:#4054B2;font-weight:600;">'
        f'Download your report PDF</a></p>'
    ) if pdf_url else ''

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Your AI Identity Report — Human Clarity Institute</title>
</head>
<body style="margin:0;padding:0;background:#F4F6FB;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6FB;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- Header -->
  <tr><td style="background:#1B2A4A;border-radius:12px 12px 0 0;padding:34px 40px;">
    <p style="margin:0 0 10px;color:rgba(255,255,255,0.35);font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">Human Clarity Institute · AI Identity &amp; Behaviour Assessment</p>
    <h1 style="margin:0 0 12px;color:#ffffff;font-size:27px;font-weight:800;letter-spacing:-0.5px;line-height:1.15;">Your AI Identity Report</h1>
    <p style="margin:0;color:rgba(255,255,255,0.45);font-size:13px;">{age_group} &nbsp;·&nbsp; {country} &nbsp;·&nbsp; {frequency} AI user &nbsp;·&nbsp; {date_str}</p>
  </td></tr>

  <!-- Most surprising finding (short) -->
  <tr><td style="background:#F9F7F2;border:1px solid #D9CEBD;border-top:none;padding:26px 40px;">
    <p style="margin:0 0 8px;color:#6B7280;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">Your most surprising finding</p>
    <p style="margin:0;color:#1B2A4A;font-size:15px;line-height:1.7;font-weight:500;">{surprising}</p>
  </td></tr>

  <!-- CTA: full report (PDF + web) -->
  <tr><td style="background:#ffffff;padding:26px 40px 8px;text-align:center;">
    <p style="margin:0 0 16px;color:#1A1A1A;font-size:14px;line-height:1.6;">Your full report — every dimension, the cross-dimensional patterns, your perception gap and the complete 39-question appendix — is <strong>attached as a PDF</strong> and available to read online.</p>
    <a href="{report_url}" style="display:inline-block;background:#4054B2;color:#ffffff;font-size:14px;font-weight:700;text-decoration:none;padding:13px 30px;border-radius:8px;">View your full report online →</a>
    {pdf_link_html}
  </td></tr>

  <!-- Nine dimension summary -->
  <tr><td style="background:#ffffff;padding:18px 40px 6px;">
    <p style="margin:0 0 14px;color:#6B7280;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">Your nine dimensions at a glance</p>
    <table width="100%" cellpadding="0" cellspacing="0">{dim_rows}</table>
  </td></tr>

  <!-- Methodology (fixed verbatim, 10,000+) -->
  <tr><td style="background:#ffffff;border-radius:0 0 12px 12px;padding:18px 40px 24px;border-top:1px solid #E2E6EF;">
    <p style="margin:14px 0 8px;color:#9CA3AF;font-size:11px;line-height:1.7;">{methodology}</p>
    <p style="margin:0;color:#9CA3AF;font-size:11px;">Benchmark data and methodology: <a href="https://github.com/humanclarityinstitute" style="color:#4054B2;">github.com/humanclarityinstitute</a></p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:24px 0;text-align:center;">
    <p style="margin:0;color:#9CA3AF;font-size:12px;">Human Clarity Institute &nbsp;·&nbsp; <a href="https://humanclarityinstitute.com" style="color:#4054B2;text-decoration:none;">humanclarityinstitute.com</a></p>
    <p style="margin:8px 0 0;color:#9CA3AF;font-size:11px;">This report was generated specifically for you. It is not intended for redistribution.</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_report_email(to_email, report, demographics, resend_api_key,
                      report_url='https://humanclarityinstitute.com',
                      pdf_bytes=None,
                      pdf_url=None,
                      pdf_filename='HCI-AI-Identity-Report.pdf'):
    """
    Send the summary email via Resend, with the full report attached as PDF.

    pdf_bytes: attach the PDF if provided.
    pdf_url:   durable link to the stored PDF, shown in-body as a fallback so a
               stripped attachment or a lost inbox never loses the report.
    If both are None the email still sends (summary + web link) — so a PDF
    hiccup never blocks delivery.
    """
    html_content = generate_report_email(report, demographics, report_url, pdf_url=pdf_url)

    body = {
        'from': 'reports@updates.humanclarityinstitute.com',
        'to': [to_email],
        'reply_to': 'info@humanclarityinstitute.com',
        'subject': 'Your AI Identity & Behaviour Report — Human Clarity Institute',
        'html': html_content,
    }

    if pdf_bytes:
        body['attachments'] = [{
            'filename': pdf_filename,
            'content': base64.b64encode(pdf_bytes).decode('utf-8'),
        }]

    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {resend_api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        response = urllib.request.urlopen(req, timeout=15)
        result = json.loads(response.read())
        print(f'Email sent successfully: {result.get("id")}')
        return True
    except Exception as e:
        print(f'Email send failed (non-critical): {e}')
        return False
