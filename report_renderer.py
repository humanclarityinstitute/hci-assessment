"""report_renderer.py - renders canonical report_data to final HTML. No scoring here."""
from html import escape

from report_data_builder import assert_report_data_contract, ordinal
from report_sections import build_sections


def esc(v):
    return escape("" if v is None else str(v), quote=True)


def pct(v):
    try:
        return max(0, min(100, int(round(float(v)))))
    except Exception:
        return 0


def paras(text):
    return "".join(f"<p>{esc(p.strip())}</p>" for p in str(text or "").split("\n\n") if p.strip())


def dist(values, answer=None):
    if not values:
        return '<div class="dist-empty">Distribution data unavailable</div>'
    try:
        ans = int(answer)
    except Exception:
        ans = None
    html = '<div class="dist">'
    for i, v in enumerate(values[:7], 1):
        cls = "bar answer" if ans == i else "bar"
        h = max(3, min(100, int(v or 0)))
        html += f'<div class="{cls}" style="height:{h}%"><span>{esc(v)}%</span><em>{i}</em></div>'
    return html + "</div>"


def render_report(report_data):
    assert_report_data_contract(report_data)
    s = build_sections(report_data)
    d = report_data.get("demographics") or {}
    age = d.get("age_group", "")
    country = d.get("country", "")
    date = (report_data.get("created_at") or "")[:10]
    deep = s.get("deep_dive") or s.get("section_12_deep_dive")
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Your AI Identity Report</title>
{styles()}
</head>
<body>
<main class="report">
<header class="cover">
<div>Human Clarity Institute</div>
<h1>Your AI Identity Report</h1>
<p>{esc(age)}{(' • ' + esc(country)) if country else ''}{(' • ' + esc(date)) if date else ''}</p>
</header>
{render_opening(s['opening'])}
{render_dashboard(s['dashboard'])}
{render_typicality(s['typicality'])}
{render_rare(s['rare'])}
{render_story(s['story'])}
{render_questions(s['questions'], d)}
{render_distinctive(s['distinctive'])}
{render_perception(s['perception'])}
{render_protect(s['protect'])}
{render_trajectory(s['trajectory'])}
{render_next(s['next_steps'])}
{render_deep_dive(deep) if deep else ''}
{render_quality(report_data)}
</main>
</body>
</html>'''


def render_opening(x):
    return f'<section><h2>{esc(x.get("title"))}</h2>{paras(x.get("statement"))}<h3>Three striking features of your profile emerge immediately</h3>{paras(x.get("findings"))}</section>'


def render_dashboard(x):
    cards = ""
    for c in x.get("cards", []):
        comps = "".join(f'<div class="comparison"><span>{esc(r.get("label"))}</span><strong>{esc(r.get("percentile_label"))}</strong></div>' for r in c.get("comparisons", []))
        cards += f'''<article class="card">
<h3>{esc(c.get("label")).upper()}</h3>
<p class="muted">{esc(c.get("definition"))}</p>
<div class="barline"><span style="width:{pct(c.get("percentile"))}%"></span></div>
<div class="score"><span>{esc(c.get("plain_score"))}</span><strong>{esc(c.get("percentile_label"))} %ile</strong></div>
{comps}
<p class="insight">{esc(c.get("research_insight"))}</p>
</article>'''
    return f'<section><h2>{esc(x.get("title"))}</h2><p>{esc(x.get("subtitle"))}</p><div class="grid">{cards}</div></section>'


def render_typicality(x):
    def ul(items):
        if not items:
            return "<p>No dimensions fall cleanly into this range.</p>"
        return "<ul>" + "".join(f'<li>{esc(i.get("label"))} — {esc(i.get("position"))} ({esc(ordinal(i.get("percentile")))} %ile)</li>' for i in items) + "</ul>"
    return f'<section><h2>{esc(x.get("title"))}</h2><h3>Where You’re Distinctive</h3>{ul(x.get("distinctive", []))}<h3>Where You’re Typical</h3>{ul(x.get("typical", []))}</section>'


def render_rare(x):
    combos = x.get("combinations") or []
    if not combos:
        body = f'<p>{esc(x.get("fallback"))}</p>'
    else:
        body = "".join(f'''<h3>{esc(c.get("label_1"))} + {esc(c.get("label_2"))}</h3>
<p>{esc(c.get("label_1"))}: {esc(ordinal(c.get("percentile_1")))} %ile • {esc(c.get("label_2"))}: {esc(ordinal(c.get("percentile_2")))} %ile</p>
<p>This combination appears in roughly {esc(c.get("rarity_percent"))}% of participants.</p>
<p>{esc(c.get("research_signal"))}</p>''' for c in combos)
    return f'<section><h2>{esc(x.get("title"))}</h2>{body}{paras(x.get("narrative"))}</section>'


def render_story(x):
    return f'<section><h2>{esc(x.get("title"))}</h2>{paras(x.get("body"))}</section>'


def render_questions(x, demo):
    age = demo.get("age_group", "your age group")
    groups = ""
    for g in x.get("groups", []):
        cards = ""
        for q in g.get("questions", []):
            scale = "".join(f'<span class="{"selected" if q.get("answer") == i else ""}">{i}</span>' for i in range(1, 8))
            cards += f'''<article class="qcard">
<h4>“{esc(q.get("question_text"))}”</h4>
<p><strong>Your answer:</strong> {esc(q.get("answer_display"))}</p>
<div class="scale">{scale}</div>
<div class="scale-label"><span>Strongly disagree</span><span>Strongly agree</span></div>
<h5>Everyone</h5>{dist(q.get("distribution_everyone"), q.get("answer"))}
<h5>Your age group ({esc(age)})</h5>{dist(q.get("distribution_age_group"), q.get("answer"))}
<p>{esc(q.get("comparison_statement"))}</p>
</article>'''
        groups += f'<h3>{esc(g.get("label")).upper()}</h3><p class="muted">{esc(g.get("definition"))}</p><div class="qgrid">{cards}</div>'
    return f'<section><h2>{esc(x.get("title"))}</h2><p>{esc(x.get("subtitle"))}</p>{groups}</section>'


def render_distinctive(x):
    cards = "".join(f'<article class="card"><h3>{esc(q.get("dimension_label"))}</h3><p>“{esc(q.get("question_text"))}”</p><p>Your answer: {esc(q.get("answer_display"))}</p><p>Percentile: {esc(q.get("percentile_label"))} %ile</p></article>' for q in x.get("responses", []))
    return f'<section><h2>{esc(x.get("title"))}</h2><div class="grid">{cards}</div>{paras(x.get("narrative"))}</section>'


def render_perception(x):
    rows = "".join(f'<article class="card"><p>“{esc(i.get("question"))}”</p><p>Your answer: {esc(i.get("answer"))}</p><p>{esc(i.get("primary_dimension_label"))}: {esc(ordinal(i.get("actual_percentile")))} %ile — {esc(i.get("actual_position"))}</p></article>' for i in x.get("self_perception", []))
    return f'<section><h2>{esc(x.get("title"))}</h2><h3>How You See Yourself</h3><div class="grid">{rows}</div><h3>What The Data Shows</h3>{paras(x.get("narrative"))}</section>'


def render_protect(x):
    items = ""
    for i in x.get("items", []):
        watch = "".join(f"<li>{esc(w)}</li>" for w in i.get("watch", []))
        items += f'''<article>
<h3>{esc(i.get("title"))}</h3>
<p><strong>{esc(i.get("label"))}</strong>: {esc(i.get("definition"))}</p>
<p>Your position: {esc(i.get("positioning"))} ({esc(ordinal(i.get("percentile")))} %ile)</p>
<p>{esc(i.get("intro"))}</p>
<h4>Here’s what to watch for</h4><ul>{watch}</ul>
<p><strong>What HCI’s research shows:</strong> {esc(i.get("research"))}</p>
<p>{esc(i.get("closing"))}</p>
</article>'''
    return f'<section><h2>{esc(x.get("title"))}</h2><p>{esc(x.get("subtitle"))}</p>{items}</section>'


def render_trajectory(x):
    strengths = "".join(f'<li>{esc(d.get("label"))} — {esc(ordinal(d.get("percentile")))} %ile. {esc(d.get("research_insight", ""))}</li>' for d in x.get("strengths_likely_to_deepen", []))
    monitor = "".join(f'<li>{esc(d.get("label"))} — {esc(ordinal(d.get("percentile")))} %ile. Worth noticing as usage evolves.</li>' for d in x.get("areas_worth_monitoring", []))
    return f'<section><h2>{esc(x.get("title"))}</h2><h3>Likely To Continue</h3>{paras(x.get("likely_to_continue"))}<h3>Strengths Likely To Deepen</h3><ul>{strengths}</ul><h3>Areas Worth Monitoring</h3><ul>{monitor}</ul><h3>Overall Outlook</h3>{paras(x.get("overall_outlook"))}</section>'


def render_next(x):
    return f'<section><h2>{esc(x.get("title"))}</h2>' + "".join(f'<h3>{esc(i.get("title"))}</h3>' + "".join(f"<p>{esc(p)}</p>" for p in i.get("body", [])) for i in x.get("items", [])) + "</section>"


def render_deep_dive(x):
    return f'<section><h2>{esc(x.get("title"))}</h2>{paras(x.get("body"))}</section>'


def render_quality(report_data):
    warnings = (report_data.get("data_quality") or {}).get("warnings") or []
    if not warnings:
        return ""
    return '<section class="quality"><h2>Internal Data Quality Notes</h2><ul>' + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul></section>"


def styles():
    return '''<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f6f7f9;color:#101828;line-height:1.55;margin:0}
.report{max-width:1020px;margin:0 auto;background:#fff;padding:36px}
.cover{border-bottom:1px solid #ddd;margin-bottom:28px;padding-bottom:20px}
h1{font-size:36px;margin:8px 0} h2{font-size:26px;margin-top:34px;border-top:1px solid #e5e7eb;padding-top:24px} h3{font-size:17px;margin-top:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.qgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.card,.qcard{border:1px solid #d0d5dd;border-radius:8px;padding:16px;background:#fff}.muted,.insight{color:#667085}
.barline{height:8px;background:#eaecf0;border-radius:10px;overflow:hidden;margin:12px 0}.barline span{display:block;height:100%;background:#344054}
.score,.comparison,.scale-label{display:flex;justify-content:space-between;gap:10px}.scale{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin:10px 0}.scale span{text-align:center;border:1px solid #d0d5dd;border-radius:4px;padding:5px}.scale .selected{background:#344054;color:#fff}
.dist{height:90px;display:flex;align-items:flex-end;gap:6px;background:#f9fafb;padding:8px;border-radius:6px}.bar{flex:1;background:#d0d5dd;position:relative;min-height:3px;border-radius:3px}.bar.answer{background:#344054}.bar span{position:absolute;top:-20px;font-size:11px}.bar em{position:absolute;bottom:-20px;font-size:11px;font-style:normal}.dist-empty{background:#f2f4f7;padding:10px;border-radius:6px;color:#667085}
section{margin-bottom:22px}.quality{background:#fff7ed;border:1px solid #fed7aa;padding:16px;border-radius:8px}
</style>'''
