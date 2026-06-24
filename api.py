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

# Create Flask app
app = Flask(__name__)
CORS(app)

# Configuration
BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'benchmark_tables.json')


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
        
        # Store in Supabase
        db = get_supabase_client()
        store_result = db.store_assessment(
            session_id=session_id,
            responses=responses,
            demographics=demographics,
            full_results=scoring_results,
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
        "session_id": "assessment-session-id",
        "full_results": {...}  (optional, retrieved from DB if not provided)
    }
    
    Response:
    {
        "success": true,
        "message": "Report generated and emailed"
    }
    
    This endpoint:
    1. Checks if report is already cached (prevent duplicate generation)
    2. Marks assessment as paid
    3. Calls report_generator (Layer 3) to create HTML report
    4. Generates PDF and uploads to Supabase Storage
    5. Sends email with report link
    6. Caches report in Supabase
    """
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get('session_id')
        full_results = request_data.get('full_results')
        
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400
        
        db = get_supabase_client()
        
        # Step 1: Check cache
        cached_report = db.get_cached_report(session_id)
        if cached_report:
            print(f'Report cache hit for session {session_id}')
            return jsonify({
                'success': True,
                'message': 'Report retrieved from cache'
            }), 200
        
        # Step 2: Get full_results if not provided
        if not full_results:
            full_results = db.get_full_results(session_id)
            if not full_results:
                return jsonify({
                    'success': False,
                    'error': 'Assessment data not found'
                }), 404
        
        # Step 3: Mark as paid
        db.mark_as_paid(session_id)
        
        # Step 4: Generate report (Layer 3 - to be implemented)
        # For now, return placeholder
        report_html = {
            'dashboard': 'Report will be generated here',
            'section1': 'Section 1 content',
            # Full report would have 10+ sections
        }
        
        # Step 5: Generate PDF and upload
        pdf_handler = get_report_pdf()
        # TODO: Convert report_html to actual HTML string
        report_html_str = json.dumps(report_html)  # Placeholder
        pdf_bytes, pdf_url = pdf_handler.generate_and_upload(report_html_str, session_id)
        
        # Step 6: Send email
        assessment = db.get_assessment(session_id)
        report_email = assessment.get('report_email') if assessment else None
        
        if report_email:
            email = get_email_template()
            email_result = email.send_report_email(
                report_email,
                session_id,
                pdf_url=pdf_url
            )
            if email_result.get('success'):
                print(f'Report email sent to {report_email}')
        
        # Step 7: Cache report
        db.update_report(session_id, report_html=report_html, report_pdf_url=pdf_url)
        
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
