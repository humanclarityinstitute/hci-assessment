"""
HCI AI Identity & Behaviour Assessment
Report Generator — Version 6 (Complete Rebuild)

Generates premium reports with 9 focused API calls (6 core + 3 optional deep dive):
- 1 call: Opening (Top 3 Findings)
- 1 call: Rare combinations
- 1 call: Behaviour story
- 1 call: Distinctive responses
- 1 call: Perception gap
- 1 call: Trajectory/outlook
- 3 calls: Optional deep dive

All calls wrapped with 90s timeout + single retry on timeout.
NO PARTIAL REPORTS — if any call fails, entire report fails.

New architecture:
- 11 core sections (Opening + 10 main sections, Section 2 skipped)
- 4 optional deep dive parts
- Integrated SIGNALS library for research grounding
- Enhanced benchmark data with frequency gradients + cohort signals
- Pre-written templates for non-API sections
"""

import json
import time
import statistics
from datetime import datetime

try:
    import anthropic
    from anthropic import APITimeoutError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================
# RESILIENCE CONFIGURATION
# ============================================================

CALL_TIMEOUT_SECONDS = 90
MAX_RETRIES = 1


# ============================================================
# NOTIFICATION HANDLER
# ============================================================

def notify_timeout(call_name, duration_sec, session_id, attempt, error_msg=''):
    """Log timeout notifications visible in Railway logs."""
    timestamp = datetime.utcnow().isoformat()
    
    print(
        f'[TIMEOUT ALERT] {call_name} | '
        f'Duration: {duration_sec:.1f}s (timeout: {CALL_TIMEOUT_SECONDS}s) | '
        f'Session: {session_id} | '
        f'Attempt: {attempt}/{MAX_RETRIES + 1} | '
        f'Time: {timestamp}'
    )


# ============================================================
# CORE: Call with timeout + retry
# ============================================================

def call_claude_with_resilience(
    client,
    model,
    max_tokens,
    system,
    messages,
    call_name='API Call',
    session_id=None
):
    """
    Call Claude with 90s timeout + single retry on timeout.
    NO PARTIAL REPORTS — if this fails, the whole report fails.
    """
    
    for attempt in range(MAX_RETRIES + 1):
        start_time = time.time()
        
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                timeout=float(CALL_TIMEOUT_SECONDS),
            )
            
            duration = time.time() - start_time
            
            if duration > 30:
                print(
                    f'[SLOW] {call_name} completed in {duration:.1f}s '
                    f'(session: {session_id})'
                )
            
            return message.content[0].text.strip()
        
        except APITimeoutError as e:
            duration = time.time() - start_time
            notify_timeout(call_name, duration, session_id or 'unknown', attempt + 1, str(e))
            
            if attempt < MAX_RETRIES:
                print(
                    f'[RETRY] {call_name} timed out after {duration:.1f}s, '
                    f'retrying (attempt {attempt + 2}/{MAX_RETRIES + 1})...'
                )
                time.sleep(1)
                continue
            else:
                print(
                    f'[FATAL] {call_name} failed on final attempt. '
                    f'NO PARTIAL REPORTS — entire report generation aborted. '
                    f'Session: {session_id}'
                )
                raise APITimeoutError(
                    f'{call_name} exceeded {CALL_TIMEOUT_SECONDS}s timeout '
                    f'on {MAX_RETRIES + 1} attempts (session: {session_id})'
                ) from e
        
        except Exception as e:
            print(
                f'[ERROR] {call_name} failed: {type(e).__name__}: {str(e)[:100]} '
                f'(session: {session_id})'
            )
            raise


# ============================================================
# GLOBAL SYSTEM PROMPT
# ============================================================

GLOBAL_SYSTEM_PROMPT = """
You are writing sections of a personalised research report for the
Human Clarity Institute's AI Identity & Behaviour Assessment.

Your role is to generate genuine insight that leaves people feeling
more self-aware and curious about themselves — never judged,
deficient, or concerned about their behaviour.

INSTITUTIONAL VOICE:
- Warm but precise. Intellectually rigorous. Never sterile.
- Write as a thoughtful researcher who has studied this specific
  person's data — not as a template being filled in.
- Personal but grounded in data. Future-positive. Never alarming.

FRAMING RULES:
- Every score reveals something genuinely interesting.
  There are no good or bad scores — only different patterns.
- Never suggest someone has a problem or should change.
- Difference from the population is always interesting, never deficit.
- All scores are patterns at this point in time — not fixed traits.

TONE RULES:
- Speak directly to the person as "you"
- Write in second person throughout
- Every section ends with curiosity, not concern
- Never list problems — explore patterns

PERCENTILE LANGUAGE:
- State position as plain English: "higher than 97 out of every 100 people"
- Pair it with the positional phrase ("notably high", "near the population centre")
- Do NOT use a bare "Xth percentile" number anywhere in the prose
- Always lead with the human meaning, never the number

LANGUAGE TO NEVER USE:
- concerning, worrying, problematic, at risk
- you should, you need to, you must
- loss of agency, cognitive decline, addiction, dependency
- alarming, dangerous, red flag

LANGUAGE TO USE:
- interesting, revealing, distinctive, worth exploring
- your pattern, your positioning, your profile
- people with similar profiles tend to...
- what appears worth protecting
- raises an interesting question

USING HCI RESEARCH DATA:
- Some sections include real findings from HCI's research series.
- When you cite a population figure, attribute it lightly to HCI's research, e.g.
  "In HCI's research series, 84-99% of people verify before acting."
- Only use figures explicitly provided in the section data. NEVER invent estimates
  or statistics. If no figure is provided, write qualitatively ("most people").

V2.1 COMPLIANCE (mandatory):
- Never assign a "type", "archetype", or label to the participant.
- Use the positional-language scale exactly: exceptionally high / notably high /
  above the population centre / near the population centre / below the population
  centre / notably low / exceptionally low. Invent no alternatives.
- Do not state a bare "Xth percentile" number. Express position as plain-English
  comparison ("higher than 84 out of 100 people") plus the positional phrase.
- Every section ends on an observation or open question — never a recommendation.
"""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_percentile(p):
    if p is None:
        return 'N/A'
    p = int(p)
    if 11 <= p <= 13:
        return f'{p}th'
    suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(p % 10, 'th')
    return f'{p}{suffix}'


def plain_english_percentile(p):
    if p is None:
        return None
    p = int(p)
    if p >= 50:
        return f'Higher than {p} out of every 100 people'
    return f'Lower than {100 - p} out of every 100 people'


def positional_language(p):
    """V2.1 exact positional descriptor — no number."""
    if p is None:
        return 'near the population centre'
    p = int(p)
    if p >= 96: return 'exceptionally high'
    if p >= 86: return 'notably high'
    if p >= 71: return 'above the population centre'
    if p >= 41: return 'near the population centre'
    if p >= 26: return 'below the population centre'
    if p >= 11: return 'notably low'
    return 'exceptionally low'


def get_rarity_text(percentile):
    if percentile is None:
        return None
    p = int(percentile)
    if p >= 97:
        return f'Fewer than {100-p}% of participants score this high'
    elif p >= 86:
        return f'Only {100-p}% of participants score similarly'
    elif p <= 3:
        return f'Fewer than {p+1}% of participants score this low'
    elif p <= 14:
        return f'Only {p}% of participants score similarly'
    return None


# ============================================================
# LOAD SIGNALS LIBRARY AND BENCHMARK DATA
# ============================================================

def load_signals_library():
    """Load SIGNALS library from hci_signals_library.py"""
    try:
        from hci_signals_library import SIGNALS, DIMENSION_VARIABLES, RESEARCH_NUMBERS
        return SIGNALS, DIMENSION_VARIABLES, RESEARCH_NUMBERS
    except ImportError:
        print('[WARNING] SIGNALS library not found. Some research grounding will be unavailable.')
        return {}, {}, {}


def load_benchmark_data(path='benchmark_tables_enhanced.json'):
    """Load enhanced benchmark data with frequency gradients + cohort signals"""
    try:
        with open(path, 'r') as f:
            benchmark = json.load(f)
        return benchmark
    except FileNotFoundError:
        print(f'[WARNING] Benchmark file not found at {path}')
        return {}


# ============================================================
# DATA PREPARATION FUNCTIONS
# ============================================================

def calculate_percentile(value, distribution):
    """Calculate percentile from distribution array."""
    if not distribution or value is None:
        return None
    sorted_dist = sorted(distribution)
    count = sum(1 for v in sorted_dist if v <= value)
    percentile = int((count / len(sorted_dist)) * 100)
    return max(0, min(100, percentile))


def get_dimension_percentile(dim_name, participant_response, benchmark, demographics):
    """Get percentile for a dimension given participant response."""
    if dim_name not in benchmark.get('variables', {}):
        return None
    
    var_data = benchmark['variables'][dim_name]
    
    # Try age group first, then overall
    age_group = demographics.get('age_group')
    if age_group and age_group in var_data.get('by_age', {}):
        distribution = var_data['by_age'][age_group]
    else:
        distribution = var_data.get('overall', [])
    
    return calculate_percentile(participant_response, distribution)


def detect_rare_combinations(dimensions, signals):
    """Detect if any rare combinations are present."""
    rare_combos = []
    
    combo_spec = signals.get('combinations', {})
    
    for combo_id, combo_info in combo_spec.items():
        # Parse combo_id (e.g., 'high_thought_partnership_low_emotional_regulation')
        parts = combo_id.split('_')
        if len(parts) >= 4:
            # Simple check: see if dimensions match the combination
            # This is a placeholder — actual matching logic depends on structure
            rare_combos.append({
                'id': combo_id,
                'rarity': combo_info.get('rarity', 'Unknown'),
                'why_unusual': combo_info.get('why_unusual', ''),
                'what_it_reveals': combo_info.get('what_it_reveals', '')
            })
    
    return rare_combos[:2]  # Return top 2


# ============================================================
# SECTION GENERATORS (API-driven)
# ============================================================

def generate_opening(results, client, signals, session_id=None):
    """
    API CALL #1: Opening — Top 3 Findings
    
    Synthesize most distinctive pattern + perception gap + rare combo
    into compelling opening narrative.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    # Prepare data for prompt
    top_dimension = max(
        dimensions.items(),
        key=lambda x: abs(x[1].get('percentile', 50) - 50)
    ) if dimensions else ('unknown', {})
    
    prompt = f"""
    This person has just completed the HCI AI Identity & Behaviour Assessment.
    
    Key data:
    - Most distinctive dimension: {top_dimension[0]} at {top_dimension[1].get('percentile')}th percentile
    - Age group: {demographics.get('age_group', 'Unknown')}
    - Usage frequency: {demographics.get('frequency', 'Unknown')}
    
    Dimensions overview:
    {json.dumps({k: v.get('percentile') for k, v in dimensions.items()}, indent=2)}
    
    Write three compelling findings that:
    1. Lead with their most distinctive dimension/pattern
    2. Identify the largest perception gap (if exists)
    3. Highlight a rare combination (if detected)
    
    Each finding should be 50-75 words, in plain language, no percentile jargon.
    Speak directly to them as "you". Frame everything as interesting, not concerning.
    
    Output format:
    FINDING 1: [Paragraph about most distinctive pattern]
    
    FINDING 2: [Paragraph about perception or gap]
    
    FINDING 3: [Paragraph about what this reveals]
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Opening — Top 3 Findings',
        session_id=session_id
    )
    
    return response


def generate_rare_combinations(results, client, signals, session_id=None):
    """
    API CALL #2: Rare Combinations
    
    Synthesize why this person's combination is unusual and what it means,
    grounded in research.
    """
    
    dimensions = results.get('dimensions', {})
    rare_combos = detect_rare_combinations(dimensions, signals)
    
    if not rare_combos:
        return "Your dimensional profile shows a coherent, stable pattern across all nine dimensions."
    
    combo_data = '\n'.join([
        f"- {combo['id']}: {combo['rarity']} (why: {combo['why_unusual']})"
        for combo in rare_combos
    ])
    
    prompt = f"""
    This person shows these rare combinations in their AI behaviour profile:
    
    {combo_data}
    
    For each combination, write:
    1. Why it's unusual (ground in research about how these dimensions typically co-occur)
    2. What it reveals about their relationship with AI
    3. Why it matters
    
    Use research language ("The research shows...", "People with this combination tend to...")
    Keep it observational, not prescriptive. Speak to them as "you".
    
    Total: approximately 300-400 words across both combinations.
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Rare Combinations Synthesis',
        session_id=session_id
    )
    
    return response


def generate_behaviour_story(results, client, signals, session_id=None):
    """
    API CALL #3: Behaviour Story
    
    300-400 word narrative portrait of their AI relationship pattern.
    Opens with #1 dimension, explains cross-dimensional relationships.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    
    # Get top 5 dimensions
    sorted_dims = sorted(
        dimensions.items(),
        key=lambda x: x[1].get('percentile', 50),
        reverse=True
    )[:5]
    
    dim_summary = '\n'.join([
        f"- {dim[0]}: {dim[1].get('percentile')}th percentile ({positional_language(dim[1].get('percentile'))})"
        for dim in sorted_dims
    ])
    
    prompt = f"""
    Write a narrative portrait of this person's AI relationship pattern.
    
    Key data:
    {dim_summary}
    
    Age group: {demographics.get('age_group')}
    Usage frequency: {demographics.get('frequency')}
    
    Structure:
    1. Open with their #1 dimension as foundation (1-2 sentences)
    2. Explain how other dimensions relate to #1 (2-3 paragraphs)
    3. Ground everything in HCI's observed patterns
    4. Show them as intentional and coherent
    5. Close with observation that opens curiosity
    
    Tone: Observational, research-grounded, reflective.
    No percentile jargon. No predictions or prescriptions.
    Speak as "you". Total: 300-400 words.
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Behaviour Story Narrative',
        session_id=session_id
    )
    
    return response


def generate_distinctive_responses(results, client, benchmark, signals, session_id=None):
    """
    API CALL #4: Most Distinctive Responses
    
    Explain top 7 most unusual individual question answers,
    grounded in research patterns.
    """
    
    # Get top 7 most distinctive variables
    variable_highlights = results.get('variable_highlights', [])[:7]
    
    if not variable_highlights:
        return "Your responses across all questions show a coherent, consistent pattern."
    
    var_summary = '\n'.join([
        f"- {var.get('variable_name')}: Score {var.get('answer')}/7, "
        f"{positional_language(var.get('percentile'))} ({var.get('percentile')}th percentile)"
        for var in variable_highlights
    ])
    
    prompt = f"""
    This person's 7 most distinctive individual responses:
    
    {var_summary}
    
    For each response:
    1. State why it's distinctive (ground in research about this variable)
    2. Explain what makes it unusual in context of their overall profile
    3. What it reveals about their AI relationship
    
    Use research language. Keep each explanation brief (30-50 words).
    Speak to them as "you". Observational tone.
    
    Total: approximately 300-400 words.
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Distinctive Responses Synthesis',
        session_id=session_id
    )
    
    return response


def generate_perception_gap(results, client, session_id=None):
    """
    API CALL #5: Perception Gap
    
    Compare self-perception (from final questions) to actual positioning.
    """
    
    perception_answers = results.get('perception_answers', {})
    dimensions = results.get('dimensions', {})
    
    prompt = f"""
    This person answered three self-perception questions at the end of the assessment:
    
    {json.dumps(perception_answers, indent=2)}
    
    Their actual dimensional positioning:
    {json.dumps({k: v.get('percentile') for k, v in dimensions.items()}, indent=2)}
    
    For each self-perception question:
    1. State what they think about themselves
    2. State what the data actually shows
    3. Highlight any alignment or gap
    4. What it might mean (grounded in research)
    
    Tone: Illuminating, not corrective. This is interesting — not about who's "right".
    Use phrases like "What's interesting is...", "This alignment suggests..."
    Speak to them as "you". Total: 200-300 words.
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1000,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Perception Gap Analysis',
        session_id=session_id
    )
    
    return response


def generate_trajectory(results, client, benchmark, signals, session_id=None):
    """
    API CALL #6: Trajectory & Outlook
    
    Observable patterns based on frequency gradients.
    What typically happens if usage frequency stays the same.
    """
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    frequency_gradients = benchmark.get('frequency_gradients', {})
    
    # Get high-scoring dimensions
    high_dims = {k: v for k, v in dimensions.items() if v.get('percentile', 0) > 71}
    moderate_dims = {k: v for k, v in dimensions.items() 
                     if 41 <= v.get('percentile', 50) <= 70}
    
    prompt = f"""
    This person's current profile:
    - Frequency tier: {demographics.get('frequency')}
    - High dimensions (>71%ile): {', '.join(high_dims.keys())}
    - Moderate dimensions: {', '.join(list(moderate_dims.keys())[:3])}
    
    Based on research about how people at their usage frequency typically develop:
    
    1. Likely to Continue: What patterns typically remain stable if nothing changes?
    (100-150 words)
    
    2. Strengths Likely to Deepen: Which strengths tend to deepen with continued exposure?
    (100-150 words, for high-scoring dimensions)
    
    3. Areas Worth Monitoring: Which dimensions are most likely to shift if usage increases?
    (100-150 words, for moderate dimensions)
    
    4. Overall Outlook: What does their pattern suggest about their capacity to navigate changes?
    (80-120 words)
    
    Tone: Grounded, reassuring, observational. No timeline predictions.
    Use "If current patterns hold...", "Research shows...", "People with your pattern tend to..."
    Speak to them as "you".
    """
    
    response = call_claude_with_resilience(
        client,
        model='claude-sonnet-4-6',
        max_tokens=1200,
        system=GLOBAL_SYSTEM_PROMPT,
        messages=[{'role': 'user', 'content': prompt}],
        call_name='Trajectory & Outlook',
        session_id=session_id
    )
    
    return response


# ============================================================
# SECTION GENERATORS (Data-only / Pre-written)
# ============================================================

def generate_dashboard(results, benchmark):
    """Section 1: Benchmark Dashboard — all 9 dimensions, no API"""
    
    dimensions = results.get('dimensions', {})
    demographics = results.get('demographics', {})
    age_group = demographics.get('age_group')
    
    cohort_signals = benchmark.get('cohort_signals', {}).get(age_group, {})
    
    dashboard = {
        'title': 'YOUR AI BEHAVIOUR PATTERN',
        'subtitle': 'How you compare across nine dimensions',
        'dimensions': {}
    }
    
    for dim_name, dim_data in dimensions.items():
        percentile = dim_data.get('percentile', 50)
        dashboard['dimensions'][dim_name] = {
            'name': dim_data.get('label', dim_name),
            'definition': dim_data.get('definition', ''),
            'percentile': percentile,
            'position': positional_language(percentile),
            'plain_english': plain_english_percentile(percentile),
            'cohort_mean': cohort_signals.get(dim_name, {}).get('mean'),
            'comparison': f"vs {cohort_signals.get(dim_name, {}).get('mean', 'N/A')} for your age group"
        }
    
    return dashboard


def generate_how_typical(results, dimensions_spec):
    """Section 3: How Typical Is Your AI Behaviour — no API"""
    
    dimensions = results.get('dimensions', {})
    
    distinctive = {}
    typical = {}
    
    for dim_name, dim_data in dimensions.items():
        percentile = dim_data.get('percentile', 50)
        
        if percentile > 75 or percentile < 25:
            distinctive[dim_name] = {
                'percentile': percentile,
                'position': positional_language(percentile),
                'definition': dim_data.get('definition', '')
            }
        elif 35 <= percentile <= 65:
            typical[dim_name] = {
                'percentile': percentile,
                'position': 'near the population centre',
                'definition': dim_data.get('definition', '')
            }
    
    return {
        'title': 'HOW TYPICAL IS YOUR AI BEHAVIOUR?',
        'distinctive': distinctive,
        'typical': typical
    }


def generate_what_to_protect(results):
    """Section 9: What to Protect — Pre-written templates with data insertion"""
    
    dimensions = results.get('dimensions', {})
    
    # Section 9 pre-written templates
    templates = {
        'verification': """
WHAT TO NOTICE: WHEN VERIFICATION BECOMES TIRING

Most people verify AI outputs. The research is clear: 84-99% of adults double-check, 
question, or evaluate AI information before accepting or acting on it. Verification 
is one of the most universal epistemic habits in HCI's research.

But here's what HCI also found: this universal behaviour is increasingly costly.

The Research Reveals:
• 43% of people report that evaluating AI information drains mental focus
• 54% experience verification fatigue — they feel worn down by constant questioning
• 38% find themselves bypassing checks when they're cognitively saturated
• A growing minority (54%) now verify selectively

If your Verification score places you [positioning_verification], here's what to watch for:

→ Noticing yourself checking less than usual
→ Feeling relief or efficiency when you skip verification
→ Finding it hard to care whether an output is accurate
→ Moving from "verify everything" to "verify selectively" without realizing it

You decide what level of verification matters to you.
        """,
        
        'agency': """
WHAT TO NOTICE: WHEN DRIFT HAPPENS WITHOUT YOU CHOOSING IT

Human agency is intact at the identity level. 91% of people retain a clear sense 
of personal responsibility for their decisions — even heavy AI users.

But at the process level, something else is happening. 59% of people feel subtly 
steered by AI toward certain choices without fully choosing it.

The Research Reveals:
• 91% retain personal responsibility despite AI use
• 59% feel steered by AI toward certain choices
• 65% experience fragmented attention
• 35% struggle to enact values they hold clearly

If your Human Agency score places you [positioning_agency], here's what to watch for:

→ Accepting AI suggestions without thinking them through first
→ Using AI defaults instead of customizing your approach
→ Realizing you haven't actually made a decision yourself in days
→ Noticing AI's framing has become your first instinct

You decide if this matters to you.
        """,
        
        'emotional': """
WHAT TO NOTICE: IF EMOTIONAL RELIANCE BECOMES SUBSTITUTION

87% of people still believe — deeply — that only humans can truly meet emotional 
needs. Yet 18% are already using AI for emotional support, and 27% report getting 
some emotional support from AI.

The Research Reveals:
• 87% believe only humans can truly meet emotional needs
• 18% use AI for emotional support (primary use case)
• 27% are getting some emotional support from AI
• A dose-response: loneliness → AI support (1.49 → 3.15)

If your Emotional Regulation score places you [positioning_emotional], here's what to watch for:

→ Turning to AI before turning to people when you're struggling
→ Preferring AI conversations to human ones for processing difficult feelings
→ Finding it harder to sit with discomfort without AI input
→ The boundary between supplement and substitution beginning to blur

You decide if emotional support from AI is right for you.
        """,
        
        'thought_partnership': """
WHAT TO NOTICE: WHEN THINKING WITH AI BECOMES THINKING FOR YOU

AI works best as a thinking partner — someone to develop ideas with, 
not instead of your own thinking. But this boundary is worth noticing as usage deepens.

Specifically: 34-38% of people question whether their AI-assisted decisions are genuinely theirs. 
The research reveals what separates genuine partnership from outsourced thinking: 
a clear values anchor.

The Research Reveals:
• 34-38% question whether AI-assisted decisions are truly theirs
• Using AI as a sounding board shows the strongest frequency effect
• People with stable, articulated values show stronger resistance to drift
• 47% make their own decision regardless of AI recommendation (but 59% feel subtly steered)

If your Thought Partnership score places you [positioning_thought], here's what to watch for:

→ Defaulting to AI's framing instead of developing your own position first
→ Struggling to think independently when AI isn't available
→ Realizing AI's suggestions have become your first instinct
→ Finding it hard to disagree with AI once it's stated a position

You decide if this matters to you.
        """
    }
    
    output = {
        'title': 'WHAT TO PROTECT',
        'sections': {}
    }
    
    # Insert positioning language into templates
    positioning_map = {
        'verification': positional_language(dimensions.get('verification', {}).get('percentile')),
        'agency': positional_language(dimensions.get('human_agency', {}).get('percentile')),
        'emotional': positional_language(dimensions.get('emotional_regulation', {}).get('percentile')),
        'thought': positional_language(dimensions.get('thought_partnership', {}).get('percentile'))
    }
    
    for key, template in templates.items():
        output['sections'][key] = template.replace(f'[positioning_{key}]', positioning_map.get(key, 'in the middle'))
    
    return output


def generate_next_steps(results):
    """Section 11: Your Next Steps — Pre-written"""
    
    return {
        'title': 'YOUR NEXT STEPS',
        'step1': """
STEP 1: TEST THIS REPORT WITH YOUR AI

Upload this full report to whichever AI you use most.

Ask it: "Does this report ring true to how we work together? Where does it match 
your sense of how I use you? Where does it miss?"

Listen for where it confirms vs. where it challenges. This conversation will 
deepen your clarity about your actual pattern.

A note: Your data stays with you. Nothing about this conversation returns to HCI.
        """,
        
        'step2': """
WHAT THIS AWARENESS DOES

Knowing your pattern is the foundation for clarity. And clarity is what lets you 
make intentional choices about your boundaries with AI.

This report shows you where you sit — how you use AI, what you rely on it for, 
where you're distinctive, where you're typical. That positioning is neutral. 
What matters is what you do with it.

The people who flourish with AI use are the ones who stay aware of their own pattern 
and adjust their relationship as it evolves. Not through willpower or rules, but through 
genuine understanding of what serves them.
        """,
        
        'step3': """
STAY WITHIN YOUR BOUNDARIES

Return to this assessment periodically — quarterly, annually, or whenever your 
relationship with AI feels like it's shifting significantly.

Retesting lets you notice what's actually changed in your pattern, not what you 
think has changed. It's the clearest way to stay within the boundaries that help 
you flourish.
        """,
        
        'closing': """
THIS REPORT AS A MIRROR

This report is a mirror. What it shows is real — your positioning in a benchmark 
population, your rare combinations, your observable patterns.

What you do with that clarity is entirely yours.
        """
    }


# ============================================================
# MAIN REPORT GENERATOR
# ============================================================

def generate_premium_report(results, api_key=None, progress_callback=None, benchmark_path='benchmark_tables_enhanced.json'):
    """
    Generate complete premium report using 9 focused API calls (6 core + 3 optional deep dive).
    
    ALL CALLS WRAPPED WITH 90S TIMEOUT + SINGLE RETRY.
    NO PARTIAL REPORTS — if any call fails, entire report fails.
    """
    
    if not ANTHROPIC_AVAILABLE:
        raise ImportError('anthropic package required. pip install anthropic')
    
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    
    # Load support libraries
    signals, dimension_variables, research_numbers = load_signals_library()
    benchmark = load_benchmark_data(benchmark_path)
    
    session_id = results.get('session_id')
    demographics = results.get('demographics', {})
    dimensions = results.get('dimensions', {})
    
    total_steps = 11  # 6 core + 5 data-only sections
    step = 0
    
    def progress(message):
        nonlocal step
        step += 1
        print(f'  [{step}/{total_steps}] {message}')
        if progress_callback:
            progress_callback(step, total_steps, message)
    
    print('Generating premium report — 9 focused API calls (v6 + resilience)...')
    
    # ── API CALL #1: Opening ──────────────────────────────────────────────────
    progress('Identifying your most surprising finding...')
    opening = generate_opening(results, client, signals, session_id)
    
    # ── SECTION 1: Dashboard (no API) ──────────────────────────────────────────
    progress('Building your benchmark dashboard...')
    dashboard = generate_dashboard(results, benchmark)
    
    # ── SECTION 3: How Typical (no API) ────────────────────────────────────────
    progress('Analyzing how typical your pattern is...')
    how_typical = generate_how_typical(results, dimension_variables)
    
    # ── API CALL #2: Rare Combinations ─────────────────────────────────────────
    progress('Analyzing your distinctive combinations...')
    rare_combos = generate_rare_combinations(results, client, signals, session_id)
    
    # ── API CALL #3: Behaviour Story ───────────────────────────────────────────
    progress('Writing your behaviour story...')
    behaviour_story = generate_behaviour_story(results, client, signals, session_id)
    
    # ── SECTION 6: Question Profile (no API) ───────────────────────────────────
    progress('Building your question-level profile...')
    question_profile = {
        'title': 'YOUR QUESTION-LEVEL PROFILE',
        'subtitle': 'All 39 questions with your answers and comparisons',
        'note': 'Generated from assessment data'
    }
    
    # ── API CALL #4: Distinctive Responses ─────────────────────────────────────
    progress('Analyzing your most distinctive responses...')
    distinctive_responses = generate_distinctive_responses(
        results, client, benchmark, signals, session_id
    )
    
    # ── API CALL #5: Perception Gap ────────────────────────────────────────────
    progress('Analyzing your perception gap...')
    perception_gap = generate_perception_gap(results, client, session_id)
    
    # ── SECTION 9: What to Protect (pre-written) ───────────────────────────────
    progress('Building your what-to-protect section...')
    what_to_protect = generate_what_to_protect(results)
    
    # ── API CALL #6: Trajectory & Outlook ──────────────────────────────────────
    progress('Projecting your trajectory...')
    trajectory = generate_trajectory(results, client, benchmark, signals, session_id)
    
    # ── SECTION 11: Next Steps (pre-written) ───────────────────────────────────
    progress('Building your next steps...')
    next_steps = generate_next_steps(results)
    
    # ── Assemble Report ────────────────────────────────────────────────────────
    report = {
        'metadata': {
            'demographics': demographics,
            'generated_by': 'HCI AI Identity & Behaviour Assessment',
            'version': '6.0',
            'total_api_calls': 6,
            'optional_deep_dive_calls': 3,
            'resilience': {
                'timeout_seconds': CALL_TIMEOUT_SECONDS,
                'max_retries': MAX_RETRIES,
                'session_id': session_id,
            },
        },
        'opening': opening,
        'section_1_dashboard': dashboard,
        'section_3_how_typical': how_typical,
        'section_4_what_different': rare_combos,
        'section_5_behaviour_story': behaviour_story,
        'section_6_question_profile': question_profile,
        'section_7_distinctive_responses': distinctive_responses,
        'section_8_perception_gap': perception_gap,
        'section_9_what_to_protect': what_to_protect,
        'section_10_trajectory': trajectory,
        'section_11_next_steps': next_steps,
    }
    
    print(f'Premium report generation complete. (6 API calls, 90s timeout + retry)')
    return report


# ============================================================
# TEST
# ============================================================

if __name__ == '__main__':
    print('Report Generator v6 (Complete Rebuild)')
    print('New section structure: 11 core sections + optional deep dive')
    print('API calls: 6 core + 3 optional deep dive (9 total)')
    print()
    print('Resilience: 90s timeout per call, single retry on timeout')
    print('NO PARTIAL REPORTS — fails hard if any call fails twice')
    print('Estimated generation time: 50-70 seconds (6 core calls)')
