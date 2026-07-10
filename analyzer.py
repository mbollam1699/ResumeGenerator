"""
Sponsorship checker, fit scorer, and ATS keyword coverage.
"""
import re

from claude_client import call_claude_structured


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

Also extract the job description's most important ATS keywords — the exact
terms a recruiter or ATS filter would search for (technologies, frameworks,
methodologies, domain terms). Use the JD's literal wording."""

FIT_USER_TEMPLATE = """Evaluate this candidate's fit for the job.

=== MASTER RESUME ===
{resume}

=== JOB DESCRIPTION ===
{job_description}

=== JOB TITLE ===
{job_title}

=== COMPANY ===
{company}"""

FIT_SCHEMA = {
    "type": "object",
    "properties": {
        "fit_score": {
            "type": "integer", "minimum": 0, "maximum": 100,
            "description": "Honest 0-100 fit score",
        },
        "strong_matches": {
            "type": "array", "items": {"type": "string"},
            "description": "Skills/experience that directly match requirements",
        },
        "weak_matches": {
            "type": "array", "items": {"type": "string"},
            "description": "Partial or tangential matches",
        },
        "gaps": {
            "type": "array", "items": {"type": "string"},
            "description": "Required skills/experience the candidate clearly lacks",
        },
        "nice_to_haves": {
            "type": "array", "items": {"type": "string"},
            "description": "Preferred skills the candidate has",
        },
        "ats_keywords": {
            "type": "array", "items": {"type": "string"},
            "minItems": 10, "maxItems": 20,
            "description": "The 10-20 most important ATS keywords from the JD, in its literal wording",
        },
        "recommendation": {
            "type": "string",
            "enum": [
                "Strong fit — apply now",
                "Decent fit — tailor carefully",
                "Weak fit — consider skipping",
            ],
        },
        "summary": {
            "type": "string",
            "description": "2-3 sentence honest assessment",
        },
    },
    "required": [
        "fit_score", "strong_matches", "weak_matches", "gaps",
        "nice_to_haves", "ats_keywords", "recommendation", "summary",
    ],
}


def score_fit(
    master_resume: str,
    job_description: str,
    job_title: str,
    company: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """
    Use Claude to score the candidate's fit for the job.

    Returns the parsed JSON dict from Claude.
    Raises RuntimeError on API or parse failure.
    """
    user_msg = FIT_USER_TEMPLATE.format(
        resume=master_resume,
        job_description=job_description[:30000],
        job_title=job_title,
        company=company,
    )

    return call_claude_structured(
        task="fit scoring",
        system=FIT_SYSTEM_PROMPT,
        user_msg=user_msg,
        schema=FIT_SCHEMA,
        api_key=api_key,
        max_tokens=2000,
        base_url=base_url,
        model=model,
        temperature=0.2,
    )


# ── Keyword coverage ───────────────────────────────────────────────────────────

def keyword_coverage(keywords: list[str], resume_text: str) -> dict:
    """
    Check which of the JD's ATS keywords actually appear in the tailored
    resume text (case-insensitive).

    Returns {"pct": int, "matched": [...], "missing": [...]}.
    """
    text = resume_text.lower()
    matched, missing = [], []
    for kw in keywords:
        kw_clean = kw.strip()
        if not kw_clean:
            continue
        (matched if kw_clean.lower() in text else missing).append(kw_clean)
    total = len(matched) + len(missing)
    pct = round(len(matched) / total * 100) if total else 0
    return {"pct": pct, "matched": matched, "missing": missing}
