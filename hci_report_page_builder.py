"""
report_page_builder.py — HCI Premium Report HTML Builder

Transforms report_dict from report_generator into final HTML
by injecting data into the hci-report-page.html template.

Main entry point: build_report_html(report_dict)

Input: report_dict from report_generator.py
Output: Complete HTML string ready for rendering/PDF/email
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

# Path to HTML template
TEMPLATE_PATH = Path(__file__).parent / 'hci-report-page.html'

# Dimension definitions (locked, from SIGNALS)
DIMENSION_LABELS = {
    'reliance': 'Reliance',
    'trust': 'Trust',
    'verification': 'Verification',
    'decision_delegation': 'Decision Delegation',
    'human_agency': 'Human Agency',
    'emotional_regulation': 'Emotional Regulation',
    'disclosure': 'Disclosure',
    'thought_partnership': 'Thought Partnership',
    'social_transparency': 'Social Transparency'
}

# ============================================================
# HELPER: Transform report_dict for HTML
# ============================================================

def transform_report_for_html(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform report_dict from report_generator to match HTML expectations.
    
    Fixes structural mismatches:
    1. Combine opening_statement + top_3_findings → single 'opening' field
    2. Wrap dashboard: section_1_dashboard → {'dimensions': {...}}
    3. Add 'label' field to each dimension card
    4. Ensure all prose has \n\n paragraph separators
    5. Standardize dimension names to lowercase
    
    Args:
        report_dict: Raw dict from report_generator.py
    
    Returns:
        Dict formatted for HTML template
    """
    
    logger.info("[Transform] Starting report_dict transformation...")
    
    transformed = report_dict.copy()
    
    # ── Fix 1: Combine opening fields ──────────────────────────────
    logger.info("[Transform] Fixing opening section...")
    
    opening_statement = report_dict.get('opening_statement', '')
    top_3_findings = report_dict.get('top_3_findings', '')
    
    # Combine with \n\n separator
    combined_opening = opening_statement
    if top_3_findings:
        combined_opening = f"{opening_statement}\n\n{top_3_findings}"
    
    transformed['opening'] = combined_opening
    # Remove old fields
    transformed.pop('opening_statement', None)
    transformed.pop('top_3_findings', None)
    
    logger.info("[Transform] ✓ Opening combined")
    
    # ── Fix 2 & 3: Transform dashboard section ─────────────────────
    logger.info("[Transform] Fixing dashboard section...")
    
    dashboard = report_dict.get('section_1_dashboard', {})
    
    if dashboard:
        # Add 'label' field to each dimension and wrap in 'dimensions' key
        dimensions_with_labels = {}
        
        for dim_name, dim_data in dashboard.items():
            # Standardize dimension name to lowercase
            dim_key = dim_name.lower()
            
            # Add label if not present
            if isinstance(dim_data, dict):
                dim_data_copy = dim_data.copy()
                if 'label' not in dim_data_copy:
                    dim_data_copy['label'] = DIMENSION_LABELS.get(dim_key, dim_key.title())
                dimensions_with_labels[dim_key] = dim_data_copy
            else:
                logger.warning(f"[Transform] Dashboard data for {dim_name} is not a dict")
                dimensions_with_labels[dim_key] = dim_data
        
        # Wrap in 'dimensions' key for HTML
        transformed['section_1_dashboard'] = {
            'dimensions': dimensions_with_labels
        }
        
        logger.info(f"[Transform] ✓ Dashboard wrapped with {len(dimensions_with_labels)} dimensions")
    
    # ── Fix 4: Ensure prose has \n\n separators ────────────────────
    logger.info("[Transform] Ensuring prose formatting...")
    
    prose_fields = [
        'section_4_rare_combos',
        'section_5_behaviour_story',
        'section_7_distinctive',
        'section_8_perception_gap',
        'section_10_trajectory'
    ]
    
    for field_name in prose_fields:
        if field_name in transformed and isinstance(transformed[field_name], str):
            prose = transformed[field_name].strip()
            # Ensure paragraphs are separated by \n\n (not just \n)
            prose = '\n\n'.join([p.strip() for p in prose.split('\n') if p.strip()])
            transformed[field_name] = prose
    
    logger.info("[Transform] ✓ Prose formatting verified")
    
    logger.info("[Transform] ✓ Report transformation complete")
    
    return transformed


# ============================================================
# HELPER: Inject data into HTML template
# ============================================================

def inject_data_into_html(template_html: str, report_dict: Dict[str, Any]) -> str:
    """
    Inject report_dict data into hci-report-page.html template via JavaScript.
    
    The template has placeholders that are filled by JavaScript:
    - hci-report-meta, hci-opening, hci-dimension-grid, etc.
    
    We inject the report_dict as a JavaScript variable that the template's
    existing JavaScript uses to populate these placeholders.
    
    Args:
        template_html: Raw HTML template string
        report_dict: Transformed report_dict with data
    
    Returns:
        HTML string with report_dict injected
    """
    
    logger.info("[Inject] Starting data injection into template...")
    
    # Serialize report_dict as JSON
    # Use json.dumps with ensure_ascii=False to handle special characters
    report_json = json.dumps(report_dict, ensure_ascii=False, default=str)
    
    # Inject as window variable before existing script
    injection_script = f"""
<script>
// HCI Report Data (injected by report_page_builder.py)
window.hciReportData = {report_json};
</script>
"""
    
    # Find the start of the existing script tag and inject before it
    # Look for: <script>
    # (function() {
    
    script_start = template_html.find('<script>')
    if script_start == -1:
        logger.error("[Inject] Could not find <script> tag in template")
        raise Exception("Template does not contain <script> tag")
    
    # Insert injection script before the first script tag
    injected_html = template_html[:script_start] + injection_script + template_html[script_start:]
    
    logger.info(f"[Inject] ✓ Data injected ({len(report_json)} bytes)")
    
    return injected_html


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def build_report_html(report_dict: Dict[str, Any]) -> str:
    """
    Build complete HTML report from report_dict.
    
    This is the main entry point called by api.py:
    
        report_response = report_generator.generate_premium_report(...)
        if report_response['success']:
            html = report_page_builder.build_report_html(
                report_response['report']
            )
            # html is ready for PDF rendering or email
    
    Args:
        report_dict: Dict from report_generator.py['report']
    
    Returns:
        str: Complete HTML string
    
    Raises:
        Exception: If template not found or transformation fails
    """
    
    try:
        logger.info(f"[BUILDER] Building HTML report...")
        
        # Verify report_dict has required fields
        if not report_dict:
            raise ValueError("report_dict is empty")
        
        if 'metadata' not in report_dict:
            raise ValueError("report_dict missing 'metadata'")
        
        session_id = report_dict.get('metadata', {}).get('session_id', 'unknown')
        logger.info(f"[BUILDER] Session: {session_id}")
        
        # Step 1: Load template
        logger.info("[BUILDER] Loading template...")
        
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
        
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template_html = f.read()
        
        logger.info(f"[BUILDER] ✓ Template loaded ({len(template_html)} bytes)")
        
        # Step 2: Transform report_dict
        logger.info("[BUILDER] Transforming report...")
        
        transformed_dict = transform_report_for_html(report_dict)
        
        logger.info("[BUILDER] ✓ Report transformed")
        
        # Step 3: Inject data into template
        logger.info("[BUILDER] Injecting data...")
        
        html = inject_data_into_html(template_html, transformed_dict)
        
        logger.info(f"[BUILDER] ✓ Data injected")
        
        # Step 4: Verify output
        logger.info("[BUILDER] Verifying output...")
        
        if '<html' not in html or '</html>' not in html:
            raise Exception("Output HTML is malformed")
        
        if 'window.hciReportData' not in html:
            raise Exception("Data injection failed")
        
        logger.info(f"[BUILDER] ✓ Output verified ({len(html)} bytes)")
        
        logger.info("[BUILDER] ✓ HTML report complete")
        
        return html
    
    except Exception as e:
        logger.error(f"[BUILDER] Error: {e}")
        import traceback
        traceback.print_exc()
        raise


# ============================================================
# FOR TESTING
# ============================================================

if __name__ == '__main__':
    print("report_page_builder.py loaded successfully")
    print("Entry point: build_report_html(report_dict)")
    print("\nTransformations applied:")
    print("  ✓ Combine opening_statement + top_3_findings → 'opening'")
    print("  ✓ Wrap dashboard in {'dimensions': {...}}")
    print("  ✓ Add 'label' field to each dimension")
    print("  ✓ Ensure prose has \\n\\n separators")
    print("  ✓ Inject data as window.hciReportData into template")
    print("\nOutput: Complete HTML string ready for PDF/email")
