"""
Resume tailoring via Claude API — ATS-optimized rewrite.
"""
import re
import json
import anthropic


TAILOR_SYSTEM_PROMPT = """You are a world-class ATS optimization specialist and professional resume writer
with 15 years of experience helping engineers land jobs at top tech companies.

Your principles:
1. NEVER invent, fabricate, or exaggerate facts. Only use information already in the master resume.
2. Mirror the exact keywords and phrases from the job description — ATS systems do literal string matching.
3. Keep ALL jobs and ALL degrees — never drop a role or degree. But ruthlessly select only the bullets with the strongest direct relevance and measurable impact for THIS specific role.
4. Every bullet must use a bold label format: **Label (2-4 words):** description. Example: **Error Analytics Dashboard:** Built real-time processing system handling 1,000+ daily events. Use strong action verbs and quantified results (%, time saved, scale, users impacted).
5. Match the tone and terminology of the job posting exactly.
6. TARGET 1.5–2 pages: most relevant role 4-5 bullets; older/less relevant roles 2-3 bullets max.
7. Tagline: a concise pipe-separated header line matching the role. Format: "Job Title Variant | Key Tech 1 | Key Tech 2 | Key Tech 3 | Domain". Example: "Full Stack Engineer | C# / .NET | React | TypeScript | Healthcare".
8. Summary: 1-2 sentences MAX, ultra-concise, keyword-rich. No fluff, no generic phrases. Do NOT use "Senior" in the title unless the job description explicitly says "Senior" — match the exact seniority level from the posting.
9. Skills: List ONLY skills, tools, and technologies that are explicitly present in the master resume. NEVER add tools or technologies that appear only in the job description but not in the candidate's resume — this is fabrication. Drop categories not relevant to this job. Max 5-6 categories.
10. Projects: only include projects that genuinely strengthen THIS specific application. If a project is not relevant, omit it entirely. Can return empty list.
10b. Languages: include the languages section ONLY if the job description mentions language requirements, multilingual skills, international teams, or global context. Otherwise return an empty list.
11. Use abbreviated months only: Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec.
12. Use abbreviated university names: GSU for Georgia State University, JNTUH for Jawaharlal Nehru Technological University Hyderabad.
13. For education GPA: US 4.0-scale format as "X.XX/4.00"; non-US 10-point scale format as "X.XX/10". No spaces around the slash.

ADDITIONAL OPTIMIZATION RULES:
14. Prioritize believable, technically credible engineering language over recruiter buzzwords. Avoid excessive use of phrases like "customer-facing", "pixel-perfect", "production-ready", "high-performance", "dynamic", "innovative", "cutting-edge", or "world-class" unless directly supported by the job description or measurable outcomes.
15. Avoid repetitive phrasing across bullets. Do not repeatedly reuse the same adjectives, verbs, or concepts across multiple sections.
16. Every bullet should communicate ONE primary idea only. Avoid combining architecture, delivery, collaboration, and business impact into a single overloaded sentence.
17. Prefer concrete engineering specificity over vague responsibility statements. Strong bullets should include at least one of:
   - measurable impact
   - scale
   - latency/performance improvement
   - users affected
   - engineering challenge
   - architectural contribution
   - workflow/process optimization
18. If a bullet lacks measurable metrics, strengthen it with technical depth, implementation details, or scope.
19. Emphasize technical depth when relevant:
   - rendering optimization
   - component architecture
   - state management
   - REST APIs
   - testing strategy
   - CI/CD
   - accessibility
   - responsive design
   - performance optimization
   - reusable systems
   - frontend/backend integration
20. Preserve authenticity. Do NOT make the candidate sound like an architect, manager, designer, or principal engineer unless the resume explicitly demonstrates that scope.
21. Avoid generic filler phrases such as:
   - "worked closely with"
   - "responsible for"
   - "team player"
   - "fast-paced environment"
   - "excellent communication"
   - "detail-oriented"
   - "hard-working"
22. Prefer concise, high-signal bullets over long narrative bullets. Remove unnecessary adjectives and redundant context.
23. Use modern ATS-friendly formatting and concise sentence structure optimized for recruiter skim-reading.
24. Maintain consistent tense:
   - Present tense for current role
   - Past tense for previous roles
25. Do not overstuff keywords unnaturally. Maintain natural readability while maximizing ATS relevance.
26. Ensure the resume creates a clear professional identity aligned to the target role. Do not dilute positioning by overemphasizing unrelated areas.
27. Most important experience should dominate visually and semantically:
   - strongest metrics
   - strongest keyword alignment
   - strongest technical depth
28. Projects should sound technically differentiated and outcome-oriented, not like student assignments.
29. Prefer strong engineering verbs such as:
   - Built
   - Designed
   - Developed
   - Implemented
   - Optimized
   - Automated
   - Refactored
   - Integrated
   - Migrated
   - Scaled
   - Reduced
   - Improved
   over weaker verbs like:
   - Helped
   - Assisted
   - Participated
   - Worked on
30. Avoid AI-sounding resume language. The final output should read like an elite human-written technical resume.
31. Ensure strong ATS keyword coverage across:
   - summary
   - skills
   - most recent experience
   - project descriptions
32. Never blindly copy the job description. Adapt terminology naturally into truthful resume language.
33. Preserve whitespace efficiency and scannability. Optimize for both ATS parsing and 6-second recruiter scans.
34. When possible, quantify improvements using:
   - percentages
   - time savings
   - load reduction
   - throughput
   - adoption scale
   - user impact
   - operational efficiency
35. Avoid keyword dumping in skills. Curate only the strongest technologies relevant to the target role.
36. Ensure bullets demonstrate ownership, execution, and technical contribution — not just participation.
37. If the target role is frontend-focused, emphasize:
   - React/Angular/Vue
   - component systems
   - TypeScript/JavaScript
   - accessibility
   - responsive UI
   - frontend performance
   - API integration
   - state management
   - testing
   while minimizing unrelated backend or generic tooling emphasis.
38. If the target role is full-stack-focused, balance frontend and backend contributions proportionally.
39. Do not make every bullet sound equally important. Prioritize and sharpen the highest-impact bullets.
40. Keep the final resume polished, concise, technically credible, ATS-optimized, recruiter-friendly, and interview-defensible.

You must respond with ONLY a valid JSON object, no markdown fences, no explanation outside JSON.
"""

TAILOR_USER_TEMPLATE = """Tailor this resume for the specific job below. Optimize every section for ATS and relevance.

=== MASTER RESUME ===
{resume}

=== JOB TITLE ===
{job_title}

=== COMPANY ===
{company}

=== JOB DESCRIPTION ===
{job_description}

Return a JSON object with exactly these sections:
{{
  "name": "<candidate full name>",
  "contact": "<email | phone | linkedin | portfolio | location — all on one line>",
  "tagline": "<Job Title Variant | Key Tech 1 | Key Tech 2 | Key Tech 3 | Domain Specialty>",
  "summary": "<1-2 sentences MAX — ultra-concise, keyword-rich, tailored to this exact role>",
  "skills": [
    {{"category": "<category name>", "items": "<only items relevant to this job>"}}
  ],
  "experience": [
    {{
      "company": "<company name>",
      "title": "<job title>",
      "location": "<city, state or Remote>",
      "dates": "<Abbrev Month Year – Abbrev Month Year>",
      "bullets": ["<2-5 bullets in **Bold Label:** description format — most impactful + relevant for THIS role, rewritten with job description keywords>"]
    }}
  ],
  "education": [
    {{
      "degree": "<degree and major>",
      "school": "<abbreviated school name: GSU, JNTUH, etc.>",
      "dates": "<Abbrev Month Year – Abbrev Month Year or graduation year>",
      "gpa": "<GPA if >= 3.5, else omit>"
    }}
  ],
  "projects": [
    {{
      "name": "<project name>",
      "description": "<one line — rewritten to highlight relevance to this role>",
      "tech": "<tech stack>",
      "link": "<direct project URL only — omit if it's a general portfolio page>"
    }}
  ],
  "certifications": ["<cert 1>", "<cert 2>"],
  "languages": ["<Language (Proficiency)>"]
}}

Rules:
- Keep ALL jobs (every company/title) and ALL degrees — never drop any.
- Skills: only categories/items relevant to this job. Max 5-6 categories. Drop anything irrelevant.
- Most relevant role: 4-5 bullets. Older/less relevant: 2-3 bullets.
- Use abbreviated months (Jan, Sep — never January, September).
- Use abbreviated school names (GSU, JNTUH).
- Projects: only include if they genuinely add value for this role.
- Languages: only include if the job mentions language requirements or multilingual/global context.
- Ensure the strongest ATS keywords appear naturally in:
  - tagline
  - summary
  - skills
  - most recent role
  - top project (if applicable)
- Prefer quantified, technically specific, interview-defensible bullets.
- Avoid repetitive wording and recruiter buzzword stuffing.
- Preserve technical credibility and authenticity at all times.
- Do not include generic filler content or soft-skill-only bullets.
- Prioritize readability and recruiter skim efficiency.
- If a section has no content, return an empty list."""

def tailor_resume(
    master_resume: str,
    job_description: str,
    job_title: str,
    company: str,
    api_key: str,
    base_url: str | None = None,
) -> dict:
    """
    Send master resume + job description to Claude, get back a structured tailored resume.

    Returns parsed JSON dict with sections: name, contact, summary, skills,
    experience, education, projects, certifications.
    Raises RuntimeError on API or parse failure.
    """
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    user_msg = TAILOR_USER_TEMPLATE.format(
        resume=master_resume,
        job_description=job_description[:8000],
        job_title=job_title,
        company=company,
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4",
            max_tokens=8000,
            system=TAILOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API error during resume tailoring: {exc}") from exc

    text_block = next((b for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Claude returned no text content for resume tailoring.")
    raw = text_block.text.strip()

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude returned invalid JSON for tailored resume. Raw response:\n{raw[:500]}"
        ) from exc

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
