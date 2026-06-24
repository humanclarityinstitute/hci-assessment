"""
HCI AI Identity & Behaviour Assessment
API Layer — Version 5.4

Changes from v5.3:
- Updated to work with report_generator v8 (clean, robust implementation)
- Passes session_id to generate_premium_report() for logging and tracking
- All functionality from v5.3 preserved (Stripe, Resend, recovery, etc.)
- No structural changes — purely updated generator integration

Changes from v5.1:
- notify_timeout() — send internal alerts (to info@humanclarityinstitute.com)
  and customer alerts (to delivery_email) when report generation fails or times out.
  Integrated into /premium exception handler; non-fatal (never blocks error response).

Changes from v5.0:
- /premium now passes session_id to generate_premium_report() for reporting
  and caching purposes.

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

Changes from v3:
- get_stored_report() — retrieve cached premium report from Supabase
- store_premium_report() — save generated report to Supabase
- /premium endpoint checks cache before generating (prevents duplicate generation on refresh)
- /premium stores report after generation
- /premium sends email via Resend after generation
- /get-results endpoint for session-based retrieval
- store_response updated to save session_id, full_results, report_email

Changes in earlier v5 revisions (row-integrity fix):
- /score now accepts the session_id sent by the frontend instead of minting
  its own (frontend owns a single stable id for the whole journey). Falls back
  to a generated id only if none is supplied.
- store_response() now UPSERTS on session_id instead of blind-INSERTing, so a
  results-page reload updates the existing row instead of creating a duplicate.
  Relies on the UNIQUE(session_id) constraint on assessment_responses.
- Removed the stray store_response(..., result_type='premium') insert at the
  end of /premium that was creating empty premium stub rows.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import sys
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

# UPDATED: Import both functions from report_generator v8
# v8 generates complete premium reports with 9 API calls (6 core + 3 deep dive)
# session_id is passed for logging and error tracking
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
                   full_results=None, report_email=None,
                   consent=None, consent_timestamp=None):
    """
    Store assessment response in Supabase.

    UPSERTS on session_id: if a row with this session_id already exists (e.g.
    the user reloaded the results page), the existing row is updated in place
    rather than a duplicate being inserted. This relies on the
    UNIQUE(session_id) constraint on assessment_responses. When no session_id
    is supplied it falls back to a plain insert.

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
        if consent is not None:
            record['consent'] = consent
        if consent_timestamp:
            record['consent_timestamp'] = consent_timestamp

        body = json.dumps(record).encode('utf-8')

        # Upsert when we have a session_id: on conflict with the existing row's
        # session_id, merge (update) instead of inserting a duplicate. Without a
        # session_id, behave as a plain insert (unchanged from before).
        url = f'{supabase_url}/rest/v1/assessment_responses'
        prefer = 'return=minimal'
        if session_id:
            url += '?on_conflict=session_id'
            prefer = 'return=minimal,resolution=merge-duplicates'

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
                'Prefer': prefer,
            },
            method='POST'
        )
        urllib.request.urlopen(req, timeout=5)
        return True

    except Exception as e:
        print(f'Storage failed (non-critical): {e}')
        return None


def get_stored_full_results(session_id):
    """
    Retrieve stored assessment full_results from Supabase by session_id.
    Called by /premium as fallback when sessionStorage was lost or empty.
    Returns the full_results dict if found, None otherwise.
    Non-fatal: if retrieval fails, None is returned and /premium handles it.
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
            f'&select=full_results'
            f'&limit=1'
        )
        req = urllib.request.Request(
            url,
            headers={
                'apikey': supabase_key,
                'Authorization': f'Bearer {supabase_key}',
            }
        )
        response = urllib.request.urlopen(req, timeout=5)
        rows = json.loads(response.read().decode('utf-8'))
        if rows and len(rows) > 0:
            stored = rows[0].get('full_results')
            if stored:
                print(f'Retrieved full_results from Supabase for session {session_id}')
                return stored
        return None
    except Exception as e:
        print(f'Retrieval of full_results failed (non-critical): {e}')
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

        # Use the session_id supplied by the frontend (it owns a single stable
        # id for the whole journey). Fall back to a generated id only if none
        # was sent, so older clients still work.
        session_id = request_data.get('session_id')
        if not session_id:
            import hashlib
            import time
            session_id = hashlib.md5(
                f"{time.time()}{json.dumps(demographics)}".encode()
            ).hexdigest()[:16]

        results = score_assessment(responses, demographics, BENCHMARK_PATH)
        results['session_id'] = session_id
        free_result = generate_free_result(results)

        # Get report email if provided
        report_email = request_data.get('report_email') or \
                       demographics.get('report_email')

        store_response(
            request_data,
            result_type='free',
            session_id=session_id,
            full_results=results,
            report_email=report_email,
            consent=request_data.get('consent', False),
            consent_timestamp=request_data.get('consent_timestamp'),
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
        session_id = request_data.get('session_id')
        report_email = request_data.get('report_email')
        stripe_session_id = request_data.get('stripe_session_id')

        # FALLBACK RECOVERY: If full_results is empty/missing (e.g., sessionStorage
        # was cleared or frontend couldn't send it), try to recover from Supabase
        # using session_id. This handles browser refresh cases gracefully.
        if (not full_results or not full_results.get('dimensions')) and session_id:
            print(f'Attempting Supabase recovery for session {session_id}...')
            recovered = get_stored_full_results(session_id)
            if recovered and recovered.get('dimensions'):
                full_results = recovered
                print(f'Successfully recovered full_results from Supabase')

        # If after recovery we still have no valid results, fail
        if not full_results or not full_results.get('dimensions'):
            return jsonify({
                'success': False,
                'error': 'Assessment data could not be retrieved. Please contact support if this persists.'
            }), 400

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
            # If we just recovered session_id from Stripe AND we still don't have
            # full_results, try to recover from Supabase now that we have the id
            if not full_results or not full_results.get('dimensions'):
                print(f'Attempting secondary Supabase recovery with Stripe-recovered session_id...')
                recovered = get_stored_full_results(session_id)
                if recovered and recovered.get('dimensions'):
                    full_results = recovered
                    print(f'Successfully recovered full_results in secondary attempt')

        # Delivery email: PREFER the email entered at Stripe checkout (the
        # verified, reliable address where the customer expects their purchase),
        # falling back to any assessment-page email passed through. The
        # assessment-page email is primarily a marketing lead; the payment
        # email is the delivery address.
        stripe_email = None
        if stripe_session:
            details = stripe_session.get('customer_details') or {}
            stripe_email = details.get('email') or stripe_session.get('customer_email')
        delivery_email = stripe_email or report_email

        # Stamp the row PAID before generation runs, so a "paid but no report"
        # state is always cleanly queryable regardless of where generation might
        # fail. Non-fatal: never block generation on this.
        if session_id:
            mark_row_paid(session_id, delivery_email, stripe_session_id)

        # 3) Payment confirmed — now, and only now, spend on generation.
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report = generate_premium_report(
            results=full_results,
            api_key=api_key,
            session_id=session_id
        )

        # Store immediately so refresh works
        if session_id:
            store_premium_report(session_id, report)

        # Send email (lightweight summary + full-report PDF attachment) to the
        # delivery_email resolved above (Stripe payment email preferred).
        # Fully isolated: a PDF or email failure must never fail /premium —
        # the report is already generated and stored, and the page renders it.
        if delivery_email:
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
                        delivery_email, report, demographics, resend_key,
                        report_url=report_url, pdf_bytes=pdf_bytes, pdf_url=pdf_url,
                    )
                    print(
                        f'Report email sent to {delivery_email}'
                        + (' with PDF' if pdf_bytes else ' (summary only — no PDF)')
                        + (' + stored link' if pdf_url else '')
                    )
                else:
                    print('RESEND_API_KEY not configured — skipping email')
            except Exception as email_err:
                print(f'Email/PDF step failed (non-fatal): {email_err}')
                traceback.print_exc()
        else:
            print('No delivery email available — skipping email')

        return jsonify({
            'success': True,
            'report': report,
        })

    except Exception as e:
        error_msg = str(e)
        error_type = 'generation_timeout' if 'timeout' in error_msg.lower() else 'generation_error'
        
        print(f'Premium endpoint error: {e}')
        traceback.print_exc()
        
        # Send alerts — non-fatal, never blocks the error response
        if session_id and delivery_email:
            notify_timeout(session_id, delivery_email, error_msg, error_type=error_type)
        
        return jsonify({
            'success': False,
            'error': 'Report generation failed — please contact support'
        }), 500


def mark_row_paid(session_id, delivery_email=None, stripe_session_id=None):
    """
    Stamp the assessment row as PAID (PATCH) the moment payment is verified,
    BEFORE generation runs. This makes "paid but no report" a clean, queryable
    state no matter where generation might later fail. Non-fatal: any failure
    here is logged and ignored so it can never block report generation.

    Writes:
      paid = true, paid_at = now, and (if available) the delivery email and the
      Stripe checkout session id, for support/recovery cross-referencing.
    """
    try:
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')
        if not supabase_url or not supabase_key or not session_id:
            return False

        import urllib.request
        import urllib.parse

        record = {
            'paid': True,
            'paid_at': datetime.utcnow().isoformat(),
        }
        if delivery_email:
            record['report_email'] = delivery_email
        if stripe_session_id:
            record['stripe_session_id'] = stripe_session_id

        body = json.dumps(record).encode('utf-8')
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
            method='PATCH',
        )
        urllib.request.urlopen(req, timeout=10)
        print(f'Row stamped paid for session {session_id}')
        return True
    except Exception as e:
        print(f'mark_row_paid failed (non-critical): {e}')
        return False


# Lookup key for the report price in Stripe. The price amount/currency live in
# the Stripe dashboard against this key, so the price can be changed there
# (transfer the lookup key to a new price) without any code change.
REPORT_PRICE_LOOKUP_KEY = os.environ.get('REPORT_PRICE_LOOKUP_KEY', 'hci_report_standard')

# Where Stripe sends the customer after checkout. Success carries Stripe's own
# checkout session id, which /premium reads as stripe_session_id and verifies.
CHECKOUT_SUCCESS_URL = os.environ.get(
    'CHECKOUT_SUCCESS_URL',
    REPORT_BASE_URL + '?stripe_session_id={CHECKOUT_SESSION_ID}',
)
CHECKOUT_CANCEL_URL = os.environ.get(
    'CHECKOUT_CANCEL_URL',
    'https://humanclarityinstitute.com/ai-assessment/results',
)


def _stripe_form_post(url, fields):
    """POST application/x-www-form-urlencoded to the Stripe API. Returns parsed
    JSON, or raises. Stripe's API takes form-encoded bodies (incl. bracketed
    keys for nested params)."""
    import urllib.request
    import urllib.parse

    stripe_key = os.environ.get('STRIPE_SECRET_KEY')
    if not stripe_key:
        raise RuntimeError('STRIPE_SECRET_KEY not set')

    data = urllib.parse.urlencode(fields).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'Authorization': f'Bearer {stripe_key}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    response = urllib.request.urlopen(req, timeout=15)
    return json.loads(response.read())


def _resolve_price_id():
    """Resolve the active Stripe Price ID from the lookup key, so price changes
    are made in the Stripe dashboard (no code change). Returns the price id or
    None on failure."""
    try:
        import urllib.request
        import urllib.parse

        stripe_key = os.environ.get('STRIPE_SECRET_KEY')
        if not stripe_key:
            return None

        q = urllib.parse.urlencode({
            'lookup_keys[]': REPORT_PRICE_LOOKUP_KEY,
            'active': 'true',
            'limit': 1,
        })
        req = urllib.request.Request(
            f'https://api.stripe.com/v1/prices?{q}',
            headers={'Authorization': f'Bearer {stripe_key}'},
        )
        import urllib.request as _u
        resp = _u.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        items = data.get('data') or []
        if items:
            return items[0]['id']
        print(f'No active price found for lookup key {REPORT_PRICE_LOOKUP_KEY}')
        return None
    except Exception as e:
        print(f'Price lookup failed: {e}')
        return None


@app.route('/create-checkout', methods=['POST'])
def create_checkout():
    """
    Create a Stripe Checkout Session in code and return its hosted URL.

    Replaces the old fixed Payment Link. Sets client_reference_id to the
    assessment session_id so the paid checkout is matched back to the right
    row, enables promotion codes (so 100%-off trial/test codes work), and
    collects the customer email for delivery. The price is resolved from the
    lookup key, so it can be changed in the Stripe dashboard with no code change.
    """
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400

        if not os.environ.get('STRIPE_SECRET_KEY'):
            return jsonify({
                'success': False,
                'error': 'Checkout is temporarily unavailable. Please try again later.'
            }), 503

        price_id = _resolve_price_id()
        if not price_id:
            return jsonify({
                'success': False,
                'error': 'Could not determine the product price. Please contact support.'
            }), 500

        fields = {
            'mode': 'payment',
            'line_items[0][price]': price_id,
            'line_items[0][quantity]': 1,
            'client_reference_id': session_id,
            'allow_promotion_codes': 'true',
            'success_url': CHECKOUT_SUCCESS_URL,
            'cancel_url': CHECKOUT_CANCEL_URL,
        }
        sess = _stripe_form_post('https://api.stripe.com/v1/checkout/sessions', fields)

        checkout_url = sess.get('url')
        if not checkout_url:
            print(f'Checkout session created but no URL returned: {sess}')
            return jsonify({
                'success': False,
                'error': 'Could not start checkout. Please try again.'
            }), 500

        return jsonify({'success': True, 'checkout_url': checkout_url})

    except Exception as e:
        print(f'Create-checkout error: {e}')
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Could not start checkout. Please try again.'
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


def notify_timeout(session_id, delivery_email, error_msg, error_type='generation_timeout'):
    """
    Send alert emails when a report fails to generate or times out.

    - Internal alert to info@humanclarityinstitute.com (minimal detail: session + error type)
    - Customer alert to delivery_email (friendly "we're investigating" message)

    Non-fatal: notification failures never block the main flow.
    """
    try:
        resend_key = os.environ.get('RESEND_API_KEY')
        if not resend_key:
            print('RESEND_API_KEY not configured — skipping failure notifications')
            return False

        import urllib.request

        ops_email = 'info@humanclarityinstitute.com'
        timestamp = datetime.utcnow().isoformat()

        # 1) Internal alert — minimal detail for ops triage
        ops_subject = f'⚠️ Report {error_type}: session {session_id}'
        ops_body = f"""Report generation failed.

Session: {session_id}
Error type: {error_type}
Timestamp: {timestamp}
Customer email: {delivery_email}

Error details: {error_msg}

Action: Check the Railway logs and Supabase row for this session to investigate.
"""

        ops_payload = {
            'from': 'reports@humanclarityinstitute.com',
            'to': [ops_email],
            'subject': ops_subject,
            'html': ops_body,
        }

        ops_body_json = json.dumps(ops_payload).encode('utf-8')
        ops_req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=ops_body_json,
            headers={
                'Authorization': f'Bearer {resend_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'HCI-Reports/1.0',
            },
            method='POST',
        )
        urllib.request.urlopen(ops_req, timeout=10)
        print(f'Internal alert sent to {ops_email} for session {session_id}')

        # 2) Customer alert — friendly, reassuring tone
        if delivery_email:
            customer_subject = 'Your HCI AI Assessment Report — We\'re Resolving This'
            customer_body = f"""Hi there,

We encountered an issue while generating your premium report. We apologise for the inconvenience — our team is investigating right now, and we're committed to getting your report to you within 48 hours.

Your assessment data is completely safe and stored securely. We'll regenerate your report as soon as the issue is resolved — no further action needed from you.

What we're offering you:
• Your premium report, regenerated and sent within 48 hours
• Two free retake tokens so you can benchmark your progress in the future and see how your relationship with AI has evolved

Session ID (for reference): {session_id}
Timestamp: {timestamp}

If you have any questions or concerns, please reach out to support@humanclarityinstitute.com — we're here to help.

Thanks for your patience and understanding.

Human Clarity Institute
"""

            customer_payload = {
                'from': 'reports@humanclarityinstitute.com',
                'to': delivery_email,
                'subject': customer_subject,
                'text': customer_body,
            }

            customer_body_json = json.dumps(customer_payload).encode('utf-8')
            customer_req = urllib.request.Request(
                'https://api.resend.com/emails',
                data=customer_body_json,
                headers={
                    'Authorization': f'Bearer {resend_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'HCI-Reports/1.0',
                },
                method='POST',
            )
            urllib.request.urlopen(customer_req, timeout=10)
            print(f'Customer alert sent to {delivery_email} for session {session_id}')

        return True

    except Exception as e:
        print(f'Failure notification failed (non-critical): {e}')
        traceback.print_exc()
        return False



# ============================================================
# RECOVERY ENDPOINT — regenerate + resend a failed report
# ============================================================

@app.route('/recover-report', methods=['GET', 'POST'])
def recover_report():
    """
    Admin recovery endpoint: regenerate and resend a report for a paid customer
    whose report failed to generate.

    GET: shows a simple form where you paste the session_id
    POST: accepts JSON with {"session_id": "the_session_id"}

    Retrieves full_results and report_email from Supabase, regenerates the
    report, stores it, and sends the email.
    """
    # GET request — show the form
    if request.method == 'GET':
        return '''<!DOCTYPE html>
<html>
<head>
    <title>HCI Report Recovery</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input { width: 100%; padding: 8px; box-sizing: border-box; font-size: 14px; }
        button { background-color: #4054B2; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #2d3a7f; }
        .result { margin-top: 20px; padding: 15px; border-radius: 5px; }
        .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <h1>HCI Report Recovery</h1>
    <p>Paste the customer's session ID to regenerate and resend their report.</p>
    
    <form onsubmit="submitForm(event)">
        <div class="form-group">
            <label for="session_id">Session ID:</label>
            <input type="text" id="session_id" name="session_id" placeholder="e.g., 3fdea24fb107bf3d" required>
        </div>
        <button type="submit">Recover Report</button>
    </form>
    
    <div id="result"></div>
    
    <script>
        async function submitForm(event) {
            event.preventDefault();
            const sessionId = document.getElementById('session_id').value;
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<p>Processing...</p>';
            
            try {
                const response = await fetch('/recover-report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    resultDiv.innerHTML = `<div class="result success">✓ Success! Report regenerated and sent to ${data.message.split('to ')[1]}</div>`;
                } else {
                    resultDiv.innerHTML = `<div class="result error">✗ Error: ${data.error}</div>`;
                }
            } catch (err) {
                resultDiv.innerHTML = `<div class="result error">✗ Network error: ${err.message}</div>`;
            }
        }
    </script>
</body>
</html>'''
    
    # POST request — process the recovery
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        session_id = request_data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'No session_id provided'}), 400

        # Retrieve their stored data from Supabase
        supabase_url = os.environ.get('SUPABASE_URL')
        supabase_key = os.environ.get('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            return jsonify({'success': False, 'error': 'Storage not configured'}), 500

        import urllib.request
        import urllib.parse

        url = (
            f'{supabase_url}/rest/v1/assessment_responses'
            f'?session_id=eq.{urllib.parse.quote(session_id)}'
            f'&select=full_results,report_email,stripe_session_id,paid'
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
        report_email = record.get('report_email')
        paid = record.get('paid')

        if not full_results:
            return jsonify({'success': False, 'error': 'No results stored for this session'}), 404

        if not paid:
            return jsonify({'success': False, 'error': 'This session is not marked as paid'}), 402

        if not report_email:
            return jsonify({'success': False, 'error': 'No delivery email on file'}), 400

        print(f'Recovering report for session {session_id}, email {report_email}')

        # Generate the report
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        report = generate_premium_report(
            results=full_results,
            api_key=api_key,
            session_id=session_id
        )

        # Store it
        store_premium_report(session_id, report)

        # Send email with PDF
        if report_email:
            try:
                resend_key = os.environ.get('RESEND_API_KEY')
                if resend_key:
                    demographics = full_results.get('demographics', {})
                    report_url = f'{REPORT_BASE_URL}?session_id={session_id}'
                    pdf_bytes = build_report_pdf(report, REPORT_TEMPLATE_PATH, demographics)
                    pdf_url = upload_report_pdf(session_id, pdf_bytes) if pdf_bytes else None
                    send_report_email(
                        report_email, report, demographics, resend_key,
                        report_url=report_url, pdf_bytes=pdf_bytes, pdf_url=pdf_url,
                    )
                    print(f'Recovery email sent to {report_email}')
                else:
                    print('RESEND_API_KEY not configured — skipping email')
            except Exception as email_err:
                print(f'Recovery email/PDF step failed: {email_err}')
                traceback.print_exc()

        return jsonify({
            'success': True,
            'message': f'Report regenerated and sent to {report_email}',
        })

    except Exception as e:
        print(f'Recovery endpoint error: {e}')
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Report recovery failed'}), 500


if __name__ == '__main__':
    print('HCI Assessment API — Version 5.3')
    print('=' * 40)
    print(f'Benchmark file: {BENCHMARK_PATH}')
    print(f'Benchmark exists: {os.path.exists(BENCHMARK_PATH)}')
    print()
    print('v5.3: Fixed imports to work with report_generator v7')
    print('      (which has both generate_free_result and generate_premium_report)')
    print()
    print('v5.2: notify_timeout() sends failure alerts to ops + customer.')
    print('      Integrated into /premium exception handler (non-fatal).')
    print()
    print('Starting API server on http://localhost:5000')
    app.run(debug=True, port=5000)
