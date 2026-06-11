"""
HCI Premium Report Email Template
Generates HTML email with full report content
"""

def generate_report_email(report, demographics):
    """Generate HTML email for the premium report."""
    
    age_group = demographics.get('age_group', '')
    country = demographics.get('country', '')
    frequency = demographics.get('ai_tool_use_frequency', '')
    
    from datetime import datetime
    date_str = datetime.utcnow().strftime('%d %B %Y')
    
    # Build dimension profiles HTML
    dim_order = ['reliance', 'trust', 'verification', 'decision_delegation',
                 'human_agency', 'disclosure', 'emotional_regulation',
                 'thought_partnership', 'social_transparency']
    
    dim_html = ''
    profiles = report.get('dimension_profiles', {})
    for dim_key in dim_order:
        dim = profiles.get(dim_key)
        if not dim:
            continue
        pct = int(dim.get('percentile', 0))
        plain = dim.get('plain_english', '')
        rarity = dim.get('rarity', '')
        narrative = dim.get('narrative', '').replace('\n', '<br>')
        
        dim_html += f"""
        <div style="background:#f8f9fc;border-radius:8px;padding:24px;margin-bottom:16px;border-left:4px solid #4054B2;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td><h3 style="margin:0 0 4px;color:#1B2A4A;font-size:16px;font-weight:700;">{dim.get('label','')}</h3>
                    <p style="margin:0;color:#6B7280;font-size:12px;">{dim.get('subtitle','')}</p></td>
                    <td align="right"><span style="font-size:28px;font-weight:800;color:#1B2A4A;letter-spacing:-1px;">{pct}<sup style="font-size:14px;">th</sup></span><br>
                    <span style="font-size:11px;color:#6B7280;">percentile</span></td>
                </tr>
            </table>
            <p style="margin:12px 0 8px;color:#4054B2;font-size:13px;font-weight:600;">{plain}</p>
            {f'<p style="margin:0 0 12px;background:#EDEBFB;color:#3D2B8C;font-size:11px;font-weight:600;padding:4px 10px;border-radius:20px;display:inline-block;">{rarity}</p>' if rarity else ''}
            <p style="margin:12px 0 0;color:#1A1A1A;font-size:14px;line-height:1.7;">{narrative}</p>
        </div>"""
    
    opening = report.get('opening', '').replace('\n\n', '</p><p style="margin:0 0 14px;color:#1B2A4A;font-size:15px;line-height:1.75;">').replace('\n', '<br>')
    cross = report.get('cross_dimensional', '').replace('\n\n', '</p><p style="margin:0 0 14px;color:#1A1A1A;font-size:14px;line-height:1.75;">').replace('\n', '<br>')
    changing = report.get('what_is_changing', '').replace('\n\n', '</p><p style="margin:0 0 14px;color:rgba(255,255,255,0.85);font-size:14px;line-height:1.75;">').replace('\n', '<br>')
    closing = report.get('closing', '').replace('\n\n', '</p><p style="margin:0 0 14px;color:#1B2A4A;font-size:14px;line-height:1.75;">').replace('\n', '<br>')
    methodology = report.get('methodology_note', '')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Your AI Identity Report — Human Clarity Institute</title>
</head>
<body style="margin:0;padding:0;background:#F4F6FB;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F4F6FB;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- Header -->
  <tr><td style="background:#1B2A4A;border-radius:12px 12px 0 0;padding:36px 40px;">
    <p style="margin:0 0 10px;color:rgba(255,255,255,0.35);font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">Human Clarity Institute · AI Identity & Behaviour Assessment</p>
    <h1 style="margin:0 0 12px;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;line-height:1.15;">Your AI Identity Report</h1>
    <p style="margin:0;color:rgba(255,255,255,0.4);font-size:13px;">{age_group} &nbsp;·&nbsp; {country} &nbsp;·&nbsp; {frequency} AI user &nbsp;·&nbsp; {date_str}</p>
  </td></tr>

  <!-- Opening -->
  <tr><td style="background:#F9F7F2;border:1px solid #D9CEBD;border-top:none;padding:28px 40px;">
    <p style="margin:0 0 8px;color:#6B7280;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">Most Surprising Finding & Why Most People Miss This</p>
    <p style="margin:0 0 14px;color:#1B2A4A;font-size:15px;line-height:1.75;font-weight:500;">{opening}</p>
  </td></tr>

  <!-- White spacer -->
  <tr><td style="background:#ffffff;padding:8px 40px;">
    <p style="margin:0;color:#6B7280;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:16px 0 8px;">Your Nine Dimension Profiles</p>
  </td></tr>

  <!-- Dimensions -->
  <tr><td style="background:#ffffff;padding:0 40px 24px;">
    {dim_html}
  </td></tr>

  <!-- Cross-dimensional -->
  <tr><td style="background:#ffffff;padding:0 40px 24px;">
    <div style="border:1px solid #E2E6EF;border-radius:12px;padding:24px;">
      <p style="margin:0 0 8px;color:#3D2B8C;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;">Cross-Dimensional Patterns</p>
      <p style="margin:0 0 14px;color:#1A1A1A;font-size:14px;line-height:1.75;">{cross}</p>
    </div>
  </td></tr>

  <!-- What Is AI Changing -->
  <tr><td style="background:#1B2A4A;padding:32px 40px;">
    <p style="margin:0 0 8px;color:rgba(255,255,255,0.35);font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">HCI Research Insight</p>
    <h2 style="margin:0 0 16px;color:#ffffff;font-size:20px;font-weight:800;">What is AI changing in you?</h2>
    <p style="margin:0 0 14px;color:rgba(255,255,255,0.85);font-size:14px;line-height:1.75;">{changing}</p>
  </td></tr>

  <!-- Closing -->
  <tr><td style="background:#F9F7F2;border:1px solid #D9CEBD;border-top:none;padding:28px 40px;">
    <p style="margin:0 0 8px;color:#6B7280;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">Profile Directions & Human Flourishing Reflection</p>
    <p style="margin:0 0 14px;color:#1B2A4A;font-size:14px;line-height:1.75;">{closing}</p>
  </td></tr>

  <!-- Methodology -->
  <tr><td style="background:#ffffff;border-radius:0 0 12px 12px;padding:24px 40px;border-top:1px solid #E2E6EF;">
    <p style="margin:0 0 8px;color:#9CA3AF;font-size:11px;line-height:1.7;">{methodology}</p>
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

    return html


def send_report_email(to_email, report, demographics, resend_api_key):
    """Send the premium report via Resend."""
    import urllib.request
    import json

    html_content = generate_report_email(report, demographics)
    
    payload = json.dumps({
        'from': 'reports@updates.humanclarityinstitute.com',
        'to': [to_email],
        'reply_to': 'info@humanclarityinstitute.com',
        'subject': 'Your AI Identity & Behaviour Report — Human Clarity Institute',
        'html': html_content,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={
            'Authorization': f'Bearer {resend_api_key}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )

    try:
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read())
        print(f'Email sent successfully: {result.get("id")}')
        return True
    except Exception as e:
        print(f'Email send failed (non-critical): {e}')
        return False
