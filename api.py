"""
HCI AI Identity & Behaviour Assessment
API Layer — Version 5

Changes from v4:
- No structural change to the /score response: it already forwards
  variable_highlights and dimension percentiles. v5 documents the new
  upstream contract from scoring_engine / benchmark_builder:
    * variable_highlights is now POPULATED (1 personalised + 2 fixed cards).
      Each card carries: type, variable, question_text, raw_response,
      percentiles {overall, age_group}, distribution {overall, age_group}
      (the 1-7 counts the results-page histograms draw from), and n.
    * dimension percentiles now use the average-of-percentiles method
      (reverse-aware), replacing the previous single-variable lookup.
    * benchmark_tables.json now also carries compact dist_* tables.
  No payload fields added or removed — existing consumers are unaffected.
- /premium now passes session_id into send_report_email() so the report
  email links back to the web report (pairs with email_template's session_id).

Changes from v3:
- get_stored_report() — retrieve cached premium report from Supabase
- store_premium_report() — save generated report to Supabase
- /premium endpoint checks cache before generating (prevents duplicate generation on refresh)
- /premium stores report after generation
- /premium sends email via Resend after generation
- /get-results endpoint for session-based retrieval
- store_response updated to save session_id, full_results, report_email
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
from report_pdf import build_report_pdf

app = Flask(__name__)
CORS(app)

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), 'benchmark_tables.json')

# Canonical report page used to render the PDF attachment. Commit a copy of the
# SAME hci-report-page.html the WordPress site serves into this repo so the PDF
# matches the live page; override with REPORT_TEMPLATE_PATH if it lives elsewhere.
REPORT_TEMPLATE_PATH = os.environ.get(
    'REPORT_TEMPLATE_PATH',
    os.path.join(os.path.dirname(__file__), 'hci-report-page.html'),
)
# Public report page; the email CTA links here with ?session_id=...
REPORT_BASE_URL = os.environ.get(
    'REPORT_BASE_URL',
    'https://humanclarityinstitute.com/ai-assessment/report',
)
# Supabase Storage bucket that holds generated report PDFs (create it as a
# PUBLIC bucket; the session_id in the path is the unguessable access token,
# same security model as the report page link).
REPORT_PDF_BUCKET = os.environ.get('REPORT_PDF_BUCKET', 'reports')


# ============================================================
# SUPABASE STORAGE
# ============================================================

def store_response(payload, result_type='free', session_id=None,
                   full_results=None, report_email=None):
    """
    Store assessment response in Supabase.
    Fails silently — storage failure should not break the user flow.
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            print('Supabase not configured — skipping storage')
            return None

        import urllib.request

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
        if report_email:
            record['report_email'] = report_email

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


def get_stored_report(session_id):
    """
    Retrieve a cached premium report from Supabase by session_id.
    Returns the report object if found, None otherwise.
    """
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
            f'&select=premium_report'
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
            print(f'Cached report found for session {session_id}')
            return records[0]['premium_report']
        return None

    except Exception as e:
        print(f'Report retrieval failed (non-critical): {e}')
        return None


def store_premium_report(session_id, report):
    """
    Save a generated premium report to Supabase against the session_id.
    Uses PATCH to update the existing row created during /score.
    """
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


def upload_report_pdf(session_id, pdf_bytes):
    """
    Upload the generated report PDF to Supabase Storage and return its public
    URL. Overwrites any existing PDF for this session (x-upsert) so a
    regenerated report replaces the old file.

    Returns the public URL, or None on any failure (non-fatal — the email then
    sends with the attachment only, or summary + web link).
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key or not pdf_bytes or not session_id:
            return None

        import urllib.request
        import urllib.parse

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
        print(f'PDF upload failed (non-critical): {e}')
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
        k for k in REQUIRED_QUESTION_KEYS if k not in responses
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
        k for k in REQUIRED_DEMOGRAPHIC_KEYS if not demographics.get(k)
    ]
    if missing_demographics:
        return False, f'Missing demographics: {missing_demographics}'

    return True, None


# ============================================================
# API ENDPOINTS
# ============================================================

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
    """
    Score a completed assessment and return the free result.
    Stores session_id, full_results, and report_email in Supabase.
    """
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

       session_id = request_data.get('session_id')
        if not session_id:
            # Fallback only — frontend should always supply one now.
            import hashlib, time
            session_id = hashlib.md5(
                f"{time.time()}{json.dumps(demographics)}".encode()
            ).hexdigest()[:16]

        # Get report email if provided
        report_email = request_data.get('report_email') or \
                       demographics.get('report_email')

        store_response(
            request_data,
            result_type='free',
            session_id=session_id,
            full_results=results,
            report_email=report_email,
        )

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
    Retrieve stored full_results by session_id.
    Called by the premium report page when sessionStorage is unavailable.
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
            f'&select=full_results,demographics,report_email,premium_report'
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

        if not records:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        record = records[0]
        full_results = record.get('full_results')

        if not full_results:
            return jsonify({
                'success': False,
                'error': 'Results not stored for this session'
            }), 404

        return jsonify({
            'success': True,
            'full_results': full_results,
            'session_id': session_id,
            'report_email': record.get('report_email'),
            # Stored premium report, if one has been generated. Lets the report
            # page render directly in any browser from an emailed ?session_id
            # link — a pure read, no /premium call, no regeneration.
            'report': record.get('premium_report'),
        })

    except Exception as e:
        print(f'Get results error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Could not retrieve results'}), 500


@app.route('/premium', methods=['POST'])
def premium():
    """
    Generate premium report after payment confirmation.

    - Checks Supabase cache first — returns instantly if already generated
    - Generates fresh report if not cached
    - Stores report in Supabase immediately after generation
    - Sends email via Resend if report_email provided
    """
    try:
        request_data = request.get_json()

        if not request_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        full_results = request_data.get('full_results')
        if not full_results:
            return jsonify({'success': False, 'error': 'No results provided'}), 400

        session_id = request_data.get('session_id')
        report_email = request_data.get('report_email')
        stripe_session_id = request_data.get('stripe_session_id')

        # 1) CACHE FIRST — if this report was already generated (which only
        #    happens after a verified payment, in step 2 below), return it
        #    immediately. This makes refreshes and the emailed report link work
        #    even when they arrive without the Stripe id, and costs nothing.
        if session_id:
            existing_report = get_stored_report(session_id)
            if existing_report:
                print(f'Returning cached report for session {session_id}')
                return jsonify({
                    'success': True,
                    'report': existing_report,
                    'cached': True,
                })

        # 2) STRICT PAYMENT GATE — reached only when there is NO cached report,
        #    i.e. we are about to spend money generating one. No Claude calls run
        #    until Stripe confirms this checkout session is paid. Fails CLOSED:
        #    a missing key, or a missing/unverified Stripe id, refuses here — so
        #    generation can never run without a confirmed payment.
        if not os.environ.get('STRIPE_SECRET_KEY'):
            print('STRICT GATE: STRIPE_SECRET_KEY not set — refusing to generate.')
            return jsonify({
                'success': False,
                'error': 'Payment verification is temporarily unavailable. '
                         'Please contact support — no report has been generated.'
            }), 503

        stripe_session = fetch_stripe_session(stripe_session_id) if stripe_session_id else None
        paid = bool(stripe_session) and stripe_session.get('payment_status') == 'paid'
        if not paid:
            print(
                'STRICT GATE: payment not verified '
                f'(stripe id present: {bool(stripe_session_id)}) — refusing to generate.'
            )
            return jsonify({
                'success': False,
                'error': 'Payment could not be verified. If you have just paid, '
                         'please refresh this page; otherwise contact support.'
            }), 402

        # Recover the assessment id from the verified Stripe session if it did
        # not arrive in the URL, so the report is stored/emailed against the
        # right session even when the redirect didn't carry it.
        if not session_id and stripe_session:
            session_id = stripe_session.get('client_reference_id')

        # 3) Payment confirmed — now, and only now, spend on generation.
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report = generate_premium_report(full_results, api_key=api_key)

        # Store immediately so refresh works
        if session_id:
            store_premium_report(session_id, report)

        # Send email (lightweight summary + full-report PDF attachment).
        # Fully isolated: a PDF or email failure must never fail /premium —
        # the report is already generated and stored, and the page renders it.
        if report_email:
            try:
                resend_key = os.environ.get('RESEND_API_KEY')
                if resend_key:
                    demographics = full_results.get('demographics', {})
                    report_url = (
                        f'{REPORT_BASE_URL}?session_id={session_id}'
                        if session_id else REPORT_BASE_URL
                    )
                    # Returns PDF bytes, or None on any rendering problem.
                    pdf_bytes = build_report_pdf(
                        report, REPORT_TEMPLATE_PATH, demographics
                    )
                    # Store the PDF (durable, survives a lost inbox) and link it
                    # in the email as a fallback to the attachment.
                    pdf_url = upload_report_pdf(session_id, pdf_bytes) if pdf_bytes else None
                    send_report_email(
                        report_email, report, demographics, resend_key,
                        report_url=report_url, pdf_bytes=pdf_bytes, pdf_url=pdf_url,
                    )
                    print(
                        f'Report email sent to {report_email}'
                        + (' with PDF' if pdf_bytes else ' (summary only — no PDF)')
                        + (' + stored link' if pdf_url else '')
                    )
                else:
                    print('RESEND_API_KEY not configured — skipping email')
            except Exception as email_err:
                print(f'Email/PDF step failed (non-fatal): {email_err}')
                traceback.print_exc()
        else:
            print('No report_email provided — skipping email')


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


def fetch_stripe_session(stripe_session_id):
    """
    Fetch a Stripe Checkout Session. Returns the parsed session dict (which
    includes payment_status and client_reference_id), or None on any error.

    Note: returns None when STRIPE_SECRET_KEY is unset — callers treat that as
    'not verified' and refuse, so generation never runs without a real check.
    """
    try:
        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            print('Stripe not configured — cannot verify payment')
            return None

        import urllib.request
        req = urllib.request.Request(
            f'https://api.stripe.com/v1/checkout/sessions/{stripe_session_id}',
            headers={'Authorization': f'Bearer {stripe_key}'}
        )
        response = urllib.request.urlopen(req, timeout=10)
        return json.loads(response.read())

    except Exception as e:
        print(f'Stripe verification error: {e}')
        return None


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == '__main__':
    print('HCI Assessment API — Version 5')
    print('=' * 40)
    print(f'Benchmark file: {BENCHMARK_PATH}')
    print(f'Benchmark exists: {os.path.exists(BENCHMARK_PATH)}')
    print()
    print('v5: documents new scoring_engine contract (variable_highlights now')
    print('    populated with histogram distributions; average-of-percentiles')
    print('    dimension scoring). No /score payload change.')
    print()
    print('Starting API server on http://localhost:5000')
    app.run(debug=True, port=5000)
