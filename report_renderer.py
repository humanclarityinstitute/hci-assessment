"""report_renderer.py - renders canonical report_data to final HTML. No scoring here."""
from html import escape
from report_data_builder import assert_report_data_contract, ordinal
from report_sections import build_sections

def esc(v): return escape("" if v is None else str(v), quote=True)
def pct(v):
    try: return max(0, min(100, int(round(float(v)))))
    except Exception: return 0
def paras(text):
    return "".join(f"<p>{esc(p.strip())}</p>" for p in str(text or "").split("\n\n") if p.strip())
def dist(values, answer=None):
    if not values: return '<div class="dist-missing">Distribution data unavailable</div>'
    try: ans=int(answer)
    except Exception: ans=None
    html='<div class="distribution">'
    for i,v in enumerate(values[:7],1):
        cls='bar answer' if ans==i else 'bar'; h=max(3,min(100,int(v or 0)))
        html+=f'<div class="dist-col"><div class="dist-pct">{esc(v)}%</div><div class="bar-wrap"><div class="{cls}" style="height:{h}%"></div></div><div class="dist-label">{i}</div></div>'
    return html+'</div>'

def render_report(report_data):
    assert_report_data_contract(report_data)
    s=build_sections(report_data); d=report_data.get("demographics") or {}
    age=d.get("age_group",""); country=d.get("country",""); date=(report_data.get("created_at") or "")[:10]
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>Your AI Identity Report</title><meta name="viewport" content="width=device-width, initial-scale=1">{styles()}</head><body><main class="report">
<header class="cover"><div class="eyebrow">Human Clarity Institute</div><h1>Your AI Identity Report</h1><p class="meta">{esc(age)}{(' • '+esc(country)) if country else ''}{(' • '+esc(date)) if date else ''}</p></header>
{render_opening(s['opening'])}{render_dashboard(s['dashboard'])}{render_typicality(s['typicality'])}{render_rare(s['rare'])}{render_story(s['story'])}{render_questions(s['questions'], d)}{render_distinctive(s['distinctive'])}{render_perception(s['perception'])}{render_protect(s['protect'])}{render_trajectory(s['trajectory'])}{render_next(s['next_steps'])}{render_quality(report_data)}
</main></body></html>'''

def render_opening(x): return f'<section class="section opening"><h2>{esc(x["title"])}</h2><div class="opening-statement">{paras(x.get("statement"))}</div><h3>Three striking features of your profile emerge immediately</h3>{paras(x.get("findings"))}</section>'
def render_dashboard(x):
    cards=''
    for c in x.get('cards',[]):
        comps=''.join(f'<div class="comparison-row"><span>{esc(r.get("label"))}</span><strong>{esc(r.get("percentile_label"))}</strong></div>' for r in c.get('comparisons',[]))
        cards+=f'<article class="dimension-card"><h3>{esc(c.get("label")).upper()}</h3><p class="definition">{esc(c.get("definition"))}</p><div class="pctbar"><div style="width:{pct(c.get("percentile"))}%"></div></div><div class="score-row"><span>{esc(c.get("plain_score"))}</span><strong>{esc(c.get("percentile_label"))} %ile</strong></div><div class="comparisons">{comps}</div><p class="insight">{esc(c.get("research_insight"))}</p></article>'
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><p class="subtitle">{esc(x.get("subtitle"))}</p><div class="dimension-grid">{cards}</div></section>'
def render_typicality(x):
    def ul(items): return '<p>No dimensions fall cleanly into this range.</p>' if not items else '<ul>'+''.join(f'<li><strong>{esc(i.get("label"))}</strong> — {esc(i.get("position"))} ({esc(ordinal(i.get("percentile")))} %ile)</li>' for i in items)+'</ul>'
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><div class="two-col"><div><h3>Where You’re Distinctive</h3>{ul(x.get("distinctive",[]))}</div><div><h3>Where You’re Typical</h3>{ul(x.get("typical",[]))}</div></div></section>'
def render_rare(x):
    combos=x.get('combinations') or []
    if not combos: body=f'<p>{esc(x.get("fallback"))}</p>'
    else:
        body=''.join(f'<article class="combo-card"><h3>{esc(c.get("label_1"))} + {esc(c.get("label_2"))}</h3><p>{esc(c.get("label_1"))}: {esc(ordinal(c.get("percentile_1")))} %ile • {esc(c.get("label_2"))}: {esc(ordinal(c.get("percentile_2")))} %ile</p><p>This combination appears in roughly {esc(c.get("rarity_percent"))}% of participants.</p><p class="insight">{esc(c.get("research_signal"))}</p></article>' for c in combos)
        body += paras(x.get('narrative'))
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2>{body}</section>'
def render_story(x): return f'<section class="section"><h2>{esc(x.get("title"))}</h2>{paras(x.get("body"))}</section>'
def render_questions(x,demo):
    age=demo.get('age_group','your age group'); groups=''
    for g in x.get('groups',[]):
        cards=''
        for q in g.get('questions',[]):
            scale=''.join(f'<span class="scale-point {"selected" if q.get("answer")==i else ""}">{i}</span>' for i in range(1,8))
            cards+=f'<article class="question-card"><p class="qtext">“{esc(q.get("question_text"))}”</p><div class="answer-row">Your answer: <strong>{esc(q.get("answer_display"))}</strong></div><div class="scale">{scale}</div><div class="scale-labels"><span>Strongly disagree</span><span>Strongly agree</span></div><h4>Everyone</h4>{dist(q.get("distribution_everyone"), q.get("answer"))}<h4>Your age group ({esc(age)})</h4>{dist(q.get("distribution_age_group"), q.get("answer"))}<p class="comparison">{esc(q.get("comparison_statement"))}</p></article>'
        groups+=f'<div class="question-group"><h3>{esc(g.get("label")).upper()}</h3><p class="definition">{esc(g.get("definition"))}</p><div class="question-grid">{cards}</div></div>'
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><p class="subtitle">{esc(x.get("subtitle"))}</p>{groups}</section>'
def render_distinctive(x):
    cards=''.join(f'<article class="response-card"><h3>{esc(q.get("dimension_label"))}</h3><p>“{esc(q.get("question_text"))}”</p><p><strong>Your answer:</strong> {esc(q.get("answer_display"))}</p><p><strong>Percentile:</strong> {esc(q.get("percentile_label"))} %ile</p></article>' for q in x.get('responses',[]))
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><div class="response-grid">{cards}</div>{paras(x.get("narrative"))}</section>'
def render_perception(x):
    rows=''.join(f'<div class="perception-row"><div><p class="qtext">“{esc(i.get("question"))}”</p><p>Your answer: <strong>{esc(i.get("answer"))}</strong></p></div><div><p>{esc(i.get("primary_dimension_label"))}</p><strong>{esc(ordinal(i.get("actual_percentile")))} %ile</strong><p class="muted">{esc(i.get("actual_position"))}</p></div></div>' for i in x.get('self_perception',[]))
    narrative = x.get('narrative') or ("Your self-perception and actual benchmark positioning show at least one meaningful gap." if x.get('has_significant_gap') else "Your self-perception aligns closely with your actual responses. There are no significant gaps between how you think you relate to AI and how your benchmark pattern currently appears.")
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><h3>How You See Yourself</h3>{rows}<h3>What The Data Shows</h3>{paras(narrative)}</section>'
def render_protect(x):
    items=''
    for i in x.get('items',[]):
        items+=f'<article class="protect-card"><h3>{esc(i.get("title"))}</h3><p class="definition">{esc(i.get("label"))}: {esc(i.get("definition"))}</p><p><strong>Your position:</strong> {esc(i.get("positioning"))} ({esc(ordinal(i.get("percentile")))} %ile)</p><p>{esc(i.get("intro"))}</p><h4>Here’s what to watch for</h4><ul>'+''.join(f'<li>{esc(w)}</li>' for w in i.get('watch',[]))+f'</ul><p><strong>What HCI’s research shows:</strong> {esc(i.get("research"))}</p><p>{esc(i.get("closing"))}</p></article>'
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><p class="subtitle">{esc(x.get("subtitle"))}</p><div class="protect-grid">{items}</div></section>'
def render_trajectory(x):
    strengths=''.join(f'<li><strong>{esc(d.get("label"))}</strong> — {esc(ordinal(d.get("percentile")))} %ile. {esc(d.get("research_insight",""))}</li>' for d in x.get('strengths_likely_to_deepen',[]))
    monitor=''.join(f'<li><strong>{esc(d.get("label"))}</strong> — {esc(ordinal(d.get("percentile")))} %ile. Worth noticing as usage evolves.</li>' for d in x.get('areas_worth_monitoring',[]))
    return f'<section class="section"><h2>{esc(x.get("title"))}</h2><h3>Likely To Continue</h3>{paras(x.get("likely_to_continue"))}<h3>Strengths Likely To Deepen</h3><ul>{strengths}</ul><h3>Areas Worth Monitoring</h3><ul>{monitor}</ul><h3>Overall Outlook</h3>{paras(x.get("overall_outlook"))}</section>'
def render_next(x): return f'<section class="section"><h2>{esc(x.get("title"))}</h2>'+''.join(f'<article class="next-step"><h3>{esc(i.get("title"))}</h3>'+''.join(f'<p>{esc(p)}</p>' for p in i.get('body',[]))+'</article>' for i in x.get('items',[]))+'</section>'
def render_quality(report_data):
    warnings=(report_data.get('data_quality') or {}).get('warnings') or []
    if not warnings: return ''
    return '<section class="section data-quality"><h2>Internal Data Quality Notes</h2><ul>'+''.join(f'<li>{esc(w)}</li>' for w in warnings)+'</ul></section>'
def styles(): return '''<style>
:root{--ink:#1f2933;--muted:#64748b;--line:#d9dee7;--soft:#f6f7f9;--accent:#25364d}*{box-sizing:border-box}body{margin:0;background:#f3f4f6;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.55}.report{width:min(1120px,100%);margin:0 auto;background:white;padding:48px}.cover{border-bottom:1px solid var(--line);padding-bottom:28px;margin-bottom:36px}.eyebrow{text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-size:12px;font-weight:700}h1{font-size:44px;line-height:1.05;margin:8px 0 12px}h2{font-size:26px;margin:0 0 18px}h3{font-size:16px;margin:18px 0 8px}h4{font-size:13px;margin:14px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.meta,.subtitle,.definition,.muted{color:var(--muted)}.section{page-break-inside:avoid;border-bottom:1px solid var(--line);padding:30px 0}.opening-statement{background:var(--soft);padding:18px;border:1px solid var(--line);border-radius:8px}.dimension-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.dimension-card,.question-card,.response-card,.combo-card,.protect-card,.next-step{border:1px solid var(--line);border-radius:8px;padding:16px;background:white}.dimension-card h3{margin-top:0;font-size:13px;letter-spacing:.04em}.pctbar{height:8px;background:#e9edf3;border-radius:999px;overflow:hidden;margin:14px 0}.pctbar div{height:100%;background:var(--accent)}.score-row,.comparison-row,.answer-row,.scale-labels{display:flex;justify-content:space-between;gap:16px}.score-row strong{font-size:18px;color:var(--accent)}.comparisons{border-top:1px solid var(--line);margin-top:12px;padding-top:10px;font-size:12px}.insight{border-top:1px solid var(--line);margin-top:10px;padding-top:10px;color:var(--muted);font-size:12px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:28px}.question-group{margin-top:28px}.question-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.qtext{font-weight:600}.scale{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin:10px 0 4px}.scale-point{border:1px solid var(--line);text-align:center;border-radius:4px;padding:4px 0;font-size:12px}.scale-point.selected{background:var(--accent);color:white;border-color:var(--accent)}.scale-labels{color:var(--muted);font-size:11px}.distribution{height:92px;display:grid;grid-template-columns:repeat(7,1fr);gap:5px;align-items:end}.dist-col{height:92px;display:grid;grid-template-rows:18px 1fr 16px;align-items:end;text-align:center}.dist-pct,.dist-label{font-size:10px;color:var(--muted)}.bar-wrap{height:52px;display:flex;align-items:end;justify-content:center}.bar{width:100%;background:#b9c2cf;border-radius:3px 3px 0 0}.bar.answer{background:var(--accent)}.dist-missing{color:var(--muted);font-size:12px;background:var(--soft);padding:8px;border-radius:6px}.response-grid,.protect-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.perception-row{display:grid;grid-template-columns:1.7fr .8fr;gap:16px;border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:10px}.data-quality{background:#fff7ed;padding:20px}@media print{body{background:white}.report{padding:24px}.section{page-break-inside:avoid}}@media(max-width:760px){.report{padding:24px}.question-grid,.response-grid,.protect-grid,.two-col{grid-template-columns:1fr}}
</style>'''
