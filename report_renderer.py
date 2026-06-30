"""report_renderer.py - renders canonical report_data to final premium HTML. No scoring here.

V1 renderer principles:
- Input is canonical report_data.
- Uses report_sections.build_sections(report_data) as the presentation adapter.
- No redirects, no API calls, no Stripe logic.
- Output is complete standalone HTML for /report?session_id=... responses.
- CSS is included in both <head> and <body> so the WordPress Option B container can safely inject returned HTML and retain styling.
"""
from html import escape

from report_data_builder import assert_report_data_contract, ordinal
from report_sections import build_sections


DIMENSION_ORDER = [
    "reliance",
    "trust",
    "verification",
    "decision_delegation",
    "human_agency",
    "emotional_regulation",
    "thought_partnership",
    "disclosure",
    "social_transparency",
]


# -----------------------------------------------------------------------------
# Basic helpers
# -----------------------------------------------------------------------------

def esc(v):
    return escape("" if v is None else str(v), quote=True)


def pct(v):
    try:
        return max(0, min(100, int(round(float(v)))))
    except Exception:
        return 0


def safe_ordinal(v):
    try:
        return ordinal(v)
    except Exception:
        return str(pct(v))


def paras(text):
    """Render plain text into safe paragraphs."""
    if not text:
        return ""
    return "".join(
        f"<p>{esc(p.strip())}</p>"
        for p in str(text).split("\n\n")
        if p.strip()
    )


def labelize(value):
    return esc(str(value or "").replace("_", " ").title())


def section_kicker(text):
    return f'<div class="section-kicker">{esc(text)}</div>' if text else ""


def render_empty(message="This section is being prepared."):
    return f'<div class="empty-state">{esc(message)}</div>'


# -----------------------------------------------------------------------------
# Data visual helpers
# -----------------------------------------------------------------------------

def percentile_bar(value, label=None):
    p = pct(value)
    label = label or f"{p}th percentile"
    return f'''
    <div class="percentile-block">
      <div class="percentile-meta">
        <span>Lower</span>
        <strong>{esc(label)}</strong>
        <span>Higher</span>
      </div>
      <div class="percentile-track" aria-label="Percentile {p}">
        <span class="percentile-fill" style="width:{p}%"></span>
        <i class="percentile-marker" style="left:{p}%"></i>
      </div>
    </div>'''


def dist(values, answer=None):
    """Render a 1-7 response distribution histogram."""
    if not values:
        return '<div class="dist-empty">Distribution data unavailable</div>'

    try:
        ans = int(answer)
    except Exception:
        ans = None

    vals = list(values[:7])
    # Values are usually percentages already. If all are tiny / counts, scale by max.
    try:
        numeric = [float(v or 0) for v in vals]
    except Exception:
        numeric = [0 for _ in vals]

    max_v = max(numeric) if numeric else 0
    html = '<div class="dist" role="img" aria-label="Response distribution from 1 to 7">'
    for i, raw in enumerate(numeric, 1):
        cls = "dist-bar answer" if ans == i else "dist-bar"
        height = max(4, min(100, int(round(raw if max_v <= 100 else (raw / max_v) * 100))))
        shown = int(round(raw))
        html += f'''
          <div class="{cls}" style="height:{height}%">
            <span class="dist-value">{esc(shown)}%</span>
            <span class="dist-index">{i}</span>
          </div>'''
    return html + "</div>"


def stat_pill(label, value):
    if value in (None, ""):
        return ""
    return f'<div class="stat-pill"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'


# -----------------------------------------------------------------------------
# Main renderer
# -----------------------------------------------------------------------------

def render_report(report_data):
    assert_report_data_contract(report_data)
    s = build_sections(report_data)
    d = report_data.get("demographics") or {}

    age = d.get("age_group", "")
    country = d.get("country", "")
    date = (report_data.get("created_at") or "")[:10]
    deep = s.get("deep_dive") or s.get("section_12_deep_dive")

    meta = " • ".join([esc(x) for x in [age, country, date] if x])

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your AI Identity Report — Human Clarity Institute</title>
{styles()}
</head>
<body>
{styles()}
<main class="hci-report">
  <header class="cover page-section">
    <div class="brand-row">
      <div class="brand-mark">HCI</div>
      <div>
        <div class="brand-name">Human Clarity Institute</div>
        <div class="brand-subtitle">AI Behaviour Benchmarking</div>
      </div>
    </div>
    <div class="cover-grid">
      <div>
        <p class="eyebrow">Personal benchmark report</p>
        <h1>Your AI Identity Report</h1>
        <p class="lede">A measured view of how your AI use compares with HCI benchmark patterns across trust, reliance, agency, verification, emotional reliance, disclosure and decision behaviour.</p>
      </div>
      <aside class="cover-panel">
        {stat_pill("Report type", "Premium")}
        {stat_pill("Comparison basis", "HCI benchmark data")}
        {stat_pill("Profile", meta)}
      </aside>
    </div>
  </header>

  {render_opening(s.get('opening') or {})}
  {render_dashboard(s.get('dashboard') or {})}
  {render_typicality(s.get('typicality') or {})}
  {render_rare(s.get('rare') or {})}
  {render_story(s.get('story') or {})}
  {render_questions(s.get('questions') or {}, d)}
  {render_distinctive(s.get('distinctive') or {})}
  {render_perception(s.get('perception') or {})}
  {render_protect(s.get('protect') or {})}
  {render_trajectory(s.get('trajectory') or {})}
  {render_next(s.get('next_steps') or {})}
  {render_deep_dive(deep) if deep else ''}
  {render_quality(report_data)}

  <footer class="report-footer">
    <strong>Human Clarity Institute</strong>
    <p>This report is intended for reflection, benchmarking and self-understanding. It is not medical, psychological, legal or financial advice.</p>
  </footer>
</main>
</body>
</html>'''


# -----------------------------------------------------------------------------
# Sections
# -----------------------------------------------------------------------------

def render_opening(x):
    findings = x.get("findings")
    finding_html = paras(findings) if isinstance(findings, str) else ""
    if isinstance(findings, list):
        finding_html = '<div class="insight-list">' + ''.join(f'<div class="insight-row"><span></span><p>{esc(i)}</p></div>' for i in findings) + '</div>'

    return f'''
    <section class="page-section opening-section">
      {section_kicker('Initial read')}
      <h2>{esc(x.get('title') or 'Most Striking Finding')}</h2>
      <div class="narrative narrow">{paras(x.get('statement'))}</div>
      <div class="evidence-callout">
        <h3>Three striking features of your profile emerge immediately</h3>
        {finding_html or render_empty('No opening findings were available.')}
      </div>
    </section>'''


def render_dashboard(x):
    cards = ""
    for c in x.get("cards", []):
        percentile = pct(c.get("percentile"))
        comps = "".join(
            f'<div class="comparison"><span>{esc(r.get("label"))}</span><strong>{esc(r.get("percentile_label") or safe_ordinal(r.get("percentile")))} %ile</strong></div>'
            for r in c.get("comparisons", [])
        )
        cards += f'''
        <article class="dimension-card">
          <div class="card-topline">{esc(c.get('label')).upper()}</div>
          <h3>{esc(c.get('plain_score') or c.get('position') or f'{percentile}th percentile')}</h3>
          <p class="muted">{esc(c.get('definition'))}</p>
          {percentile_bar(percentile, f"{safe_ordinal(percentile)} percentile")}
          <div class="comparison-list">{comps}</div>
          <p class="insight">{esc(c.get('research_insight') or c.get('insight'))}</p>
        </article>'''

    return f'''
    <section class="page-section dashboard-section">
      {section_kicker('Benchmark overview')}
      <h2>{esc(x.get('title') or 'Your AI Behaviour Pattern')}</h2>
      <p class="section-intro">{esc(x.get('subtitle') or 'How your profile compares across the core HCI dimensions.')}</p>
      <div class="dimension-grid">{cards or render_empty('No dimension cards were available.')}</div>
    </section>'''


def render_typicality(x):
    def bucket(title, items, empty):
        if not items:
            body = f'<p class="muted">{esc(empty)}</p>'
        else:
            body = ''.join(
                f'<div class="typical-row"><span>{esc(i.get("label"))}</span><strong>{esc(i.get("position"))} · {esc(safe_ordinal(i.get("percentile")))} %ile</strong></div>'
                for i in items
            )
        return f'<article class="split-card"><h3>{esc(title)}</h3>{body}</article>'

    return f'''
    <section class="page-section">
      {section_kicker('Pattern shape')}
      <h2>{esc(x.get('title') or 'How Typical Is Your Pattern?')}</h2>
      <div class="two-col">
        {bucket('Where you are distinctive', x.get('distinctive', []), 'No dimensions fall cleanly into this range.')}
        {bucket('Where you are typical', x.get('typical', []), 'No dimensions fall cleanly into this range.')}
      </div>
    </section>'''


def render_rare(x):
    combos = x.get("combinations") or []
    if not combos:
        body = f'<div class="evidence-callout"><p>{esc(x.get("fallback") or "No rare combination signal was available for this profile.")}</p></div>'
    else:
        body = '<div class="two-col">'
        for c in combos:
            body += f'''
            <article class="split-card">
              <h3>{esc(c.get('label_1'))} + {esc(c.get('label_2'))}</h3>
              <p class="muted">{esc(c.get('label_1'))}: {esc(safe_ordinal(c.get('percentile_1')))} %ile · {esc(c.get('label_2'))}: {esc(safe_ordinal(c.get('percentile_2')))} %ile</p>
              <p class="rarity">Appears in roughly <strong>{esc(c.get('rarity_percent'))}%</strong> of participants.</p>
              <p>{esc(c.get('research_signal'))}</p>
            </article>'''
        body += '</div>'
    return f'<section class="page-section">{section_kicker("Combinations")}<h2>{esc(x.get("title") or "What Is Different About Your Pattern")}</h2>{body}<div class="narrative narrow">{paras(x.get("narrative"))}</div></section>'


def render_story(x):
    return f'<section class="page-section story-section">{section_kicker("Interpretation")}<h2>{esc(x.get("title") or "Your Behaviour Story")}</h2><div class="narrative narrow">{paras(x.get("body")) or render_empty("No behaviour story was available.")}</div></section>'


def render_questions(x, demo):
    age = demo.get("age_group", "your age group")
    groups = ""
    for g in x.get("groups", []):
        cards = ""
        for q in g.get("questions", []):
            answer = q.get("answer")
            scale = "".join(f'<span class="{"selected" if answer == i else ""}">{i}</span>' for i in range(1, 8))
            cards += f'''
            <article class="question-card">
              <h4>“{esc(q.get('question_text'))}”</h4>
              <p class="answer"><strong>Your answer:</strong> {esc(q.get('answer_display'))}</p>
              <div class="scale">{scale}</div>
              <div class="scale-label"><span>Strongly disagree</span><span>Strongly agree</span></div>
              <div class="histogram-grid">
                <div><h5>Everyone</h5>{dist(q.get('distribution_everyone'), answer)}</div>
                <div><h5>Your age group ({esc(age)})</h5>{dist(q.get('distribution_age_group'), answer)}</div>
              </div>
              <p class="comparison-note">{esc(q.get('comparison_statement'))}</p>
            </article>'''
        groups += f'''
          <div class="question-group">
            <h3>{esc(g.get('label')).upper()}</h3>
            <p class="muted group-definition">{esc(g.get('definition'))}</p>
            <div class="question-grid">{cards}</div>
          </div>'''

    return f'''
    <section class="page-section questions-section">
      {section_kicker('Question-level evidence')}
      <h2>{esc(x.get('title') or 'Your Question-Level Profile')}</h2>
      <p class="section-intro">{esc(x.get('subtitle') or 'How your individual responses compare with benchmark distributions.')}</p>
      {groups or render_empty('No question-level profile was available.')}
    </section>'''


def render_distinctive(x):
    cards = "".join(
        f'''
        <article class="evidence-card">
          <div class="card-topline">{esc(q.get('dimension_label'))}</div>
          <p>“{esc(q.get('question_text'))}”</p>
          <div class="evidence-meta"><span>Your answer</span><strong>{esc(q.get('answer_display'))}</strong></div>
          <div class="evidence-meta"><span>Position</span><strong>{esc(q.get('percentile_label') or safe_ordinal(q.get('percentile')))} %ile</strong></div>
        </article>'''
        for q in x.get("responses", [])
    )
    return f'<section class="page-section">{section_kicker("Distinctive responses")}<h2>{esc(x.get("title") or "Your Most Distinctive Responses")}</h2><div class="evidence-grid">{cards or render_empty("No distinctive responses were available.")}</div><div class="narrative narrow">{paras(x.get("narrative"))}</div></section>'


def render_perception(x):
    rows = "".join(
        f'''
        <article class="evidence-card">
          <p>“{esc(i.get('question'))}”</p>
          <div class="evidence-meta"><span>Your answer</span><strong>{esc(i.get('answer'))}</strong></div>
          <div class="evidence-meta"><span>{esc(i.get('primary_dimension_label'))}</span><strong>{esc(safe_ordinal(i.get('actual_percentile')))} %ile · {esc(i.get('actual_position'))}</strong></div>
        </article>'''
        for i in x.get("self_perception", [])
    )
    return f'''
    <section class="page-section">
      {section_kicker('Self-perception')}
      <h2>{esc(x.get('title') or 'Perception Gap Analysis')}</h2>
      <h3>How you see yourself</h3>
      <div class="evidence-grid">{rows or render_empty('No self-perception answers were available.')}</div>
      <h3>What the data shows</h3>
      <div class="narrative narrow">{paras(x.get('narrative'))}</div>
    </section>'''


def render_protect(x):
    items = ""
    for i in x.get("items", []):
        watch = "".join(f"<li>{esc(w)}</li>" for w in i.get("watch", []))
        items += f'''
        <article class="protect-card">
          <div class="card-topline">Protect</div>
          <h3>{esc(i.get('title'))}</h3>
          <p class="muted"><strong>{esc(i.get('label'))}</strong>: {esc(i.get('definition'))}</p>
          <p class="positioning">Your position: <strong>{esc(i.get('positioning'))}</strong> ({esc(safe_ordinal(i.get('percentile')))} %ile)</p>
          <p>{esc(i.get('intro'))}</p>
          <h4>What to watch for</h4>
          <ul>{watch}</ul>
          <p class="research-note"><strong>What HCI’s research shows:</strong> {esc(i.get('research'))}</p>
          <p>{esc(i.get('closing'))}</p>
        </article>'''
    return f'''<section class="page-section protect-section">{section_kicker("Human skills")}
      <h2>{esc(x.get("title") or "What to Protect")}</h2>
      <p class="section-intro">{esc(x.get("subtitle"))}</p>
      <div class="protect-grid">{items or render_empty("No protection signals were available.")}</div>
    </section>'''


def render_trajectory(x):
    strengths = "".join(f'<li><strong>{esc(d.get("label"))}</strong> — {esc(safe_ordinal(d.get("percentile")))} %ile. {esc(d.get("research_insight", ""))}</li>' for d in x.get("strengths_likely_to_deepen", []))
    monitor = "".join(f'<li><strong>{esc(d.get("label"))}</strong> — {esc(safe_ordinal(d.get("percentile")))} %ile. Worth noticing as usage evolves.</li>' for d in x.get("areas_worth_monitoring", []))
    return f'''
    <section class="page-section">
      {section_kicker('Trajectory')}
      <h2>{esc(x.get('title') or 'Your Trajectory & Outlook')}</h2>
      <div class="narrative narrow">
        <h3>Likely to continue</h3>{paras(x.get('likely_to_continue'))}
        <h3>Strengths likely to deepen</h3><ul>{strengths}</ul>
        <h3>Areas worth monitoring</h3><ul>{monitor}</ul>
        <h3>Overall outlook</h3>{paras(x.get('overall_outlook'))}
      </div>
    </section>'''


def render_next(x):
    items = "".join(
        f'<article class="split-card"><h3>{esc(i.get("title"))}</h3>' + "".join(f"<p>{esc(p)}</p>" for p in i.get("body", [])) + '</article>'
        for i in x.get("items", [])
    )
    return f'<section class="page-section">{section_kicker("Next steps")}<h2>{esc(x.get("title") or "Next Steps")}</h2><div class="two-col">{items or render_empty("No next steps were available.")}</div></section>'


def render_deep_dive(x):
    return f'''<section class="page-section deep-dive">{section_kicker("Deep dive")}
      <h2>{esc(x.get("title") or "Deep Dive")}</h2>
      <div class="narrative narrow">{paras(x.get("body"))}</div>
    </section>'''


def render_quality(report_data):
    warnings = (report_data.get("data_quality") or {}).get("warnings") or []
    if not warnings:
        return ""
    return '<section class="quality page-section"><h2>Internal Data Quality Notes</h2><ul>' + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul></section>"


# -----------------------------------------------------------------------------
# Premium HCI CSS
# -----------------------------------------------------------------------------

def styles():
    return r'''<style>
:root{
  --ink:#111827;
  --muted:#667085;
  --soft:#f6f7f9;
  --line:#e5e7eb;
  --line-strong:#d0d5dd;
  --panel:#ffffff;
  --accent:#174EA6;
  --accent-dark:#0f2f63;
  --cream:#fbfaf7;
  --shadow:0 14px 36px rgba(16,24,40,.08);
}
*{box-sizing:border-box}
html{font-size:16px}
body{
  margin:0;
  background:var(--soft);
  color:var(--ink);
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
  line-height:1.58;
}
.hci-report{
  max-width:1120px;
  margin:0 auto;
  background:#fff;
  min-height:100vh;
  padding:64px 72px;
}
.page-section{margin:0 0 72px 0;break-inside:avoid;page-break-inside:avoid}
.brand-row{display:flex;align-items:center;gap:14px;margin-bottom:72px}
.brand-mark{width:42px;height:42px;border:1px solid var(--ink);display:flex;align-items:center;justify-content:center;font-weight:700;letter-spacing:.04em;font-size:13px}
.brand-name{font-weight:700;letter-spacing:.01em}.brand-subtitle{color:var(--muted);font-size:13px;margin-top:1px}
.cover{padding-bottom:56px;border-bottom:1px solid var(--line)}
.cover-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:54px;align-items:end}
.eyebrow,.section-kicker,.card-topline{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700;margin-bottom:14px}
h1{font-family:Georgia,"Times New Roman",serif;font-size:66px;line-height:1.02;letter-spacing:-.045em;margin:0 0 24px 0;font-weight:500;color:#080b12}
h2{font-family:Georgia,"Times New Roman",serif;font-size:38px;line-height:1.12;letter-spacing:-.025em;margin:0 0 18px 0;font-weight:500;color:#080b12}
h3{font-size:18px;line-height:1.35;margin:26px 0 10px 0;color:#111827}h4{font-size:15px;line-height:1.45;margin:0 0 12px 0}h5{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:18px 0 8px 0}
p{margin:0 0 14px}.lede{font-size:21px;line-height:1.55;color:#344054;max-width:720px}.section-intro{font-size:18px;color:#475467;max-width:760px;margin-bottom:28px}.muted{color:var(--muted)}
.cover-panel{background:var(--cream);border:1px solid var(--line);padding:22px;box-shadow:var(--shadow)}
.stat-pill{border-bottom:1px solid var(--line);padding:0 0 13px;margin-bottom:13px}.stat-pill:last-child{border-bottom:0;margin-bottom:0;padding-bottom:0}.stat-pill span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}.stat-pill strong{display:block;margin-top:4px;font-size:15px}
.narrow{max-width:820px}.narrative p{font-size:17px;color:#253044}.opening-section .narrative p:first-child{font-size:22px;color:#1d2939;line-height:1.48}
.evidence-callout{background:var(--cream);border-left:4px solid var(--accent);padding:26px 30px;margin-top:28px}.evidence-callout h3{margin-top:0}.insight-list{display:grid;gap:12px}.insight-row{display:grid;grid-template-columns:18px 1fr;gap:12px}.insight-row span{width:8px;height:8px;background:var(--accent);border-radius:50%;margin-top:10px}.insight-row p{margin:0}
.dimension-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.dimension-card,.evidence-card,.split-card,.question-card,.protect-card{border:1px solid var(--line);background:#fff;padding:24px;break-inside:avoid;page-break-inside:avoid}.dimension-card{min-height:330px;display:flex;flex-direction:column}.dimension-card h3{margin-top:0;font-size:20px}.insight{color:#475467;font-size:14px;margin-top:auto;padding-top:12px;border-top:1px solid var(--line)}
.percentile-block{margin:20px 0}.percentile-meta{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;color:var(--muted);font-size:12px}.percentile-meta strong{color:var(--accent-dark);font-size:14px}.percentile-meta span:last-child{text-align:right}.percentile-track{height:8px;background:#eef2f6;border-radius:20px;position:relative;margin-top:9px}.percentile-fill{display:block;height:100%;background:linear-gradient(90deg,var(--accent-dark),var(--accent));border-radius:20px}.percentile-marker{position:absolute;top:50%;width:14px;height:14px;background:#fff;border:3px solid var(--accent);border-radius:50%;transform:translate(-50%,-50%)}
.comparison-list{display:grid;gap:8px;margin:14px 0}.comparison,.evidence-meta,.typical-row{display:flex;justify-content:space-between;gap:18px;border-top:1px solid var(--line);padding-top:9px;color:#475467;font-size:14px}.comparison strong,.evidence-meta strong,.typical-row strong{color:#101828;text-align:right}.two-col{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.split-card h3{margin-top:0}.rarity strong{font-size:20px;color:var(--accent-dark)}
.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.evidence-card p{font-size:15px;color:#344054}.protect-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.protect-card{background:#fcfcfd}.protect-card h3{font-family:Georgia,"Times New Roman",serif;font-size:25px;font-weight:500;margin-top:0}.positioning,.research-note{background:var(--cream);padding:12px;border-left:3px solid var(--accent)}ul{margin:8px 0 0 20px;padding:0}li{margin-bottom:8px}
.question-group{margin-top:40px}.group-definition{max-width:820px}.question-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.question-card h4{font-size:16px;color:#111827}.answer{color:#344054}.scale{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin:12px 0 6px}.scale span{text-align:center;border:1px solid var(--line-strong);padding:7px 0;font-size:12px;color:#475467}.scale .selected{background:var(--accent-dark);border-color:var(--accent-dark);color:#fff;font-weight:700}.scale-label{display:flex;justify-content:space-between;color:var(--muted);font-size:11px}.histogram-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px}.dist{height:112px;display:flex;align-items:flex-end;gap:7px;background:#f9fafb;border:1px solid var(--line);padding:26px 10px 22px;border-radius:2px}.dist-bar{flex:1;background:#cfd6df;position:relative;min-height:4px;border-radius:2px 2px 0 0}.dist-bar.answer{background:var(--accent-dark)}.dist-value{position:absolute;top:-19px;left:50%;transform:translateX(-50%);font-size:10px;color:#475467}.dist-index{position:absolute;bottom:-19px;left:50%;transform:translateX(-50%);font-size:10px;color:#667085}.dist-empty{background:#f2f4f7;border:1px solid var(--line);padding:14px;color:var(--muted);font-size:13px}.comparison-note{font-size:14px;color:#475467;margin-top:14px}.empty-state{background:#f9fafb;border:1px dashed var(--line-strong);padding:18px;color:var(--muted)}
.deep-dive{background:#101828;color:#fff;padding:42px}.deep-dive h2,.deep-dive h3{color:#fff}.deep-dive .section-kicker{color:#9cc2ff}.deep-dive p{color:#e4e7ec}.quality{background:#fff7ed;border:1px solid #fed7aa;padding:20px}.report-footer{border-top:1px solid var(--line);padding-top:24px;color:var(--muted);font-size:13px}
@media(max-width:900px){.hci-report{padding:36px 22px}.cover-grid,.dimension-grid,.two-col,.evidence-grid,.protect-grid,.question-grid,.histogram-grid{grid-template-columns:1fr}h1{font-size:44px}h2{font-size:30px}.brand-row{margin-bottom:42px}}
@media print{body{background:#fff}.hci-report{max-width:none;padding:34px}.page-section{break-inside:avoid;page-break-inside:avoid;margin-bottom:46px}.dimension-grid{grid-template-columns:repeat(3,1fr)}.question-grid{grid-template-columns:repeat(2,1fr)}.cover-panel,.dimension-card,.evidence-card,.split-card,.question-card,.protect-card{box-shadow:none}a{color:inherit}}
</style>'''
