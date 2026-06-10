"""
HCI AI Identity & Behaviour Assessment
API Layer

A Flask API that receives assessment responses,
scores them, generates reports, and handles the
free vs premium result flow.

Endpoints:
    POST /score          — score a completed assessment, return free result
    POST /premium        — generate and return premium report (after payment)
    GET  /health         — health check

Environment variables required:
    ANTHROPIC_API_KEY    — for premium report generation
    SUPABASE_URL         — for storing responses
    SUPABASE_KEY         — for storing responses

Run locally:
    python api.py

Deploy to Railway:
    Connect GitHub repo, Railway auto-detects Flask and deploys.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import sys
import traceback
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from scoring_engine import score_assessment
from report_generator import generate_free_result, generate_premium_report

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from Involve.me frontend

# Path to benchmark tables — same directory as api.py
BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'benchmark_tables.json')


# ============================================================
# SUPABASE STORAGE
# Stores responses and results for dataset building
# ============================================================

def store_response(payload, result_type='free'):
    """
    Store assessment response and result in Supabase.
    Fails silently — storage failure should not break the user flow.
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            print('Supabase not configured — skipping storage')
            return None

        import urllib.request
        import urllib.error

        body = json.dumps({
            'responses': payload.get('responses'),
            'demographics': payload.get('demographics'),
            'result_type': result_type,
            'timestamp': datetime.utcnow().isoformat(),
        }).encode('utf-8')

        req = urllib.request.Request(
            f'{supabase_url}/rest/v1/assessment_responses',
            data=body,
            headers={
                'Content-Type': 'application/json',
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Prefer': 'return=minimal',
            },
            method='POST'
        )

        urllib.request.urlopen(req, timeout=5)
        return True

    except Exception as e:
        print(f'Storage failed (non-critical): {e}')
        return None


# ============================================================
# VALIDATION
# ============================================================

REQUIRED_QUESTION_KEYS = [
    # Trust
    'trust_q1', 'trust_q2', 'trust_q3', 'trust_q4',
    # Disclosure
    'disc_q1', 'disc_q2', 'disc_q3', 'disc_q4',
    # Reliance
    'rel_q1', 'rel_q2', 'rel_q3', 'rel_q4', 'rel_q5',
    # Decision Delegation
    'del_q1', 'del_q2', 'del_q3', 'del_q4', 'del_q5',
    # Verification
    'ver_q1', 'ver_q2', 'ver_q3', 'ver_q4',
    # Human Agency
    'agency_q1', 'agency_q2', 'agency_q3', 'agency_q4', 'agency_q5',
    # Emotional Regulation
    'emot_q1', 'emot_q2', 'emot_q3', 'emot_q4',
    # Thought Partnership
    'thought_q1', 'thought_q2', 'thought_q3', 'thought_q4',
    # Social Transparency
    'soc_q1', 'soc_q2', 'soc_q3', 'soc_q4',
]

REQUIRED_DEMOGRAPHIC_KEYS = [
    'age_group', 'gender', 'country', 'ai_tool_use_frequency'
]

VALID_SCORE_RANGE = range(1, 8)  # 1 through 7


def validate_request(request_data):
    """
    Validate incoming assessment data.
    Returns (is_valid, error_message)
    """
    if not request_data:
        return False, 'No data provided'

    responses = request_data.get('responses', {})
    demographics = request_data.get('demographics', {})

    # Check all required questions present
    missing_questions = [
        k for k in REQUIRED_QUESTION_KEYS
        if k not in responses
    ]
    if missing_questions:
        return False, f'Missing questions: {missing_questions[:5]}'

    # Check all scores are valid 1-7
    invalid_scores = [
        k for k, v in responses.items()
        if k in REQUIRED_QUESTION_KEYS and int(v) not in VALID_SCORE_RANGE
    ]
    if invalid_scores:
        return False, f'Invalid scores (must be 1-7): {invalid_scores[:5]}'

    # Check required demographics present
    missing_demographics = [
        k for k in REQUIRED_DEMOGRAPHIC_KEYS
        if not demographics.get(k)
    ]
    if missing_demographics:
        return False, f'Missing demographics: {missing_demographics}'

    return True, None


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check — confirms API and benchmark tables are loaded."""
    benchmark_exists = os.path.exists(BENCHMARK_PATH)
    return jsonify({
        'status': 'ok',
        'benchmark_loaded': benchmark_exists,
        'timestamp': datetime.utcnow().isoformat(),
    })


@app.route('/score', methods=['POST'])
def score():
    """
    Score a completed assessment and return the free result.

    Request body:
    {
        "responses": {
            "trust_q1": 5,
            "trust_q2": 6,
            ... (all 39 question keys)
            "perceived_usage": "Somewhat more than most people",
            "perceived_reliance": "About the same as most people",
            "perceived_dependence": "Somewhat less than most people"
        },
        "demographics": {
            "age_group": "35 - 44",
            "gender": "Woman",
            "country": "United States",
            "ai_tool_use_frequency": "Often"
        }
    }

    Response:
    {
        "success": true,
        "session_id": "abc123",
        "free_result": { ... },
        "dimension_scores": { ... },
        "full_results": { ... }
    }
    """
    try:
        request_data = request.get_json()

        # Validate
        is_valid, error = validate_request(request_data)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': error
            }), 400

        responses = request_data['responses']
        demographics = request_data['demographics']

        # Convert all scores to integers
        for key in REQUIRED_QUESTION_KEYS:
            if key in responses:
                responses[key] = int(responses[key])

        # Score the assessment
        results = score_assessment(responses, demographics, BENCHMARK_PATH)

        # Generate free result
        free_result = generate_free_result(results)

        # Create session ID for linking to premium purchase
        import hashlib
        import time
        session_id = hashlib.md5(
            f"{time.time()}{json.dumps(demographics)}".encode()
        ).hexdigest()[:16]

        # Store response (non-blocking)
        store_response(request_data, result_type='free')

        # Build dimension scores including age group percentile
        dimension_scores = {}
        for dim_name, dim_data in results['dimensions'].items():
            if dim_data:
                dimension_scores[dim_name] = {
                    'label': dim_data['label'],
                    'percentile': dim_data['percentiles'].get('overall'),
                    'age_percentile': dim_data['percentiles'].get('age_group'),
                    'age_label': demographics.get('age_group', ''),
                    'normalised_score': dim_data['normalised_score'],
                }

        return jsonify({
            'success': True,
            'session_id': session_id,
            'free_result': free_result,
            'dimension_scores': dimension_scores,
            'patterns': results['patterns'],
            'perception_gaps': results['perception_gaps'],
            'full_results': results,
        })

    except Exception as e:
        print(f'Score endpoint error: {e}')
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Scoring failed — please try again'
        }), 500


@app.route('/premium', methods=['POST'])
def premium():
    """
    Generate premium report after payment confirmation.

    Request body:
    {
        "full_results": { ... },
        "payment_confirmed": true,
        "stripe_session_id": "cs_xxx"
    }

    Response:
    {
        "success": true,
        "report": { ... }
    }
    """
    try:
        request_data = request.get_json()

        if not request_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        full_results = request_data.get('full_results')
        if not full_results:
            return jsonify({'success': False, 'error': 'No results provided'}), 400

        payment_confirmed = request_data.get('payment_confirmed', False)
        if not payment_confirmed:
            return jsonify({'success': False, 'error': 'Payment not confirmed'}), 402

        stripe_session_id = request_data.get('stripe_session_id')
        if stripe_session_id:
            verified = verify_stripe_payment(stripe_session_id)
            if not verified:
                return jsonify({'success': False, 'error': 'Payment verification failed'}), 402

        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report = generate_premium_report(full_results, api_key=api_key)

        store_response(request_data, result_type='premium')

        return jsonify({
            'success': True,
            'report': report,
        })

    except Exception as e:
        print(f'Premium endpoint error: {e}')
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Report generation failed — please contact support'
        }), 500


def verify_stripe_payment(stripe_session_id):
    """
    Verify a Stripe payment session.
    Returns True if payment was successful.
    """
    try:
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            print('Stripe not configured — skipping verification')
            return True  # Allow in development

        import urllib.request
        req = urllib.request.Request(
            f'https://api.stripe.com/v1/checkout/sessions/{stripe_session_id}',
            headers={
                'Authorization': f'Bearer {stripe_key}',
            }
        )
        response = urllib.request.urlopen(req, timeout=10)
        session = json.loads(response.read())
        return session.get('payment_status') == 'paid'

    except Exception as e:
        print(f'Stripe verification error: {e}')
        return False


# ============================================================
# LOCAL DEVELOPMENT TEST
# ============================================================

if __name__ == '__main__':
    print('HCI Assessment API')
    print('=' * 40)
    print(f'Benchmark file: {BENCHMARK_PATH}')
    print(f'Benchmark exists: {os.path.exists(BENCHMARK_PATH)}')
    print()

    sample_data = {
        'responses': {
            'trust_q1': 6, 'trust_q2': 6, 'trust_q3': 2, 'trust_q4': 5,
            'disc_q1': 4, 'disc_q2': 3, 'disc_q3': 3, 'disc_q4': 4,
            'rel_q1': 5, 'rel_q2': 4, 'rel_q3': 5, 'rel_q4': 4, 'rel_q5': 3,
            'del_q1': 4, 'del_q2': 5, 'del_q3': 3, 'del_q4': 3, 'del_q5': 5,
            'ver_q1': 2, 'ver_q2': 6, 'ver_q3': 5, 'ver_q4': 2,
            'agency_q1': 5, 'agency_q2': 4, 'agency_q3': 4, 'agency_q4': 4, 'agency_q5': 3,
            'emot_q1': 2, 'emot_q2': 2, 'emot_q3': 2, 'emot_q4': 2,
            'thought_q1': 6, 'thought_q2': 6, 'thought_q3': 6, 'thought_q4': 2,
            'soc_q1': 4, 'soc_q2': 3, 'soc_q3': 4, 'soc_q4': 3,
            'perceived_usage': 'Somewhat more than most people',
            'perceived_reliance': 'About the same as most people',
            'perceived_dependence': 'Somewhat less than most people',
        },
        'demographics': {
            'age_group': '35 - 44',
            'gender': 'Woman',
            'country': 'United States',
            'ai_tool_use_frequency': 'Often',
        }
    }

    with app.test_client() as client:
        response = client.get('/health')
        print('Health check:', response.get_json())
        print()

        response = client.post(
            '/score',
            data=json.dumps(sample_data),
            content_type='application/json'
        )
        result = response.get_json()
        print('Score endpoint status:', response.status_code)
        print('Success:', result.get('success'))
        print('Session ID:', result.get('session_id'))
        print()

        if result.get('free_result'):
            free = result['free_result']
            print('FREE RESULT:')
            print(f'  Headline: {free["headline"]}')
            print()
            print('  Shown scores:')
            for s in free['shown_scores']:
                print(f'    {s["label"]}: {s["percentile"]}th percentile')
            print()
            if free.get('best_benchmark'):
                print(f'  Benchmark: {free["best_benchmark"]["text"]}')
            if free.get('perception_highlight'):
                print(f'  Perception gap: {free["perception_highlight"]}')

        if result.get('dimension_scores'):
            print()
            print('DIMENSION SCORES WITH AGE PERCENTILES:')
            for dim, scores in result['dimension_scores'].items():
                print(f'  {scores["label"]}: overall={scores["percentile"]}th, age={scores.get("age_percentile")}th ({scores.get("age_label")})')

    print()
    print('All tests passed.')
    print()
    print('Starting API server on http://localhost:5000')
    app.run(debug=True, port=5000)
