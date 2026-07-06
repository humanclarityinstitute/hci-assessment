"""
api.py
HCI Assessment Platform — Flask API

Main application file that orchestrates:
- Assessment scoring (Layer 1)
- Database operations (supabase_client)
- Payment processing (stripe_config)
- Email delivery (email_template)
- PDF generation (report_pdf)
- Report generation (report_generator)

Endpoints:
- GET /health — Health check
- POST /score — Score assessment
- GET /results — Retrieve stored results
- POST /create-checkout — Stripe checkout
- POST /webhook/stripe — Payment webhook
- POST /premium — Generate premium report
- GET /report — Retrieve premium report
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import json
import traceback
import time
import urllib.request
import urllib.parse
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import Layer 1 (Scoring)
from scoring_engine import score_assessment
from benchmark_builder import get_benchmark
from question_metadata import QUESTION_MAP

# Import Layer 2 (API integrations)
from supabase_client import get_supabase_client
from stripe_config import get_stripe_config

# Import Phase 1: Data enrichment (optional, with fallback)
try:
    from data_enrichment import enrich_results_for_report
    HAS_DATA_ENRICHMENT = True
except ImportError:
    HAS_DATA_ENRICHMENT = False
    print('WARNING: data_enrichment module not found. Phase 1 features will not work.')
    def enrich_results_for_report(full_results, demographics, benchmark_path):
        """Fallback: return results as-is without enrichment"""
        return full_results


# Clean premium report system
# These replace the broken old report_generator/report_page_builder pipeline.
from report_data_builder import build_report_data, assert_report_data_contract
from report_renderer import render_report
from claude_narrative import add_claude_narratives

# Optional legacy helpers kept only for email/PDF fallback paths.
# The clean report flow does not depend on old report_generator or report_page_builder.
try:
    from email_sender import (
        send_report_email,
        send_admin_error_email,
        send_customer_delay_email,
    )
except ImportError:
    send_report_email = None
    send_admin_error_email = None
    send_customer_delay_email = None
    print('WARNING: email_sender module not found. Report email sending disabled.')

try:
    from report_pdf_creator import build_report_pdf
except ImportError:
    build_report_pdf = None
    print('WARNING: report_pdf_creator module not found. PDF generation disabled.')

# Legacy report generator modules are intentionally not imported.
generate_premium_report = None
build_report_html = None



# ============================================================
# RENDER REPORT HTML WITH DATA INJECTION
# ============================================================

def render_report_html(rendering_dict):
    """
    Render report HTML with data injection.
    
    Takes rendering_dict (output from report_page_builder) and injects it
    into hci-report-new.html so JavaScript can access window.hciRenderingData.
    
    Args:
        rendering_dict: Dict from report_page_builder.build_report_html()
    
    Returns:
        str: Complete HTML with data injected
    """
    import json
    
    # Read hci-report-new.html template
    template_path = os.path.join(os.path.dirname(__file__), 'hci-report-new.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_html = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Template not found: {template_path}\n"
            "Make sure hci-report-new.html is in the project root directory"
        )
    
    # Serialize rendering_dict to JSON
    try:
        rendering_json = json.dumps(rendering_dict)
    except (TypeError, ValueError) as e:
        raise ValueError(f"rendering_dict not JSON-serializable: {e}")
    
    # Inject data into HTML
    data_injection = f"""    <script>
    window.hciRenderingData = {rendering_json};
    </script>
"""
    
    if '</head>' in template_html:
        final_html = template_html.replace(
            '</head>',
            f'{data_injection}</head>',
            1
        )
    else:
        final_html = template_html.replace(
            '<body>',
            f'<body>\n{data_injection}',
            1
        )
    
    return final_html


# Create Flask app
# Report storage configuration
REPORT_BASE_URL = os.environ.get(
    'REPORT_BASE_URL',
    'https://humanclarityinstitute.com/ai-assessment/report/'
)

def make_report_url(session_id):
    """Return the URL the front end/customer should use to view the paid report."""
    if REPORT_BASE_URL:
        sep = '&' if '?' in REPORT_BASE_URL else '?'
        return f"{REPORT_BASE_URL}{sep}session_id={urllib.parse.quote(str(session_id))}"
    return f"/report?session_id={urllib.parse.quote(str(session_id))}"

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://humanclarityinstitute.com",
            "https://www.humanclarityinstitute.com"
        ]
    }
})

# PDF storage bucket (create as PUBLIC bucket in Supabase)
REPORT_PDF_BUCKET = os.environ.get('REPORT_PDF_BUCKET', 'reports')

# Configuration
BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'benchmark_tables.json')
# ============================================================
# HELPER: Fetch Stripe Session
# ============================================================

def fetch_stripe_session(stripe_session_id):
    """
    Fetch Stripe checkout session details.
    
    Used to:
    - Verify payment status (payment_status == 'paid')
    - Recover client_reference_id (assessment session_id)
    - Get customer email
    
    Args:
        stripe_session_id (str): Stripe checkout session ID
    
    Returns:
        dict: Session data, or None if not found/error
    """
    if not stripe_session_id:
        return None
    
    try:
        import urllib.request
        stripe_config = get_stripe_config()
        
        url = f'https://api.stripe.com/v1/checkout/sessions/{stripe_session_id}'
        req = urllib.request.Request(
            url,
            headers={'Authorization': f'Bearer {stripe_config.secret_key}'},
        )
        
        response = urllib.request.urlopen(req, timeout=15)
        session_data = json.loads(response.read())
        return session_data
    
    except Exception as e:
        print(f'Failed to fetch Stripe session {stripe_session_id}: {e}')
        return None


def upload_report_pdf(session_id, pdf_bytes):
    """
    Upload the generated report PDF to Supabase Storage and return its public URL.
    
    Overwrites any existing PDF for this session (x-upsert) so a regenerated
    report replaces the old file.
    
    Args:
        session_id: Session identifier (used as filename)
        pdf_bytes: PDF binary data from build_report_pdf()
    
    Returns:
        Public URL string, or None on any failure (non-fatal)
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key or not pdf_bytes or not session_id:
            return None

        path = f'{urllib.parse.quote(session_id)}.pdf'
        upload_url = f'{supabase_url}/storage/v1/object/{REPORT_PDF_BUCKET}/{path}'

        req = urllib.request.Request(
            upload_url,
            data=pdf_bytes,
            headers={
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Content-Type': 'application/pdf',
                'x-upsert': 'true',
            },
            method='POST',
        )
        urllib.request.urlopen(req, timeout=20)

        public_url = (
            f'{supabase_url}/storage/v1/object/public/'
            f'{REPORT_PDF_BUCKET}/{path}'
        )
        print(f'Report PDF uploaded for session {session_id}')
        return public_url

    except Exception as e:
        error_str = str(e)
        print(f'PDF upload failed: {error_str}')
        import traceback
        traceback.print_exc()  # Full stack trace
        return None



# ============================================================
# REPORT FAILURE SAFETY NETS
# ============================================================

ADMIN_ERROR_EMAIL = os.environ.get('ADMIN_ERROR_EMAIL', 'info@humanclarityinstitute.com')
ENABLE_ERROR_EMAILS = os.environ.get('ENABLE_ERROR_EMAILS', 'true').lower() not in ('0', 'false', 'no')


def run_with_retries(step_name, operation, attempts=3, base_delay_seconds=1):
    """Run an operation with simple exponential backoff before surfacing failure."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            print(f'[{step_name}] Attempt {attempt}/{attempts}')
            return operation()
        except Exception as e:
            last_error = e
            print(f'[{step_name}] Attempt {attempt}/{attempts} failed: {e}')
            traceback.print_exc()
            if attempt < attempts:
                time.sleep(base_delay_seconds * attempt)
    raise last_error


def notify_report_failure(
    session_id=None,
    customer_email=None,
    failed_step='unknown',
    error=None,
    traceback_text=None,
    notify_customer=False,
    context=None,
):
    """Send admin/customer failure emails without breaking the main error path."""
    if not ENABLE_ERROR_EMAILS:
        print('[FAILURE_NOTIFY] Skipped because ENABLE_ERROR_EMAILS is disabled')
        return

    resend_key = os.environ.get('RESEND_API_KEY')
    report_url = make_report_url(session_id) if session_id else ''
    error_message = str(error) if error else 'Unknown error'
    traceback_text = traceback_text or traceback.format_exc()

    if send_admin_error_email and resend_key and ADMIN_ERROR_EMAIL:
        try:
            result = send_admin_error_email(
                to_email=ADMIN_ERROR_EMAIL,
                resend_api_key=resend_key,
                session_id=session_id or '',
                customer_email=customer_email or '',
                failed_step=failed_step,
                error_message=error_message,
                traceback_text=traceback_text,
                report_url=report_url,
                context=context or {}
            )
            print(f'[FAILURE_NOTIFY] Admin alert result: {result}')
        except Exception as notify_error:
            print(f'[FAILURE_NOTIFY] Admin alert failed: {notify_error}')
            traceback.print_exc()
    else:
        print('[FAILURE_NOTIFY] Admin alert not sent: missing sender, RESEND_API_KEY, or ADMIN_ERROR_EMAIL')

    if notify_customer and customer_email and send_customer_delay_email and resend_key:
        try:
            result = send_customer_delay_email(
                to_email=customer_email,
                resend_api_key=resend_key,
                session_id=session_id or '',
                report_url=report_url
            )
            print(f'[FAILURE_NOTIFY] Customer delay email result: {result}')
        except Exception as notify_error:
            print(f'[FAILURE_NOTIFY] Customer delay email failed: {notify_error}')
            traceback.print_exc()

# ============================================================
# HEALTH CHECK
# ============================================================




# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    benchmark_exists = os.path.exists(BENCHMARK_PATH)
    return jsonify({
        'status': 'ok',
        'benchmark_loaded': benchmark_exists,
        'clean_report_system': True,
        'timestamp': datetime.utcnow().isoformat(),
    }), 200


# ============================================================
# HELPER: Generate response percentiles (Requirement 2)
# ============================================================

def generate_percentiles(responses, demographics, scoring_results):
    """
    Generate percentiles and histogram data for each individual question response.

    Important:
    - Question text comes from question_metadata. Do not use rewritten or shortened
      question text here.
    - Distributions are question-level distributions from benchmark_tables["variables"],
      not dimension-level distributions.
    - The results page needs three comparison views: everyone, people your age,
      and AI users with the same usage frequency.
    """
    try:
        benchmark = get_benchmark()
        benchmark_data = getattr(benchmark, 'data', {}) or {}
        variables_data = benchmark_data.get('variables', {}) or {}

        percentiles = {}
        age_group = demographics.get('age_group')
        frequency = demographics.get('ai_tool_use_frequency')

        def _normalise_label(value):
            if value is None:
                return None
            return str(value).replace(' - ', '-').replace(' ', '').strip().lower()

        def _find_segment(container, label):
            if not container or label is None:
                return None
            if label in container:
                return container.get(label)
            target = _normalise_label(label)
            for key, value in container.items():
                if _normalise_label(key) == target:
                    return value
            return None

        def _distribution_from_values(values):
            counts = [0, 0, 0, 0, 0, 0, 0]
            for value in values or []:
                try:
                    idx = int(float(value))
                    if 1 <= idx <= 7:
                        counts[idx - 1] += 1
                except (TypeError, ValueError):
                    continue
            return counts

        for q_key, meta in QUESTION_MAP.items():
            if q_key not in responses:
                continue

            user_response = responses.get(q_key)
            dim_name = meta.get('dimension')

            pct_overall = benchmark.get_percentile(q_key, user_response, segment=None)
            pct_age_group = benchmark.get_percentile(q_key, user_response, segment=('age_group', age_group)) if age_group else None
            pct_frequency = benchmark.get_percentile(q_key, user_response, segment=('frequency', frequency)) if frequency else None

            n_overall = benchmark.get_sample_size(q_key, segment=None)
            n_age_group = benchmark.get_sample_size(q_key, segment=('age_group', age_group)) if age_group else None
            n_frequency = benchmark.get_sample_size(q_key, segment=('frequency', frequency)) if frequency else None

            variable_entry = variables_data.get(q_key, {}) or {}
            overall_entry = variable_entry.get('overall') or {}
            age_entry = _find_segment(variable_entry.get('by_age') or {}, age_group) or {}
            frequency_entry = _find_segment(variable_entry.get('by_frequency') or {}, frequency) or {}

            distribution_overall = _distribution_from_values(overall_entry.get('values'))
            distribution_age = _distribution_from_values(age_entry.get('values'))
            distribution_frequency = _distribution_from_values(frequency_entry.get('values'))

            # Keep legacy keys for the current frontend, and add explicit keys for the
            # upgraded three-way toggle.
            percentiles[q_key] = {
                'response': user_response,
                'percentile_overall': pct_overall,
                'percentile_age_group': pct_age_group,
                'percentile_frequency': pct_frequency,
                'question_text': meta.get('text') or f'Question {q_key}',
                'dimension': dim_name,
                'n_overall': n_overall,
                'n_age_group': n_age_group,
                'n_frequency': n_frequency,
                'is_rare': pct_overall is not None and (pct_overall >= 86 or pct_overall <= 14),
                'distribution': distribution_overall,
                'distribution_overall': distribution_overall,
                'distribution_age': distribution_age or distribution_overall,
                'distribution_frequency': distribution_frequency or distribution_overall,
            }

        return percentiles

    except Exception as e:
        print(f'Error generating response percentiles: {e}')
        traceback.print_exc()
        return {}

# ============================================================
# ASSESSMENT SCORING (POST /score)
# ============================================================

@app.route('/score', methods=['POST'])
def score():
    """
    Score a completed assessment and store results.
    
    Request:
    {
        "responses": {39 question responses},
        "demographics": {age_group, gender, country, ai_tool_use_frequency},
        "report_email": "user@example.com",
        "consent": true,
        "consent_timestamp": "2026-06-25T...",
        "session_id": "optional-existing-session-id"
    }
    
    Response:
    {
        "success": true,
        "session_id": "...",
        "dimension_scores": {...},
        "full_results": {...}
    }
    """
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Extract data
        responses = request_data.get('responses', {})
        demographics = request_data.get('demographics', {})
        report_email = request_data.get('report_email')
        consent = request_data.get('consent', False)
        consent_timestamp = request_data.get('consent_timestamp')
        session_id = request_data.get('session_id')
        
        # Validate required fields
        if not responses or not demographics:
            return jsonify({'success': False, 'error': 'Missing responses or demographics'}), 400
        
        # Generate session_id if not provided
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
        
        # Score the assessment (Layer 1)
        scoring_results = score_assessment(responses, demographics, session_id=session_id)
        
        # Generate response percentiles (Requirement 2: variable-level answers vs full + age group)
        percentiles = generate_percentiles(responses, demographics, scoring_results)
        scoring_results['percentiles'] = percentiles
        
        # CLEAN PREMIUM REPORT DATA
        # Build ONE canonical report_data object here, immediately after scoring.
        # This object is saved to Supabase and becomes the only source of truth for /report.
        report_data = build_report_data(
            scoring_results=scoring_results,
            responses=responses,
            demographics=demographics,
            email=report_email,
            session_id=session_id
        )
        assert_report_data_contract(report_data)

        # Store in Supabase - include ALL data so results page has complete access
        db = get_supabase_client()
        store_result = db.store_assessment(
            session_id=session_id,
            responses=responses,
            demographics=demographics,
            full_results=scoring_results,
            dimension_scores=scoring_results.get('dimension_scores', {}),
            perception_gaps=scoring_results.get('perception_gaps', []),
            patterns=scoring_results.get('rare_combinations', []),
            percentiles=percentiles,
            report_data=report_data,
            report_email=report_email,
            consent=consent,
            consent_timestamp=consent_timestamp
        )
        
        if not store_result.get('success'):
            print(f'Failed to store assessment: {store_result.get("message")}')
            return jsonify({
                'success': False,
                'error': 'Failed to store assessment in database',
                'message': store_result.get('message')
            }), 500
        
        # Return results
        return jsonify({
            'success': True,
            'session_id': session_id,
            'dimension_scores': scoring_results.get('dimension_scores', {}),
            'percentiles': percentiles,          # ← Question-level percentiles
            'perception_gaps': scoring_results.get('perception_gaps', []),
            'rare_combinations': scoring_results.get('rare_combinations', []),
            'demographics': demographics,        # ← ADD
            'responses': responses,              # ← ADD
            'full_results': scoring_results
        }), 200
    
    except Exception as e:
        print(f'Score endpoint error: {e}')
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Assessment scoring failed'
        }), 500


# ============================================================
# RETRIEVE RESULTS (GET /results)
# ============================================================

@app.route('/results', methods=['GET'])
def get_results():
    """
    Retrieve stored assessment results by session_id.
    
    Query params:
        session_id: Assessment session ID
    
    Response:
    {
        "success": true,
        "session_id": "...",
        "full_results": {...},
        "report_email": "..."
    }
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400
        
        db = get_supabase_client()
        assessment = db.get_assessment(session_id)
        
        if not assessment:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'full_results': assessment.get('full_results'),
            'percentiles': assessment.get('percentiles', {}),
            'demographics': assessment.get('demographics', {}),
            'responses': assessment.get('responses', {}),
            'report_email': assessment.get('report_email'),
            'paid': assessment.get('paid', False),
            'report_url': make_report_url(session_id) if assessment.get('paid', False) else None
        }), 200
    
    except Exception as e:
        print(f'Get results error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve results'}), 500


# ============================================================
# CREATE STRIPE CHECKOUT (POST /create-checkout)
# ============================================================

@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    """
    Create a Stripe Checkout Session for premium report.
    
    Request:
    {
        "session_id": "assessment-session-id",
        "email": "user@example.com"  (optional)
    }
    
    Response:
    {
        "success": true,
        "session_id": "stripe-session-id",
        "url": "https://checkout.stripe.com/..."
    }
    """
    session_id = None
    stripe_session_id = None
    report_email = None
    delivery_email = None
    failed_step = 'premium_start'
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get('session_id')
        email = request_data.get('email')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400
        
        # Create checkout via Stripe
        stripe = get_stripe_config()
        result = stripe.create_checkout_session(session_id, email)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'session_id': result['session_id'],
                'url': result['url']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', 'Checkout creation failed')
            }), 400
    
    except Exception as e:
        print(f'Create checkout error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Checkout creation failed'}), 500


# ============================================================
# STRIPE WEBHOOK (POST /webhook/stripe)
# ============================================================

@app.route('/webhook/stripe', methods=['POST'])
def webhook_stripe():
    """
    Stripe webhook handler for payment confirmation.
    
    Stripe sends signed events to this endpoint.
    On checkout.session.completed, we mark the assessment as paid,
    store the Stripe session ID, and trigger report generation automatically.
    """
    try:
        # Get raw request body and signature
        payload = request.get_data(as_text=True)
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            print('Missing Stripe-Signature header')
            return jsonify({'error': 'Missing signature'}), 400
        
        # Verify signature
        stripe = get_stripe_config()
        if not stripe.verify_webhook_signature(payload, signature):
            print('Webhook signature verification failed')
            return jsonify({'error': 'Invalid signature'}), 403
        
        # Parse event
        event = stripe.parse_webhook_event(payload)
        if not event:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        # Handle checkout.session.completed
        if event.get('type') == 'checkout.session.completed':
            checkout_data = stripe.handle_checkout_completed(event)
            if not checkout_data:
                return jsonify({'error': 'Invalid event data'}), 400
            
            stripe_session_id = checkout_data['stripe_session_id']
            customer_email = checkout_data['customer_email']
            report_email = customer_email  # Email report to the Stripe customer's address
            
            # Fetch Stripe session to get client_reference_id (assessment session_id)
            stripe_session = fetch_stripe_session(stripe_session_id)
            if not stripe_session:
                print(f'Failed to fetch Stripe session {stripe_session_id}')
                return jsonify({'received': True}), 200  # Still return 200 to ack webhook
            
            session_id = stripe_session.get('client_reference_id')
            if not session_id:
                print(f'No client_reference_id in Stripe session {stripe_session_id}')
                return jsonify({'received': True}), 200
            
            print(f'Webhook: Payment confirmed for Stripe session {stripe_session_id}, assessment {session_id}')
            
            # STEP 1: Update assessment to mark as paid and store stripe_session_id (SAME ROW)
            db = get_supabase_client()
            try:
                paid_at = datetime.utcnow().isoformat()
                # Use update_assessment to store stripe_session_id WITHOUT creating a new row
                db.update_assessment(
                    session_id=session_id,
                    paid=True,
                    paid_at=paid_at,
                    stripe_session_id=stripe_session_id,
                    report_email=customer_email
                )
                print(f'Marked assessment {session_id} as paid with Stripe session {stripe_session_id}')
            except Exception as e:
                print(f'Failed to mark assessment as paid: {e}')
                return jsonify({'received': True}), 200  # Still ack webhook

            # CLEAN REPORT FLOW:
            # Do not generate the premium report inside the webhook.
            # /report now renders directly from saved report_data after paid=True.
            print(f'Clean report flow: payment recorded for {session_id}; report will render on /report')
            return jsonify({'received': True}), 200

            # LEGACY BELOW DISABLED BY RETURN ABOVE
            # STEP 2: Auto-trigger premium report generation
            try:
                # Get full results from DB
                assessment = db.get_assessment(session_id)
                if not assessment:
                    print(f'Assessment {session_id} not found in DB')
                    return jsonify({'received': True}), 200
                
                full_results = assessment.get('full_results')
                if not full_results:
                    print(f'No full_results for assessment {session_id}')
                    return jsonify({'received': True}), 200
                
                # Generate report
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                if not api_key:
                    print('ANTHROPIC_API_KEY not configured')
                    return jsonify({'received': True}), 200
                
                # Build complete results structure with ALL needed fields
                # Must match structure expected by generate_premium_report()
                # This includes ALL data types: assessment responses (39), perception questions (3), demographics (4)
                demographics = assessment.get('demographics', {})  # age_group, gender, country, ai_tool_use_frequency
                responses = assessment.get('responses', {})        # 39 assessment + 3 perception questions
                percentiles = assessment.get('percentiles', {})
                
                results_for_report = {
                    'full_results': full_results,
                    'demographics': demographics,  # ← CRITICAL: Used for cohort context in opening section
                    'responses': responses,
                    'percentiles': percentiles,
                    'session_id': session_id
                }
                
                print(f'Webhook: Generating premium report for session {session_id}')
                report_response = generate_premium_report(
                    results=results_for_report,
                    api_key=api_key,
                    session_id=session_id
                )
                
                if not report_response or not report_response.get('success'):
                    print(f'Report generation failed: {report_response.get("error") if report_response else "no response"}')
                    return jsonify({'received': True}), 200
                
                report_dict = report_response.get('report', {})
                if not report_dict:
                    print(f'Report dict empty for session {session_id}')
                    return jsonify({'received': True}), 200
                
                # Build HTML
                # Transform to rendering dict (same as /premium endpoint)
                rendering_dict = build_report_html(report_dict)
                if not rendering_dict:
                    print(f'HTML builder failed for session {session_id}')
                    return jsonify({'received': True}), 200
                
                # Render final HTML with data injection (CRITICAL: was missing this step)
                report_html_str = render_report_html(rendering_dict)
                if not report_html_str:
                    print(f'HTML rendering failed for session {session_id}')
                    return jsonify({'received': True}), 200
                
                # Generate PDF
                pdf_bytes = None
                try:
                    pdf_bytes = build_report_pdf(report_html_str, demographics=demographics)
                    if pdf_bytes:
                        print(f'Report PDF generated successfully for session {session_id}')
                    else:
                        print(f'PDF generation returned None - email will send without attachment')
                except Exception as e:
                    print(f'PDF generation failed (non-fatal): {e}')
                    traceback.print_exc()
                
                # Send email with report

                
                # Update DB with cached report
                try:
                    db.update_report(
                        session_id=session_id,
                        report_html=report_html_str  # Store final HTML (matches /premium flow), use correct column name
                    )
                    print(f'Report cached in DB for session {session_id}')
                except Exception as e:
                    print(f'Failed to cache report: {e}')
                
            except Exception as e:
                print(f'Webhook: Report generation failed: {e}')
                traceback.print_exc()
                # Still return 200 to ack webhook (don't want Stripe retrying)
        
        return jsonify({'received': True}), 200
    
    except Exception as e:
        print(f'Webhook error: {e}')
        traceback.print_exc()
        return jsonify({'error': 'Webhook processing failed'}), 500


# ============================================================
# GENERATE PREMIUM REPORT (POST /premium)
# ============================================================

@app.route('/premium', methods=['POST'])
def premium():
    """
    Generate the paid premium report after payment confirmation.

    Clean flow:
    1. Recover session_id from Stripe if needed
    2. Verify payment if stripe_session_id is provided
    3. Mark assessment as paid
    4. Ensure report_data exists
    5. Add Claude narrative blocks
    6. Render and cache final HTML
    7. Return report_url
    """
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get('session_id')
        stripe_session_id = request_data.get('stripe_session_id')
        full_results = request_data.get('full_results')
        report_email = request_data.get('report_email')

        db = get_supabase_client()

        # Step 1: Recover session_id from Stripe if not provided
        failed_step = 'stripe_session_recovery'
        stripe_session = None
        if stripe_session_id:
            stripe_session = fetch_stripe_session(stripe_session_id)
            if stripe_session and not session_id:
                session_id = stripe_session.get('client_reference_id')
                print(f'Recovered session_id from Stripe: {session_id}')

        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No session_id provided or recoverable'
            }), 400

        # Step 2: Check cached report first
        failed_step = 'cached_report_lookup'
        cached_report = db.get_cached_report(session_id)
        if cached_report:
            print(f'Report cache hit for session {session_id}')
            return jsonify({
                'success': True,
                'session_id': session_id,
                'report_url': make_report_url(session_id),
                'cached': True
            }), 200

        # Step 3: Verify payment when Stripe session is provided
        failed_step = 'payment_verification'
        if stripe_session_id:
            if not stripe_session:
                return jsonify({
                    'success': False,
                    'error': 'Payment verification failed. Please contact support.'
                }), 402

            payment_status = stripe_session.get('payment_status')
            if payment_status != 'paid':
                print(f'Payment not confirmed for Stripe session {stripe_session_id}')
                return jsonify({
                    'success': False,
                    'error': 'Payment not confirmed. If you just paid, please refresh this page.'
                }), 402

            customer_details = stripe_session.get('customer_details') or {}
            stripe_email = customer_details.get('email') or stripe_session.get('customer_email')
            if stripe_email:
                report_email = stripe_email
                db.update_assessment(
                    session_id=session_id,
                    report_email=stripe_email
                )
                print(f'Updated assessment report_email to: {stripe_email}')

        # Step 4: Load assessment
        failed_step = 'assessment_load'
        assessment = db.get_assessment(session_id)
        if not assessment:
            return jsonify({
                'success': False,
                'error': 'Assessment data not found'
            }), 404

        if not full_results:
            full_results = assessment.get('full_results')

        if not full_results:
            return jsonify({
                'success': False,
                'error': 'Assessment scoring data not found'
            }), 404

        demographics = assessment.get('demographics', {}) or {}
        responses = assessment.get('responses', {}) or {}

        if not full_results.get('perception_gaps'):
            full_results['perception_gaps'] = assessment.get('perception_gaps', [])
        if not full_results.get('rare_combinations'):
            full_results['rare_combinations'] = assessment.get('patterns', [])

        # Step 5: Mark as paid
        failed_step = 'mark_paid'
        db.update_assessment(
            session_id=session_id,
            paid=True,
            paid_at=datetime.utcnow().isoformat(),
            stripe_session_id=stripe_session_id,
            report_email=report_email or assessment.get('report_email')
        )

        # Step 6: Ensure canonical report_data exists
        failed_step = 'build_report_data'
        report_data = assessment.get('report_data')

        if not report_data:
            report_data = build_report_data(
                scoring_results=full_results,
                responses=responses,
                demographics=demographics,
                email=report_email or assessment.get('report_email'),
                session_id=session_id
            )
            assert_report_data_contract(report_data)

        # Step 7: Add Claude narrative blocks
        failed_step = 'claude_narrative_generation'
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report_data = run_with_retries(
            failed_step,
            lambda: add_claude_narratives(
                report_data=report_data,
                api_key=api_key
            ),
            attempts=3
        )

        db.update_assessment(
            session_id=session_id,
            report_data=report_data,
            report_email=report_email or assessment.get('report_email')
        )

        # Step 8: Render final HTML, generate PDF, upload PDF, cache HTML, and send email
        failed_step = 'report_html_render'
        report_html_str = run_with_retries(
            failed_step,
            lambda: render_report(report_data),
            attempts=3
        )

        pdf_bytes = None
        pdf_url = None

        if build_report_pdf:
            failed_step = 'pdf_generation_upload'
            try:
                def generate_and_upload_pdf():
                    generated_pdf = build_report_pdf(report_html_str)
                    if not generated_pdf:
                        raise RuntimeError('PDF generation returned empty bytes')
                    generated_pdf_url = upload_report_pdf(session_id, generated_pdf)
                    return generated_pdf, generated_pdf_url

                pdf_bytes, pdf_url = run_with_retries(
                    failed_step,
                    generate_and_upload_pdf,
                    attempts=3
                )
                print(f'PDF generated and uploaded for session {session_id}')
            except Exception as e:
                print(f'PDF generation/upload failed non-fatally: {e}')
                notify_report_failure(
                    session_id=session_id,
                    customer_email=report_email or assessment.get('report_email'),
                    failed_step=failed_step,
                    error=e,
                    traceback_text=traceback.format_exc(),
                    notify_customer=False,
                    context={'impact': 'Report HTML still generated; customer email may send without PDF'}
                )
        else:
            print('PDF generation skipped: build_report_pdf is not available')

        failed_step = 'cache_report'
        db.update_report(
            session_id=session_id,
            report_html=report_html_str,
            report_generated_at=datetime.utcnow().isoformat()
        )

        # Step 9: Email delivery via Resend. Non-fatal: report remains available online even if email fails.
        resend_key = os.environ.get('RESEND_API_KEY')
        delivery_email = report_email or assessment.get('report_email')

        if send_report_email and resend_key and delivery_email:
            failed_step = 'customer_report_email'
            try:
                def send_customer_report_email():
                    result = send_report_email(
                        to_email=delivery_email,
                        report_html=report_html_str,
                        demographics=demographics,
                        resend_api_key=resend_key,
                        session_id=session_id,
                        pdf_bytes=pdf_bytes
                    )
                    if not result or not result.get('success'):
                        raise RuntimeError(f'Resend report email failed: {result}')
                    return result

                email_result = run_with_retries(
                    failed_step,
                    send_customer_report_email,
                    attempts=3
                )
                print(f'Report email sent to {delivery_email}: {email_result}')
            except Exception as e:
                print(f'Email sending failed non-fatally: {e}')
                notify_report_failure(
                    session_id=session_id,
                    customer_email=delivery_email,
                    failed_step=failed_step,
                    error=e,
                    traceback_text=traceback.format_exc(),
                    notify_customer=False,
                    context={'impact': 'Report generated and cached, but customer email failed'}
                )
        else:
            print('Email not sent: missing send_report_email, RESEND_API_KEY, or delivery email')
            if delivery_email:
                notify_report_failure(
                    session_id=session_id,
                    customer_email=delivery_email,
                    failed_step='customer_report_email_configuration',
                    error=RuntimeError('Missing send_report_email, RESEND_API_KEY, or delivery email'),
                    traceback_text='',
                    notify_customer=False,
                    context={
                        'has_send_report_email': bool(send_report_email),
                        'has_resend_key': bool(resend_key),
                        'has_delivery_email': bool(delivery_email)
                    }
                )

        return jsonify({
            'success': True,
            'message': 'Premium report ready',
            'session_id': session_id,
            'report_url': make_report_url(session_id),
            'pdf_url': pdf_url,
            'email_sent_to': delivery_email if send_report_email and resend_key and delivery_email else None,
            'cached': False,
            'narrative_generation': report_data.get('narrative_generation', {})
        }), 200
    except Exception as e:
        tb = traceback.format_exc()
        print(f'Premium endpoint error: {e}')
        traceback.print_exc()
        notify_report_failure(
            session_id=session_id,
            customer_email=delivery_email or report_email,
            failed_step=failed_step,
            error=e,
            traceback_text=tb,
            notify_customer=bool(delivery_email or report_email),
            context={'endpoint': '/premium', 'stripe_session_id': stripe_session_id or ''}
        )
        return jsonify({
            'success': False,
            'error': 'Report generation failed'
        }), 500


# ============================================================
# RETRIEVE PREMIUM REPORT (GET /report)
# ============================================================

@app.route('/report', methods=['GET'])
def get_report():
    """
    Retrieve and display premium report by session_id.

    Clean report flow:
    - Load assessment row
    - Require paid=True
    - Render final HTML from report_data
    - Cache report_html as a convenience
    - Return text/html
    """
    try:
        session_id = request.args.get('session_id')
        print(f'[REPORT] Requested report for session_id={session_id}')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400

        db = get_supabase_client()
        assessment = db.get_assessment(session_id)

        if not assessment:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        if not assessment.get('paid'):
            return jsonify({'success': False, 'error': 'Report not purchased'}), 403

        report_data = assessment.get('report_data')

        # Recovery fallback for older rows created before report_data existed.
        if not report_data:
            full_results = assessment.get('full_results') or {}
            responses = assessment.get('responses') or {}
            demographics = assessment.get('demographics') or {}

            if not full_results or not responses or not demographics:
                # Final fallback: if old cached HTML exists, return it.
                old_report_html = assessment.get('report_html')
                if old_report_html:
                    return old_report_html, 200, {'Content-Type': 'text/html; charset=utf-8'}

                return jsonify({'success': False, 'error': 'Report data not found'}), 404

            report_data = build_report_data(
                scoring_results=full_results,
                responses=responses,
                demographics=demographics,
                email=assessment.get('report_email'),
                session_id=session_id
            )
            assert_report_data_contract(report_data)
            db.update_assessment(session_id=session_id, report_data=report_data)

        report_html = render_report(report_data)

        # Cache final HTML, but keep report_data as the source of truth.
        try:
            db.update_report(
                session_id=session_id,
                report_html=report_html,
                report_generated_at=datetime.utcnow().isoformat()
            )
        except Exception as e:
            print(f'Non-fatal: failed to cache report_html: {e}')

        print(f'[REPORT] Returning HTML report for session_id={session_id}, length={len(report_html)}')
        return report_html, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        print(f'Get report error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve report'}), 500



# ============================================================
# TEST FAILURE EMAILS (POST /test-error-email)
# ============================================================

@app.route('/test-error-email', methods=['POST'])
def test_error_email():
    """Send test admin/customer failure notifications without generating a real report."""
    try:
        data = request.get_json() or {}
        test_customer_email = data.get('customer_email') or data.get('email')
        test_session_id = data.get('session_id') or 'test-session-id'
        try:
            raise RuntimeError('Test report failure notification')
        except Exception as test_error:
            notify_report_failure(
                session_id=test_session_id,
                customer_email=test_customer_email,
                failed_step='test_error_email',
                error=test_error,
                traceback_text=traceback.format_exc(),
                notify_customer=bool(test_customer_email),
                context={'endpoint': '/test-error-email', 'test': True}
            )
        return jsonify({
            'success': True,
            'message': 'Test failure notification attempted',
            'admin_email': ADMIN_ERROR_EMAIL,
            'customer_email': test_customer_email
        }), 200
    except Exception as e:
        print(f'Test error email endpoint failed: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# TEST OPENING SECTION (GET /test-opening)
# ============================================================

@app.route('/test-opening', methods=['GET'])
def test_opening():
    """
    Test endpoint for opening section builder.
    
    Query params:
        session_id: Assessment session ID to test with
    
    Response:
    {
        "success": true,
        "prewritten_statement": "...",
        "findings": "...",
        "metadata": {...}
    }
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No session_id provided',
                'usage': 'GET /test-opening?session_id=<uuid>'
            }), 400
        
        # Import report_builder
        try:
            from report_builder import build_opening_section
        except ImportError as e:
            print(f'Failed to import report_builder: {e}')
            return jsonify({
                'success': False,
                'error': 'report_builder module not found'
            }), 500
        
        # Get API key
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'ANTHROPIC_API_KEY not configured'
            }), 500
        
        # Load assessment from Supabase
        db = get_supabase_client()
        assessment = db.get_assessment(session_id)
        
        if not assessment:
            return jsonify({
                'success': False,
                'error': f'Session {session_id} not found'
            }), 404
        
        # Build results dict
        full_results = assessment.get('full_results', {})
        percentiles = assessment.get('percentiles', {})
        responses = assessment.get('responses', {})
        demographics = assessment.get('demographics', {})
        
        if not percentiles:
            return jsonify({
                'success': False,
                'error': 'No percentiles data for this session'
            }), 400
        
        results = {
            'full_results': full_results,
            'percentiles': percentiles,
            'responses': responses,
            'demographics': demographics,
            'session_id': session_id
        }
        
        print(f'[TEST OPENING] Building opening for session {session_id}')
        
        # Call report_builder
        output = build_opening_section(
            results=results,
            api_key=api_key,
            session_id=session_id
        )
        
        if not output or not output.get('success'):
            print(f'[TEST OPENING] Failed: {output.get("error")}')
            return jsonify(output), 500
        
        print(f'[TEST OPENING] Success')
        
        return jsonify(output), 200
    
    except Exception as e:
        print(f'Test opening error: {e}')
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error: {str(e)}'
        }), 500


# ============================================================
# MANUAL REPORT RECOVERY
# ============================================================

@app.route('/recover-report', methods=['GET'])
def recover_report_page():
    """
    UI for manually regenerating reports.
    Paste a session ID and click Generate to:
    1. Fetch assessment data from Supabase
    2. Generate premium report
    3. Create PDF
    4. Send email
    """
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>HCI Report Recovery</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 500px;
                width: 100%;
                padding: 40px;
            }
            h1 {
                font-size: 28px;
                margin-bottom: 10px;
                color: #333;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: #333;
                font-size: 14px;
            }
            input {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 14px;
                font-family: monospace;
                transition: border-color 0.2s;
            }
            input:focus {
                outline: none;
                border-color: #667eea;
            }
            button {
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            button:active {
                transform: translateY(0);
            }
            button:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
            }
            .status {
                margin-top: 20px;
                padding: 15px;
                border-radius: 6px;
                display: none;
                font-size: 14px;
            }
            .status.loading {
                display: block;
                background: #e3f2fd;
                color: #1976d2;
                border: 1px solid #90caf9;
            }
            .status.success {
                display: block;
                background: #e8f5e9;
                color: #388e3c;
                border: 1px solid #81c784;
            }
            .status.error {
                display: block;
                background: #ffebee;
                color: #d32f2f;
                border: 1px solid #ef5350;
            }
            .spinner {
                display: inline-block;
                width: 12px;
                height: 12px;
                border: 2px solid transparent;
                border-radius: 50%;
                border-top-color: #1976d2;
                animation: spin 0.8s linear infinite;
                margin-right: 8px;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .info {
                background: #f5f5f5;
                padding: 15px;
                border-radius: 6px;
                margin-top: 20px;
                font-size: 13px;
                color: #666;
                line-height: 1.6;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 Report Recovery</h1>
            <p class="subtitle">Regenerate and email a report</p>
            
            <form id="recoveryForm">
                <div class="form-group">
                    <label for="sessionId">Session ID</label>
                    <input
                        type="text"
                        id="sessionId"
                        name="sessionId"
                        placeholder="Paste session UUID here"
                        required
                    />
                </div>
                <button type="submit" id="generateBtn">Generate & Email Report</button>
            </form>
            
            <div class="status" id="status"></div>
            
            <div class="info">
                <strong>How to use:</strong><br>
                1. Get the session ID from Supabase<br>
                2. Paste it above<br>
                3. Click "Generate & Email Report"<br>
                4. Report will be created and emailed immediately
            </div>
        </div>

        <script>
            const form = document.getElementById('recoveryForm');
            const statusEl = document.getElementById('status');
            const generateBtn = document.getElementById('generateBtn');
            const sessionIdInput = document.getElementById('sessionId');

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const sessionId = sessionIdInput.value.trim();
                if (!sessionId) {
                    showStatus('Please enter a session ID', 'error');
                    return;
                }

                generateBtn.disabled = true;
                showStatus('<span class="spinner"></span>Generating report and sending email...', 'loading');

                try {
                    const response = await fetch('/recover-report-action', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: sessionId })
                    });

                    const data = await response.json();

                    if (data.success) {
                        showStatus(
                            '✓ Report generated and email sent successfully!\\n' + 
                            'Email should arrive within a few seconds.',
                            'success'
                        );
                        sessionIdInput.value = '';
                    } else {
                        showStatus('✗ Error: ' + (data.error || 'Unknown error'), 'error');
                    }
                } catch (err) {
                    showStatus('✗ Connection error: ' + err.message, 'error');
                } finally {
                    generateBtn.disabled = false;
                }
            });

            function showStatus(message, type) {
                statusEl.textContent = message;
                statusEl.className = 'status ' + type;
            }
        </script>
    </body>
    </html>
    '''


@app.route('/recover-report-action', methods=['POST'])
def recover_report_action():
    """
    Manual recovery action for paid report delivery.

    Takes a session_id, rebuilds report_data, regenerates the HTML report,
    generates/uploads the PDF when available, caches the report, and sends
    the customer report email again.
    """
    try:
        data = request.json or {}
        session_id = (data.get('session_id') or '').strip()

        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        print(f'[RECOVER] Processing session {session_id}')

        db = get_supabase_client()
        assessment = db.get_assessment(session_id)

        if not assessment:
            return jsonify({'success': False, 'error': 'Session not found in database'}), 404

        responses = assessment.get('responses') or {}
        demographics = assessment.get('demographics') or {}
        full_results = assessment.get('full_results') or {}
        delivery_email = assessment.get('report_email')

        if not responses or not demographics or not full_results:
            return jsonify({
                'success': False,
                'error': 'Assessment row missing responses, demographics, or full_results'
            }), 500

        if not delivery_email:
            return jsonify({
                'success': False,
                'error': 'Assessment row has no report_email/customer email to send to'
            }), 500

        # Preserve stored gap/pattern fields if full_results is missing them.
        if not full_results.get('perception_gaps'):
            full_results['perception_gaps'] = assessment.get('perception_gaps', [])
        if not full_results.get('rare_combinations'):
            full_results['rare_combinations'] = assessment.get('patterns', [])

        # Rebuild the canonical report_data source of truth.
        report_data = build_report_data(
            scoring_results=full_results,
            responses=responses,
            demographics=demographics,
            email=delivery_email,
            session_id=session_id
        )
        assert_report_data_contract(report_data)

        # Regenerate Claude narrative blocks where the API key is configured.
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            report_data = add_claude_narratives(
                report_data=report_data,
                api_key=api_key
            )
        else:
            print('[RECOVER] ANTHROPIC_API_KEY not configured; using deterministic report fallback')

        report_html = render_report(report_data)

        # Generate and upload PDF, matching the live /premium path.
        pdf_bytes = None
        pdf_url = None
        if build_report_pdf:
            try:
                pdf_bytes = build_report_pdf(report_html)
                if pdf_bytes:
                    pdf_url = upload_report_pdf(session_id, pdf_bytes)
                    print(f'[RECOVER] PDF generated for session {session_id}')
                else:
                    print(f'[RECOVER] PDF generation returned empty bytes for session {session_id}')
            except Exception as pdf_error:
                print(f'[RECOVER] PDF generation/upload failed: {pdf_error}')
                traceback.print_exc()
        else:
            print('[RECOVER] PDF generation skipped: build_report_pdf is not available')

        # Cache report_data and HTML before email, so the customer link works even if email has no PDF.
        db.update_assessment(
            session_id=session_id,
            report_data=report_data,
            paid=True,
            report_email=delivery_email
        )
        db.update_report(
            session_id=session_id,
            report_html=report_html,
            report_generated_at=datetime.utcnow().isoformat()
        )

        # Send the customer email with PDF attachment when available.
        resend_key = os.environ.get('RESEND_API_KEY')
        email_result = {'success': False, 'error': 'Email not attempted'}
        if send_report_email and resend_key:
            email_result = send_report_email(
                to_email=delivery_email,
                report_html=report_html,
                demographics=demographics,
                resend_api_key=resend_key,
                session_id=session_id,
                pdf_bytes=pdf_bytes
            )
            if not email_result.get('success'):
                print(f'[RECOVER] Email send failed for {session_id}: {email_result}')
                return jsonify({
                    'success': False,
                    'error': 'Report rebuilt, but email sending failed',
                    'session_id': session_id,
                    'report_url': make_report_url(session_id),
                    'pdf_url': pdf_url,
                    'email_result': email_result
                }), 500
        else:
            missing = []
            if not send_report_email:
                missing.append('send_report_email')
            if not resend_key:
                missing.append('RESEND_API_KEY')
            return jsonify({
                'success': False,
                'error': 'Report rebuilt, but email could not be sent because configuration is missing: ' + ', '.join(missing),
                'session_id': session_id,
                'report_url': make_report_url(session_id),
                'pdf_url': pdf_url
            }), 500

        print(f'[RECOVER] ✓ Report recovered and emailed to {delivery_email} for {session_id}')
        return jsonify({
            'success': True,
            'message': 'Report regenerated and emailed successfully',
            'session_id': session_id,
            'report_url': make_report_url(session_id),
            'pdf_url': pdf_url,
            'email_sent_to': delivery_email,
            'email_result': email_result,
            'data_quality': report_data.get('data_quality', {}),
            'narrative_generation': report_data.get('narrative_generation', {})
        }), 200

    except Exception as e:
        print(f'[RECOVER] Error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Server error'}), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == '__main__':
    # Verify dependencies on startup
    try:
        _ = get_supabase_client()
        print('✓ Supabase client initialized')
    except Exception as e:
        print(f'⚠ Supabase initialization failed: {e}')
    
    try:
        _ = get_stripe_config()
        print('✓ Stripe config initialized')
    except Exception as e:
        print(f'⚠ Stripe initialization failed: {e}')
    
    
    try:
        _ # PDF generation uses build_report_pdf - no separate initialization needed
        print('✓ PDF handler configured')
    except Exception as e:
        print(f'⚠ PDF handler configuration failed: {e}')
    
    print('\nStarting HCI Assessment API...')
    app.run(host='0.0.0.0', port=5000, debug=False)
