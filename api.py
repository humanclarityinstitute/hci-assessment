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
import urllib.request
import urllib.parse
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import Layer 1 (Scoring)
from scoring_engine import score_assessment
from benchmark_builder import get_benchmark

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


# Import Phase 2 & 3: Report generation and transformation
from report_generator import generate_premium_report
from report_page_builder import build_report_html
from email_sender import send_report_email
from report_pdf_creator import build_report_pdf



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

app = Flask(__name__)
CORS(app)

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
        print(f'PDF upload failed (non-fatal): {e}')
        return None


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
        'timestamp': datetime.utcnow().isoformat(),
    }), 200


# ============================================================
# HELPER: Generate response percentiles (Requirement 2)
# ============================================================

def generate_percentiles(responses, demographics, scoring_results):
    """
    Generate percentiles for each individual question response.
    
    For each of the 39 questions, calculate:
    - User's response (1-7)
    - Percentile vs all participants
    - Percentile vs age group
    - Question text
    - Dimension
    - Sample sizes
    
    Args:
        responses (dict): User's 39 question responses
        demographics (dict): Age group, gender, country, frequency
        scoring_results (dict): Output from scoring_engine (has dimension_scores)
    
    Returns:
        dict: {question_key: {response, percentile_overall, percentile_age_group, ...}}
    """
    try:
        # Load benchmark to calculate percentiles
        benchmark = get_benchmark()
        
        # Map questions to dimensions
        dimension_variables = {
            'trust': ['trust_q1', 'trust_q2', 'trust_q3', 'trust_q4'],
            'disclosure': ['disc_q1', 'disc_q2', 'disc_q3', 'disc_q4'],
            'reliance': ['rel_q1', 'rel_q2', 'rel_q3', 'rel_q4', 'rel_q5'],
            'decision_delegation': ['del_q1', 'del_q2', 'del_q3', 'del_q4', 'del_q5'],
            'verification': ['ver_q1', 'ver_q2', 'ver_q3', 'ver_q4'],
            'human_agency': ['agency_q1', 'agency_q2', 'agency_q3', 'agency_q4', 'agency_q5'],
            'emotional_regulation': ['emot_q1', 'emot_q2', 'emot_q3', 'emot_q4'],
            'thought_partnership': ['thought_q1', 'thought_q2', 'thought_q3', 'thought_q4'],
            'social_transparency': ['soc_q1', 'soc_q2', 'soc_q3', 'soc_q4']
        }
        
        # Question text mapping (basic — can be enhanced)
        question_text_map = {
            'trust_q1': 'I feel confident trusting information from AI',
            'trust_q2': 'I would rely on AI output without additional verification',
            'trust_q3': 'I worry that AI might present false information to me',
            'trust_q4': 'I trust AI to give me accurate information',
            'disc_q1': 'I share personal thoughts and feelings with AI',
            'disc_q2': 'I tell AI things I haven\'t told other people',
            'disc_q3': 'I am more open with AI than I am with people',
            'disc_q4': 'I use AI as a space to think through personal concerns',
            'rel_q1': 'I feel restless when I don\'t have access to AI',
            'rel_q2': 'I struggle to work without access to my AI tools',
            'rel_q3': 'I feel confident relying on AI outputs',
            'rel_q4': 'I would have difficulty doing my work without AI assistance',
            'rel_q5': 'I rely on AI regularly in my daily work',
            'del_q1': 'I rely on AI to make decisions for me',
            'del_q2': 'I tend to follow AI recommendations even if I\'m unsure',
            'del_q3': 'I worry my skills are declining from delegating to AI',
            'del_q4': 'I regularly hand over tasks to AI',
            'del_q5': 'I accept AI suggestions without much modification',
            'ver_q1': 'I double-check information that AI provides',
            'ver_q2': 'I skip verification because the effort isn\'t worth it',
            'ver_q3': 'I use external sources to verify AI outputs',
            'ver_q4': 'I proceed without checking AI information',
            'agency_q1': 'I feel self-directed when using AI',
            'agency_q2': 'I feel in control of my decisions when AI is involved',
            'agency_q3': 'I trust my own judgement over AI suggestions',
            'agency_q4': 'AI nudges influence me without my realizing it',
            'agency_q5': 'I feel ownership over decisions I make with AI help',
            'emot_q1': 'AI provides me emotional support',
            'emot_q2': 'I use AI as an alternative to human emotional support',
            'emot_q3': 'AI helps me process difficult emotions',
            'emot_q4': 'I use AI to cope with stress or anxiety',
            'thought_q1': 'AI helps me think more deeply',
            'thought_q2': 'AI validates my existing beliefs rather than challenging them',
            'thought_q3': 'I use AI as a thinking partner to develop ideas',
            'thought_q4': 'AI helps me challenge my assumptions',
            'soc_q1': 'I am transparent with others about my use of AI',
            'soc_q2': 'I conceal how much I use AI from others',
            'soc_q3': 'I am comfortable telling people about my AI use',
            'soc_q4': 'There\'s a gap between how much AI I actually use and what others think',
        }
        
        percentiles = {}
        age_group = demographics.get('age_group', 'unknown')
        
        # Process each question
        for dim_name, questions in dimension_variables.items():
            for q_key in questions:
                if q_key not in responses:
                    continue
                
                user_response = responses[q_key]
                
                # Get percentiles from benchmark
                pct_overall = benchmark.get_percentile(q_key, user_response, segment=None)
                pct_age_group = benchmark.get_percentile(q_key, user_response, segment=('age_group', age_group))
                
                # Get sample sizes
                n_overall = benchmark.get_sample_size(q_key, segment=None)
                n_age_group = benchmark.get_sample_size(q_key, segment=('age_group', age_group))
                
                # Determine if rare or distinctive
                is_rare = pct_overall >= 86 or pct_overall <= 14
                
                                
                percentiles[q_key] = {
                    'response': user_response,
                    'percentile_overall': pct_overall,
                    'percentile_age_group': pct_age_group,
                    'question_text': question_text_map.get(q_key, f'Question {q_key}'),
                    'dimension': dim_name,
                    'n_overall': n_overall,
                    'n_age_group': n_age_group,
                    'is_rare': is_rare,
                    'distribution': [sum(1 for v in benchmark.data['dimensions'][dim_name]['overall']['values'] if int(v) == i) for i in range(1, 8)],
                }
        
        return percentiles
    
    except Exception as e:
        print(f'Error generating response percentiles: {e}')
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
            report_email=report_email,
            consent=consent,
            consent_timestamp=consent_timestamp
        )
        
        if not store_result.get('success'):
            print(f'Failed to store assessment: {store_result.get("message")}')
        
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
            'paid': assessment.get('paid', False)
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
                report_html_str = build_report_html(report_dict)
                if not report_html_str:
                    print(f'HTML builder failed for session {session_id}')
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
                        premium_report=report_dict
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
    Generate premium report after payment confirmation.
    
    Request:
    {
        "session_id": "assessment-session-id",  (optional - can be recovered from Stripe)
        "stripe_session_id": "stripe_session_id",  (optional - used to verify payment)
        "full_results": {...}  (optional, retrieved from DB if not provided)
    }
    
    Response:
    {
        "success": true,
        "message": "Report generated and emailed"
    }
    
    This endpoint:
    1. Checks if report is already cached (prevent duplicate generation)
    2. Verifies payment via Stripe (if stripe_session_id provided)
    3. Recovers session_id from Stripe client_reference_id if needed
    4. Marks assessment as paid
    5. Calls report_generator (Layer 3) to create HTML report
    6. Generates PDF and uploads to Supabase Storage
    7. Sends email with report link
    8. Caches report in Supabase
    """
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get('session_id')
        stripe_session_id = request_data.get('stripe_session_id')
        full_results = request_data.get('full_results')
        report_email = request_data.get('report_email')
        
        db = get_supabase_client()
        
        # Step 1: Recover session_id from Stripe if not provided
        # This handles the redirect case where session_id might not be in URL
        stripe_session = None
        if stripe_session_id:
            stripe_session = fetch_stripe_session(stripe_session_id)
            if stripe_session and not session_id:
                session_id = stripe_session.get('client_reference_id')
                print(f'Recovered session_id from Stripe: {session_id}')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided or recoverable'}), 400
        
        # Step 2: Check cache first
        cached_report = db.get_cached_report(session_id)
        if cached_report:
            print(f'Report cache hit for session {session_id}')
            return jsonify({
                'success': True,
                'report': cached_report,
                'cached': True
            }), 200
        
        # Step 3: Verify payment (STRICT GATE)
        # If Stripe session was provided, verify payment was actually made
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
            
            # Get customer email from Stripe (preferred over form email)
            customer_details = stripe_session.get('customer_details') or {}
            stripe_email = customer_details.get('email') or stripe_session.get('customer_email')
            if stripe_email:
                report_email = stripe_email
                # Update assessment row with correct Stripe email (overrides burner email from /score)
                db.update_assessment(
                    session_id=session_id,
                    report_email=stripe_email
                )
                print(f'Updated assessment report_email to: {stripe_email}')
        
        # Step 4: Get complete assessment (all fields needed for report)
        if not full_results:
            assessment = db.get_assessment(session_id)
            if not assessment:
                return jsonify({
                    'success': False,
                    'error': 'Assessment data not found'
                }), 404
            full_results = assessment.get('full_results')
            if not full_results:
                return jsonify({
                    'success': False,
                    'error': 'Assessment scoring data not found'
                }), 404
        else:
            # If full_results was provided in request, still get full assessment for other fields
            assessment = db.get_assessment(session_id)
        
        # Extract all needed fields from assessment
        demographics = assessment.get('demographics', {})
        responses = assessment.get('responses', {})
        percentiles = assessment.get('percentiles', {})
        
        # CRITICAL: Restore data that was calculated in /score but stored in separate DB columns
        # /score calculates these and returns them, but stores them as separate columns
        # We need to put them BACK into full_results so report_generator can find them
        if not full_results.get('perception_gaps'):
            full_results['perception_gaps'] = assessment.get('perception_gaps', [])
        if not full_results.get('rare_combinations'):
            full_results['rare_combinations'] = assessment.get('patterns', [])
        
        # Step 5: Mark as paid and store stripe_session_id (SAME ROW)
        from datetime import datetime
        db.update_assessment(
            session_id=session_id,
            paid=True,
            paid_at=datetime.utcnow().isoformat(),
            stripe_session_id=stripe_session_id
        )
        
        # Step 6: Generate premium report (Layer 3)
        # This calls report_generator which makes 9 Claude API calls
        try:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                print('ANTHROPIC_API_KEY not configured')
                return jsonify({
                    'success': False,
                    'error': 'Report generation not available'
                }), 503
            
            print(f'Generating premium report for session {session_id}')
            
            # PHASE 1: Enrich full_results with calculated data
            # This adds: demographic_percentiles, perception_gaps, rare_combinations,
            # distinctive_responses, question_distributions
            print('Phase 1: Enriching assessment data...')
            full_results = enrich_results_for_report(
                full_results=full_results,
                demographics=demographics,
                benchmark_path=BENCHMARK_PATH
            )
            print('Phase 1: Data enrichment complete')
            
            # Build complete results structure with all data report generator needs
            results_for_report = {
                'full_results': full_results,
                'demographics': demographics,
                'responses': responses,
                'percentiles': percentiles,
                'session_id': session_id,
                'demographic_percentiles': full_results.get('demographic_percentiles', {}),
                'perception_gaps': full_results.get('perception_gaps', []),
                'rare_combinations': full_results.get('rare_combinations', []),
                'distinctive_responses': full_results.get('distinctive_responses', []),
                'question_distributions': full_results.get('question_distributions', {})
            }
            
            # Generate report dict (9 API calls + data sections)
            # PHASE 2 & 3 will be implemented in report_generator.py and hci_report_page_builder.py
            print('Phase 2-3: Generating report...')
            report_response = generate_premium_report(
                results=results_for_report,
                api_key=api_key,
                session_id=session_id
            )
            
            if not report_response or not report_response.get('success'):
                print(f'Report generator failed: {report_response.get("error")}')
                return jsonify({
                    'success': False,
                    'error': 'Report generation failed'
                }), 500
            
            # Extract report dict from response
            report_dict = report_response.get('report', {})
            if not report_dict:
                print(f'Report generator returned empty report dict for session {session_id}')
                return jsonify({
                    'success': False,
                    'error': 'Report generation failed'
                }), 500
            
            # PHASE 4: Transform report_dict to rendering_dict
            print(f'Phase 4: Transforming report to rendering dict for session {session_id}...')
            try:
                rendering_dict = build_report_html(report_dict)
            except Exception as e:
                print(f'report_page_builder.build_report_html() failed: {e}')
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': 'Report transformation failed'
                }), 500
            
            # PHASE 5: Render final HTML with data injection
            print(f'Phase 5: Rendering HTML with data injection for session {session_id}...')
            try:
                report_html_str = render_report_html(rendering_dict)
            except Exception as e:
                print(f'HTML rendering failed: {e}')
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'error': 'HTML rendering failed'
                }), 500
            
            # Report HTML successfully generated - check that it has content
            if not report_html_str:
                print(f'HTML builder returned empty string for session {session_id}')
                return jsonify({
                    'success': False,
                    'error': 'Report rendering failed'
                }), 500
        
        except ImportError as e:
            print(f'Missing report generator module: {e}')
            return jsonify({
                'success': False,
                'error': 'Report generator not available'
            }), 500
        except Exception as e:
            print(f'Report generation error: {e}')
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': f'Report generation failed: {str(e)}'
            }), 500
        
        # Step 7: PDF generation
        pdf_bytes = None
        try:
            pdf_bytes = build_report_pdf(report_html_str, demographics=demographics)
            if pdf_bytes:
                print(f'Report PDF generated successfully for session {session_id}')
            else:
                print(f'PDF generation returned None - email will send without attachment')
        except Exception as e:
            print(f'PDF generation error (non-fatal): {e}')
            traceback.print_exc()
            # Non-fatal - report still displays in browser without PDF
        
        # Step 8: Send email with report link
        email_sent = False
        try:
            if report_email:
                # Call send_report_email directly with all required parameters
                resend_key = os.environ.get('RESEND_API_KEY')
                if resend_key:
                    email_result = send_report_email(
                        to_email=report_email,
                        report_html=report_html_str,
                        demographics=demographics,
                        resend_api_key=resend_key,
                        session_id=session_id,
                        pdf_bytes=pdf_bytes
                    )
                    if email_result.get('success'):
                        email_sent = True
                        print(f'Report email sent to {report_email}')
                    else:
                        print(f'Email send failed: {email_result.get("error")}')
                else:
                    print('RESEND_API_KEY not configured')
        
        except Exception as e:
            print(f'Email sending error: {e}')
            traceback.print_exc()
        
        # Step 9: Upload PDF to Supabase Storage and cache report
        pdf_url = None
        try:
            if pdf_bytes:
                pdf_url = upload_report_pdf(session_id, pdf_bytes)
                print(f'PDF stored with URL: {pdf_url}' if pdf_url else 'PDF upload failed')
        except Exception as e:
            print(f'PDF storage step failed (non-fatal): {e}')

        # Step 10: Cache report and PDF URL in Supabase
        try:
            db.update_assessment(
                session_id=session_id,
                premium_report=report_html_str,  # Complete HTML with window.hciRenderingData
                report_pdf_url=pdf_url,           # Public PDF URL (may be None if upload failed)
                report_generated_at=datetime.utcnow().isoformat()
            )
            print(f'Report and PDF URL cached for session {session_id}')
        
        except Exception as e:
            print(f'Report caching error: {e}')
        
        return jsonify({
            'success': True,
            'report': rendering_dict
        }), 200
    
    except Exception as e:
        print(f'Premium endpoint error: {e}')
        traceback.print_exc()
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
    
    Returns complete HTML (not JSON) that displays in browser.
    
    Query params:
        session_id: Assessment session ID
    
    Returns:
        HTML document with complete report
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400
        
        db = get_supabase_client()
        assessment = db.get_assessment(session_id)
        
        if not assessment:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        if not assessment.get('paid'):
            return jsonify({'success': False, 'error': 'Report not purchased'}), 403
        
        # Get final HTML (with data injection already included)
        report_html = assessment.get('premium_report')
        if not report_html:
            return jsonify({'success': False, 'error': 'Report not yet generated'}), 404
        
        # Return as HTML (not JSON)
        return report_html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    
    except Exception as e:
        print(f'Get report error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve report'}), 500


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
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
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
    Backend for report recovery.
    Takes session_id, regenerates report, and emails it.
    """
    try:
        data = request.json
        session_id = data.get('session_id', '').strip()
        
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        
        print(f'[RECOVER] Processing session {session_id}')
        
        # Get database client and API key
        db = get_supabase_client()
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        
        if not api_key:
            return jsonify({'success': False, 'error': 'API key not configured'}), 500
        
        # Fetch assessment from database
        print(f'[RECOVER] Fetching assessment data...')
        assessment = db.get_assessment(session_id)
        
        if not assessment:
            return jsonify({'success': False, 'error': 'Session not found in database'}), 404
        
        # Extract components
        responses = assessment.get('responses', {})
        demographics = assessment.get('demographics', {})
        full_results = assessment.get('full_results', {})
        percentiles = assessment.get('percentiles', {})
        
        # Build results dict for report generator
        results_for_report = {
            'percentiles': percentiles,
            'full_results': full_results,
            'demographics': demographics,
            'responses': responses,
            'session_id': session_id
        }
        
        # Generate report
        print(f'[RECOVER] Generating premium report...')
        report_response = generate_premium_report(
            results=results_for_report,
            api_key=api_key,
            session_id=session_id
        )
        
        if not report_response.get('success'):
            error_msg = report_response.get('error', 'Unknown error')
            print(f'[RECOVER] Report generation failed: {error_msg}')
            return jsonify({'success': False, 'error': f'Report generation failed: {error_msg}'}), 500
        
        report_dict = report_response.get('report', {})
        if not report_dict:
            return jsonify({'success': False, 'error': 'Report dict is empty'}), 500
        
        # DEBUG: Check what's in report_dict
        print(f'[RECOVER] Report dict keys: {list(report_dict.keys())}')
        print(f'[RECOVER] opening_statement length: {len(report_dict.get("opening_statement", ""))} chars')
        print(f'[RECOVER] top_3_findings length: {len(report_dict.get("top_3_findings", ""))} chars')
        
        # Build HTML
        print(f'[RECOVER] Building HTML...')
        report_html_str = build_report_html(report_dict)
        if not report_html_str:
            return jsonify({'success': False, 'error': 'HTML builder failed'}), 500
        
        # Generate PDF
        print(f'[RECOVER] Generating PDF...')
        pdf_bytes = None
        try:
            pdf_bytes = build_report_pdf(report_html_str, demographics=demographics)
            if pdf_bytes:
                print(f'[RECOVER] PDF generated ({len(pdf_bytes)} bytes)')
        except Exception as e:
            print(f'[RECOVER] PDF generation failed (non-fatal): {e}')
        
        # Send email
        print(f'[RECOVER] Sending email...')
        resend_api_key = os.environ.get('RESEND_API_KEY')
        send_report_email(
            to_email=demographics.get('email', ''),
            report_html=report_html_str,
            demographics=demographics,
            resend_api_key=resend_api_key,
            session_id=session_id,
            pdf_bytes=pdf_bytes
        )
        
        print(f'[RECOVER] ✓ Report recovery complete for {session_id}')
        return jsonify({'success': True, 'message': 'Report generated and emailed successfully'}), 200
        
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
