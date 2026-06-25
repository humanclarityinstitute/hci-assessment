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
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import Layer 1 (Scoring)
from scoring_engine import score_assessment
from benchmark_builder import get_benchmark

# Import Layer 2 (API integrations)
from supabase_client import get_supabase_client
from stripe_config import get_stripe_config
from email_template import get_email_template
from report_pdf import get_report_pdf

# Import Layer 3 (Report generation)
from report_generator import generate_premium_report
from hci_report_page_builder import build_report_html

# Create Flask app
app = Flask(__name__)
CORS(app)

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

def generate_response_percentiles(responses, demographics, scoring_results):
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
        
        response_percentiles = {}
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
                
                response_percentiles[q_key] = {
                    'response': user_response,
                    'percentile_overall': pct_overall,
                    'percentile_age_group': pct_age_group,
                    'question_text': question_text_map.get(q_key, f'Question {q_key}'),
                    'dimension': dim_name,
                    'n_overall': n_overall,
                    'n_age_group': n_age_group,
                    'is_rare': is_rare
                }
        
        return response_percentiles
    
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
        response_percentiles = generate_response_percentiles(responses, demographics, scoring_results)
        
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
            percentiles=response_percentiles,
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
            'response_percentiles': response_percentiles,          # ← NEW (Requirement 2)
            'perception_gaps': scoring_results.get('perception_gaps', []),
            'rare_combinations': scoring_results.get('rare_combinations', []),
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
            'response_percentiles': assessment.get('response_percentiles', {}),
            'demographics': assessment.get('demographics', {}),
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
    On checkout.session.completed, we mark the assessment as paid
    and trigger report generation.
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
            
            # TODO: In future, correlate stripe_session_id back to assessment session_id
            # For now, we rely on the /premium endpoint to provide the assessment session_id
            
            print(f'Webhook: Payment confirmed for Stripe session {stripe_session_id}')
        
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
                'message': 'Report retrieved from cache',
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
        
        # Step 4: Get full_results if not provided
        if not full_results:
            full_results = db.get_full_results(session_id)
            if not full_results:
                return jsonify({
                    'success': False,
                    'error': 'Assessment data not found'
                }), 404
        
        # Step 5: Mark as paid
        db.mark_as_paid(session_id, stripe_session_id=stripe_session_id)
        
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
            
            # Generate report dict (9 API calls + 4 data sections)
            report_dict = generate_premium_report(
                results=full_results,
                api_key=api_key,
                session_id=session_id
            )
            
            if not report_dict:
                print(f'Report generator returned empty dict for session {session_id}')
                return jsonify({
                    'success': False,
                    'error': 'Report generation failed'
                }), 500
            
            # Convert report_dict to professional HTML for PDF
            print(f'Building HTML for session {session_id}')
            report_html_str = build_report_html(report_dict)
            
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
        
        # Step 7: Generate PDF and upload to Supabase
        try:
            pdf_handler = get_report_pdf()
            pdf_bytes, pdf_url = pdf_handler.generate_and_upload(report_html_str, session_id)
            
            if not pdf_url:
                print(f'PDF generation failed for session {session_id}')
                # Don't fail entirely - report still displays in browser
                pdf_url = None
        
        except Exception as e:
            print(f'PDF generation error: {e}')
            pdf_url = None
        
        # Step 8: Send email with report link
        email_sent = False
        try:
            if report_email:
                email = get_email_template()
                email_result = email.send_report_email(
                    report_email,
                    session_id,
                    pdf_url=pdf_url
                )
                if email_result.get('success'):
                    email_sent = True
                    print(f'Report email sent to {report_email}')
                else:
                    print(f'Email send failed: {email_result.get("message")}')
        
        except Exception as e:
            print(f'Email sending error: {e}')
        
        # Step 9: Store report in Supabase for later retrieval
        try:
            db.update_report(
                session_id,
                report_html=report_dict,  # Store dict for browser display
                report_pdf_url=pdf_url
            )
            print(f'Report cached for session {session_id}')
        
        except Exception as e:
            print(f'Report caching error: {e}')
        
        return jsonify({
            'success': True,
            'message': 'Report generated and cached'
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
    Retrieve cached premium report by session_id.
    
    Query params:
        session_id: Assessment session ID
    
    Response:
    {
        "success": true,
        "report": {...cached report HTML...}
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
        
        if not assessment.get('paid'):
            return jsonify({'success': False, 'error': 'Report not purchased'}), 403
        
        report_html = assessment.get('report_html')
        if not report_html:
            return jsonify({'success': False, 'error': 'Report not yet generated'}), 404
        
        return jsonify({
            'success': True,
            'report': report_html
        }), 200
    
    except Exception as e:
        print(f'Get report error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve report'}), 500


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
        _ = get_email_template()
        print('✓ Email template initialized')
    except Exception as e:
        print(f'⚠ Email template initialization failed: {e}')
    
    try:
        _ = get_report_pdf()
        print('✓ PDF handler initialized')
    except Exception as e:
        print(f'⚠ PDF handler initialization failed: {e}')
    
    print('\nStarting HCI Assessment API...')
    app.run(host='0.0.0.0', port=5000, debug=False)
