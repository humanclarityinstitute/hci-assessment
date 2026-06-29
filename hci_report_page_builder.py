"""
hci_report_page_builder.py

Builds professional HTML report pages from report_dict output.
Used for both PDF generation (via PDFShift) and browser display.

Takes the report_dict structure from report_generator.py and converts it
to formatted HTML using locked design tokens from hci-report-design.css.
"""

import json
from typing import Dict, Any, Optional
from question_metadata import (
    QUESTION_MAP,
    get_question_text,
    get_dimension,
    DIMENSIONS,
    PERCEPTION_QUESTIONS,
    get_perception_text,
    DEMOGRAPHIC_QUESTIONS,
    get_demographic_text,
    is_perception_question,
    is_demographic_question,
    is_assessment_question
)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def format_prose(text: str) -> str:
    """Convert prose text to HTML paragraphs."""
    if not text:
        return ""
    
    paragraphs = text.strip().split('\n\n')
    html = ""
    for para in paragraphs:
        if para.strip():
            html += f'<p class="narrative-paragraph">{escape_html(para.strip())}</p>'
    return html


def plain_english_percentile(p: Optional[int]) -> str:
    """Convert percentile to plain English."""
    if p is None or p == '':
        return "at the population centre"
    
    try:
        p = int(p)
    except (ValueError, TypeError):
        return "at the population centre"
    
    if p >= 50:
        return f"Higher than {p} out of every 100 people"
    else:
        return f"Lower than {100-p} out of every 100 people"


def positional_label(p: Optional[int]) -> str:
    """Convert percentile to positional label."""
    if p is None or p == '':
        return "near the population centre"
    
    try:
        p = int(p)
    except (ValueError, TypeError):
        return "near the population centre"
    
    if p >= 96:
        return "exceptionally high"
    elif p >= 86:
        return "notably high"
    elif p >= 71:
        return "above the population centre"
    elif p >= 41:
        return "near the population centre"
    elif p >= 26:
        return "below the population centre"
    elif p >= 11:
        return "notably low"
    else:
        return "exceptionally low"


def format_how_typical(how_typical_data: Dict[str, Any]) -> str:
    """Format Section 3: How Typical data into HTML.
    
    Data already includes pre-written interpretation text from signals library
    (pulled by generate_how_typical in report_generator.py).
    
    Data structure (now dicts indexed by position):
    {
        'distinctive': {'0': {key, name, percentile, interpretation}, '1': {...}},
        'typical': {'0': {...}, '1': {...}},
        'moderate': {'0': {...}, '1': {...}}
    }
    """
    if not how_typical_data:
        return ""
    
    html = ""
    
    # PART 1: DISTINCTIVE AREAS
    distinctive = how_typical_data.get('distinctive', {})
    if distinctive:
        html += '<div class="how-typical-section">\n'
        html += '<h3 class="how-typical-heading">Where You\'re Distinctive</h3>\n'
        html += '<div class="how-typical-items">\n'
        
        for dim in distinctive.values():
            name = dim.get('name', 'Unknown')
            pct = dim.get('percentile', 50)
            label = positional_label(pct)
            interpretation = dim.get('interpretation', '')
            
            html += f'''<div class="how-typical-item">
    <div class="how-typical-label">{name} — {label} ({pct}th %ile)</div>
    <div class="how-typical-interpretation">{escape_html(interpretation)}</div>
</div>\n'''
        
        html += '</div>\n'
        html += '<div class="how-typical-summary">You sit notably above or below average on these dimensions. This reflects distinctive patterning in these areas of your relationship with AI.</div>\n'
        html += '</div>\n'
    
    # PART 2: TYPICAL AREAS
    typical = how_typical_data.get('typical', {})
    if typical:
        html += '<div class="how-typical-section">\n'
        html += '<h3 class="how-typical-heading">Where You\'re Typical</h3>\n'
        html += '<div class="how-typical-items">\n'
        
        for dim in typical.values():
            name = dim.get('name', 'Unknown')
            pct = dim.get('percentile', 50)
            label = positional_label(pct)
            interpretation = dim.get('interpretation', '')
            
            html += f'''<div class="how-typical-item">
    <div class="how-typical-label">{name} — {label} ({pct}th %ile)</div>
    <div class="how-typical-interpretation">{escape_html(interpretation)}</div>
</div>\n'''
        
        html += '</div>\n'
        html += '<div class="how-typical-summary">You sit in the middle range on these dimensions, meaning you move through these areas without distinctive patterning.</div>\n'
        html += '</div>\n'
    
    return html


def build_dimension_cards(dimensions: Dict[str, Any]) -> str:
    """Build HTML for dimension cards (Section 1: Dashboard)."""
    if not dimensions:
        return ""
    
    html = '<div class="dimension-grid">\n'
    
    for dim_name, dim_data in dimensions.items():
        if not isinstance(dim_data, dict):
            continue
        
        percentile = dim_data.get('percentile', 50)
        raw_score = dim_data.get('raw_score', 3.5)
        plain = plain_english_percentile(percentile)
        pos = positional_label(percentile)
        
        html += f'''
        <div class="dimension-card">
            <div class="dimension-label">{escape_html(dim_name.upper())}</div>
            <div class="dimension-name">{escape_html(dim_name.title())}</div>
            <div style="margin-bottom: 8pt; font-size: 10.5px; line-height: 1.3; color: #666;">
                {escape_html(dim_data.get('research_insight', ''))}
            </div>
            <div style="margin-bottom: 8pt;">
                <span class="score-number">{percentile}</span>
                <span style="margin-left: 6pt; font-size: 10.5px; color: #666;">percentile</span>
            </div>
            <div class="percentile-bar">
                <div class="percentile-fill" style="width: {percentile}%;"></div>
            </div>
            <div style="border-top: 0.5pt solid #e0e0e0; padding-top: 8pt; font-size: 10.5px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 3pt;">
                    <span style="color: #666;">Your position</span>
                    <span style="font-weight: 500; color: #0066cc;">{escape_html(pos)}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #666;">Plain English</span>
                    <span style="font-weight: 500; color: #0066cc; font-size: 9px;">{escape_html(plain)}</span>
                </div>
            </div>
        </div>
'''
    
    html += '</div>\n'
    return html


def build_question_profile(questions: list) -> str:
    """Build HTML for question-level profile (Section 6)."""
    if not questions or not isinstance(questions, list):
        return ""
    
    html = ""
    current_dim = ""
    
    for q in questions:
        if not isinstance(q, dict):
            continue
        
        # Add dimension header if changed
        q_dim = q.get('dimension', 'unknown')
        if q_dim != current_dim:
            if current_dim != "":
                html += "</div>\n"
            current_dim = q_dim
            html += f'<div class="question-dimension"><h3>{escape_html(q_dim.upper())}</h3>\n'
        
        # Build histogram
        distribution = q.get('distribution', [])
        bars_html = ""
        if distribution:
            max_dist = max(distribution) if distribution else 1
            for i, pct in enumerate(distribution):
                if max_dist > 0:
                    height = (pct / max_dist * 100)
                else:
                    height = 0
                bars_html += f'<div class="histogram-bar" style="height: {height}%; background: #ccc;"></div>'
        
        q_num = q.get('number', i+1)
        q_var = q.get('variable', 'unknown')
        q_answer = q.get('respondent_answer', '?')
        q_percentile = q.get('respondent_percentile', 50)
        q_position = positional_label(q_percentile)
        q_plain = plain_english_percentile(q_percentile)
        q_age_group = q.get('age_group', '25-34')
        q_age_percentile = q.get('age_percentile', 50)
        
        html += f'''
        <div class="question-card">
            <div class="question-header">
                <span class="question-number">Q{q_num}</span>
                <span class="question-key">{escape_html(q_var)}</span>
            </div>
            
            <div class="question-answer">
                <span class="answer-label">Your answer:</span>
                <span class="answer-value">{escape_html(str(q_answer))}</span>
                <span class="answer-scale">/7</span>
            </div>
            
            <div class="histogram-container">
                <div class="histogram">{bars_html}</div>
                <div class="histogram-scale">
                    <span>1</span><span>2</span><span>3</span><span>4</span><span>5</span><span>6</span><span>7</span>
                </div>
            </div>
            
            <div class="question-comparison">
                <div class="percentile-line">
                    <span class="label">Your percentile:</span>
                    <span class="value">{q_percentile}th</span>
                    <span class="position">({escape_html(q_position)})</span>
                </div>
                <div class="plain-english">{escape_html(q_plain)}</div>
                <div class="age-comparison">
                    vs {escape_html(q_age_group)}: {q_age_percentile}th percentile
                </div>
            </div>
        </div>
'''
    
    if current_dim != "":
        html += "</div>\n"
    
    return html


def build_report_html(report_dict: Dict[str, Any]) -> str:
    """
    Build complete HTML report from report_dict.
    
    Args:
        report_dict: Output from report_generator.generate_premium_report()
    
    Returns:
        str: Complete HTML string ready for PDF or display
    """
    
    if not isinstance(report_dict, dict):
        return "<p>Error: Invalid report data</p>"
    
    metadata = report_dict.get('metadata', {})
    demographics = metadata.get('demographics', {})
    
    # Extract key sections
    opening = report_dict.get('opening', '')
    section_1_dashboard = report_dict.get('section_1_dashboard', {})
    section_3_how_typical = report_dict.get('section_3_how_typical', {})
    section_4_what_different = report_dict.get('section_4_what_different', '')
    section_5_behaviour_story = report_dict.get('section_5_behaviour_story', '')
    section_6_question_profile = report_dict.get('section_6_question_profile', {})
    # DEBUG: Check what page builder received
    if section_6_question_profile and section_6_question_profile.get('questions'):
        q_list = section_6_question_profile['questions']
        print(f"[DEBUG] Page builder received section_6 with {len(q_list)} questions")
        if q_list:
            first_q = q_list[0]
            print(f"[DEBUG] First question has dimension? {'dimension' in first_q}")
            if 'dimension' in first_q:
                print(f"[DEBUG] First question dimension value: {first_q.get('dimension')}")
            print(f"[DEBUG] First question keys: {list(first_q.keys())}")
    else:
        print(f"[DEBUG] Page builder received NO section_6_question_profile or empty questions")
    section_7_distinctive_responses = report_dict.get('section_7_distinctive_responses', '')
    section_8_perception_gap = report_dict.get('section_8_perception_gap', '')
    section_10_trajectory = report_dict.get('section_10_trajectory', '')
    deep_dive = report_dict.get('deep_dive', {})
    
    # Build metadata line
    meta_parts = []
    if demographics.get('age_group'):
        meta_parts.append(escape_html(demographics['age_group']))
    if demographics.get('country'):
        meta_parts.append(escape_html(demographics['country']))
    from datetime import datetime
    meta_parts.append(datetime.now().strftime('%B %d, %Y'))
    meta_text = ' • '.join(meta_parts)
    
    # Build complete HTML
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your AI Identity Report — Human Clarity Institute</title>
    <style>
        :root {
            --font-family-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            --font-size-body: 10.5px;
            --color-primary: #0066cc;
            --color-text: #1a1a1a;
            --color-text-secondary: #666;
            --color-bg-light: #fafafa;
            --color-border: #e0e0e0;
            --spacing-lg: 12pt;
            --spacing-md: 8pt;
            --spacing-sm: 6pt;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html { font-size: 16px; }
        body {
            font-family: var(--font-family-body);
            font-size: var(--font-size-body);
            color: var(--color-text);
            background: #fff;
            line-height: 1.3;
        }
        
        .report {
            max-width: 8in;
            margin: 0 auto;
            padding: 0.5in 0.75in;
            background: #fff;
        }
        
        h1, h2, h3, h4 { font-weight: 600; margin: 0 0 var(--spacing-md) 0; }
        h1 { font-size: 16px; }
        h2 { font-size: 13px; color: var(--color-primary); }
        h3 { font-size: 12px; }
        p { margin: 0 0 var(--spacing-sm) 0; line-height: 1.3; }
        
        .report-section { margin-bottom: 20pt; }
        .section-subtitle { font-size: var(--font-size-body); color: var(--color-text-secondary); }
        
        .dimension-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16pt;
            margin-bottom: 20pt;
        }
        
        .dimension-card {
            border: 0.5pt solid var(--color-border);
            padding: 16pt;
            border-radius: 6px;
        }
        
        .dimension-label { font-size: 9px; text-transform: uppercase; color: #999; margin-bottom: 3pt; }
        .dimension-name { font-size: 12px; font-weight: 600; margin-bottom: 8pt; }
        .score-number { font-size: 18px; font-weight: 700; color: var(--color-primary); }
        .percentile-bar { width: 100%; height: 12px; background: #f5f5f5; margin-bottom: 8pt; border-radius: 2px; }
        .percentile-fill { height: 100%; background: var(--color-primary); width: 0; }
        
        .narrative { font-size: var(--font-size-body); line-height: 1.3; margin-bottom: var(--spacing-lg); }
        .narrative-paragraph { margin-bottom: var(--spacing-sm); }
        
        .divider { border: none; border-top: 0.5pt solid var(--color-border); margin: var(--spacing-lg) 0; }
        
        .question-dimension {
            margin-bottom: 24pt;
            border-top: 0.5pt solid var(--color-border);
            padding-top: 12pt;
        }
        
        .question-dimension h3 {
            font-size: 11px;
            color: var(--color-primary);
            margin-bottom: 12pt;
            text-transform: uppercase;
        }
        
        .question-card {
            margin-bottom: 16pt;
            padding: 12pt;
            border: 0.5pt solid var(--color-border);
            border-radius: 4px;
            background: #fafafa;
        }
        
        .question-header {
            display: flex;
            gap: 12pt;
            margin-bottom: 8pt;
            font-size: 9px;
        }
        
        .question-number {
            font-weight: 600;
            color: var(--color-primary);
        }
        
        .question-key {
            color: #999;
            font-style: italic;
        }
        
        .question-answer {
            display: flex;
            gap: 6pt;
            align-items: baseline;
            margin-bottom: 10pt;
            font-size: 10px;
        }
        
        .answer-label {
            color: #666;
        }
        
        .answer-value {
            font-weight: 700;
            font-size: 12px;
            color: var(--color-primary);
        }
        
        .answer-scale {
            color: #999;
            font-size: 9px;
        }
        
        .histogram-container {
            margin-bottom: 10pt;
        }
        
        .histogram {
            display: flex;
            align-items: flex-end;
            gap: 2px;
            height: 40px;
            padding: 4pt 0;
            border-bottom: 0.5pt solid var(--color-border);
        }
        
        .histogram-bar {
            flex: 1;
            min-height: 2px;
            border-radius: 1px;
        }
        
        .histogram-scale {
            display: flex;
            justify-content: space-between;
            font-size: 8px;
            color: #999;
            padding: 2pt 0;
        }
        
        .question-comparison {
            font-size: 9px;
        }
        
        .percentile-line {
            display: flex;
            gap: 8pt;
            margin-bottom: 4pt;
        }
        
        .percentile-line .label {
            color: #666;
        }
        
        .percentile-line .value {
            font-weight: 600;
            color: var(--color-primary);
        }
        
        .percentile-line .position {
            color: #999;
        }
        
        .plain-english {
            color: #666;
            margin-bottom: 4pt;
            line-height: 1.3;
        }
        
        .age-comparison {
            color: #999;
            font-size: 8px;
        }
        
        @media print {
            body { margin: 0; padding: 0; }
            .report { max-width: 100%; margin: 0; }
        }
    </style>
</head>
<body>

<div class="report">

    <div class="report-section">
        <h1>Your AI Identity Report</h1>
        <p class="text-secondary">{meta_text}</p>
        <hr class="divider">
    </div>

    <div class="report-section">
        <h2>Most Surprising Finding</h2>
        <div class="narrative">{format_prose(opening)}</div>
    </div>

    <div class="report-section">
        <h2>Your AI Behaviour Pattern</h2>
        <p class="section-subtitle">How you compare across nine dimensions</p>
        {build_dimension_cards(section_1_dashboard.get('dimensions', {}))}
    </div>

    <div class="report-section">
        <h2>How Typical Is Your AI Behaviour?</h2>
        {format_how_typical(section_3_how_typical)}
    </div>

    <div class="report-section">
        <h2>What's Different About Your Pattern</h2>
        <div class="narrative">{format_prose(section_4_what_different)}</div>
    </div>

    <div class="report-section">
        <h2>Your Behaviour Story</h2>
        <div class="narrative">{format_prose(section_5_behaviour_story)}</div>
    </div>

    <div class="report-section">
        <h2>Your Question-Level Profile</h2>
        {build_question_profile(section_6_question_profile.get('questions', []))}
    </div>

    <div class="report-section">
        <h2>Your Most Distinctive Responses</h2>
        <div class="narrative">{format_prose(section_7_distinctive_responses)}</div>
    </div>

    <div class="report-section">
        <h2>Perception Gap Analysis</h2>
        <div class="narrative">{format_prose(section_8_perception_gap)}</div>
    </div>

    <div class="report-section">
        <h2>Your Trajectory & Outlook</h2>
        <div class="narrative">{format_prose(section_10_trajectory)}</div>
    </div>

    <div class="report-section">
        <hr class="divider">
        <h2>Deep Dive: Deeper Insights Into Your Pattern</h2>
        <div class="narrative">{format_prose(deep_dive.get('opening', ''))}</div>
    </div>

    <div class="report-section">
        <h3>Your Pattern Across Research Lenses</h3>
        <div class="narrative">{format_prose(deep_dive.get('part_1_research_lenses', ''))}</div>
    </div>

    <div class="report-section">
        <h3>What Your Rare Combination Reveals</h3>
        <div class="narrative">{format_prose(deep_dive.get('part_4_rare_combination', ''))}</div>
    </div>

    <div class="report-section">
        <h3>Cross-Dimensional Architecture</h3>
        <div class="narrative">{format_prose(deep_dive.get('part_5_cross_dimensional', ''))}</div>
    </div>

    <div class="report-section">
        <hr class="divider">
        <p style="font-size: 9px; color: var(--color-text-secondary);">
            <strong>About This Report</strong><br>
            This assessment measures nine dimensions of your AI behaviour, benchmarked against 10,500+ participants.
            Learn more at <a href="https://humanclarityinstitute.com" style="color: var(--color-primary);">humanclarityinstitute.com</a>
        </p>
    </div>

</div>

</body>
</html>'''
    
    # ✅ Apply dynamic content substitutions (template is raw string, not f-string)
    html = html.replace('{format_how_typical(section_3_how_typical)}', format_how_typical(section_3_how_typical))
    html = html.replace('{format_prose(section_7_distinctive_responses)}', format_prose(section_7_distinctive_responses))
    html = html.replace('{format_prose(section_5_behaviour_story)}', format_prose(section_5_behaviour_story))
    html = html.replace('{format_prose(section_8_perception_gap)}', format_prose(section_8_perception_gap))
    html = html.replace('{format_prose(section_10_trajectory)}', format_prose(section_10_trajectory))
    html = html.replace('{build_dimension_cards(section_1_dashboard.get("dimensions", {}))}', build_dimension_cards(section_1_dashboard.get('dimensions', {})))
    html = html.replace('{build_question_profile(section_6_question_profile.get("questions", []))}', build_question_profile(section_6_question_profile.get('questions', [])))
    
    return html


if __name__ == '__main__':
    # Test with sample data
    sample_report = {
        'metadata': {
            'demographics': {
                'age_group': '25-34',
                'country': 'New Zealand'
            }
        },
        'opening': 'This is a test opening paragraph.',
        'section_1_dashboard': {
            'dimensions': {
                'trust': {
                    'percentile': 72,
                    'raw_score': 5.2,
                    'research_insight': 'You show above-average trust in AI systems.'
                }
            }
        }
    }
    
    html = build_report_html(sample_report)
    print(f"Generated {len(html)} characters of HTML")
