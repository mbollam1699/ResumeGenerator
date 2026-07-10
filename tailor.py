"""
Resume tailoring via Claude API — ATS-optimized rewrite.

Pipeline: tailor -> (optional) critique/refine pass -> skills audit.
The audit programmatically enforces the "never invent skills" rule
instead of trusting the prompt alone.
"""
import re

from claude_client import call_claude_structured
from config import school_abbreviation_rules


TAILOR_SYSTEM_PROMPT = f"""You are an elite ATS optimization specialist and technical resume writer.
Rewrite the candidate's master resume for one specific job. Follow these rules in priority order:

1. TRUTH ABOVE ALL: never invent, fabricate, or exaggerate. Every fact, skill, tool, and metric must already exist in the master resume. The skills section may contain ONLY technologies present in the master resume — never ones that appear only in the job description.
2. Mirror the job description's exact keywords and phrasing naturally (ATS systems do literal string matching), especially in the tagline, summary, skills, and most recent role. Do not stuff keywords unnaturally.
3. Keep ALL jobs and ALL degrees. Trim bullets instead: 4-5 for the most relevant role, 2-3 for older or less relevant roles. Target 1.5-2 pages total.
4. Bullet format: "**Label (2-4 words):** description". One primary idea per bullet, strong verb (Built, Designed, Optimized, Automated, Migrated, Reduced...), quantified impact where the master resume supports it. If a bullet has no metric, add technical depth (architecture, scale, implementation detail) instead.
5. Match the posting's exact seniority — do not write "Senior" unless the job title says so.
6. Tagline: pipe-separated, "Job Title Variant | Key Tech 1 | Key Tech 2 | Key Tech 3 | Domain".
7. Summary: 1-2 sentences maximum, ultra-concise and keyword-rich. No fluff.
8. Tense: present for the current role, past for previous roles.
9. Dates: abbreviated months only (Jan, Feb, ... Dec). {school_abbreviation_rules()} GPA format: "X.XX/4.00" for US, "X.XX/10" for 10-point scales, no spaces around the slash.
10. Projects: include only those that genuinely strengthen THIS application (empty list is fine). Languages: include only if the JD mentions languages, multilingual work, or global teams.
11. Skills section: max 5-6 categories, only ones relevant to this job.
12. Banned filler: "worked closely with", "responsible for", "team player", "fast-paced environment", "detail-oriented", "dynamic", "innovative", "cutting-edge", "world-class". Avoid repeating the same verbs or adjectives across bullets.
13. The result must read like an elite human-written resume: technically credible, interview-defensible, optimized for both ATS parsing and a 6-second recruiter scan. Sharpen the highest-impact bullets; not everything can sound equally important."""

TAILOR_USER_TEMPLATE = """Tailor this resume for the specific job below.

=== MASTER RESUME ===
{resume}

=== JOB TITLE ===
{job_title}

=== COMPANY ===
{company}

=== JOB DESCRIPTION ===
{job_description}

=== ROLE FOCUS ===
{role_focus}"""

CRITIQUE_SYSTEM_PROMPT = """You are a ruthless resume reviewer doing a final quality pass on a tailored resume draft.

Fix these problems if present, and return the FULL corrected resume:
- Important JD keywords missing from the tagline, summary, skills, or most recent role
- Weak, vague, or overloaded bullets (more than one idea per bullet)
- Repeated verbs/adjectives across bullets
- Seniority mismatch with the posting
- Buzzword filler or AI-sounding phrasing
- Wrong tense (must be: present tense for current role, past for previous)

HARD CONSTRAINT: never add any fact, skill, tool, or metric that is not in the MASTER resume. When in doubt, cut rather than embellish. Keep every job and degree. Preserve the bullet format "**Label:** description"."""

CRITIQUE_USER_TEMPLATE = """=== MASTER RESUME (source of truth — nothing outside this may be claimed) ===
{resume}

=== JOB DESCRIPTION ===
{job_description}

=== DRAFT TAILORED RESUME (JSON) ===
{draft}

Review the draft against the job description and return the full corrected resume."""


RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "contact": {
            "type": "string",
            "description": "email | phone | linkedin | portfolio | location — all on one line",
        },
        "tagline": {
            "type": "string",
            "description": "Job Title Variant | Key Tech 1 | Key Tech 2 | Key Tech 3 | Domain",
        },
        "summary": {"type": "string", "description": "1-2 sentences max"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "items": {"type": "string", "description": "comma-separated"},
                },
                "required": ["category", "items"],
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "location": {"type": "string"},
                    "dates": {"type": "string", "description": "Abbrev Month Year – Abbrev Month Year"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string", "description": "**Bold Label:** description"},
                    },
                },
                "required": ["company", "title", "location", "dates", "bullets"],
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "degree": {"type": "string"},
                    "school": {"type": "string", "description": "abbreviated"},
                    "dates": {"type": "string"},
                    "gpa": {"type": "string", "description": "only if >= 3.5, else empty string"},
                },
                "required": ["degree", "school", "dates"],
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "tech": {"type": "string"},
                    "link": {"type": "string", "description": "direct project URL only, else empty"},
                },
                "required": ["name", "description", "tech"],
            },
        },
        "certifications": {"type": "array", "items": {"type": "string"}},
        "languages": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "name", "contact", "tagline", "summary", "skills",
        "experience", "education", "projects", "certifications", "languages",
    ],
}


# ── Role focus detection ───────────────────────────────────────────────────────

_ROLE_SIGNALS = {
    "frontend": [
        "react", "angular", "vue", "css", "frontend", "front-end", "ui engineer",
        "user interface", "component", "accessibility", "responsive",
    ],
    "backend": [
        "backend", "back-end", ".net", "c#", "java", "microservice", "rest api",
        "api design", "server-side", "distributed", "scalab",
    ],
    "data": [
        "etl", "data pipeline", "power bi", "tableau", "data analyst", "analytics",
        "data warehouse", "data model", "bi ", "visualization",
    ],
    "healthcare": [
        "fhir", "hl7", "ehr", "epic", "cerner", "clinical", "hipaa", "patient",
        "interoperability", "healthcare",
    ],
}

_ROLE_GUIDANCE = {
    "frontend": (
        "This role leans FRONTEND: emphasize React/Angular/Vue work, component "
        "architecture, state management, TypeScript, accessibility, responsive UI, "
        "and frontend performance. De-emphasize unrelated backend tooling."
    ),
    "backend": (
        "This role leans BACKEND: emphasize C#/.NET, API design, databases, "
        "performance, reliability, and system architecture. Keep frontend work "
        "secondary."
    ),
    "data": (
        "This role leans DATA: emphasize SQL, ETL pipelines, dashboards/BI, data "
        "quality, and turning data into decisions. De-emphasize generic web work."
    ),
    "healthcare": (
        "This role is HEALTHCARE-domain: lead with FHIR/HL7/EHR integration work, "
        "clinical impact metrics, and HIPAA-aware engineering."
    ),
}


def detect_role_focus(job_description: str, job_title: str = "") -> str:
    """Score the JD against role families and return injected guidance text."""
    text = f"{job_title}\n{job_description}".lower()
    scores = {
        family: sum(text.count(sig) for sig in signals)
        for family, signals in _ROLE_SIGNALS.items()
    }
    top = [f for f, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s >= 3][:2]
    if not top:
        return (
            "This role is a general software engineering role: balance frontend and "
            "backend contributions proportionally to the job description."
        )
    return " ".join(_ROLE_GUIDANCE[f] for f in top)


# ── Fabrication guard ──────────────────────────────────────────────────────────

def _item_in_master(item: str, master_lower: str) -> bool:
    """Relaxed check: the skill (or most of its words) appears in the master resume."""
    it = item.lower().strip()
    if not it or it in master_lower:
        return True
    words = [w for w in re.split(r"[^a-z0-9+#.]+", it) if len(w) > 2]
    if not words:
        return True
    hits = sum(1 for w in words if w in master_lower)
    return hits / len(words) >= 0.6


def audit_skills(tailored: dict, master_resume: str) -> tuple[dict, list[str]]:
    """
    Enforce rule #1 programmatically: strip any skill item from the tailored
    resume that does not appear in the master resume.

    Returns (cleaned_resume, removed_items) so the UI can surface what was cut.
    """
    master_lower = master_resume.lower()
    removed = []
    cleaned_groups = []
    for group in tailored.get("skills", []):
        kept = []
        for item in (i.strip() for i in group.get("items", "").split(",")):
            if not item:
                continue
            if _item_in_master(item, master_lower):
                kept.append(item)
            else:
                removed.append(item)
        if kept:
            cleaned_groups.append({"category": group.get("category", ""), "items": ", ".join(kept)})
    tailored["skills"] = cleaned_groups
    return tailored, removed


# ── Main entry point ───────────────────────────────────────────────────────────

def tailor_resume(
    master_resume: str,
    job_description: str,
    job_title: str,
    company: str,
    api_key: str,
    base_url: str | None = None,
    model: str | None = None,
    refine: bool = True,
) -> dict:
    """
    Send master resume + job description to Claude, get back a structured
    tailored resume. When `refine` is True, a second critique pass reviews
    and corrects the draft against the JD.

    Raises RuntimeError on API failure.
    """
    jd = job_description[:30000]
    user_msg = TAILOR_USER_TEMPLATE.format(
        resume=master_resume,
        job_description=jd,
        job_title=job_title,
        company=company,
        role_focus=detect_role_focus(jd, job_title),
    )

    result = call_claude_structured(
        task="resume tailoring",
        system=TAILOR_SYSTEM_PROMPT,
        user_msg=user_msg,
        schema=RESUME_SCHEMA,
        api_key=api_key,
        max_tokens=8000,
        base_url=base_url,
        model=model,
        temperature=0.5,
    )

    if refine:
        import json as _json
        critique_msg = CRITIQUE_USER_TEMPLATE.format(
            resume=master_resume,
            job_description=jd,
            draft=_json.dumps(result, indent=1),
        )
        result = call_claude_structured(
            task="resume refinement",
            system=CRITIQUE_SYSTEM_PROMPT,
            user_msg=critique_msg,
            schema=RESUME_SCHEMA,
            api_key=api_key,
            max_tokens=8000,
            base_url=base_url,
            model=model,
            temperature=0.3,
        )

    return _abbreviate_months_in_resume(result)


_MONTH_MAP = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "June": "Jun", "July": "Jul", "August": "Aug", "September": "Sep",
    "October": "Oct", "November": "Nov", "December": "Dec",
}
_MONTH_RE = re.compile(r'\b(' + '|'.join(_MONTH_MAP) + r')\b')


def _abbreviate_months_in_resume(data: dict) -> dict:
    """Replace full month names with abbreviations in all date fields."""
    def _fix(s: str) -> str:
        return _MONTH_RE.sub(lambda m: _MONTH_MAP[m.group()], s) if isinstance(s, str) else s

    for job in data.get("experience", []):
        job["dates"] = _fix(job.get("dates", ""))
    for edu in data.get("education", []):
        edu["dates"] = _fix(edu.get("dates", ""))
    return data


def resume_to_text(tailored: dict) -> str:
    """Convert structured tailored resume dict to a plain text preview."""
    lines = []

    if tailored.get("name"):
        lines.append(tailored["name"].upper())
    if tailored.get("contact"):
        lines.append(tailored["contact"])
    if tailored.get("tagline"):
        lines.append(tailored["tagline"])
    lines.append("")

    if tailored.get("summary"):
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(tailored["summary"])
        lines.append("")

    if tailored.get("skills"):
        lines.append("SKILLS")
        lines.append("-" * 40)
        for skill_group in tailored["skills"]:
            lines.append(f"{skill_group.get('category', '')}: {skill_group.get('items', '')}")
        lines.append("")

    if tailored.get("experience"):
        lines.append("EXPERIENCE")
        lines.append("-" * 40)
        for job in tailored["experience"]:
            lines.append(f"{job.get('title', '')} — {job.get('company', '')}")
            lines.append(f"{job.get('location', '')} | {job.get('dates', '')}")
            for bullet in job.get("bullets", []):
                lines.append(f"  • {bullet}")
            lines.append("")

    if tailored.get("education"):
        lines.append("EDUCATION")
        lines.append("-" * 40)
        for edu in tailored["education"]:
            gpa = f" | GPA: {edu['gpa']}" if edu.get("gpa") else ""
            edu_dates = edu.get('dates', edu.get('year', ''))
            lines.append(f"{edu.get('degree', '')} — {edu.get('school', '')} ({edu_dates}){gpa}")
        lines.append("")

    if tailored.get("projects"):
        lines.append("PROJECTS")
        lines.append("-" * 40)
        for proj in tailored["projects"]:
            link = f" | {proj['link']}" if proj.get("link") else ""
            lines.append(f"{proj.get('name', '')}: {proj.get('description', '')} [{proj.get('tech', '')}]{link}")
        lines.append("")

    if tailored.get("certifications"):
        lines.append("CERTIFICATIONS")
        lines.append("-" * 40)
        for cert in tailored["certifications"]:
            lines.append(f"  • {cert}")

    if tailored.get("languages"):
        lines.append("")
        lines.append("LANGUAGES")
        lines.append("-" * 40)
        for lang in tailored["languages"]:
            lines.append(f"  • {lang}")

    return "\n".join(lines)
