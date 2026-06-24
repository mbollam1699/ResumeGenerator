"""
Sponsorship checker and fit scorer using Claude API.
"""
import re
import json
import anthropic


# ── Sponsorship ────────────────────────────────────────────────────────────────

POSITIVE_PATTERNS = [
    r"will sponsor",
    r"visa sponsorship",
    r"h[\-\s]?1[\-\s]?b",
    r"work authorization (?:provided|offered|available)",
    r"sponsorship (?:available|provided|offered)",
    r"open to sponsoring",
    r"sponsorship considered",
]

NEGATIVE_PATTERNS = [
    # Explicit "will not sponsor" variants
    r"no (?:visa )?sponsorship",
    r"cannot sponsor",
    r"will not sponsor",
    r"does not (?:provide|offer|support) (?:visa )?sponsorship",
    r"not (?:able|in a position) to (?:provide|offer|support) (?:visa )?sponsorship",
    r"sponsorship (?:is )?not (?:available|provided|offered)",
    r"we (?:do not|don't|are unable to|cannot) (?:provide|offer|support|consider) (?:visa )?sponsorship",
    r"unable to (?:provide|offer|sponsor)",
    r"not eligible for (?:visa )?sponsorship",
    r"must have(?: the)? right to work without (?:visa )?sponsorship",
    # "will not consider candidates who require sponsorship" (Philips-style phrasing)
    r"not consider (?:candidates?|applicants?) (?:who (?:require|need)|requiring|needing) (?:visa )?sponsorship",
    r"(?:candidates?|applicants?) (?:who (?:require|need)|requiring|needing) (?:visa )?sponsorship (?:will not|cannot|are not)",
    r"require(?:s|ing)? sponsorship for (?:a )?(?:work(?:-authorized)?|employment|u\.?s\.?) visa",
    r"sponsorship.{0,60}now or in the future",
    # Citizenship / residency requirements (implies no sponsorship path)
    r"(?:us |u\.s\. )?citizens? only",
    r"must be a (?:us |u\.s\. )?citizen",
    r"permanent residents? only",
    r"green card (?:holders? only|required)",
    r"require(?:s)? (?:us |u\.s\. )?citizenship",
    # Security clearance (requires citizenship — no sponsorship possible)
    r"(?:active|current|valid) (?:secret|top secret|ts[\/ ]?sci) clearance",
    r"security clearance (?:is )?required",
    r"must (?:hold|have|possess) (?:a |an )?(?:active |current )?(?:secret|top secret|security) clearance",
    r"clearance (?:is )?required",
    r"must be clearable",
]


def check_sponsorship(job_description: str) -> dict:
    """
    Scan the job description for sponsorship signals.

    Returns:
        {
          "status": "positive" | "negative" | "neutral",
          "matches": [list of matching snippet strings],
          "label": human-readable label,
          "color": "green" | "red" | "yellow"
        }
    """
    lower = job_description.lower()
    positive_hits = []
    negative_hits = []

    for pat in POSITIVE_PATTERNS:
        m = re.search(pat, lower)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(lower), m.end() + 40)
            positive_hits.append(job_description[start:end].strip())

    for pat in NEGATIVE_PATTERNS:
        m = re.search(pat, lower)
        if m:
            start = max(0, m.start() - 40)
            end = min(len(lower), m.end() + 40)
            negative_hits.append(job_description[start:end].strip())

    if positive_hits and not negative_hits:
        return {
            "status": "positive",
            "matches": positive_hits,
            "label": "Sponsorship mentioned",
            "color": "green",
        }
    elif negative_hits:
        return {
            "status": "negative",
            "matches": negative_hits,
            "label": "No sponsorship / authorization required",
            "color": "red",
        }
    else:
        return {
            "status": "neutral",
            "matches": [],
            "label": "Not mentioned — check manually",
            "color": "yellow",
        }


# ── Fit Scorer ─────────────────────────────────────────────────────────────────

FIT_SYSTEM_PROMPT = """You are a candid, experienced technical recruiter and career coach.
Your job is to honestly assess how well a candidate's resume matches a job description.
Be realistic — don't inflate scores to make the candidate feel good.
A score of 70+ means genuinely competitive. 50-69 means worth applying with significant tailoring.
Below 50 means a tough sell.

You must respond with ONLY a valid JSON object, no markdown fences, no explanation outside JSON."""

FIT_USER_TEMPLATE = """Evaluate this candidate's fit for the job.

=== MASTER RESUME ===
{resume}

=== JOB DESCRIPTION ===
{job_description}

=== JOB TITLE ===
{job_title}

=== COMPANY ===
{company}

Return a JSON object with exactly these fields:
{{
  "fit_score": <integer 0-100>,
  "strong_matches": [<list of strings — skills/experience that directly match requirements>],
  "weak_matches": [<list of strings — partial or tangential matches>],
  "gaps": [<list of strings — required skills/experience the candidate clearly lacks>],
  "nice_to_haves": [<list of strings — preferred skills the candidate has>],
  "recommendation": "<one of: 'Strong fit — apply now', 'Decent fit — tailor carefully', 'Weak fit — consider skipping'>",
  "summary": "<2-3 sentence honest assessment>"
}}"""


def score_fit(
    master_resume: str,
    job_description: str,
    job_title: str,
    company: str,
    api_key: str,
    base_url: str | None = None,
) -> dict:
    """
    Use Claude to score the candidate's fit for the job.

    Returns the parsed JSON dict from Claude.
    Raises RuntimeError on API or parse failure.
    """
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    user_msg = FIT_USER_TEMPLATE.format(
        resume=master_resume,
        job_description=job_description[:8000],
        job_title=job_title,
        company=company,
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4",
            max_tokens=1500,
            system=FIT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API error during fit scoring: {exc}") from exc

    text_block = next((b for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Claude returned no text content for fit score.")
    raw = text_block.text.strip()

    # Strip markdown fences if Claude added them despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude returned invalid JSON for fit score. Raw response:\n{raw}"
        ) from exc
