"""
HCI AI Identity & Behaviour Assessment
API Layer — Version 2

Changes from v1:
- Variable name collision fix (request_data instead of data)
- dimension_scores now includes age_percentile and age_label
- variable_highlights now included in /score response
- store_response parameter renamed to payload
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import sys
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from scoring_engine import score_assessment
from report_generator import generate_free_result, generate_premium_report
from email_template import send_report_email

app = Flask(__name__)
CORS(app)

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'benchmark_tables.json')


# ============================================================
# SUPABASE STORAGE
# ============================================================

def store_response(payload, result_type='free', session_id=None, full_results=None):
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            print('Supabase not configured — skipping storage')
            return None

        import urllib.request
        import urllib.error

        demographics = payload.get('demographics', {})
        record = {
            'result_type': result_type,
            'timestamp': datetime.utcnow().isoformat(),
            'responses': payload.get('responses'),
            'demographics': demographics,
            'age_group': demographics.get('age_group', ''),
            'gender': demographics.get('gender', ''),
            'country': demographics.get('country', ''),
            'ai_tool_use_frequency': demographics.get('ai_tool_use_frequency', ''),
        }
        if session_id:
            record['session_id'] = session_id
        if full_results:
            record['full_results'] = full_results

        body = json.dumps(record).encode('utf-8')

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
    'trust_q1', 'trust_q2', 'trust_q3', 'trust_q4',
    'disc_q1', 'disc_q2', 'disc_q3', 'disc_q4',
    'rel_q1', 'rel_q2', 'rel_q3', 'rel_q4', 'rel_q5',
    'del_q1', 'del_q2', 'del_q3', 'del_q4', 'del_q5',
    'ver_q1', 'ver_q2', 'ver_q3', 'ver_q4',
    'agency_q1', 'agency_q2', 'agency_q3', 'agency_q4', 'agency_q5',
    'emot_q1', 'emot_q2', 'emot_q3', 'emot_q4',
    'thought_q1', 'thought_q2', 'thought_q3', 'thought_q4',
    'soc_q1', 'soc_q2', 'soc_q3', 'soc_q4',
]

REQUIRED_DEMOGRAPHIC_KEYS = [
    'age_group', 'gender', 'country', 'ai_tool_use_frequency'
]

VALID_SCORE_RANGE = range(1, 8)


def validate_request(request_data):
    if not request_data:
        return False, 'No data provided'

    responses = request_data.get('responses', {})
    demographics = request_data.get('demographics', {})

    missing_questions = [
        k for k in REQUIRED_QUESTION_KEYS
        if k not in responses
    ]
    if missing_questions:
        return False, f'Missing questions: {missing_questions[:5]}'

    invalid_scores = [
        k for k, v in responses.items()
        if k in REQUIRED_QUESTION_KEYS and int(v) not in VALID_SCORE_RANGE
    ]
    if invalid_scores:
        return False, f'Invalid scores (must be 1-7): {invalid_scores[:5]}'

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

def get_stored_report(session_id):
    """Retrieve a stored premium report from Supabase by session_id."""
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            return None

        import urllib.request
        import urllib.parse

        url = (
            f'{supabase_url}/rest/v1/assessment_responses'
            f'?session_id=eq.{urllib.parse.quote(session_id)}'
            f'&select=premium_report,demographics'
            f'&limit=1'
        )
        req = urllib.request.Request(
            url,
            headers={
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
            }
        )
        response = urllib.request.urlopen(req, timeout=10)
        records = json.loads(response.read())
        if records and records[0].get('premium_report'):
            return records[0]['premium_report']
        return None
    except Exception as e:
        print(f'Report retrieval failed: {e}')
        return None


def store_premium_report(session_id, report):
    """Store generated premium report in Supabase."""
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key:
            return False

        import urllib.request
        import urllib.parse

        body = json.dumps({
            'premium_report': report,
            'report_generated_at': datetime.utcnow().isoformat(),
        }).encode('utf-8')

        url = (
            f'{supabase_url}/rest/v1/assessment_responses'
            f'?session_id=eq.{urllib.parse.quote(session_id)}'
        )
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Prefer': 'return=minimal',
            },
            method='PATCH'
        )
        urllib.request.urlopen(req, timeout=10)
        print(f'Premium report stored for session {session_id}')
        return True
    except Exception as e:
        print(f'Report storage failed (non-critical): {e}')
        return False


@app.route('/health', methods=['GET'])
def health():
    benchmark_exists = os.path.exists(BENCHMARK_PATH)
    return jsonify({
        'status': 'ok',
        'benchmark_loaded': benchmark_exists,
        'timestamp': datetime.utcnow().isoformat(),
    })


@app.route('/score', methods=['POST'])
def score():
    try:
        request_data = request.get_json()

        is_valid, error = validate_request(request_data)
        if not is_valid:
            return jsonify({'success': False, 'error': error}), 400

        responses = request_data['responses']
        demographics = request_data['demographics']

        for key in REQUIRED_QUESTION_KEYS:
            if key in responses:
                responses[key] = int(responses[key])

        results = score_assessment(responses, demographics, BENCHMARK_PATH)
        free_result = generate_free_result(results)

        import hashlib
        import time
        session_id = hashlib.md5(
            f"{time.time()}{json.dumps(demographics)}".encode()
        ).hexdigest()[:16]

        store_response(request_data, result_type='free', session_id=session_id, full_results=results)

        # Build dimension scores with age percentile
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
            'variable_highlights': results.get('variable_highlights', []),
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


@app.route('/get-results', methods=['GET'])
def get_results():
    """
    Retrieve stored assessment results by session_id.
    Called by the premium report page to get full_results
    without depending on sessionStorage.

    Query params:
        session_id: the session ID from the /score response
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400

        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            return jsonify({'success': False, 'error': 'Storage not configured'}), 500

        import urllib.request
        import urllib.parse

        url = (
            f'{supabase_url}/rest/v1/assessment_responses'
            f'?session_id=eq.{urllib.parse.quote(session_id)}'
            f'&select=full_results,demographics'
            f'&limit=1'
        )

        req = urllib.request.Request(
            url,
            headers={
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Content-Type': 'application/json',
            }
        )

        response = urllib.request.urlopen(req, timeout=10)
        records = json.loads(response.read())

        if not records:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        record = records[0]
        full_results = record.get('full_results')

        if not full_results:
            return jsonify({'success': False, 'error': 'Results not stored for this session'}), 404

        return jsonify({
            'success': True,
            'full_results': full_results,
            'session_id': session_id,
        })

    except Exception as e:
        print(f'Get results error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve results'}), 500


@app.route('/premium', methods=['POST'])
def premium():
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

        session_id = request_data.get('session_id')

        # Check if report already exists — return immediately if so
        if session_id:
            existing_report = get_stored_report(session_id)
            if existing_report:
                print(f'Returning cached report for session {session_id}')
                return jsonify({'success': True, 'report': existing_report, 'cached': True})

        # Generate new report
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report = generate_premium_report(full_results, api_key=api_key)

        # Store report in Supabase immediately
        if session_id:
            store_premium_report(session_id, report)

        # Send email if address provided
        report_email = request_data.get('report_email')
        if report_email:
            resend_key = os.environ.get('RESEND_API_KEY')
            if resend_key:
                demographics = full_results.get('demographics', {})
                send_report_email(report_email, report, demographics, resend_key)
            else:
                print('RESEND_API_KEY not configured — skipping email')

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
    try:
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            print('Stripe not configured — skipping verification')
            return True

        import urllib.request
        req = urllib.request.Request(
            f'https://api.stripe.com/v1/checkout/sessions/{stripe_session_id}',
            headers={'Authorization': f'Bearer {stripe_key}'}
        )
        response = urllib.request.urlopen(req, timeout=10)
        session = json.loads(response.read())
        return session.get('payment_status') == 'paid'

    except Exception as e:
        print(f'Stripe verification error: {e}')
        return False


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == '__main__':
    print('HCI Assessment API v2')
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
        print()

        if result.get('variable_highlights'):
            print('VARIABLE HIGHLIGHTS:')
            for h in result['variable_highlights']:
                print(f'  [{h["type"]}] {h["question_key"]}')
                print(f'  Q: {h["question_text"][:70]}')
                print(f'  Response: {h["raw_response"]}/7')
                print(f'  Overall: {h["percentiles"]["overall"]}th')
                print(f'  Age group: {h["percentiles"].get("age_group")}th')
                print()

        if result.get('dimension_scores'):
            print('DIMENSION SCORES (sample):')
            for dim, scores in list(result['dimension_scores'].items())[:3]:
                print(f'  {scores["label"]}: {scores["percentile"]}th overall, {scores.get("age_percentile")}th age group')

    print()
    print('Starting API server on http://localhost:5000')
    app.run(debug=True, port=5000)
