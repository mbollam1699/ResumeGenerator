"""
Cover letter generator via Claude API + ReportLab PDF.
Friendly, genuine tone — not robotic. Same formatting rules as resume.
"""
import re
import json
from datetime import date
from io import BytesIO
from pathlib import Path
import anthropic
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors


OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

H_MARGIN = 0.60 * inch
V_MARGIN = 0.60 * inch


# ── Prompt ────────────────────────────────────────────────────────────────────

CL_SYSTEM_PROMPT = """You are writing a cover letter for a job applicant. Write in first person with a warm, genuine, confident tone — not robotic or overly formal.

AVOID these clichés:
- "I am writing to express my interest"
- "I would be a great fit"
- "I am excited to apply for this opportunity"
- "I believe my skills align with"
- Any opener that starts with "I"

Structure — 4 short paragraphs:
1. OPENING (2-3 sentences): A specific, compelling hook about why THIS role at THIS company excites you. Reference something real about the company or role. Start with something other than "I".
2. BODY 1 (3-4 sentences): Your strongest relevant achievement with a metric. Connect it directly to what the job needs.
3. BODY 2 (3-4 sentences): A second strength — leadership, collaboration, learning speed, or a complementary technical dimension. Keep it genuine and specific.
4. CLOSING (2-3 sentences): Warm enthusiasm for next steps, availability, thank-you. Confident, not desperate.

Rules:
- Use ONLY facts from the master resume — never invent or exaggerate.
- Mirror keywords from the job description naturally.
- Total 250–320 words. Tight and genuine beats long and impressive.
- No bullet points. Flowing paragraphs only.
- Tone: like a confident, friendly engineer writing to someone they genuinely respect.

Respond with ONLY a valid JSON object, no markdown fences, no explanation."""

CL_USER_TEMPLATE = """Write a cover letter for the following application.

=== CANDIDATE RESUME (facts only — do not invent) ===
{resume}

=== JOB TITLE ===
{job_title}

=== COMPANY ===
{company}

=== JOB DESCRIPTION ===
{job_description}

Return exactly this JSON:
{{
  "greeting": "Dear Hiring Team,",
  "paragraphs": ["<opening>", "<body1>", "<body2>", "<closing>"],
  "sign_off": "Sincerely,",
  "name": "<candidate full name>"
}}"""


# ── API call ──────────────────────────────────────────────────────────────────

def generate_cover_letter(
    master_resume: str,
    job_description: str,
    job_title: str,
    company: str,
    api_key: str,
    base_url: str | None = None,
) -> dict:
    """
    Call Claude to generate a structured cover letter dict.
    Returns dict with: greeting, paragraphs, sign_off, name.
    Raises RuntimeError on failure.
    """
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**client_kwargs)

    user_msg = CL_USER_TEMPLATE.format(
        resume=master_resume,
        job_description=job_description[:8000],
        job_title=job_title,
        company=company,
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4",
            max_tokens=2000,
            system=CL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as exc:
        raise RuntimeError(f"Claude API error during cover letter generation: {exc}") from exc

    text_block = next((b for b in response.content if b.type == "text"), None)
    if not text_block:
        raise RuntimeError("Claude returned no text for cover letter.")
    raw = text_block.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Claude returned invalid JSON for cover letter. Raw:\n{raw[:400]}"
        ) from exc


# ── PDF ───────────────────────────────────────────────────────────────────────

def _build_styles():
    name_style = ParagraphStyle(
        "CLName",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    contact_style = ParagraphStyle(
        "CLContact",
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    meta_style = ParagraphStyle(
        "CLMeta",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    body_style = ParagraphStyle(
        "CLBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor=colors.black,
    )
    sign_style = ParagraphStyle(
        "CLSign",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    return {
        "name": name_style,
        "contact": contact_style,
        "meta": meta_style,
        "body": body_style,
        "sign": sign_style,
    }


def generate_cover_letter_pdf(
    cl_data: dict,
    contact_line: str,
    company: str,
    job_title: str,
    output_dir: Path = OUTPUT_DIR,
) -> tuple[str, bytes]:
    """
    Render cover letter dict to PDF.
    Returns (filepath_str, pdf_bytes).
    """
    import re as _re
    safe = lambda t: _re.sub(r"[^\w\-]", "_", t.strip())
    candidate_name = cl_data.get("name", "Candidate")
    filename = f"{safe(candidate_name.replace(' ', '_'))}_CoverLetter_{safe(company)}.pdf"
    filepath = output_dir / filename

    styles = _build_styles()
    story = []

    # ── Header (same as resume) ────────────────────────────────────────────────
    story.append(Paragraph(candidate_name, styles["name"]))
    if contact_line:
        story.append(Paragraph(contact_line, styles["contact"]))
    story.append(HRFlowable(width="100%", thickness=0.7, color=colors.black, spaceAfter=6))
    story.append(Spacer(1, 4))

    # ── Date + addressee ───────────────────────────────────────────────────────
    _placeholders = {"", "unknown company", "unknown role", "unknown", "the company", "open position"}
    today = date.today().strftime("%B %d, %Y")
    story.append(Paragraph(today, styles["meta"]))
    story.append(Spacer(1, 4))
    if company.strip().lower() not in _placeholders:
        story.append(Paragraph(company, styles["meta"]))
    if job_title.strip().lower() not in _placeholders:
        story.append(Paragraph(f"Re: {job_title}", styles["meta"]))
    story.append(Spacer(1, 10))

    # ── Greeting ───────────────────────────────────────────────────────────────
    story.append(Paragraph(cl_data.get("greeting", "Dear Hiring Team,"), styles["body"]))

    # ── Body paragraphs ────────────────────────────────────────────────────────
    for para in cl_data.get("paragraphs", []):
        story.append(Paragraph(para, styles["body"]))

    # ── Sign-off ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(Paragraph(cl_data.get("sign_off", "Sincerely,"), styles["sign"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph(candidate_name, styles["sign"]))

    try:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=H_MARGIN,
            rightMargin=H_MARGIN,
            topMargin=V_MARGIN,
            bottomMargin=V_MARGIN,
        )
        doc.build(story)
        pdf_bytes = buf.getvalue()
        filepath.write_bytes(pdf_bytes)
    except Exception as exc:
        raise RuntimeError(f"Cover letter PDF generation failed: {exc}") from exc

    return str(filepath), pdf_bytes
