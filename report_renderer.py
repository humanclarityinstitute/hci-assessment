"""report_renderer.py - renders canonical report_data to final premium HTML. No scoring here.

V1 renderer principles:
- Input is canonical report_data.
- Uses report_sections.build_sections(report_data) as the presentation adapter.
- No redirects, no API calls, no Stripe logic.
- Output is complete standalone HTML for /report?session_id=... responses.
- CSS is included in both <head> and <body> so the WordPress Option B container can safely inject returned HTML and retain styling.
"""
from html import escape
from datetime import datetime

from report_data_builder import assert_report_data_contract, ordinal
from report_sections import build_sections


DIMENSION_ORDER = [
    "reliance",
    "trust",
    "verification",
    "decision_delegation",
    "human_agency",
    "emotional_regulation",
    "disclosure",
    "thought_partnership",
    "social_transparency",
]


DIMENSION_CODES = {
    "reliance": "R",
    "trust": "T",
    "verification": "V",
    "decision_delegation": "DD",
    "human_agency": "HA",
    "emotional_regulation": "ER",
    "disclosure": "D",
    "thought_partnership": "TP",
    "social_transparency": "ST",
}

DIMENSION_ACCENTS = {
    "reliance": "#174EA6",
    "trust": "#3E6B5B",
    "verification": "#6B5CA5",
    "decision_delegation": "#9A5A24",
    "human_agency": "#1F7A7A",
    "emotional_regulation": "#6F3D6E",
    "disclosure": "#6C7F3F",
    "thought_partnership": "#4054B2",
    "social_transparency": "#344054",
}


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


def response_dots(answer, total=7):
    """Premium filled/unfilled response indicator for 1-7 answers."""
    try:
        a = int(round(float(answer)))
    except Exception:
        a = 0
    a = max(0, min(total, a))
    return "".join(
        f'<span class="{"filled" if i <= a else "empty"}"></span>'
        for i in range(1, total + 1)
    )


def compact_position_label(item):
    text = str(item.get("position") or "benchmark range").lower()
    if "exceptionally high" in text:
        return "Very high"
    if "notably high" in text:
        return "High"
    if "above" in text:
        return "Elevated"
    if "exceptionally low" in text:
        return "Very low"
    if "notably low" in text:
        return "Low"
    if "below" in text:
        return "Lower"
    return "Benchmark range"


def inline_text(text):
    """Render safe inline text and tolerate simple Claude Markdown bold if it appears."""
    if text is None:
        return ""
    safe = esc(text)
    # Convert escaped **bold** markers to real bold text.
    # Content is already escaped, so this remains safe.
    import re
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    return safe


def paras(text):
    """Render plain text into safe paragraphs, with minimal Markdown-bold cleanup."""
    if not text:
        return ""
    return "".join(
        f"<p>{inline_text(p.strip())}</p>"
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
    """Render a 1-7 response distribution histogram.

    Accepts either percentages or raw counts. Always displays percentages and
    scales bars to the largest percentage in the 1-7 response distribution.
    """
    if not values:
        return '<div class="dist-empty">Distribution data unavailable</div>'

    try:
        ans = int(answer)
    except Exception:
        ans = None

    vals = list(values[:7])
    try:
        numeric = [max(0.0, float(v or 0)) for v in vals]
    except Exception:
        numeric = [0.0 for _ in vals]

    total = sum(numeric)
    if total > 0:
        if total > 105 or max(numeric) > 100:
            percents = [(v / total) * 100 for v in numeric]
        elif 95 <= total <= 105:
            percents = numeric
        else:
            percents = [(v / total) * 100 for v in numeric]
    else:
        percents = [0.0 for _ in numeric]

    max_p = max(percents) if percents else 0
    html = '<div class="dist" role="img" aria-label="Response distribution from 1 to 7">'
    for i, raw in enumerate(percents, 1):
        cls = "dist-bar answer" if ans == i else "dist-bar"
        height = 4 if max_p <= 0 else max(4, min(100, int(round((raw / max_p) * 100))))
        shown = int(round(raw))
        html += f'''
          <div class="{cls}" style="height:{height}%">
            <span class="dist-value">{esc(shown)}%</span>
            <span class="dist-index">{i}</span>
          </div>'''
    return html + "</div>"


def position_band(percentile):
    p = pct(percentile)
    if p >= 71:
        return "at the high end"
    if p >= 41:
        return "in the middle"
    return "at the low end"


def extract_dimension_percentiles(report_data):
    """Best-effort extraction of dimension percentiles from canonical report_data."""
    out = {}
    candidates = [
        report_data.get("dimensions"),
        report_data.get("dimension_scores"),
        report_data.get("scores"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key, val in candidate.items():
                if isinstance(val, dict):
                    out[key] = val.get("percentile") or val.get("overall_percentile") or val.get("score_percentile") or val.get("percentile_overall")
                else:
                    out[key] = val
        elif isinstance(candidate, list):
            for item in candidate:
                if isinstance(item, dict):
                    key = item.get("key") or item.get("dimension") or item.get("name")
                    if key:
                        out[str(key).lower().replace(" ", "_")] = item.get("percentile") or item.get("overall_percentile") or item.get("score_percentile")
    return out


def stat_pill(label, value):
    if value in (None, ""):
        return ""
    return f'<div class="stat-pill"><span>{esc(label)}</span><strong>{esc(value)}</strong></div>'


COUNTRY_NAMES = {
    "NZ": "New Zealand",
    "AU": "Australia",
    "US": "United States",
    "USA": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "IE": "Ireland",
    "CA": "Canada",
}


def country_name(value):
    if not value:
        return ""
    text = str(value).strip()
    return COUNTRY_NAMES.get(text.upper(), text)


def format_report_date(value):
    if not value:
        return ""
    raw = str(value).strip()
    try:
        iso = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %B %Y").lstrip("0")
    except Exception:
        pass
    try:
        dt = datetime.strptime(raw[:10], "%Y-%m-%d")
        return dt.strftime("%d %B %Y").lstrip("0")
    except Exception:
        return raw


def participant_detail(label, value):
    if value in (None, ""):
        return ""
    return f'<span><strong>{esc(label)}:</strong> {esc(value)}</span>'


def participant_meta(age="", country="", date=""):
    parts = [participant_detail("Age", age), participant_detail("Country", country), participant_detail("Completed", date)]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    return '<div class="participant-meta"><span class="participant-meta-label">Participant details</span>' + '<span class="meta-sep">•</span>'.join(parts) + '</div>'


def opening_synthesis_html(text):
    """Render Claude's opening synthesis as editorial prose with optional subheadings."""
    if not text:
        return render_empty("No opening synthesis was available.")

    raw = str(text).strip()
    blocks = [b.strip() for b in raw.split("\n\n") if b.strip()]
    html = '<div class="opening-synthesis narrative">'
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        first = lines[0]
        clean_first = first.lstrip("#").strip().strip("*").strip()
        if (first.startswith("#") or (len(clean_first) <= 95 and len(lines) > 1 and not clean_first.endswith("."))):
            html += f'<h3>{esc(clean_first)}</h3>'
            body = " ".join(lines[1:]).strip()
            if body:
                html += f'<p>{esc(body)}</p>'
        else:
            html += f'<p>{esc(" ".join(lines))}</p>'
    html += '</div>'
    return html


def dim_key(value):
    """Normalize a dimension label/key to a CSS/data key."""
    raw = str(value or "").strip().lower().replace("&", "and")
    raw = raw.replace("-", " ").replace("/", " ")
    return "_".join(raw.split())


def dim_accent(key_or_label):
    return DIMENSION_ACCENTS.get(dim_key(key_or_label), "#174EA6")


def rarity_label(percentile):
    """Return a restrained rarity label based on distance from population centre."""
    p = pct(percentile)
    distance = abs(p - 50)
    if distance >= 45:
        return "Very rare"
    if distance >= 35:
        return "Rare"
    if distance >= 25:
        return "Uncommon"
    return "Common"


def question_identifier(group_key, index):
    code = DIMENSION_CODES.get(dim_key(group_key), "")
    return f"{code}{index}" if code else str(index)


def mini_percentile_row(label, value):
    p = pct(value)
    return f"""
      <div class="mini-position-row">
        <span>{esc(label)}</span>
        <div class="mini-track" style="--mini-fill:{p}%" aria-label="{esc(label)} percentile {p}">
          <i style="left:{p}%"></i>
        </div>
        <strong>{p} / 100</strong>
      </div>"""


DASHBOARD_QUESTION_COUNTS = {
    "reliance": 5,
    "trust": 4,
    "verification": 4,
    "decision_delegation": 5,
    "human_agency": 5,
    "emotional_regulation": 4,
    "disclosure": 4,
    "thought_partnership": 4,
    "social_transparency": 4,
}


def dashboard_count_label(card):
    key = dim_key(card.get("dimension") or card.get("key") or card.get("label"))
    count = card.get("question_count") or card.get("item_count") or card.get("response_count") or DASHBOARD_QUESTION_COUNTS.get(key)
    try:
        count = int(count)
    except Exception:
        count = None
    if not count:
        return "Constructed from behavioural indicators"
    return f"Constructed from {count} behavioural indicators"


def dashboard_comparisons(card):
    """Keep the dashboard compact: show population + age only, not frequency groups."""
    rows = []
    seen = set()
    for r in card.get("comparisons", []) or []:
        raw_label = str(r.get("label") or "").strip()
        norm = raw_label.lower()
        pct_value = r.get("percentile")
        pct_label = r.get("percentile_label") or safe_ordinal(pct_value)

        if any(term in norm for term in ["everyday", "daily", "frequent", "frequency", "users"]):
            continue
        if any(term in norm for term in ["age", "cohort"]):
            label = raw_label.replace("Your age group", "Age group").replace("Your ", "")
            key = "age"
        elif any(term in norm for term in ["everyone", "overall", "population", "benchmark"]):
            label = "Population"
            key = "population"
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        rows.append({"label": label, "percentile_label": pct_label, "percentile": pct_value, "key": key})

    if "population" not in seen:
        rows.insert(0, {"label": "Population", "percentile_label": safe_ordinal(card.get("percentile")), "percentile": card.get("percentile"), "key": "population"})
    return rows[:2] if any(r.get("key") == "age" for r in rows) else rows[:1]


def dashboard_insight(card):
    """Concise, participant-facing dashboard interpretation. No research trivia or hard-to-interpret stats."""
    key = dim_key(card.get("dimension") or card.get("key") or card.get("label"))
    p = pct(card.get("percentile"))
    band = "high" if p >= 71 else "low" if p <= 40 else "middle"

    copy = {
        "reliance": {
            "high": "Your reliance on AI is higher than most participants. This suggests AI has become embedded in your normal thinking workflow, bringing efficiency while increasing the chance that some tasks feel harder when AI is unavailable.",
            "middle": "Your reliance sits close to the benchmark range. AI appears useful in your workflow, but not so central that it dominates how you think, decide, or function day to day.",
            "low": "Your reliance on AI is lower than most participants. AI may still be useful, but your responses suggest you retain a relatively independent working rhythm when tools are unavailable.",
        },
        "trust": {
            "high": "Your trust in AI outputs is higher than most participants. This suggests you have developed working confidence in AI, which can make collaboration smoother but also makes your verification rhythm more important.",
            "middle": "Your trust sits close to the benchmark range. You appear to use AI with a balanced level of confidence, neither rejecting its outputs quickly nor accepting them without some internal judgement.",
            "low": "Your trust in AI outputs is lower than most participants. This suggests you keep more distance from AI recommendations, which can protect judgement but may also limit how readily you use AI as a collaborator.",
        },
        "verification": {
            "high": "Your verification behaviour is stronger than most participants. This suggests you place value on checking AI outputs before using them, which can protect accuracy while adding more cognitive effort to the process.",
            "middle": "Your verification sits close to the benchmark range. You appear to check AI outputs selectively, using scrutiny when it feels warranted rather than treating every answer the same way.",
            "low": "Your verification behaviour is lower than most participants. This suggests AI outputs may move into use with relatively little checking, making trust, context, and stakes especially important in how you work with AI.",
        },
        "decision_delegation": {
            "high": "Your decision delegation is higher than most participants. This suggests AI has become involved not only in information gathering, but in shaping choices and recommendations that you are willing to act on.",
            "middle": "Your decision delegation sits close to the benchmark range. AI appears to support some choices without fully taking over the decision process, leaving room for situational judgement.",
            "low": "Your decision delegation is lower than most participants. This suggests you may use AI for input while keeping final authority firmly with yourself, especially when decisions carry personal or practical weight.",
        },
        "human_agency": {
            "high": "Your sense of agency is stronger than most participants. This suggests you experience AI as something you direct, rather than something that quietly takes over your decisions or sense of authorship.",
            "middle": "Your agency sits close to the benchmark range. You appear to retain a reasonable sense of control while still allowing AI to shape parts of your thinking and decision process.",
            "low": "Your sense of agency is lower than most participants. This does not mean loss of identity; it suggests the process of deciding may feel more influenced by AI systems than fully self-directed.",
        },
        "emotional_regulation": {
            "high": "Your emotional use of AI is higher than most participants. This suggests AI may play a role in processing stress, uncertainty, or emotional load, making the boundary between support and substitution worth noticing.",
            "middle": "Your emotional use of AI sits close to the benchmark range. AI may offer some support or relief, but your responses do not suggest it has become the primary place you turn emotionally.",
            "low": "Your emotional use of AI is lower than most participants. This suggests you keep AI more functionally or intellectually bounded, with emotional processing likely remaining outside the AI relationship.",
        },
        "disclosure": {
            "high": "Your disclosure to AI is higher than most participants. This suggests you are relatively open with AI about personal thoughts or experiences, which can deepen usefulness while changing the boundary around what feels private.",
            "middle": "Your disclosure sits close to the benchmark range. You appear to share some personal material with AI while still keeping clear limits around what belongs in that interaction.",
            "low": "Your disclosure to AI is lower than most participants. This suggests you keep AI in a more bounded role, using it without making it a central space for personal or private expression.",
        },
        "thought_partnership": {
            "high": "Your thought partnership with AI is higher than most participants. This suggests you use AI as an active thinking partner, developing ideas through interaction rather than only asking for finished answers.",
            "middle": "Your thought partnership sits close to the benchmark range. AI appears to support parts of your thinking, but not so strongly that it becomes the main structure for how ideas develop.",
            "low": "Your thought partnership with AI is lower than most participants. This suggests you may use AI more for answers, tasks, or assistance than as a sustained space for developing your own thinking.",
        },
        "social_transparency": {
            "high": "Your social transparency is higher than most participants. This suggests you are relatively open about how AI contributes to your work or thinking, reducing the gap between actual use and what others see.",
            "middle": "Your social transparency sits close to the benchmark range. You appear neither highly private nor unusually open about AI use, with disclosure likely depending on context and audience.",
            "low": "Your social transparency is lower than most participants. This suggests your AI use may be more private or context-dependent, with a wider gap between how much you use AI and how visible that use is to others.",
        },
    }
    return (copy.get(key) or {}).get(band) or (card.get("research_insight") or card.get("insight") or "")


def position_without_percentile(item):
    return str(item.get("position") or "within the benchmark range").replace("typical", "within the benchmark range")


# -----------------------------------------------------------------------------
# Main renderer
# -----------------------------------------------------------------------------

def render_report(report_data):
    assert_report_data_contract(report_data)
    s = build_sections(report_data)
    d = report_data.get("demographics") or {}

    age = d.get("age_group", "")
    country = d.get("country_display") or country_name(d.get("country", ""))
    date = format_report_date(report_data.get("created_at"))
    deep = s.get("deep_dive") or s.get("section_12_deep_dive")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Identity & Behaviour Report — Human Clarity Institute</title>
{styles()}
</head>
<body>
{styles()}
<main class="hci-report">
  {render_opening(s.get('opening') or {}, report_data, age, country, date)}
  {render_dashboard(s.get('dashboard') or {})}
  {render_typicality(s.get('typicality') or {})}
  {render_rare(s.get('rare') or {})}
  {render_story(s.get('story') or {})}
  {render_questions(s.get('questions') or {}, d)}
  {render_distinctive(s.get('distinctive') or {})}
  {render_perception(s.get('perception') or {})}
  {render_protect(s.get('protect') or {}, report_data)}
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

def render_opening(x, report_data=None, age="", country="", date=""):
    report_data = report_data or {}
    statement = x.get("statement") or (
        "Your relationship with AI is beginning to form a behavioural pattern.\n\n"
        "This report compares that pattern with more than 10,500 participants across 21 Human Clarity Institute research studies, helping identify where your AI use is typical, where it is distinctive, and which aspects of your relationship with AI are changing most rapidly.\n\n"
        "Rather than judging behaviour as good or bad, this report maps how you currently work with AI and provides evidence you can use to make more informed decisions as that relationship evolves."
    )
    findings = x.get("findings") or ""

    return f'''
    <section class="page-section opening-section report-opening">
      <div class="brand-row opening-brand">
        <div class="brand-mark">HCI</div>
        <div>
          <div class="brand-name">Human Clarity Institute</div>
          <div class="brand-subtitle">AI Behaviour Benchmarking</div>
        </div>
      </div>

      <div class="opening-title-row">
        <div>
          <p class="eyebrow">AI Identity &amp; Behaviour Report</p>
          <h1>AI Identity &amp; Behaviour Report</h1>
        </div>
        {participant_meta(age, country, date)}
      </div>

      <div class="opening-intro">
        {paras(statement)}
      </div>

      <div class="opening-analysis">
        {section_kicker('Initial analysis')}
        <h2>What stands out immediately</h2>
        {opening_synthesis_html(findings)}
        <p class="opening-transition">Together, these patterns provide the context for the rest of the report. The next section shows how the same profile appears across the nine HCI behavioural dimensions, before later sections unpack the question-level evidence behind it.</p>
      </div>
    </section>'''

def render_dashboard(x):
    cards = ""
    for c in x.get("cards", []):
        percentile = pct(c.get("percentile"))
        key = c.get("dimension") or c.get("key") or c.get("label")
        accent = dim_accent(key)
        comps = "".join(
            f'<div class="comparison"><span>{esc(r.get("label"))}</span><strong>{esc(r.get("percentile_label") or safe_ordinal(r.get("percentile")))} percentile</strong></div>'
            for r in dashboard_comparisons(c)
        )
        cards += f"""
        <article class="dimension-card" style="--dim-accent:{esc(accent)};">
          <div class="card-topline">{esc(c.get('label')).upper()}</div>
          <p class="dimension-definition">{esc(c.get('definition'))}</p>
          <h3>{esc(safe_ordinal(percentile))} percentile</h3>
          {percentile_bar(percentile, f"{safe_ordinal(percentile)} percentile")}
          <div class="comparison-list">{comps}</div>
          <p class="insight">{esc(dashboard_insight(c))}</p>
          <p class="dimension-footnote">{esc(dashboard_count_label(c))}</p>
        </article>"""

    return f"""
    <section class="page-section dashboard-section">
      {section_kicker('Benchmark overview')}
      <h2>{esc(x.get('title') or 'Your AI Behaviour Pattern')}</h2>
      <p class="section-intro">{esc(x.get('subtitle') or 'How your profile compares across the core HCI dimensions.')}</p>
      <div class="dimension-grid">{cards or render_empty('No dimension cards were available.')}</div>
    </section>"""


def render_typicality(x):
    distinctive = list(x.get('distinctive', []) or [])
    benchmark_range = list(x.get('benchmark_range', []) or [])
    if not benchmark_range:
        benchmark_range = list(x.get('typical', []) or []) + list(x.get('moderate', []) or [])

    section_intro = (
        "Across the nine behavioural dimensions measured by HCI, this section shows where your AI behaviour differs most clearly from the benchmark population "
        "and where it remains broadly aligned. Looking across dimensions rather than individual scores reveals the overall shape of your relationship with AI."
    )

    def signal_items(items, empty, show_position=True):
        if not items:
            return f'<p class="muted">{esc(empty)}</p>'
        html = ''
        for i in items:
            key = i.get("dimension") or i.get("key") or i.get("label")
            p = pct(i.get("percentile"))
            label = compact_position_label(i)
            html += f"""
              <div class="shape-signal" style="--shape-accent:{esc(dim_accent(key))}; --shape-fill:{p}%">
                <div class="shape-signal-main">
                  <span class="shape-dot"></span>
                  <strong>{esc(i.get("label"))}</strong>
                  {f'<em>{esc(label)}</em>' if show_position else ''}
                </div>
                <div class="shape-mini-bar"><span></span></div>
              </div>"""
        return html

    distinctive_rows = signal_items(distinctive, "No dimensions fall cleanly into a strongly distinctive range.", True)
    benchmark_rows = signal_items(benchmark_range, "No dimensions sit close to the benchmark range.", False)

    return f"""
    <section class="page-section standing-section profile-shape-section">
      {section_kicker('Profile shape')}
      <h2>{esc(x.get('title') or 'The Shape of Your Profile')}</h2>
      <p class="section-intro compact">{esc(section_intro)}</p>

      <div class="profile-shape-layout">
        <article class="shape-panel shape-panel-primary">
          <h3>Strongest behavioural signals</h3>
          <p class="shape-panel-note">These dimensions carry the clearest signal in your profile.</p>
          <div class="shape-signal-list">{distinctive_rows}</div>
        </article>

        <article class="shape-panel">
          <h3>Other measured dimensions</h3>
          <p class="shape-panel-note">These sit closer to the benchmark pattern and add context.</p>
          <div class="shape-signal-list compact">{benchmark_rows}</div>
        </article>
      </div>

      <article class="profile-shape-summary">
        <h3>How these dimensions work together</h3>
        {paras(x.get('profile_shape_summary')) or render_empty('No profile shape summary was available.')}
      </article>
    </section>"""

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
        group_label = g.get("label") or ""
        group_key = g.get("key") or g.get("dimension") or group_label
        accent = dim_accent(group_key)
        cards = ""
        for idx, q in enumerate(g.get("questions", []), 1):
            answer = q.get("answer")
            try:
                ans_int = int(answer)
            except Exception:
                ans_int = None

            overall_pct = (
                q.get("percentile")
                or q.get("percentile_overall")
                or q.get("overall_percentile")
                or q.get("comparison_percentile")
            )
            age_pct = (
                q.get("percentile_age_group")
                or q.get("age_group_percentile")
                or q.get("percentile_age")
                or q.get("cohort_percentile")
            )
            if age_pct in (None, ""):
                age_pct = overall_pct

            qid = q.get("id") or q.get("question_id") or question_identifier(group_key, idx)
            rare = q.get("rarity_label") or rarity_label(overall_pct)
            scale = "".join(
                f'<span class="{"selected" if ans_int == i else ""}">{i}</span>'
                for i in range(1, 8)
            )
            cards += f"""
            <article class="question-card" style="--q-accent:{esc(accent)};">
              <div class="question-card-head">
                <span class="question-id">{esc(qid)}</span>
                <span class="rarity-pill">{esc(rare)}</span>
              </div>

              <h4>“{esc(q.get('question_text'))}”</h4>

              <div class="answer-panel">
                <div class="answer-label">Your response</div>
                <div class="answer-scale circles">{scale}</div>
                <div class="scale-label compact"><span>Strongly disagree</span><span>Strongly agree</span></div>
              </div>

              <div class="question-divider"></div>

              <h5>Everyone distribution</h5>
              {dist(q.get('distribution_everyone'), answer)}

              <div class="position-rows">
                {mini_percentile_row("Everyone", overall_pct)}
                {mini_percentile_row(f"Age {age}", age_pct)}
              </div>

              <p class="comparison-note">{esc(q.get('comparison_statement'))}</p>
            </article>"""
        groups += f"""
          <div class="question-group" style="--q-accent:{esc(accent)};">
            <h3>{esc(group_label).upper()}</h3>
            <p class="muted group-definition">{esc(g.get('definition'))}</p>
            <div class="question-grid">{cards}</div>
          </div>"""

    return f"""
    <section class="page-section questions-section">
      {section_kicker('Question-level evidence')}
      <h2>{esc(x.get('title') or 'Your Question-Level Profile')}</h2>
      <p class="section-intro">{esc(x.get('subtitle') or 'How your individual responses compare with benchmark distributions.')}</p>
      {groups or render_empty('No question-level profile was available.')}
    </section>"""


def render_distinctive(x):
    cards = ""
    for q in x.get("responses", []):
        percentile = q.get('percentile')
        accent = dim_accent(q.get('dimension') or q.get('dimension_label'))
        cards += f"""
        <article class="evidence-card distinctive-card" style="--evidence-accent:{esc(accent)};">
          <div class="card-topline">{esc(q.get('dimension_label'))}</div>
          <p class="distinctive-question">“{esc(q.get('question_text'))}”</p>
          <div class="response-metric">
            <span>Your response</span>
            <div class="response-dots">{response_dots(q.get('answer'))}</div>
            <strong>{esc(q.get('answer_display'))}</strong>
          </div>
          <div class="benchmark-metric">
            <span>Higher than</span>
            <strong>{pct(percentile)} of 100 participants</strong>
          </div>
        </article>"""
    return f'<section class="page-section distinctive-section">{section_kicker("Distinctive responses")}<h2>{esc(x.get("title") or "Your Most Distinctive Responses")}</h2><div class="evidence-grid distinctive-grid">{cards or render_empty("No distinctive responses were available.")}</div><div class="narrative narrow distinctive-narrative">{paras(x.get("narrative"))}</div></section>'

def render_perception(x):
    def measured_label(item):
        p = pct(item.get('actual_percentile'))
        if p >= 71:
            return 'Higher than most people'
        if p <= 40:
            return 'Lower than most people'
        return 'Near the population centre'

    def perception_scale(item):
        p = pct(item.get('actual_percentile'))
        active_count = max(1, round(p / 5))
        dots = ''.join(f'<span class="{"active" if i <= active_count else ""}"></span>' for i in range(1, 21))
        return (f'<div class="perception-scale" style="--perception-position:{p}%">'
                f'<div class="perception-scale-label perception-scale-label-you">You<br><strong>{esc(safe_ordinal(p))} percentile</strong></div>'
                f'<div class="perception-scale-track">{dots}<i></i></div>'
                '<div class="perception-scale-captions"><span>Lower<br>than most people</span><span>About average</span><span>Higher<br>than most people</span></div></div>')

    cards = []
    for i in x.get('self_perception', []):
        html = ''
        html += '<article class="perception-card">'
        html += '<div class="perception-card-head">'
        html += f'<span class="perception-number">{esc(i.get("index"))}</span><div>'
        html += f'<h3>{esc(i.get("area") or "AI pattern")}</h3><p>“{esc(i.get("question"))}”</p></div></div>'
        html += '<div class="perception-divider"></div>'
        html += f'<div class="perception-block perception-self-view"><span>Your perception</span><strong>{esc(i.get("answer"))}</strong></div>'
        html += '<div class="perception-block perception-measured-view"><span>Your measured pattern</span>'
        html += f'<p>{esc(i.get("measured_copy") or "Based on your responses across the assessment.")}</p>{perception_scale(i)}<strong>{esc(measured_label(i))}</strong></div>'
        html += f'<div class="perception-interpretation"><span>Interpretation</span><p>{esc(i.get("interpretation"))}</p></div>'
        html += '</article>'
        cards.append(html)
    cards = ''.join(cards)
    return f'''
    <section class="page-section perception-section">
      {section_kicker('Self-perception')}
      <h2>{esc(x.get('title') or 'How You See Yourself')}</h2>
      <p class="section-intro compact">{esc(x.get('subtitle') or 'Comparing your self-perception with your measured AI behaviour.')}</p>
      <p class="section-intro compact perception-explainer">{esc(x.get('intro') or 'This section compares what you said about yourself with the behavioural pattern created by your assessment responses.')}</p>
      <div class="perception-grid">{cards or render_empty('No self-perception answers were available.')}</div>
      <p class="perception-footnote">Your measured pattern is derived from the assessment as a whole. It reflects observable behaviour mapped to each area, not just how you feel about it from the inside.</p>
      <div class="perception-narrative-block"><h3>{esc(x.get('narrative_heading') or 'What this comparison suggests')}</h3><div class="narrative narrow">{paras(x.get('narrative'))}</div></div>
    </section>'''

def protect_badge_label(value):
    text = str(value or "").upper()
    if "HIGH" in text:
        return "HIGH"
    if "MIDDLE" in text or "CENTRE" in text or "CENTER" in text:
        return "MIDDLE"
    if "LOW" in text:
        return "LOW"
    return "CURRENT"


def render_protect(x, report_data=None):
    """Render locked What to Protect section.

    The product spec requires four capacity sections every time:
    Verification, Human Agency, Emotional Boundaries, and Thought Partnership.
    This renderer presents them as four premium briefing cards in a balanced 2 x 2 grid.
    """
    supplied = x.get("items", []) if isinstance(x, dict) else []

    def render_item(i):
        watch = "".join(
            f'<li><span>✓</span><strong>{esc(w)}</strong></li>'
            for w in i.get("watch", [])
        )
        percentile = i.get("percentile")
        pct_label = f"{esc(safe_ordinal(percentile))} percentile" if percentile not in (None, "") else ""
        badge = protect_badge_label(i.get("position_badge") or i.get("positioning"))
        title = str(i.get("title") or "")
        title = title.replace("What to Notice:", "").replace("WHAT TO NOTICE:", "").strip()
        capacity = i.get("capacity") or i.get("label") or "Capacity"

        return f'''
        <article class="protect-card premium-protect-card">
          <div class="card-topline">What to notice</div>
          <h3>{esc(title)}</h3>

          <div class="protect-capacity">
            <span>Capacity</span>
            <strong>{esc(capacity)}</strong>
          </div>

          <div class="protect-position-badge">
            <span>Your current position</span>
            <strong>{esc(badge)}</strong>
            {f'<em>{pct_label}</em>' if pct_label else ''}
          </div>

          <div class="protect-divider"></div>

          <p class="protect-intro">{esc(i.get("intro"))}</p>

          <div class="protect-divider"></div>

          <div class="protect-watch">
            <h4>Early signs to notice</h4>
            <ul>{watch}</ul>
          </div>

          <div class="protect-research-callout">
            <h4>Research insight</h4>
            <p>{esc(i.get("research"))}</p>
          </div>

          <div class="protect-closing">
            <p>{esc(i.get("closing"))}</p>
          </div>
        </article>'''

    if supplied:
        items = "".join(render_item(i) for i in supplied)
        return f'''<section class="page-section protect-section">{section_kicker("Human skills")}
          <h2>{esc(x.get("title") or "What To Protect")}</h2>
          <p class="section-intro">{esc(x.get("subtitle") or "Four capacities worth staying aware of as your AI use evolves.")}</p>
          <div class="protect-grid four">{items}</div>
        </section>'''

    dims = extract_dimension_percentiles(report_data or {})
    templates = [
        {
            "key": "verification",
            "title": "When verification becomes tiring",
            "capacity": "Verification",
            "intro": "Most people verify AI outputs before acting. Over time, however, checking can become mentally demanding, leading many people to verify only what feels important or high-risk.",
            "research": "Verification fatigue is real and common. It is not laziness — it is the cost of constant cognitive effort. The question worth noticing is whether your verification rhythm still serves your needs.",
            "watch": [
                "Noticing yourself checking less than usual",
                "Feeling relief or efficiency when you skip verification",
                "Finding it hard to care whether an output is accurate",
                "Selective checking becoming automatic",
            ],
            "closing": "You decide what level of verification matters to you.",
        },
        {
            "key": "human_agency",
            "title": "When drift happens without you choosing it",
            "capacity": "Human Agency",
            "intro": "Agency usually remains strong at the identity level, but the process can still drift. Small suggestions, defaults, and framings can quietly shape decisions before you fully notice.",
            "research": "Drift happens through convenience, not collapse. You are not losing agency overnight; the shift happens through small moments where the path of least resistance aligns with what AI suggests.",
            "watch": [
                "Accepting AI suggestions without thinking them through first",
                "Using AI defaults instead of customizing your approach",
                "Realizing AI's framing has become your first instinct",
                "Finding it harder to develop your own position before consulting AI",
            ],
            "closing": "You decide if this matters to you.",
        },
        {
            "key": "emotional_regulation",
            "title": "If emotional reliance becomes substitution",
            "capacity": "Emotional Regulation",
            "intro": "AI can offer a useful space for relief, support, or reflection. The key distinction is whether it supplements human connection or gradually begins to replace it.",
            "research": "This is not inherently a problem. For some people, AI offers a genuinely safe space that human relationships do not. The important distinction is whether AI is supplementing connection or replacing it.",
            "watch": [
                "Turning to AI before turning to people when you are struggling",
                "Preferring AI conversations to human ones for difficult feelings",
                "Finding it harder to sit with discomfort without AI input",
                "Feeling more emotionally open with AI than with people you trust",
            ],
            "closing": "You decide if emotional support from AI is right for you.",
        },
        {
            "key": "thought_partnership",
            "title": "When thinking with AI becomes thinking for you",
            "capacity": "Thought Partnership",
            "intro": "AI works best as a thinking partner: something to develop ideas with, not instead of your own thinking. The important question is whether it is challenging your thought or quietly replacing it.",
            "research": "Genuine partnership requires you to retain authorship. The clearest patterns use AI to challenge and develop thinking, not replace it. Values clarity keeps that distinction alive.",
            "watch": [
                "Defaulting to AI's framing instead of developing your own position first",
                "Struggling to think independently when AI is not available",
                "Finding it hard to disagree with AI once it has stated a position",
                "Using AI to avoid the discomfort of thinking through hard problems alone",
            ],
            "closing": "You decide if this matters to you.",
        },
    ]

    items = ""
    for t in templates:
        percentile = dims.get(t["key"])
        pos = position_band(percentile)
        t = dict(t)
        t["percentile"] = percentile
        t["positioning"] = pos
        t["position_badge"] = protect_badge_label(pos)
        items += render_item(t)

    section_title = x.get("title") if isinstance(x, dict) else ""
    section_subtitle = x.get("subtitle") if isinstance(x, dict) else ""
    return f'''<section class="page-section protect-section">{section_kicker("Human skills")}
      <h2>{esc(section_title or "What To Protect")}</h2>
      <p class="section-intro">{esc(section_subtitle or "Four capacities worth staying aware of as your AI use evolves. This section is about awareness and choice, not danger or diagnosis.")}</p>
      <div class="protect-grid four">{items}</div>
    </section>'''


def trajectory_card_percentile(item):
    return f"{esc(safe_ordinal(item.get('percentile')))} percentile"


def trajectory_research_text(item):
    return (
        item.get("research_summary")
        or (item.get("strength_deepening") or {}).get("research")
        or item.get("research_insight")
        or "Research shows this pattern can become more fluent when it is already part of a person's AI relationship."
    )


def trajectory_deepening_text(item):
    return (
        item.get("deepening_summary")
        or (item.get("strength_deepening") or {}).get("deepening")
        or (item.get("strength_deepening") or {}).get("looks_like")
        or "The behaviour becomes easier, more fluent, and more automatic within the existing pattern."
    )


def trajectory_monitor_text(item):
    return (
        item.get("why_monitor")
        or (item.get("monitoring") or {}).get("research")
        or item.get("research_insight")
        or "This area is worth noticing because it is one of the places AI behaviour can shift quietly with repeated use."
    )


def trajectory_monitor_position(item):
    return (
        item.get("current_position")
        or item.get("positioning")
        or position_without_percentile(item)
        or "This dimension is part of your current benchmark profile."
    )


def trajectory_monitor_early_sign(item):
    return (
        item.get("early_sign")
        or (item.get("monitoring") or {}).get("early_sign")
        or "Noticing the behaviour becoming more automatic than deliberate."
    )


def render_trajectory(x):
    summary_rows = "".join(
        f'''
        <div class="trajectory-summary-row">
          <span>{esc(r.get('label'))}</span>
          <strong>{esc(r.get('position'))}</strong>
          <em>{esc(r.get('direction'))}</em>
        </div>'''
        for r in x.get("summary", [])
    )

    summary = f'''
      <article class="trajectory-summary">
        <h3>At a glance</h3>
        <div class="trajectory-summary-row trajectory-summary-head">
          <span>Pattern</span>
          <strong>Current position</strong>
          <em>Typical direction</em>
        </div>
        {summary_rows or '<p class="muted">No trajectory summary was available.</p>'}
      </article>'''

    strengths = ""
    for d in x.get("strengths_likely_to_deepen", []):
        strengths += f'''
        <article class="trajectory-card strength-card">
          <div class="card-topline">Strength likely to deepen</div>
          <h3>{esc(d.get("label"))}</h3>
          <p class="trajectory-percentile">{trajectory_card_percentile(d)}</p>

          <div class="trajectory-divider"></div>

          <h4>What research shows</h4>
          <p>{esc(trajectory_research_text(d))}</p>

          <div class="trajectory-divider"></div>

          <h4>What deepening typically looks like</h4>
          <p>{esc(trajectory_deepening_text(d))}</p>
        </article>'''

    monitors = ""
    for d in x.get("areas_worth_monitoring", []):
        monitors += f'''
        <article class="trajectory-card monitor-card">
          <div class="card-topline">Area worth monitoring</div>
          <h3>{esc(d.get("label"))}</h3>
          <p class="trajectory-percentile">{trajectory_card_percentile(d)}</p>

          <div class="trajectory-divider"></div>

          <h4>Current position</h4>
          <p>{esc(trajectory_monitor_position(d))}</p>

          <div class="trajectory-divider"></div>

          <h4>Worth noticing</h4>
          <p>{esc(trajectory_monitor_text(d))}</p>

          <div class="trajectory-divider"></div>

          <h4>Early sign</h4>
          <p>{esc(trajectory_monitor_early_sign(d))}</p>
        </article>'''

    return f'''
    <section class="page-section trajectory-section">
      {section_kicker('Trajectory')}
      <h2>{esc(x.get('title') or 'If Nothing Changes')}</h2>
      <p class="section-intro compact">{esc(x.get('subtitle') or 'Observable patterns from HCI research, not predictions or prescriptions.')}</p>

      {summary}

      <article class="trajectory-narrative-block">
        <h3>Likely to continue</h3>
        <div class="narrative narrow">{paras(x.get('likely_to_continue'))}</div>
      </article>

      <div class="trajectory-subsection">
        <h3>Strengths likely to deepen</h3>
        <p class="trajectory-note">If current patterns hold, these strengths are the most likely to become more fluent with continued exposure.</p>
        <div class="trajectory-grid">{strengths or render_empty('No strengths were available for this section.')}</div>
      </div>

      <div class="trajectory-subsection">
        <h3>Areas worth monitoring</h3>
        <p class="trajectory-note">{esc(x.get('monitoring_intro') or 'These are not concerns or predictions. They are simply the parts of a profile that research shows are most likely to shift as AI becomes more integrated into everyday life.')}</p>
        <div class="trajectory-grid">{monitors or render_empty('No monitoring areas were available for this section.')}</div>
      </div>

      <article class="trajectory-narrative-block outlook">
        <h3>Overall outlook</h3>
        <div class="narrative narrow">{paras(x.get('overall_outlook'))}</div>
      </article>
    </section>'''


def render_next(x):
    x = x if isinstance(x, dict) else {}

    action = x.get("action") or {
        "step": "STEP 1",
        "title": "Test this report with your AI",
        "intro": "Upload this full report to whichever AI you use most.",
        "prompt_label": "Ask your AI",
        "prompt": "Does this report ring true to how we work together? Where does it match your sense of how I use you? Where does it miss?",
        "reflection_intro": "Then simply compare:",
        "reflection_points": ["What AI agrees with", "What surprises you", "What you disagree with"],
        "privacy_note": "Your data stays with you. Nothing from that conversation returns to HCI.",
    }
    awareness = x.get("awareness") or {
        "title": "What This Awareness Does",
        "body": [
            "Awareness creates clarity. Clarity makes intentional choices possible.",
            "This report shows where you sit — how you use AI, what you rely on it for, where you are distinctive, and where you are typical. That positioning is neutral. What matters is what you do with it.",
            "The people who flourish with AI are the ones who stay aware of their own pattern and adjust their relationship as it evolves — not through willpower or rigid rules, but through genuine understanding of what serves them.",
        ],
    }
    alignment = x.get("alignment") or {
        "title": "Stay Aligned With Your Pattern",
        "body": [
            "Return to this assessment whenever your relationship with AI feels like it has shifted significantly.",
            "Retesting lets you notice what has actually changed in your pattern, not only what you think has changed. It is the clearest way to stay within the boundaries that help you flourish.",
        ],
    }
    mirror = x.get("mirror") or {
        "title": "This Report As A Mirror",
        "intro": "This report is intended to be a mirror rather than a judgement.",
        "points": ["your benchmark positioning", "your distinctive patterns", "your behavioural relationships"],
        "closing": "What you do with that clarity is entirely yours.",
    }

    reflection_points = "".join(f"<li>{esc(p)}</li>" for p in action.get("reflection_points", []))
    awareness_paras = "".join(f"<p>{esc(p)}</p>" for p in awareness.get("body", []))
    alignment_paras = "".join(f"<p>{esc(p)}</p>" for p in alignment.get("body", []))
    mirror_points = "".join(f"<li>{esc(p)}</li>" for p in mirror.get("points", []))

    return f'''
    <section class="page-section next-section">
      {section_kicker("Next steps")}
      <h2>{esc(x.get("title") or "Your Next Steps")}</h2>
      <p class="section-intro compact">{esc(x.get("subtitle") or "Use this report as a mirror for awareness, clarity, and choice.")}</p>

      <article class="next-action-card">
        <div class="next-step-label">{esc(action.get("step") or "STEP 1")}</div>
        <h3>{esc(action.get("title") or "Test this report with your AI")}</h3>
        <p>{esc(action.get("intro"))}</p>

        <div class="ai-prompt-callout">
          <span>{esc(action.get("prompt_label") or "Ask your AI")}</span>
          <blockquote>“{esc(action.get("prompt"))}”</blockquote>
        </div>

        <div class="next-compare">
          <p>{esc(action.get("reflection_intro") or "Then simply compare:")}</p>
          <ul>{reflection_points}</ul>
        </div>

        <p class="next-privacy-note">{esc(action.get("privacy_note"))}</p>
      </article>

      <div class="next-component-grid">
        <article class="next-component">
          <h3>{esc(awareness.get("title") or "What This Awareness Does")}</h3>
          {awareness_paras}
        </article>

        <article class="next-component">
          <h3>{esc(alignment.get("title") or "Stay Aligned With Your Pattern")}</h3>
          {alignment_paras}
        </article>
      </div>

      <article class="next-mirror-card">
        <h3>{esc(mirror.get("title") or "This Report As A Mirror")}</h3>
        <p>{esc(mirror.get("intro"))}</p>
        <ul>{mirror_points}</ul>
        <p class="mirror-closing">{esc(mirror.get("closing"))}</p>
      </article>

      <div class="next-final-brand">
        <div class="next-brand-rule"></div>
        <strong>Human Clarity Institute</strong>
        <span>AI Behaviour Benchmarking</span>
      </div>
    </section>'''

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
.dimension-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.dimension-card,.evidence-card,.split-card,.question-card,.protect-card{border:1px solid var(--line);background:#fff;padding:24px;break-inside:avoid;page-break-inside:avoid}.dimension-card{min-height:0;display:flex;flex-direction:column;padding:20px 20px 18px;border-left:3px solid var(--dim-accent,var(--accent))}.dimension-card .card-topline{color:var(--dim-accent,var(--accent));margin-bottom:8px}.dimension-card h3{margin:8px 0 0;font-size:19px;color:#101828}.dimension-definition{color:#667085;font-size:13px;line-height:1.42;margin:0 0 8px}.insight{color:#475467;font-size:13px;line-height:1.45;margin-top:auto;padding-top:11px;border-top:1px solid var(--line)}.dimension-footnote{margin:10px 0 0;color:#98A2B3;font-size:10.5px;line-height:1.35}
.percentile-block{margin:14px 0}.percentile-meta{display:block;text-align:right;color:var(--muted);font-size:12px}.percentile-meta span{display:none}.percentile-meta strong{color:var(--dim-accent,var(--accent-dark));font-size:13px}.percentile-track{height:6px;background:#eef2f6;border-radius:20px;position:relative;margin-top:7px}.percentile-fill{display:block;height:100%;background:var(--dim-accent,var(--accent));border-radius:20px}.percentile-marker{position:absolute;top:50%;width:13px;height:13px;background:#fff;border:3px solid var(--dim-accent,var(--accent));border-radius:50%;transform:translate(-50%,-50%)}
.comparison-list{display:grid;gap:6px;margin:12px 0}.comparison,.evidence-meta,.typical-row{display:flex;justify-content:space-between;gap:18px;border-top:1px solid var(--line);padding-top:7px;color:#475467;font-size:13px}.comparison strong,.evidence-meta strong,.typical-row strong{color:#101828;text-align:right}.standing-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;max-width:960px}.standing-card{border:1px solid var(--line);background:#fff;padding:22px;max-width:860px}.standing-card h3{margin-top:0;font-size:16px}.stand-list{display:grid;gap:8px;margin:12px 0 0}.stand-row{display:flex;justify-content:space-between;gap:22px;border-top:1px solid var(--line);padding-top:8px;position:relative}.stand-row:before{content:"";position:absolute;left:0;top:8px;bottom:0;width:3px;background:var(--stand-accent,var(--accent));border-radius:999px}.stand-row span{font-weight:700;padding-left:12px}.stand-row strong{color:#344054;text-align:right}.standing-section .section-intro.compact{font-size:16px;line-height:1.5;margin-bottom:18px}.profile-shape-summary{max-width:960px;margin-top:18px;background:#fbfaf7;border-left:3px solid var(--accent);padding:20px 24px}.profile-shape-summary h3{margin:0 0 8px;font-size:16px}.profile-shape-summary p{font-size:15px;line-height:1.58;color:#344054;margin:0}.two-col{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.split-card h3{margin-top:0}.rarity strong{font-size:20px;color:var(--accent-dark)}
.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.evidence-card p{font-size:15px;color:#344054}.protect-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;max-width:1040px}.protect-card{background:#fcfcfd}.premium-protect-card{padding:28px;display:flex;flex-direction:column;gap:0;break-inside:avoid;page-break-inside:avoid}.premium-protect-card h3{font-family:Georgia,"Times New Roman",serif;font-size:28px;line-height:1.12;font-weight:500;margin:2px 0 18px;color:#111827}.protect-capacity{margin:0 0 16px}.protect-capacity span,.protect-position-badge span,.protect-watch h4,.protect-research-callout h4{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:var(--accent-dark);font-weight:800;margin:0 0 6px}.protect-capacity strong{display:block;font-size:15px;color:#344054}.protect-position-badge{background:#f7f9fb;border:1px solid var(--line);border-left:4px solid var(--accent);padding:14px 16px;margin:0 0 18px}.protect-position-badge strong{display:block;font-size:20px;letter-spacing:.04em;color:#111827}.protect-position-badge em{display:block;font-style:normal;font-size:13px;color:#475467;margin-top:2px}.protect-divider{border-top:1px solid var(--line);margin:18px 0}.protect-intro{font-size:15px;line-height:1.58;color:#344054;margin:0}.protect-watch ul{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:9px}.protect-watch li{display:flex;gap:9px;align-items:flex-start;margin:0;color:#344054;font-size:14px;line-height:1.45}.protect-watch li span{color:var(--accent-dark);font-weight:800;line-height:1.2}.protect-watch li strong{font-weight:500;color:#344054}.protect-research-callout{background:var(--cream);border-left:3px solid var(--accent);padding:15px 16px;margin-top:18px}.protect-research-callout p{font-size:14px;line-height:1.55;color:#344054;margin:0}.protect-closing{border-top:1px solid var(--line);margin-top:18px;padding-top:14px}.protect-closing p{font-size:14px;line-height:1.5;color:#344054;margin:0}ul{margin:8px 0 0 20px;padding:0}li{margin-bottom:8px}
.question-group{margin-top:40px}.group-definition{max-width:820px}.question-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.question-card h4{font-size:16px;color:#111827}.answer{color:#344054}.scale{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin:12px 0 6px}.scale span{text-align:center;border:1px solid var(--line-strong);padding:7px 0;font-size:12px;color:#475467}.scale .selected{background:var(--accent-dark);border-color:var(--accent-dark);color:#fff;font-weight:700}.scale-label{display:flex;justify-content:space-between;color:var(--muted);font-size:11px}.histogram-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:8px}.dist{height:112px;display:flex;align-items:flex-end;gap:7px;background:#f9fafb;border:1px solid var(--line);padding:26px 10px 22px;border-radius:2px}.dist-bar{flex:1;background:#cfd6df;position:relative;min-height:4px;border-radius:2px 2px 0 0}.dist-bar.answer{background:var(--accent-dark)}.dist-value{position:absolute;top:-19px;left:50%;transform:translateX(-50%);font-size:10px;color:#475467}.dist-index{position:absolute;bottom:-19px;left:50%;transform:translateX(-50%);font-size:10px;color:#667085}.dist-empty{background:#f2f4f7;border:1px solid var(--line);padding:14px;color:var(--muted);font-size:13px}.comparison-note{font-size:14px;color:#475467;margin-top:14px}.empty-state{background:#f9fafb;border:1px dashed var(--line-strong);padding:18px;color:var(--muted)}

/* Section 10: If Nothing Changes */
.trajectory-section .section-intro.compact{font-size:16px;line-height:1.5;margin-bottom:20px}
.trajectory-summary{max-width:960px;background:#fff;border:1px solid var(--line);padding:22px 24px;margin:24px 0 34px}
.trajectory-summary h3{margin:0 0 14px;font-size:18px}
.trajectory-summary-row{display:grid;grid-template-columns:1.2fr .8fr 1fr;gap:18px;align-items:center;border-top:1px solid var(--line);padding:11px 0;color:#344054}
.trajectory-summary-row:first-of-type{border-top:0}
.trajectory-summary-row span{font-weight:700;color:#111827}
.trajectory-summary-row strong{font-size:14px;color:#344054}
.trajectory-summary-row em{font-style:normal;color:#475467;font-size:14px;text-align:right}
.trajectory-summary-head{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#667085;padding-top:0}
.trajectory-summary-head span,.trajectory-summary-head strong,.trajectory-summary-head em{font-size:11px;color:#667085;font-weight:700}
.trajectory-narrative-block{max-width:900px;margin:38px 0}
.trajectory-narrative-block h3,.trajectory-subsection h3{font-family:Georgia,"Times New Roman",serif;font-size:28px;font-weight:500;margin:0 0 12px;color:#111827}
.trajectory-narrative-block .narrative p{font-size:17px;line-height:1.62;color:#253044}
.trajectory-subsection{margin-top:42px}
.trajectory-note{max-width:820px;color:#475467;font-size:15px;margin:0 0 18px}
.trajectory-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;max-width:1040px}
.trajectory-card{background:#fff;border:1px solid var(--line);padding:24px;break-inside:avoid;page-break-inside:avoid;box-shadow:0 1px 0 rgba(16,24,40,.04)}
.trajectory-card h3{font-family:Georgia,"Times New Roman",serif;font-size:26px;font-weight:500;margin:2px 0 4px;color:#111827}
.trajectory-percentile{font-size:15px;font-weight:700;color:#344054;margin:0 0 16px}
.trajectory-divider{border-top:1px solid var(--line);margin:18px 0}
.trajectory-card h4{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#174EA6;margin:0 0 8px}
.trajectory-card p{font-size:15px;line-height:1.58;color:#344054;margin:0}
.trajectory-narrative-block.outlook{background:var(--cream);border-left:3px solid var(--accent);padding:24px 28px;margin-top:44px}
.trajectory-narrative-block.outlook h3{font-size:26px}

.deep-dive{background:#101828;color:#fff;padding:42px}.deep-dive h2,.deep-dive h3{color:#fff}.deep-dive .section-kicker{color:#9cc2ff}.deep-dive p{color:#e4e7ec}.quality{background:#fff7ed;border:1px solid #fed7aa;padding:20px}.report-footer{border-top:1px solid var(--line);padding-top:24px;color:var(--muted);font-size:13px}

/* V1 structure fixes */
.hci-report .protect-grid.four{grid-template-columns:repeat(2,minmax(0,1fr))}
.hci-report .dimension-card,
.hci-report .evidence-card,
.hci-report .split-card,
.hci-report .question-card,
.hci-report .protect-card{box-shadow:0 1px 0 rgba(16,24,40,.04)}
.hci-report .question-card{padding:22px}
.hci-report .dist-bar{transition:none}
.hci-report .dist-value{white-space:nowrap}
.hci-report .protect-card h4{margin-top:18px}

/* Section 11 — premium closing */
.hci-report .next-section{
  margin-top:18px;
  margin-bottom:96px;
}
.hci-report .next-section h2{
  margin-bottom:10px;
}
.hci-report .next-action-card{
  border:1px solid var(--line);
  background:#fcfcfd;
  padding:34px 36px;
  margin-top:28px;
  margin-bottom:26px;
  break-inside:avoid;
  page-break-inside:avoid;
}
.hci-report .next-step-label{
  color:var(--accent-dark);
  font-size:11px;
  font-weight:800;
  letter-spacing:.14em;
  text-transform:uppercase;
  margin-bottom:12px;
}
.hci-report .next-action-card h3,
.hci-report .next-component h3,
.hci-report .next-mirror-card h3{
  font-family:Georgia,"Times New Roman",serif;
  font-weight:500;
  letter-spacing:-.02em;
  margin:0 0 14px;
}
.hci-report .next-action-card h3{
  font-size:30px;
  line-height:1.14;
}
.hci-report .ai-prompt-callout{
  margin:26px 0;
  padding:24px 26px;
  background:#fff;
  border-left:3px solid var(--accent);
  box-shadow:0 1px 0 rgba(16,24,40,.04);
}
.hci-report .ai-prompt-callout span{
  display:block;
  color:var(--accent-dark);
  font-size:11px;
  font-weight:800;
  letter-spacing:.13em;
  text-transform:uppercase;
  margin-bottom:10px;
}
.hci-report .ai-prompt-callout blockquote{
  margin:0;
  font-family:Georgia,"Times New Roman",serif;
  font-size:24px;
  line-height:1.36;
  letter-spacing:-.015em;
  color:#101828;
}
.hci-report .next-compare{
  margin-top:8px;
}
.hci-report .next-compare p{
  margin-bottom:8px;
  color:#344054;
  font-weight:700;
}
.hci-report .next-compare ul,
.hci-report .next-mirror-card ul{
  margin:0;
  padding-left:20px;
}
.hci-report .next-privacy-note{
  margin-top:22px;
  padding-top:18px;
  border-top:1px solid var(--line);
  color:#667085;
  font-size:14px;
}
.hci-report .next-component-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:22px;
  margin-top:24px;
}
.hci-report .next-component{
  border:1px solid var(--line);
  background:#fff;
  padding:28px;
  break-inside:avoid;
  page-break-inside:avoid;
}
.hci-report .next-component h3{
  font-size:25px;
  line-height:1.18;
}
.hci-report .next-component p{
  color:#344054;
  font-size:15px;
}
.hci-report .next-mirror-card{
  margin-top:26px;
  padding:34px 38px;
  background:var(--cream);
  border:1px solid var(--line);
  text-align:left;
  break-inside:avoid;
  page-break-inside:avoid;
}
.hci-report .next-mirror-card h3{
  font-size:30px;
  line-height:1.16;
}
.hci-report .next-mirror-card p{
  max-width:760px;
  color:#344054;
}
.hci-report .next-mirror-card ul{
  margin-top:12px;
  margin-bottom:18px;
  color:#344054;
}
.hci-report .mirror-closing{
  margin-top:18px;
  font-family:Georgia,"Times New Roman",serif;
  font-size:24px;
  line-height:1.35;
  color:#101828!important;
}
.hci-report .next-final-brand{
  margin-top:54px;
  text-align:center;
  color:#667085;
}
.hci-report .next-brand-rule{
  width:160px;
  height:1px;
  background:var(--line-strong);
  margin:0 auto 22px;
}
.hci-report .next-final-brand strong{
  display:block;
  font-size:13px;
  letter-spacing:.12em;
  text-transform:uppercase;
  color:#101828;
}
.hci-report .next-final-brand span{
  display:block;
  margin-top:4px;
  font-size:12px;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.hci-report .report-footer{
  margin-top:34px;
  padding-top:22px;
  color:#98A2B3;
}




/* Opening section V2 — editorial HCI report opening */
.hci-report .report-opening{
  margin-bottom:58px;
  padding-bottom:38px;
  border-bottom:1px solid var(--line);
}
.hci-report .opening-brand{margin-bottom:34px}
.hci-report .opening-title-row{
  display:grid;
  grid-template-columns:minmax(0,1fr) auto;
  gap:28px;
  align-items:start;
  margin-bottom:24px;
}
.hci-report .opening-title-row h1{
  font-size:48px;
  line-height:1.04;
  letter-spacing:-.04em;
  margin:0;
  max-width:760px;
}
.hci-report .participant-meta{
  align-self:start;
  display:flex;
  flex-wrap:wrap;
  justify-content:flex-end;
  gap:7px;
  max-width:420px;
  color:#667085;
  font-size:11px;
  line-height:1.5;
  padding-top:6px;
}
.hci-report .participant-meta-label{
  width:100%;
  text-align:right;
  text-transform:uppercase;
  letter-spacing:.12em;
  font-size:10px;
  font-weight:800;
  color:#98A2B3;
  margin-bottom:2px;
}
.hci-report .participant-meta strong{
  color:#667085;
  font-weight:700;
}
.hci-report .meta-sep{color:#D0D5DD}
.hci-report .opening-intro{
  max-width:840px;
  margin:0 0 34px 0;
  padding-bottom:26px;
  border-bottom:1px solid var(--line);
}
.hci-report .opening-intro p{
  font-size:16px;
  line-height:1.58;
  color:#344054;
  margin-bottom:12px;
}
.hci-report .opening-intro p:first-child{
  font-family:Georgia,"Times New Roman",serif;
  font-size:24px;
  line-height:1.28;
  letter-spacing:-.012em;
  color:#101828;
  margin-bottom:14px;
}
.hci-report .opening-analysis{
  max-width:900px;
}
.hci-report .opening-analysis h2{
  margin-bottom:16px;
}
.hci-report .opening-synthesis{
  max-width:840px;
  padding-left:22px;
  border-left:3px solid var(--accent);
}
.hci-report .opening-synthesis h3{
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
  font-size:15px;
  line-height:1.35;
  letter-spacing:.01em;
  font-weight:900;
  color:#0f2f63;
  margin:22px 0 8px;
}
.hci-report .opening-synthesis h3:first-child{margin-top:0}
.hci-report .opening-synthesis p{
  font-size:16px;
  line-height:1.62;
  color:#253044;
  margin-bottom:16px;
}
.hci-report .opening-transition{
  margin:26px 0 0;
  max-width:840px;
  color:#344054;
  font-size:15px;
  line-height:1.58;
  padding:16px 18px;
  background:#fbfaf7;
  border-left:3px solid var(--accent);
}
@media(max-width:900px){
  .hci-report .opening-title-row{grid-template-columns:1fr}
  .hci-report .participant-meta{justify-content:flex-start;max-width:none}
  .hci-report .participant-meta-label{text-align:left}
}

/* Section 6 locked V1 — premium benchmark intelligence cards */
.hci-report .questions-section{break-inside:auto;page-break-inside:auto}
.hci-report .question-group{margin-top:38px;break-inside:auto;page-break-inside:auto}
.hci-report .question-group>h3{
  color:var(--q-accent);
  font-size:15px;
  letter-spacing:.12em;
  text-transform:uppercase;
  margin:0 0 4px 0;
}
.hci-report .question-group .group-definition{font-size:14px;margin-bottom:18px}
.hci-report .question-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.hci-report .question-card{
  padding:20px;
  min-height:0;
  border:1px solid var(--line);
  background:#fff;
  box-shadow:0 1px 0 rgba(16,24,40,.04);
}
.hci-report .question-card-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin-bottom:16px;
}
.hci-report .question-id{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:28px;
  height:24px;
  padding:0 7px;
  border-radius:5px;
  background:#f2f4f7;
  color:#344054;
  font-size:12px;
  font-weight:700;
}
.hci-report .rarity-pill{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  border-radius:999px;
  padding:5px 10px;
  background:color-mix(in srgb, var(--q-accent) 10%, white);
  border:1px solid color-mix(in srgb, var(--q-accent) 22%, white);
  color:var(--q-accent);
  font-size:10px;
  line-height:1;
  font-weight:800;
  letter-spacing:.08em;
  text-transform:uppercase;
  white-space:nowrap;
}
.hci-report .question-card h4{
  font-family:Georgia,"Times New Roman",serif;
  font-size:18px;
  line-height:1.35;
  letter-spacing:-.01em;
  color:#0b1220;
  margin:0 0 22px 0;
}
.hci-report .answer-panel{
  width:58%;
  min-width:285px;
  max-width:360px;
  margin:0 0 18px 0;
}
.hci-report .answer-label{
  color:#475467;
  font-size:10px;
  font-weight:800;
  letter-spacing:.13em;
  text-transform:uppercase;
  margin-bottom:10px;
}
.hci-report .answer-scale.circles{
  display:grid;
  grid-template-columns:repeat(7,32px);
  gap:11px;
  align-items:center;
  margin:0 0 5px 0;
}
.hci-report .answer-scale.circles span{
  width:32px;
  height:32px;
  display:flex;
  align-items:center;
  justify-content:center;
  border-radius:50%;
  border:1px solid #d0d5dd;
  background:#fff;
  color:#344054;
  font-size:13px;
  font-weight:600;
  padding:0;
}
.hci-report .answer-scale.circles .selected{
  background:var(--q-accent);
  border-color:var(--q-accent);
  color:#fff;
  box-shadow:0 4px 10px rgba(23,78,166,.16);
}
.hci-report .scale-label.compact{
  width:100%;
  max-width:330px;
  font-size:10px;
  color:#667085;
}
.hci-report .question-divider{
  height:1px;
  background:var(--line);
  margin:18px 0 18px 0;
}
.hci-report .question-card h5{
  margin:0 0 8px 0;
  color:#475467;
  font-size:10px;
  letter-spacing:.13em;
}
.hci-report .question-card .dist{
  height:94px;
  padding:22px 9px 20px;
  background:#fafbfc;
  border:1px solid var(--line);
  gap:7px;
  margin-bottom:14px;
}
.hci-report .question-card .dist-bar{background:#cfd6df}
.hci-report .question-card .dist-bar.answer{background:var(--q-accent)}
.hci-report .question-card .dist-value{font-size:9px;color:#344054;top:-18px}
.hci-report .question-card .dist-index{font-size:9px;bottom:-17px}
.hci-report .position-rows{
  display:grid;
  gap:7px;
  padding-top:4px;
}
.hci-report .mini-position-row{
  display:grid;
  grid-template-columns:105px minmax(120px,1fr) 54px;
  gap:9px;
  align-items:center;
}
.hci-report .mini-position-row span{
  font-size:11px;
  color:#475467;
}
.hci-report .mini-position-row strong{
  font-size:11px;
  text-align:right;
  color:#0f2f63;
  font-weight:800;
}
.hci-report .mini-track{
  height:6px;
  background:#eef2f6;
  border-radius:999px;
  position:relative;
}
.hci-report .mini-track:before{
  content:"";
  position:absolute;
  left:0;
  top:0;
  bottom:0;
  width:var(--mini-fill,100%);
  max-width:100%;
  background:var(--q-accent);
  border-radius:999px;
  opacity:.92;
}
.hci-report .mini-track i{
  position:absolute;
  top:50%;
  width:12px;
  height:12px;
  background:#fff;
  border:2px solid var(--q-accent);
  border-radius:50%;
  transform:translate(-50%,-50%);
  z-index:2;
}
.hci-report .comparison-note{
  margin:12px 0 0;
  padding-top:11px;
  border-top:1px solid var(--line);
  font-size:12px;
  line-height:1.45;
  color:#344054;
}



/* Profile Shape V2 — summary, not repeated table */
.hci-report .profile-shape-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;max-width:960px;margin-top:20px}
.hci-report .shape-panel{border:1px solid var(--line);background:#fff;padding:22px}
.hci-report .shape-panel h3{margin:0 0 6px;font-size:16px;color:#101828}
.hci-report .shape-panel-note{margin:0 0 16px;color:#667085;font-size:13px;line-height:1.45}
.hci-report .shape-signal-list{display:grid;gap:13px}.hci-report .shape-signal-list.compact{gap:11px}.hci-report .shape-signal{display:grid;gap:7px}
.hci-report .shape-signal-main{display:flex;align-items:center;gap:10px;min-height:23px}.hci-report .shape-dot{width:4px;height:22px;border-radius:999px;background:var(--shape-accent,var(--accent));display:inline-block;flex:0 0 auto}
.hci-report .shape-signal-main strong{font-size:15px;color:#101828}.hci-report .shape-signal-main em{margin-left:auto;font-style:normal;font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:800;color:#475467;background:#f8fafc;border:1px solid var(--line);border-radius:999px;padding:4px 8px;white-space:nowrap}
.hci-report .shape-mini-bar{height:5px;background:#eef2f6;border-radius:999px;overflow:hidden;margin-left:14px}.hci-report .shape-mini-bar span{display:block;height:100%;width:var(--shape-fill,50%);background:var(--shape-accent,var(--accent));border-radius:999px;opacity:.9}
.hci-report .shape-signal-list.compact .shape-mini-bar{display:none}.hci-report .shape-signal-list.compact .shape-signal-main{border-top:1px solid var(--line);padding-top:9px}.hci-report .shape-signal-list.compact .shape-signal:first-child .shape-signal-main{border-top:0;padding-top:0}



/* Section 8 — Perception Gap rebuilt: perception vs measured pattern */
.hci-report .perception-section{padding-top:72px}.hci-report .perception-explainer{max-width:860px;margin-top:18px;color:#253044}.hci-report .perception-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px;max-width:1160px;margin-top:34px}.hci-report .perception-card{background:#fff;border:1px solid var(--line);box-shadow:0 12px 30px rgba(16,24,40,.04);padding:28px 28px 30px;min-height:520px;display:flex;flex-direction:column}.hci-report .perception-card-head{display:flex;gap:16px;align-items:flex-start}.hci-report .perception-number{flex:0 0 auto;width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--accent);color:#fff;font-weight:800;font-size:15px;box-shadow:0 8px 18px rgba(0,94,112,.18)}.hci-report .perception-card-head h3{margin:2px 0 7px;font-size:22px;color:#101828;letter-spacing:-.01em}.hci-report .perception-card-head p{margin:0;font-size:15px;line-height:1.45;color:#253044}.hci-report .perception-divider{height:1px;background:var(--line);margin:24px 0 22px}.hci-report .perception-block{padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid rgba(208,213,221,.75)}.hci-report .perception-block span,.hci-report .perception-interpretation span{display:block;font-size:11px;line-height:1.2;letter-spacing:.13em;text-transform:uppercase;color:#005e70;font-weight:900;margin-bottom:10px}.hci-report .perception-self-view strong{display:block;background:#fbfaf7;border:1px solid var(--line);border-radius:8px;padding:15px 16px;font-size:16px;line-height:1.35;color:#101828}.hci-report .perception-measured-view p{margin:0 0 18px;font-size:14px;line-height:1.55;color:#253044}.hci-report .perception-measured-view > strong{display:block;margin-top:16px;font-size:16px;color:#101828}.hci-report .perception-scale{position:relative;padding-top:32px;margin-top:4px}.hci-report .perception-scale-label-you{position:absolute;left:var(--perception-position);top:0;transform:translateX(-50%);font-size:12px;line-height:1.15;color:#005e70;text-align:center;font-weight:800;white-space:nowrap}.hci-report .perception-scale-label-you strong{font-size:12px;color:#253044;font-weight:700}.hci-report .perception-scale-track{position:relative;display:flex;align-items:center;justify-content:space-between;height:28px}.hci-report .perception-scale-track:before{content:"";position:absolute;left:0;right:0;top:50%;height:2px;background:#d0d5dd;transform:translateY(-50%)}.hci-report .perception-scale-track span{position:relative;z-index:1;width:7px;height:7px;border-radius:50%;background:#d0d5dd}.hci-report .perception-scale-track span.active{background:#0f7d87}.hci-report .perception-scale-track i{position:absolute;z-index:3;left:var(--perception-position);top:50%;width:24px;height:24px;border-radius:50%;background:#0f7d87;border:3px solid #fff;box-shadow:0 4px 14px rgba(0,94,112,.28);transform:translate(-50%,-50%)}.hci-report .perception-scale-captions{display:flex;justify-content:space-between;gap:12px;margin-top:8px;font-size:12px;line-height:1.35;color:#475467}.hci-report .perception-scale-captions span:nth-child(2){text-align:center}.hci-report .perception-scale-captions span:nth-child(3){text-align:right}.hci-report .perception-interpretation{margin-top:auto;padding-top:4px}.hci-report .perception-interpretation p{margin:0;font-size:15px;line-height:1.55;color:#101828}.hci-report .perception-footnote{max-width:980px;margin:24px 0 0;padding-left:22px;border-left:3px solid rgba(0,94,112,.28);font-size:13px;line-height:1.55;color:#667085}.hci-report .perception-narrative-block{margin-top:58px}.hci-report .perception-narrative-block h3{margin:0 0 18px;font-size:22px;color:#101828}@media(max-width:1000px){.hci-report .perception-grid{grid-template-columns:1fr}.hci-report .perception-card{min-height:0}}

/* Distinctive responses V2 */
.hci-report .distinctive-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.hci-report .distinctive-card{border-left:3px solid var(--evidence-accent,var(--accent));padding:22px 23px;display:flex;flex-direction:column;min-height:230px}.hci-report .distinctive-card .card-topline{color:var(--evidence-accent,var(--accent));margin-bottom:14px}
.hci-report .distinctive-question{font-size:15px;line-height:1.5;color:#253044;margin:0 0 18px;min-height:68px}.hci-report .response-metric{border-top:1px solid var(--line);padding-top:12px;display:grid;grid-template-columns:1fr auto;gap:7px 12px;align-items:center;margin-top:auto}
.hci-report .response-metric span,.hci-report .benchmark-metric span{font-size:11px;color:#667085;text-transform:uppercase;letter-spacing:.08em;font-weight:700}.hci-report .response-metric strong{font-size:13px;color:#101828;text-align:right}.hci-report .response-dots{display:flex;gap:5px;grid-column:1/2}.hci-report .response-dots span{width:9px;height:9px;border-radius:50%;border:1px solid color-mix(in srgb, var(--evidence-accent) 35%, #d0d5dd);background:#fff}.hci-report .response-dots span.filled{background:var(--evidence-accent,var(--accent));border-color:var(--evidence-accent,var(--accent))}
.hci-report .benchmark-metric{border-top:1px solid var(--line);padding-top:10px;margin-top:10px;display:flex;justify-content:space-between;gap:14px;align-items:baseline}.hci-report .benchmark-metric strong{font-size:13px;color:#101828;text-align:right}.hci-report .distinctive-narrative{margin-top:28px}.hci-report .distinctive-narrative p{font-size:15.5px;line-height:1.58}

@media(max-width:900px){.hci-report .protect-grid.four{grid-template-columns:1fr}}

@media(max-width:900px){.hci-report{padding:36px 22px}.cover-grid,.dimension-grid,.standing-grid,.profile-shape-layout,.two-col,.evidence-grid,.distinctive-grid,.protect-grid,.question-grid,.histogram-grid{grid-template-columns:1fr}h1{font-size:44px}h2{font-size:30px}.brand-row{margin-bottom:42px}}
@media print{body{background:#fff}.hci-report{max-width:none;padding:34px}.page-section{break-inside:avoid;page-break-inside:avoid;margin-bottom:42px}.dimension-grid{grid-template-columns:repeat(3,1fr);gap:14px}.profile-shape-layout{gap:14px}.shape-panel{padding:17px}.distinctive-grid{gap:14px}.distinctive-card{padding:17px;min-height:200px}.dimension-card{padding:17px 17px 15px}.percentile-block{margin:11px 0}.insight{font-size:12.5px}.dimension-definition{font-size:12.5px}.question-grid{grid-template-columns:repeat(2,1fr)}.cover-panel,.dimension-card,.evidence-card,.split-card,.question-card,.protect-card{box-shadow:none}a{color:inherit}}
</style>'''
