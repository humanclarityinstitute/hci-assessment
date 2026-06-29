"""
report_page_builder.py — Premium Report Page Builder

Transforms report_dict from report_generator into rendering-ready data
with full validation against Section_Details_Complete.txt specification.

Does NOT assume any HTML structure - returns clean data ready for
any HTML template to consume.

Main entry point: build_report_html(report_dict)

Input: report_dict from report_generator.py
Output: rendering_dict (validated, transformation-ready data)
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION & CONSTANTS
# ============================================================

# Dimension order and definitions (locked from Section_Details_Complete.txt)
DIMENSION_ORDER = [
    'reliance',
    'trust',
    'verification',
    'decision_delegation',
    'human_agency',
    'emotional_regulation',
    'disclosure',
    'thought_partnership',
    'social_transparency'
]

DIMENSION_DEFINITIONS = {
    'reliance': 'How much you depend on AI for thinking and functioning',
    'trust': 'How much you believe AI outputs are accurate',
    'verification': 'How often you check AI outputs before using them',
    'decision_delegation': 'How much you hand over decisions to AI',
    'human_agency': 'How much control you maintain over your decisions',
    'emotional_regulation': 'Whether you turn to AI for emotional support',
    'disclosure': 'How much personal information you share with AI',
    'thought_partnership': 'How much you use AI as a thinking partner',
    'social_transparency': 'How openly you discuss your AI use with others'
}

MIN_SAMPLE_SIZE = 30  # Minimum responses to show demographic comparison

# ============================================================
# VALIDATION FUNCTIONS
# ============================================================

def validate_report_dict(report_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate report_dict against Section_Details_Complete.txt specification.
    
    Args:
        report_dict: Raw dict from report_generator.py
    
    Returns:
        tuple: (is_valid: bool, errors: list of error messages)
    """
    
    logger.info("[VALIDATE] Starting validation...")
    
    errors = []
    
    # Check metadata
    if 'metadata' not in report_dict:
        errors.append("Missing 'metadata'")
    else:
        meta = report_dict['metadata']
        if 'session_id' not in meta:
            errors.append("Missing metadata.session_id")
        if 'demographics' not in meta:
            errors.append("Missing metadata.demographics")
        if 'generated_at' not in meta:
            errors.append("Missing metadata.generated_at")
    
    # Check opening
    if 'opening_statement' not in report_dict:
        errors.append("Missing 'opening_statement'")
    if 'top_3_findings' not in report_dict:
        errors.append("Missing 'top_3_findings'")
    
    # Check Section 1: Dashboard
    if 'section_1_dashboard' not in report_dict:
        errors.append("Missing 'section_1_dashboard'")
    else:
        dashboard = report_dict['section_1_dashboard']
        if not isinstance(dashboard, dict):
            errors.append("section_1_dashboard is not a dict")
        else:
            for dim in DIMENSION_ORDER:
                if dim not in dashboard:
                    errors.append(f"Dashboard missing dimension: {dim}")
                else:
                    card = dashboard[dim]
                    if 'percentile' not in card:
                        errors.append(f"Dashboard.{dim} missing 'percentile'")
                    if 'definition' not in card:
                        errors.append(f"Dashboard.{dim} missing 'definition'")
                    if 'insight' not in card:
                        errors.append(f"Dashboard.{dim} missing 'insight'")
    
    # Check Section 3: How Typical
    if 'section_3_how_typical' not in report_dict:
        errors.append("Missing 'section_3_how_typical'")
    else:
        for dim in DIMENSION_ORDER:
            if dim not in report_dict['section_3_how_typical']:
                errors.append(f"How Typical missing dimension: {dim}")
    
    # Check prose sections (allow None/empty, but must exist)
    prose_sections = [
        'section_4_rare_combos',
        'section_5_behaviour_story',
        'section_7_distinctive',
        'section_8_perception_gap',
        'section_10_trajectory'
    ]
    
    for section in prose_sections:
        if section not in report_dict:
            errors.append(f"Missing '{section}'")
    
    # Check Section 6: Question Profile
    if 'section_6_question_profile' not in report_dict:
        errors.append("Missing 'section_6_question_profile'")
    else:
        qs = report_dict['section_6_question_profile']
        if not isinstance(qs, dict) or len(qs) != 39:
            errors.append(f"Question profile has {len(qs)} questions, expected 39")
    
    # Check Section 9: What to Protect
    if 'section_9_what_to_protect' not in report_dict:
        errors.append("Missing 'section_9_what_to_protect'")
    else:
        wtp = report_dict['section_9_what_to_protect']
        if 'subsections' not in wtp:
            errors.append("What to Protect missing 'subsections'")
        else:
            subsections = wtp['subsections']
            if len(subsections) != 3:
                errors.append(f"What to Protect has {len(subsections)} subsections, expected 3")
    
    # Check Section 11: Next Steps
    if 'section_11_next_steps' not in report_dict:
        errors.append("Missing 'section_11_next_steps'")
    else:
        ns = report_dict['section_11_next_steps']
        if 'intro' not in ns:
            errors.append("Next Steps missing 'intro'")
        if 'prompts' not in ns:
            errors.append("Next Steps missing 'prompts'")
        if 'closing' not in ns:
            errors.append("Next Steps missing 'closing'")
    
    if errors:
        logger.error(f"[VALIDATE] Found {len(errors)} errors:")
        for err in errors:
            logger.error(f"  - {err}")
        return False, errors
    
    logger.info("[VALIDATE] ✓ All validations passed")
    return True, []


# ============================================================
# TRANSFORMATION FUNCTIONS
# ============================================================

def prepare_opening_section(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare opening section.
    
    Combines opening_statement + top_3_findings into single 'opening' field
    for template consumption.
    """
    
    logger.info("[Opening] Preparing opening section...")
    
    opening_statement = report_dict.get('opening_statement', '')
    top_3_findings = report_dict.get('top_3_findings', '')
    
    # Combine with \n\n separator
    combined = opening_statement
    if top_3_findings:
        combined = f"{opening_statement}\n\n{top_3_findings}"
    
    logger.info("[Opening] ✓ Combined opening and findings")
    
    return {
        'opening': combined,
        'opening_statement': opening_statement,
        'top_3_findings': top_3_findings
    }


def prepare_dashboard_section(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare Section 1: Dashboard.
    
    Validates and structures dashboard data for HTML rendering.
    Ensures all 9 dimensions have required fields.
    """
    
    logger.info("[Dashboard] Preparing 9 dimension cards...")
    
    dashboard = report_dict.get('section_1_dashboard', {})
    
    prepared_dashboard = {}
    
    for dim_name in DIMENSION_ORDER:
        if dim_name not in dashboard:
            logger.warning(f"[Dashboard] Missing dimension: {dim_name}")
            continue
        
        dim_data = dashboard[dim_name]
        
        # Validate required fields
        if not isinstance(dim_data, dict):
            logger.warning(f"[Dashboard] {dim_name} is not a dict")
            continue
        
        percentile = dim_data.get('percentile', 50)
        raw_score = dim_data.get('raw_score', 0)
        definition = dim_data.get('definition', DIMENSION_DEFINITIONS.get(dim_name, ''))
        insight = dim_data.get('insight', '')
        
        # Get comparisons (only if sample size adequate)
        percentile_frequency = dim_data.get('percentile_by_frequency')
        percentile_age_group = dim_data.get('percentile_by_age_group')
        n_frequency = dim_data.get('sample_size_frequency', 0)
        n_age_group = dim_data.get('sample_size_age_group', 0)
        
        # Build comparison display
        comparisons = []
        
        if percentile_frequency is not None and n_frequency >= MIN_SAMPLE_SIZE:
            comparisons.append({
                'label': 'Daily AI users',
                'percentile': percentile_frequency
            })
        
        if percentile_age_group is not None and n_age_group >= MIN_SAMPLE_SIZE:
            comparisons.append({
                'label': 'Your age group',
                'percentile': percentile_age_group
            })
        
        # Prepare card
        prepared_dashboard[dim_name] = {
            'dimension': dim_name,
            'display_name': dim_name.replace('_', ' ').title(),
            'percentile': int(percentile),
            'raw_score': round(float(raw_score), 2),
            'definition': definition,
            'insight': insight,
            'comparisons': comparisons,
            'sample_size_frequency': n_frequency,
            'sample_size_age_group': n_age_group
        }
    
    logger.info(f"[Dashboard] ✓ Prepared {len(prepared_dashboard)}/9 cards")
    
    return {
        'section_1_dashboard': prepared_dashboard
    }


def prepare_question_profile(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare Section 6: Question Profile.
    
    Organizes 39 questions by dimension for template rendering.
    """
    
    logger.info("[Questions] Preparing 39-question profile...")
    
    questions = report_dict.get('section_6_question_profile', {})
    
    # Group by dimension
    by_dimension = {dim: [] for dim in DIMENSION_ORDER}
    
    for q_key, q_data in questions.items():
        dim = q_data.get('dimension', 'unknown')
        if dim in by_dimension:
            by_dimension[dim].append({
                'key': q_key,
                'question_text': q_data.get('question_text', ''),
                'response_value': q_data.get('response_value', 0),
                'percentile': q_data.get('percentile', 50),
                'percentile_frequency': q_data.get('percentile_frequency'),
                'percentile_age_group': q_data.get('percentile_age_group'),
                'distribution': q_data.get('population_distribution', [])
            })
    
    logger.info(f"[Questions] ✓ Organized {len(questions)} questions by dimension")
    
    return {
        'section_6_question_profile': by_dimension
    }


def prepare_what_to_protect(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare Section 9: What to Protect.
    
    Structures protective guidance for 3 lowest dimensions.
    """
    
    logger.info("[What to Protect] Preparing protective guidance...")
    
    wtp = report_dict.get('section_9_what_to_protect', {})
    subsections = wtp.get('subsections', {})
    
    prepared_subsections = {}
    
    for dim_name, sub_data in subsections.items():
        prepared_subsections[dim_name] = {
            'dimension': dim_name,
            'display_name': dim_name.replace('_', ' ').title(),
            'title': sub_data.get('title', f'Protect Your {dim_name.replace("_", " ").title()}'),
            'definition': sub_data.get('definition', ''),
            'percentile': sub_data.get('percentile', 50),
            'content': sub_data.get('content', '')
        }
    
    logger.info(f"[What to Protect] ✓ Prepared {len(prepared_subsections)} subsections")
    
    return {
        'section_9_what_to_protect': prepared_subsections
    }


def prepare_prose_sections(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare prose sections (4, 5, 7, 8, 10).
    
    Ensures all prose has \n\n paragraph separators.
    """
    
    logger.info("[Prose] Formatting prose sections...")
    
    prose_fields = {
        'section_4_rare_combos': report_dict.get('section_4_rare_combos', ''),
        'section_5_behaviour_story': report_dict.get('section_5_behaviour_story', ''),
        'section_7_distinctive': report_dict.get('section_7_distinctive', ''),
        'section_8_perception_gap': report_dict.get('section_8_perception_gap', ''),
        'section_10_trajectory': report_dict.get('section_10_trajectory', '')
    }
    
    prepared_prose = {}
    
    for field_name, prose in prose_fields.items():
        if prose:
            # Ensure paragraphs are separated by \n\n (not just \n)
            paragraphs = [p.strip() for p in prose.split('\n') if p.strip()]
            normalized = '\n\n'.join(paragraphs)
            prepared_prose[field_name] = normalized
        else:
            prepared_prose[field_name] = ''
    
    logger.info("[Prose] ✓ Prose sections formatted")
    
    return prepared_prose


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def build_report_html(report_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform report_dict into rendering-ready data.
    
    This function:
    1. Validates report_dict against specification
    2. Transforms all sections
    3. Returns clean, validation data ready for HTML template
    
    Does NOT assume any HTML structure - returns data only.
    
    Args:
        report_dict: Dict from report_generator.py['report']
    
    Returns:
        Dict: Rendering-ready data with all sections transformed
        
    Raises:
        ValueError: If validation fails
        KeyError: If required fields missing
    """
    
    try:
        logger.info(f"[BUILDER] Starting report HTML preparation...")
        
        # Step 1: Validate
        logger.info("[BUILDER] Step 1: Validating report_dict...")
        is_valid, errors = validate_report_dict(report_dict)
        
        if not is_valid:
            error_msg = f"Validation failed with {len(errors)} errors:\n" + '\n'.join(errors)
            logger.error(f"[BUILDER] {error_msg}")
            raise ValueError(error_msg)
        
        logger.info("[BUILDER] ✓ Validation passed")
        
        # Step 2: Prepare metadata
        logger.info("[BUILDER] Step 2: Preparing metadata...")
        
        metadata = report_dict.get('metadata', {})
        prepared_metadata = {
            'session_id': metadata.get('session_id', 'unknown'),
            'email': metadata.get('email', ''),
            'demographics': metadata.get('demographics', {}),
            'generated_at': metadata.get('generated_at', datetime.utcnow().isoformat()),
            'version': metadata.get('version', '3.0')
        }
        
        logger.info("[BUILDER] ✓ Metadata prepared")
        
        # Step 3: Prepare all sections
        logger.info("[BUILDER] Step 3: Preparing all sections...")
        
        rendered = {
            'metadata': prepared_metadata,
            **prepare_opening_section(report_dict),
            **prepare_dashboard_section(report_dict),
            'section_3_how_typical': report_dict.get('section_3_how_typical', {}),
            **prepare_prose_sections(report_dict),
            **prepare_question_profile(report_dict),
            **prepare_what_to_protect(report_dict),
            'section_11_next_steps': report_dict.get('section_11_next_steps', {})
        }
        
        logger.info("[BUILDER] ✓ All sections prepared")
        
        # Step 4: Final verification
        logger.info("[BUILDER] Step 4: Final verification...")
        
        # Verify all sections present in output
        required_sections = [
            'metadata', 'opening', 'section_1_dashboard', 'section_3_how_typical',
            'section_4_rare_combos', 'section_5_behaviour_story', 'section_6_question_profile',
            'section_7_distinctive', 'section_8_perception_gap', 'section_9_what_to_protect',
            'section_10_trajectory', 'section_11_next_steps'
        ]
        
        missing = [s for s in required_sections if s not in rendered]
        if missing:
            raise ValueError(f"Missing sections in output: {missing}")
        
        logger.info("[BUILDER] ✓ Final verification passed")
        
        logger.info("[BUILDER] ✓ Report HTML preparation complete")
        
        return rendered
    
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
    print("\nFunctions:")
    print("  ✓ validate_report_dict() - Full validation against specification")
    print("  ✓ prepare_opening_section() - Combines statement + findings")
    print("  ✓ prepare_dashboard_section() - 9 dimension cards")
    print("  ✓ prepare_question_profile() - 39 questions grouped by dimension")
    print("  ✓ prepare_what_to_protect() - 3 protective guidance cards")
    print("  ✓ prepare_prose_sections() - Normalizes all narrative text")
    print("\nOutput: rendering_dict (clean data, no HTML assumptions)")
    print("Next step: Build new HTML template to consume this data")
