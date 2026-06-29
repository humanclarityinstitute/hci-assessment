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
    
    print(f"[DEBUG format_how_typical] Received data type: {type(how_typical_data)}")
    print(f"[DEBUG format_how_typical] Received keys: {how_typical_data.keys() if isinstance(how_typical_data, dict) else 'NOT A DICT'}")
    
    if 'distinctive' in how_typical_data:
        distinctive_data = how_typical_data['distinctive']
        print(f"[DEBUG format_how_typical] distinctive type: {type(distinctive_data)}, len: {len(distinctive_data) if hasattr(distinctive_data, '__len__') else 'N/A'}")
        if isinstance(distinctive_data, dict) and distinctive_data:
            first_key = list(distinctive_data.keys())[0]
            first_val = distinctive_data[first_key]
            print(f"[DEBUG format_how_typical] distinctive['{first_key}']: {first_val}")
    
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
    
    print(f"[DEBUG format_how_typical] RETURNING HTML LENGTH: {len(html)} characters")
    print(f"[DEBUG format_how_typical] HTML snippet (first 200 chars): {html[:200]}")
    return html


def build_dimension_cards(dimensions: Dict[str, Any]) -> str:
    """Build HTML for dimension cards (Section 1: Dashboard).
    
    Reads new fields from report_generator.py:
    - 'definition': Plain English description of dimension
    - 'percentile_by_frequency': Percentile for daily users
    - 'percentile_by_age_group': Percentile for age cohort
    """
    if not dimensions:
        return ""
    
    html = '<div class="dimension-grid">\n'
    
    for dim_name, dim_data in dimensions.items():
        if not isinstance(dim_data, dict):
            continue
        
        percentile = dim_data.get('percentile', 50)
        raw_score = dim_data.get('raw_score', 3.5)
        definition = dim_data.get('definition', '')  # NEW
        percentile_frequency = dim_data.get('percentile_by_frequency', None)  # NEW
        percentile_age_group = dim_data.get('percentile_by_age_group', None)  # NEW
        plain = plain_english_percentile(percentile)
        pos = positional_label(percentile)
        
        html += f'''
        <div class="dimension-card">
            <div class="dimension-label">{escape_html(dim_name.upper())}</div>
            <div class="dimension-name">{escape_html(dim_name.title())}</div>
            <div style="margin-bottom: 8pt; font-size: 10.5px; line-height: 1.3; color: #666;">
                {escape_html(definition)}
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
                <div style="display: flex; justify-content: space-between; margin-bottom: 3pt;">
                    <span style="color: #666;">Plain English</span>
                    <span style="font-weight: 500; color: #0066cc; font-size: 9px;">{escape_html(plain)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 3pt;">
                    <span style="color: #666;">Daily AI users</span>
                    <span style="font-weight: 500; color: #0066cc; font-size: 9px;">{percentile_frequency if percentile_frequency else "—"}th %ile</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #666;">Your age group</span>
                    <span style="font-weight: 500; color: #0066cc; font-size: 9px;">{percentile_age_group if percentile_age_group else "—"}th %ile</span>
                </div>
            </div>
        </div>
'''
    
    html += '</div>\n'
    return html


def format_what_to_protect(section_9_data: Dict[str, Any]) -> str:
    """Format Section 9: What to Protect into HTML."""
    if not section_9_data:
        return ""
    
    html = '<div class="section-content">\n'
    
    # Subsections with pre-written content
    subsections = section_9_data.get('subsections', {})
    
    for subsection_key, subsection_data in subsections.items():
        if isinstance(subsection_data, dict):
            title = subsection_data.get('title', '')
            content = subsection_data.get('content', '')
            
            if title or content:
                html += f'<div class="subsection">\n'
                if title:
                    html += f'<h4>{escape_html(title)}</h4>\n'
                if content:
                    html += format_prose(content)
                html += '</div>\n'
    
    html += '</div>\n'
    return html


def format_next_steps(section_11_data: Dict[str, Any]) -> str:
    """Format Section 11: Next Steps into HTML."""
    if not section_11_data:
        return ""
    
    html = '<div class="section-content">\n'
    
    # Title and tagline
    title = section_11_data.get('title', 'Your Next Steps')
    tagline = section_11_data.get('tagline', '')
    
    if tagline:
        html += f'<p class="section-tagline">{escape_html(tagline)}</p>\n'
    
    # Three prompts
    prompts = section_11_data.get('prompts', [])
    
    for prompt in prompts:
        if isinstance(prompt, dict):
            prompt_num = prompt.get('number', '')
            prompt_title = prompt.get('title', '')
            prompt_text = prompt.get('prompt', '')
            
            html += f'<div class="prompt-item">\n'
            if prompt_title:
                html += f'<h4>{escape_html(prompt_title)}</h4>\n'
            if prompt_text:
                html += f'<p>{escape_html(prompt_text)}</p>\n'
            html += '</div>\n'
    
    # Closing
    closing = section_11_data.get('closing', {})
    if closing:
        html += '<div class="closing-section">\n'
        if closing.get('title'):
            html += f'<h4>{escape_html(closing.get("title", ""))}</h4>\n'
        if closing.get('text'):
            html += f'<p>{escape_html(closing.get("text", ""))}</p>\n'
        if closing.get('link'):
            html += f'<p><a href="https://humanclarityinstitute.com">{escape_html(closing.get("link", ""))}</a></p>\n'
        html += '</div>\n'
    
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
    section_9_what_to_protect = report_dict.get('section_9_what_to_protect', {})  # NEW
    section_10_trajectory = report_dict.get('section_10_trajectory', '')
    section_11_next_steps = report_dict.get('section_11_next_steps', {})  # NEW
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
        /**
         * HCI AI Identity & Behaviour Assessment
         * Complete Design System — Typography, Spacing, Color
         * 
         * Locked based on Gallup CliftonStrengths + Big Five Personality Test
         * Target: 10.5pt body, 1.2 line-height, professional density
         * Outcome: 24-page report → 16-18 pages (same content, tighter layout)
         */

        /* ============================================================
           ROOT VARIABLES — LOCKED DESIGN TOKENS
           ============================================================ */

        :root {
          /* TYPOGRAPHY */
          --font-family-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
          --font-family-serif: Georgia, 'Times New Roman', serif;

          --font-size-body: 10.5px;
          --font-size-label: 9px;
          --font-size-sm: 9px;
          --font-size-caption: 8.5px;

          --font-size-h4: 11px;
          --font-size-h3: 12px;
          --font-size-h2: 13px;
          --font-size-h1: 16px;

          --font-weight-regular: 400;
          --font-weight-medium: 500;
          --font-weight-bold: 600;

          --line-height-tight: 1.2;
          --line-height-normal: 1.3;
          --line-height-relaxed: 1.4;

          /* SPACING — In points (pt) to match print layouts */
          --spacing-xs: 3pt;
          --spacing-sm: 6pt;
          --spacing-md: 8pt;
          --spacing-lg: 12pt;
          --spacing-xl: 16pt;
          --spacing-xxl: 20pt;

          /* PAGE MARGINS — Locked */
          --margin-left: 0.75in;
          --margin-right: 0.75in;
          --margin-top: 0.5in;
          --margin-bottom: 0.5in;

          /* COLORS */
          --color-primary: #0066cc;
          --color-primary-dark: #004a99;
          --color-primary-light: #f0f5ff;

          --color-text: #1a1a1a;
          --color-text-secondary: #666;
          --color-text-tertiary: #999;
          --color-text-muted: #bbb;

          --color-border: #e0e0e0;
          --color-border-light: #f0f0f0;
          --color-divider: #ddd;

          --color-bg-white: #ffffff;
          --color-bg-light: #fafafa;
          --color-bg-secondary: #f5f5f5;

          /* BORDER & RADIUS */
          --border-width-thin: 0.5pt;
          --border-width-medium: 1pt;
          --border-radius-sm: 3px;
          --border-radius-md: 4px;
          --border-radius-lg: 6px;
        }

        /* ============================================================
           GLOBAL RESETS & BASE STYLES
           ============================================================ */

        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        html {
          font-size: 16px; /* Browser baseline for rem calculations */
        }

        body {
          font-family: var(--font-family-body);
          font-size: var(--font-size-body);
          line-height: var(--line-height-tight);
          color: var(--color-text);
          background: var(--color-bg-white);
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
        }

        /* ============================================================
           PRINT LAYOUT CONTAINER
           ============================================================ */

        .report {
          max-width: 8in;
          margin: 0 auto;
          padding: var(--margin-top) var(--margin-right) var(--margin-bottom) var(--margin-left);
          background: var(--color-bg-white);
          color: var(--color-text);
        }

        /* For PDF/Print rendering */
        @media print {
          body {
            margin: 0;
            padding: 0;
          }

          .report {
            max-width: 100%;
            margin: 0;
            padding: var(--margin-top) var(--margin-right) var(--margin-bottom) var(--margin-left);
            page-break-after: auto;
          }
        }

        /* ============================================================
           TYPOGRAPHY HIERARCHY
           ============================================================ */

        h1, h2, h3, h4, h5, h6 {
          font-weight: var(--font-weight-bold);
          color: var(--color-text);
          margin: 0;
          line-height: var(--line-height-tight);
          page-break-after: avoid;
        }

        h1 {
          font-size: var(--font-size-h1);
          margin-bottom: var(--spacing-lg);
        }

        h2 {
          font-size: var(--font-size-h2);
          color: var(--color-primary);
          margin-bottom: var(--spacing-md);
        }

        h3 {
          font-size: var(--font-size-h3);
          font-weight: var(--font-weight-medium);
          margin-bottom: var(--spacing-sm);
        }

        h4 {
          font-size: var(--font-size-h4);
          font-weight: var(--font-weight-medium);
          margin-bottom: var(--spacing-sm);
        }

        p {
          margin: 0;
          line-height: var(--line-height-tight);
          margin-bottom: var(--spacing-sm);
        }

        p:last-child {
          margin-bottom: 0;
        }

        /* ============================================================
           SECTION STRUCTURE
           ============================================================ */

        .report-section {
          margin-bottom: var(--spacing-xxl);
          page-break-inside: avoid;
        }

        .report-section.no-break {
          page-break-inside: avoid;
        }

        .section-title {
          font-size: var(--font-size-h2);
          font-weight: var(--font-weight-bold);
          color: var(--color-primary);
          margin-bottom: var(--spacing-md);
          page-break-after: avoid;
        }

        .section-subtitle {
          font-size: var(--font-size-h4);
          color: var(--color-text-secondary);
          font-weight: var(--font-weight-regular);
          margin-bottom: var(--spacing-md);
          page-break-after: avoid;
        }

        .section-intro {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          margin-bottom: var(--spacing-lg);
          color: var(--color-text);
        }

        /* ============================================================
           DIMENSION CARDS (Section 1: Benchmark Dashboard)
           ============================================================ */

        .dimension-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: var(--spacing-xl);
          margin-bottom: var(--spacing-xxl);
        }

        .dimension-card {
          border: var(--border-width-thin) solid var(--color-border);
          padding: var(--spacing-xl);
          border-radius: var(--border-radius-lg);
          background: var(--color-bg-white);
          page-break-inside: avoid;
        }

        .dimension-card:hover {
          border-color: var(--color-primary-light);
        }

        .dimension-label {
          font-size: var(--font-size-label);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: var(--color-text-tertiary);
          margin-bottom: var(--spacing-xs);
          font-weight: var(--font-weight-medium);
        }

        .dimension-name {
          font-size: var(--font-size-h3);
          font-weight: var(--font-weight-bold);
          color: var(--color-text);
          margin-bottom: var(--spacing-md);
        }

        .dimension-definition {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          color: var(--color-text-secondary);
          margin-bottom: var(--spacing-md);
        }

        .dimension-score {
          display: flex;
          align-items: baseline;
          gap: var(--spacing-sm);
          margin-bottom: var(--spacing-md);
        }

        .score-number {
          font-size: 18px;
          font-weight: var(--font-weight-bold);
          color: var(--color-primary);
        }

        .score-label {
          font-size: var(--font-size-body);
          color: var(--color-text-secondary);
          line-height: var(--line-height-tight);
        }

        .percentile-bar {
          width: 100%;
          height: 4px;
          background: var(--color-bg-secondary);
          border-radius: 2px;
          overflow: hidden;
          margin-bottom: var(--spacing-md);
        }

        .percentile-fill {
          height: 100%;
          background: var(--color-primary);
          transition: width 0.3s ease;
        }

        .dimension-comparisons {
          border-top: var(--border-width-thin) solid var(--color-divider);
          padding-top: var(--spacing-md);
          margin-bottom: var(--spacing-md);
          font-size: var(--font-size-body);
        }

        .comparison-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-xs);
          line-height: var(--line-height-tight);
        }

        .comparison-label {
          color: var(--color-text-secondary);
          font-size: var(--font-size-sm);
        }

        .comparison-value {
          font-weight: var(--font-weight-medium);
          color: var(--color-primary);
        }

        .dimension-insight {
          font-size: var(--font-size-body);
          color: var(--color-text-secondary);
          line-height: var(--line-height-normal);
          border-top: var(--border-width-thin) solid var(--color-divider);
          padding-top: var(--spacing-md);
          margin-top: var(--spacing-md);
        }

        /* ============================================================
           NARRATIVE SECTIONS
           ============================================================ */

        .narrative {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          color: var(--color-text);
          margin-bottom: var(--spacing-lg);
        }

        .narrative-paragraph {
          margin-bottom: var(--spacing-sm);
          line-height: var(--line-height-normal);
        }

        .narrative-paragraph:last-child {
          margin-bottom: 0;
        }

        /* ============================================================
           QUESTION-LEVEL PROFILE (Section 6)
           ============================================================ */

        .question-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: var(--spacing-lg);
          margin-bottom: var(--spacing-xl);
        }

        .question-item {
          border: var(--border-width-thin) solid var(--color-border);
          padding: var(--spacing-md);
          border-radius: var(--border-radius-md);
          background: var(--color-bg-white);
          page-break-inside: avoid;
        }

        .question-text {
          font-size: var(--font-size-body);
          font-weight: var(--font-weight-medium);
          color: var(--color-text);
          margin-bottom: var(--spacing-sm);
          line-height: var(--line-height-normal);
        }

        .question-histogram {
          width: 100%;
          height: 40px;
          margin-bottom: var(--spacing-sm);
          display: flex;
          align-items: flex-end;
          gap: 2px;
        }

        .histogram-bar {
          flex: 1;
          background: var(--color-primary-light);
          border-radius: 1px;
          min-height: 2px;
        }

        .histogram-bar.filled {
          background: var(--color-primary);
        }

        .histogram-bar.active {
          background: var(--color-primary);
          box-shadow: 0 0 0 2px var(--color-primary-light);
        }

        .question-percentile {
          font-size: var(--font-size-sm);
          color: var(--color-text-secondary);
          margin-bottom: var(--spacing-xs);
          line-height: var(--line-height-tight);
        }

        .question-insight {
          font-size: var(--font-size-body);
          color: var(--color-text-secondary);
          line-height: var(--line-height-normal);
        }

        /* ============================================================
           DATA CARDS & BOXES
           ============================================================ */

        .data-card {
          background: var(--color-bg-secondary);
          border: var(--border-width-thin) solid var(--color-border);
          border-radius: var(--border-radius-md);
          padding: var(--spacing-md);
          margin-bottom: var(--spacing-lg);
          page-break-inside: avoid;
        }

        .data-card-title {
          font-size: var(--font-size-h4);
          font-weight: var(--font-weight-medium);
          margin-bottom: var(--spacing-sm);
          color: var(--color-text);
        }

        .data-card-content {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          color: var(--color-text-secondary);
        }

        /* ============================================================
           INSIGHT BOXES
           ============================================================ */

        .insight-box {
          background: var(--color-primary-light);
          border-left: 3px solid var(--color-primary);
          padding: var(--spacing-md) var(--spacing-md) var(--spacing-md) var(--spacing-lg);
          margin: var(--spacing-lg) 0;
          border-radius: var(--border-radius-sm);
        }

        .insight-box-title {
          font-size: var(--font-size-h4);
          font-weight: var(--font-weight-medium);
          color: var(--color-primary);
          margin-bottom: var(--spacing-sm);
        }

        .insight-box-content {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          color: var(--color-text);
        }

        /* ============================================================
           DIVIDERS & VISUAL BREAKS
           ============================================================ */

        .divider {
          border: none;
          border-top: var(--border-width-thin) solid var(--color-divider);
          margin: var(--spacing-lg) 0;
          height: 0;
        }

        .divider.light {
          border-top-color: var(--color-border-light);
        }

        .page-break {
          page-break-after: always;
          margin: var(--spacing-xl) 0;
          height: 0;
        }

        .section-break {
          margin: var(--spacing-xxl) 0 var(--spacing-lg) 0;
          page-break-after: avoid;
        }

        /* ============================================================
           LISTS & STRUCTURED CONTENT
           ============================================================ */

        ul, ol {
          margin: 0;
          padding: 0 0 0 var(--spacing-lg);
          margin-bottom: var(--spacing-lg);
          list-style-position: outside;
        }

        li {
          font-size: var(--font-size-body);
          line-height: var(--line-height-normal);
          color: var(--color-text);
          margin-bottom: var(--spacing-sm);
        }

        li:last-child {
          margin-bottom: 0;
        }

        /* ============================================================
           TABLES
           ============================================================ */

        table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: var(--spacing-lg);
          font-size: var(--font-size-body);
        }

        thead {
          background: var(--color-bg-secondary);
        }

        th {
          padding: var(--spacing-sm) var(--spacing-md);
          text-align: left;
          font-weight: var(--font-weight-bold);
          color: var(--color-text);
          border-bottom: var(--border-width-medium) solid var(--color-border);
          line-height: var(--line-height-tight);
        }

        td {
          padding: var(--spacing-sm) var(--spacing-md);
          border-bottom: var(--border-width-thin) solid var(--color-border-light);
          line-height: var(--line-height-tight);
          color: var(--color-text);
        }

        tbody tr:last-child td {
          border-bottom: var(--border-width-medium) solid var(--color-border);
        }

        /* ============================================================
           LABELS & TAGS
           ============================================================ */

        .label {
          display: inline-block;
          padding: 2px var(--spacing-sm);
          background: var(--color-primary-light);
          color: var(--color-primary);
          border-radius: var(--border-radius-sm);
          font-size: var(--font-size-caption);
          font-weight: var(--font-weight-medium);
          text-transform: uppercase;
          letter-spacing: 0.3px;
        }

        .label.secondary {
          background: var(--color-bg-secondary);
          color: var(--color-text-secondary);
        }

        /* ============================================================
           RESPONSIVE DESIGN
           ============================================================ */

        @media (max-width: 768px) {
          :root {
            --margin-left: 0.5in;
            --margin-right: 0.5in;
          }

          .dimension-grid {
            grid-template-columns: 1fr;
          }

          .question-grid {
            grid-template-columns: 1fr;
          }

          .report {
            max-width: 100%;
          }
        }

        @media (max-width: 480px) {
          :root {
            --font-size-body: 10px;
            --spacing-xl: 12px;
            --margin-left: 0.375in;
            --margin-right: 0.375in;
          }

          .dimension-card {
            padding: var(--spacing-lg);
          }
        }

        /* ============================================================
           PRINT-SPECIFIC STYLES
           ============================================================ */

        @media print {
          * {
            box-shadow: none !important;
            text-shadow: none !important;
          }

          a {
            text-decoration: none;
            color: var(--color-text);
          }

          .no-print {
            display: none;
          }

          .report-section {
            page-break-inside: avoid;
          }

          h2, h3, h4 {
            page-break-after: avoid;
            page-break-before: avoid;
          }

          .dimension-card,
          .data-card,
          .question-item {
            page-break-inside: avoid;
            border: var(--border-width-thin) solid var(--color-border);
          }

          .page-break {
            page-break-after: always;
          }
        }

        /* ============================================================
           ACCESSIBILITY
           ============================================================ */

        a:focus {
          outline: 2px solid var(--color-primary);
          outline-offset: 2px;
          border-radius: 2px;
        }

        button:focus,
        input:focus,
        select:focus,
        textarea:focus {
          outline: 2px solid var(--color-primary);
          outline-offset: 2px;
        }

        @media (prefers-reduced-motion: reduce) {
          * {
            animation: none !important;
            transition: none !important;
          }
        }

        /* ============================================================
           UTILITY CLASSES
           ============================================================ */

        .text-center {
          text-align: center;
        }

        .text-right {
          text-align: right;
        }

        .text-muted {
          color: var(--color-text-tertiary);
        }

        .text-secondary {
          color: var(--color-text-secondary);
        }

        .text-primary {
          color: var(--color-primary);
        }

        .mt-xs { margin-top: var(--spacing-xs); }
        .mt-sm { margin-top: var(--spacing-sm); }
        .mt-md { margin-top: var(--spacing-md); }
        .mt-lg { margin-top: var(--spacing-lg); }
        .mt-xl { margin-top: var(--spacing-xl); }

        .mb-xs { margin-bottom: var(--spacing-xs); }
        .mb-sm { margin-bottom: var(--spacing-sm); }
        .mb-md { margin-bottom: var(--spacing-md); }
        .mb-lg { margin-bottom: var(--spacing-lg); }
        .mb-xl { margin-bottom: var(--spacing-xl); }

        .no-margin { margin: 0; }
        .no-padding { padding: 0; }

        .sr-only {
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border-width: 0;
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
        <h2>What to Protect</h2>
        {format_what_to_protect(section_9_what_to_protect)}
    </div>

    <div class="report-section">
        <h2>Your Trajectory & Outlook</h2>
        <div class="narrative">{format_prose(section_10_trajectory)}</div>
    </div>

    <div class="report-section">
        <h2>Your Next Steps</h2>
        {format_next_steps(section_11_next_steps)}
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
    print(f"[DEBUG build_report_html] BEFORE replacements, looking for: '{{format_how_typical(section_3_how_typical)}}'")
    print(f"[DEBUG build_report_html] Found in template? {'{format_how_typical(section_3_how_typical)}' in html}")
    
    how_typical_html = format_how_typical(section_3_how_typical)
    print(f"[DEBUG build_report_html] format_how_typical returned: {len(how_typical_html)} characters")
    
    html = html.replace('{format_how_typical(section_3_how_typical)}', how_typical_html)
    print(f"[DEBUG build_report_html] AFTER replacement, checking if HTML is there...")
    if '<div class="how-typical-section">' in html:
        print(f"[DEBUG build_report_html] ✅ HTML WAS INSERTED - found 'how-typical-section' div")
    else:
        print(f"[DEBUG build_report_html] ❌ HTML NOT INSERTED - 'how-typical-section' div NOT found")
    
    html = html.replace('{format_prose(section_7_distinctive_responses)}', format_prose(section_7_distinctive_responses))
    html = html.replace('{format_prose(section_5_behaviour_story)}', format_prose(section_5_behaviour_story))
    html = html.replace('{format_prose(section_8_perception_gap)}', format_prose(section_8_perception_gap))
    html = html.replace('{format_what_to_protect(section_9_what_to_protect)}', format_what_to_protect(section_9_what_to_protect))  # NEW
    html = html.replace('{format_next_steps(section_11_next_steps)}', format_next_steps(section_11_next_steps))  # NEW
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
