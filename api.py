"""
api.py
HCI Assessment Platform — Clean Report Pipeline

This version preserves the existing working assessment/free-result flow:

- GET  /health
- POST /score
- GET  /results
- POST /create-checkout
- POST /webhook/stripe
- POST /premium
- GET  /report

Critical report architecture:
- /score creates ONE canonical report_data object and stores it in Supabase.
- /report renders premium HTML directly from report_data.
- The webhook only marks the assessment as paid.
- /premium is now a compatibility endpoint: it verifies payment/marks paid and returns the report URL.
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

# Core existing assets
from scoring_engine import score_assessment
from benchmark_builder import get_benchmark
from supabase_client import get_supabase_client
from stripe_config import get_stripe_config

# New clean report system
from report_data_builder import build_report_data, assert_report_data_contract
from report_renderer import render_report

# Optional email support. The clean first-pass system does not require email to work.
try:
    from email_sender import send_report_email
    HAS_EMAIL_SENDER = True
except Exception as e:
    print(f"WARNING: email_sender unavailable: {e}")
    HAS_EMAIL_SENDER = False


# ============================================================
# APP CONFIG
# ============================================================

app = Flask(__name__)
CORS(app)

BENCHMARK_PATH = os.path.join(os.path.dirname(__file__), "benchmark_tables.json")

# Report URL base shown/returned after payment.
# This should point to your Railway/API domain route if /report is served from Railway.
REPORT_BASE_URL = os.environ.get("REPORT_BASE_URL", "")


# ============================================================
# HELPERS
# ============================================================

def make_report_url(session_id: str) -> str:
    """Build the browser URL for the paid report."""
    if REPORT_BASE_URL:
        sep = "&" if "?" in REPORT_BASE_URL else "?"
        return f"{REPORT_BASE_URL}{sep}session_id={urllib.parse.quote(session_id)}"
    return f"/report?session_id={urllib.parse.quote(session_id)}"


def fetch_stripe_session(stripe_session_id):
    """
    Fetch Stripe checkout session details.

    Used to:
    - Verify payment_status == paid
    - Recover client_reference_id / assessment session_id
    - Get customer email
    """
    if not stripe_session_id:
        return None

    try:
        stripe_config = get_stripe_config()
        url = f"https://api.stripe.com/v1/checkout/sessions/{stripe_session_id}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {stripe_config.secret_key}"},
        )
        response = urllib.request.urlopen(req, timeout=15)
        session_data = json.loads(response.read())
        return session_data
    except Exception as e:
        print(f"Failed to fetch Stripe session {stripe_session_id}: {e}")
        return None


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    benchmark_exists = os.path.exists(BENCHMARK_PATH)
    return jsonify({
        "status": "ok",
        "benchmark_loaded": benchmark_exists,
        "clean_report_system": True,
        "timestamp": datetime.utcnow().isoformat(),
    }), 200


# ============================================================
# HELPER: Generate response percentiles for free results page
# ============================================================

def generate_percentiles(responses, demographics, scoring_results):
    """
    Generate percentiles for each individual question response.

    This is kept for your current free result page, which already works.
    The premium report does NOT depend on this object directly; it uses report_data.
    """
    try:
        benchmark = get_benchmark()

        dimension_variables = {
            "trust": ["trust_q1", "trust_q2", "trust_q3", "trust_q4"],
            "disclosure": ["disc_q1", "disc_q2", "disc_q3", "disc_q4"],
            "reliance": ["rel_q1", "rel_q2", "rel_q3", "rel_q4", "rel_q5"],
            "decision_delegation": ["del_q1", "del_q2", "del_q3", "del_q4", "del_q5"],
            "verification": ["ver_q1", "ver_q2", "ver_q3", "ver_q4"],
            "human_agency": ["agency_q1", "agency_q2", "agency_q3", "agency_q4", "agency_q5"],
            "emotional_regulation": ["emot_q1", "emot_q2", "emot_q3", "emot_q4"],
            "thought_partnership": ["thought_q1", "thought_q2", "thought_q3", "thought_q4"],
            "social_transparency": ["soc_q1", "soc_q2", "soc_q3", "soc_q4"],
        }

        question_text_map = {
            "trust_q1": "I feel confident trusting information from AI",
            "trust_q2": "I would rely on AI output without additional verification",
            "trust_q3": "I worry that AI might present false information to me",
            "trust_q4": "I trust AI to give me accurate information",

            "disc_q1": "I share personal thoughts and feelings with AI",
            "disc_q2": "I tell AI things I haven't told other people",
            "disc_q3": "I am more open with AI than I am with people",
            "disc_q4": "I use AI as a space to think through personal concerns",

            "rel_q1": "I feel restless when I don't have access to AI",
            "rel_q2": "I struggle to work without access to my AI tools",
            "rel_q3": "I feel confident relying on AI outputs",
            "rel_q4": "I would have difficulty doing my work without AI assistance",
            "rel_q5": "I rely on AI regularly in my daily work",

            "del_q1": "I rely on AI to make decisions for me",
            "del_q2": "I tend to follow AI recommendations even if I'm unsure",
            "del_q3": "I worry my skills are declining from delegating to AI",
            "del_q4": "I regularly hand over tasks to AI",
            "del_q5": "I accept AI suggestions without much modification",

            "ver_q1": "I double-check information that AI provides",
            "ver_q2": "I skip verification because the effort isn't worth it",
            "ver_q3": "I use external sources to verify AI outputs",
            "ver_q4": "I proceed without checking AI information",

            "agency_q1": "I feel self-directed when using AI",
            "agency_q2": "I feel in control of my decisions when AI is involved",
            "agency_q3": "I trust my own judgement over AI suggestions",
            "agency_q4": "AI nudges influence me without my realizing it",
            "agency_q5": "I feel ownership over decisions I make with AI help",

            "emot_q1": "AI provides me emotional support",
            "emot_q2": "I use AI as an alternative to human emotional support",
            "emot_q3": "AI helps me process difficult emotions",
            "emot_q4": "I use AI to cope with stress or anxiety",

            "thought_q1": "AI helps me think more deeply",
            "thought_q2": "AI validates my existing beliefs rather than challenging them",
            "thought_q3": "I use AI as a thinking partner to develop ideas",
            "thought_q4": "AI helps me challenge my assumptions",

            "soc_q1": "I am transparent with others about my use of AI",
            "soc_q2": "I conceal how much I use AI from others",
            "soc_q3": "I am comfortable telling people about my AI use",
            "soc_q4": "There's a gap between how much AI I actually use and what others think",
        }

        percentiles = {}
        age_group = demographics.get("age_group", "unknown")

        for dim_name, questions in dimension_variables.items():
            for q_key in questions:
                if q_key not in responses:
                    continue

                user_response = responses[q_key]

                try:
                    pct_overall = benchmark.get_percentile(q_key, user_response, segment=None)
                except Exception:
                    pct_overall = 50

                try:
                    pct_age_group = benchmark.get_percentile(q_key, user_response, segment=("age_group", age_group))
                except Exception:
                    pct_age_group = None

                try:
                    n_overall = benchmark.get_sample_size(q_key, segment=None)
                except Exception:
                    n_overall = None

                try:
                    n_age_group = benchmark.get_sample_size(q_key, segment=("age_group", age_group))
                except Exception:
                    n_age_group = None

                try:
                    is_rare = pct_overall >= 86 or pct_overall <= 14
                except Exception:
                    is_rare = False

                distribution = None
                try:
                    distribution = [
                        sum(
                            1
                            for v in benchmark.data["dimensions"][dim_name]["overall"]["values"]
                            if int(v) == i
                        )
                        for i in range(1, 8)
                    ]
                except Exception:
                    distribution = None

                percentiles[q_key] = {
                    "response": user_response,
                    "percentile_overall": pct_overall,
                    "percentile_age_group": pct_age_group,
                    "question_text": question_text_map.get(q_key, f"Question {q_key}"),
                    "dimension": dim_name,
                    "n_overall": n_overall,
                    "n_age_group": n_age_group,
                    "is_rare": is_rare,
                    "distribution": distribution,
                }

        return percentiles

    except Exception as e:
        print(f"Error generating response percentiles: {e}")
        traceback.print_exc()
        return {}


# ============================================================
# ASSESSMENT SCORING (POST /score)
# ============================================================

@app.route("/score", methods=["POST"])
def score():
    """
    Score a completed assessment and store results.

    Important:
    - Current free results payload is preserved.
    - New premium report_data is created and stored behind the scenes.
    """
    try:
        request_data = request.get_json()
        if not request_data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        responses = request_data.get("responses", {})
        demographics = request_data.get("demographics", {})
        report_email = request_data.get("report_email")
        consent = request_data.get("consent", False)
        consent_timestamp = request_data.get("consent_timestamp")
        session_id = request_data.get("session_id")

        if not responses or not demographics:
            return jsonify({"success": False, "error": "Missing responses or demographics"}), 400

        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())

        # Existing scoring flow.
        scoring_results = score_assessment(responses, demographics, session_id=session_id)

        # Existing free-results question percentiles.
        percentiles = generate_percentiles(responses, demographics, scoring_results)
        scoring_results["percentiles"] = percentiles

        # New clean premium report data object.
        report_data = build_report_data(
            scoring_results=scoring_results,
            responses=responses,
            demographics=demographics,
            email=report_email,
            session_id=session_id,
        )
        assert_report_data_contract(report_data)

        # Store everything in the same existing table: assessment_responses.
        db = get_supabase_client()
        store_result = db.store_assessment(
            session_id=session_id,
            responses=responses,
            demographics=demographics,
            full_results=scoring_results,
            dimension_scores=scoring_results.get("dimension_scores", {}),
            perception_gaps=scoring_results.get("perception_gaps", []),
            patterns=scoring_results.get("rare_combinations", []),
            percentiles=percentiles,
            report_data=report_data,
            report_email=report_email,
            consent=consent,
            consent_timestamp=consent_timestamp,
            paid=False,
        )

        if not store_result.get("success"):
            print(f"Failed to store assessment: {store_result.get('message')}")
            return jsonify({
                "success": False,
                "error": "Failed to store assessment in database",
                "message": store_result.get("message"),
            }), 500

        # DO NOT CHANGE this shape unless you also update the free results page.
        return jsonify({
            "success": True,
            "session_id": session_id,
            "dimension_scores": scoring_results.get("dimension_scores", {}),
            "percentiles": percentiles,
            "perception_gaps": scoring_results.get("perception_gaps", []),
            "rare_combinations": scoring_results.get("rare_combinations", []),
            "demographics": demographics,
            "responses": responses,
            "full_results": scoring_results,
        }), 200

    except Exception as e:
        print(f"Score endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Assessment scoring failed",
            "message": str(e),
        }), 500


# ============================================================
# RETRIEVE RESULTS (GET /results)
# ============================================================

@app.route("/results", methods=["GET"])
def get_results():
    """Retrieve stored assessment results by session_id."""
    try:
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"success": False, "error": "No session_id provided"}), 400

        db = get_supabase_client()
        assessment = db.get_assessment(session_id)

        if not assessment:
            return jsonify({"success": False, "error": "Session not found"}), 404

        return jsonify({
            "success": True,
            "session_id": session_id,
            "full_results": assessment.get("full_results"),
            "percentiles": assessment.get("percentiles", {}),
            "demographics": assessment.get("demographics", {}),
            "responses": assessment.get("responses", {}),
            "report_email": assessment.get("report_email"),
            "paid": assessment.get("paid", False),
            "report_url": make_report_url(session_id) if assessment.get("paid", False) else None,
        }), 200

    except Exception as e:
        print(f"Get results error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": "Could not retrieve results"}), 500


# ============================================================
# CREATE STRIPE CHECKOUT (POST /create-checkout)
# ============================================================

@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    """Create a Stripe Checkout Session for premium report."""
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get("session_id")
        email = request_data.get("email")

        if not session_id:
            return jsonify({"success": False, "error": "No session_id provided"}), 400

        stripe = get_stripe_config()
        result = stripe.create_checkout_session(session_id, email)

        if result.get("success"):
            return jsonify({
                "success": True,
                "session_id": result["session_id"],
                "url": result["url"],
            }), 200

        return jsonify({
            "success": False,
            "error": result.get("message", "Checkout creation failed"),
        }), 400

    except Exception as e:
        print(f"Create checkout error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": "Checkout creation failed"}), 500


# ============================================================
# STRIPE WEBHOOK (POST /webhook/stripe)
# ============================================================

@app.route("/webhook/stripe", methods=["POST"])
def webhook_stripe():
    """
    Stripe webhook handler.

    Clean behaviour:
    - Verify the Stripe webhook.
    - On checkout.session.completed, mark the existing assessment row as paid.
    - Do NOT generate report here. /report renders from stored report_data.
    """
    try:
        payload = request.get_data(as_text=True)
        signature = request.headers.get("Stripe-Signature")

        if not signature:
            print("Missing Stripe-Signature header")
            return jsonify({"error": "Missing signature"}), 400

        stripe = get_stripe_config()

        if not stripe.verify_webhook_signature(payload, signature):
            print("Webhook signature verification failed")
            return jsonify({"error": "Invalid signature"}), 403

        event = stripe.parse_webhook_event(payload)
        if not event:
            return jsonify({"error": "Invalid JSON"}), 400

        if event.get("type") == "checkout.session.completed":
            checkout_data = stripe.handle_checkout_completed(event)
            if not checkout_data:
                return jsonify({"error": "Invalid event data"}), 400

            stripe_session_id = checkout_data.get("stripe_session_id")
            customer_email = checkout_data.get("customer_email")

            stripe_session = fetch_stripe_session(stripe_session_id)
            if not stripe_session:
                print(f"Failed to fetch Stripe session {stripe_session_id}")
                return jsonify({"received": True}), 200

            session_id = stripe_session.get("client_reference_id")
            if not session_id:
                print(f"No client_reference_id in Stripe session {stripe_session_id}")
                return jsonify({"received": True}), 200

            print(f"Webhook: payment confirmed for assessment {session_id}")

            db = get_supabase_client()
            paid_at = datetime.utcnow().isoformat()

            ok = db.update_assessment(
                session_id=session_id,
                paid=True,
                paid_at=paid_at,
                stripe_session_id=stripe_session_id,
                report_email=customer_email,
            )

            if ok:
                print(f"Marked assessment {session_id} as paid")
            else:
                print(f"Failed to mark assessment {session_id} as paid")

        return jsonify({"received": True}), 200

    except Exception as e:
        print(f"Webhook error: {e}")
        traceback.print_exc()
        return jsonify({"error": "Webhook processing failed"}), 500


# ============================================================
# PREMIUM COMPATIBILITY ENDPOINT (POST /premium)
# ============================================================

@app.route("/premium", methods=["POST"])
def premium():
    """
    Compatibility endpoint for existing front-end calls.

    Old behaviour generated report here.
    New behaviour:
    - Recover/verify payment if stripe_session_id is supplied.
    - Mark assessment paid.
    - Ensure report_data exists.
    - Return report_url.
    """
    try:
        request_data = request.get_json() or {}
        session_id = request_data.get("session_id")
        stripe_session_id = request_data.get("stripe_session_id")
        report_email = request_data.get("report_email")

        db = get_supabase_client()

        stripe_session = None
        if stripe_session_id:
            stripe_session = fetch_stripe_session(stripe_session_id)

            if stripe_session and not session_id:
                session_id = stripe_session.get("client_reference_id")
                print(f"Recovered session_id from Stripe: {session_id}")

        if not session_id:
            return jsonify({
                "success": False,
                "error": "No session_id provided or recoverable",
            }), 400

        assessment = db.get_assessment(session_id)
        if not assessment:
            return jsonify({"success": False, "error": "Assessment data not found"}), 404

        # Strict payment gate only when Stripe session supplied.
        if stripe_session_id:
            if not stripe_session:
                return jsonify({
                    "success": False,
                    "error": "Payment verification failed. Please contact support.",
                }), 402

            payment_status = stripe_session.get("payment_status")
            if payment_status != "paid":
                return jsonify({
                    "success": False,
                    "error": "Payment not confirmed. If you just paid, please refresh this page.",
                }), 402

            customer_details = stripe_session.get("customer_details") or {}
            stripe_email = customer_details.get("email") or stripe_session.get("customer_email")
            if stripe_email:
                report_email = stripe_email

            db.update_assessment(
                session_id=session_id,
                paid=True,
                paid_at=datetime.utcnow().isoformat(),
                stripe_session_id=stripe_session_id,
                report_email=report_email,
            )

        # If report_data is missing for an older row, build it once from stored data.
        assessment = db.get_assessment(session_id)
        report_data = assessment.get("report_data")

        if not report_data:
            full_results = assessment.get("full_results") or {}
            responses = assessment.get("responses") or {}
            demographics = assessment.get("demographics") or {}

            if not full_results or not responses or not demographics:
                return jsonify({
                    "success": False,
                    "error": "Assessment data incomplete; cannot build report_data",
                }), 500

            report_data = build_report_data(
                scoring_results=full_results,
                responses=responses,
                demographics=demographics,
                email=report_email or assessment.get("report_email"),
                session_id=session_id,
            )
            assert_report_data_contract(report_data)

            db.update_assessment(
                session_id=session_id,
                report_data=report_data,
                report_email=report_email or assessment.get("report_email"),
            )

        return jsonify({
            "success": True,
            "message": "Premium report ready",
            "session_id": session_id,
            "report_url": make_report_url(session_id),
        }), 200

    except Exception as e:
        print(f"Premium endpoint error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Report preparation failed",
            "message": str(e),
        }), 500


# ============================================================
# RETRIEVE PREMIUM REPORT (GET /report)
# ============================================================

@app.route("/report", methods=["GET"])
def get_report():
    """
    Retrieve and display premium report by session_id.

    Returns complete HTML rendered from canonical report_data.
    """
    try:
        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"success": False, "error": "No session_id provided"}), 400

        db = get_supabase_client()
        assessment = db.get_assessment(session_id)

        if not assessment:
            return jsonify({"success": False, "error": "Session not found"}), 404

        if not assessment.get("paid"):
            return jsonify({"success": False, "error": "Report not purchased"}), 403

        report_data = assessment.get("report_data")

        # Recovery for older rows that predate report_data.
        if not report_data:
            full_results = assessment.get("full_results") or {}
            responses = assessment.get("responses") or {}
            demographics = assessment.get("demographics") or {}

            if not full_results or not responses or not demographics:
                return jsonify({"success": False, "error": "Report data not found"}), 404

            report_data = build_report_data(
                scoring_results=full_results,
                responses=responses,
                demographics=demographics,
                email=assessment.get("report_email"),
                session_id=session_id,
            )
            assert_report_data_contract(report_data)
            db.update_assessment(session_id=session_id, report_data=report_data)

        report_html = render_report(report_data)

        # Cache final HTML for debugging/performance. /report still always trusts report_data.
        try:
            db.update_report(
                session_id=session_id,
                report_html=report_html,
                report_generated_at=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            print(f"Non-fatal: failed to cache report_html: {e}")

        return report_html, 200, {"Content-Type": "text/html; charset=utf-8"}

    except Exception as e:
        print(f"Get report error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Could not retrieve report",
            "message": str(e),
        }), 500


# ============================================================
# SIMPLE RECOVERY ENDPOINTS
# ============================================================

@app.route("/recover-report", methods=["GET"])
def recover_report_page():
    """Minimal manual recovery page."""
    return """
    <!doctype html>
    <html>
    <head><title>HCI Report Recovery</title></head>
    <body style="font-family: system-ui; max-width: 640px; margin: 40px auto;">
      <h1>HCI Report Recovery</h1>
      <p>Enter a session ID to rebuild report_data and cache fresh HTML.</p>
      <input id="session_id" placeholder="session_id" style="width:100%;padding:10px;">
      <button onclick="recover()" style="margin-top:12px;padding:10px 16px;">Recover</button>
      <pre id="out"></pre>
      <script>
      async function recover() {
        const session_id = document.getElementById('session_id').value;
        const res = await fetch('/recover-report-action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({session_id})
        });
        const data = await res.json();
        document.getElementById('out').textContent = JSON.stringify(data, null, 2);
      }
      </script>
    </body>
    </html>
    """


@app.route("/recover-report-action", methods=["POST"])
def recover_report_action():
    """Rebuild report_data and report_html for an existing session."""
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id", "").strip()

        if not session_id:
            return jsonify({"success": False, "error": "session_id required"}), 400

        db = get_supabase_client()
        assessment = db.get_assessment(session_id)

        if not assessment:
            return jsonify({"success": False, "error": "Session not found"}), 404

        full_results = assessment.get("full_results") or {}
        responses = assessment.get("responses") or {}
        demographics = assessment.get("demographics") or {}

        if not full_results or not responses or not demographics:
            return jsonify({
                "success": False,
                "error": "Assessment row missing full_results, responses, or demographics",
            }), 500

        report_data = build_report_data(
            scoring_results=full_results,
            responses=responses,
            demographics=demographics,
            email=assessment.get("report_email"),
            session_id=session_id,
        )
        assert_report_data_contract(report_data)

        report_html = render_report(report_data)

        db.update_assessment(session_id=session_id, report_data=report_data)
        db.update_report(
            session_id=session_id,
            report_html=report_html,
            report_generated_at=datetime.utcnow().isoformat(),
        )

        return jsonify({
            "success": True,
            "message": "Report data and HTML rebuilt successfully",
            "report_url": make_report_url(session_id),
            "data_quality": report_data.get("data_quality", {}),
        }), 200

    except Exception as e:
        print(f"[RECOVER] Error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Server error"}), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":
    try:
        _ = get_supabase_client()
        print("✓ Supabase client initialized")
    except Exception as e:
        print(f"⚠ Supabase initialization failed: {e}")

    try:
        _ = get_stripe_config()
        print("✓ Stripe config initialized")
    except Exception as e:
        print(f"⚠ Stripe initialization failed: {e}")

    print("✓ Clean report renderer configured")
    print("\nStarting HCI Assessment API...")
    app.run(host="0.0.0.0", port=5000, debug=False)
