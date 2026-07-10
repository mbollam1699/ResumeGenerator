"""
PDF generator using ReportLab. ATS-safe: no graphics, no complex column layouts.
"""
import re
from io import BytesIO
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether
)
from reportlab.lib import colors


OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"


def _register_fonts() -> dict:
    """
    Register Source Sans 3 (bundled in assets/fonts) and map it for <b>/<i>
    markup. Falls back to Helvetica if the TTF files are missing so PDF
    generation never breaks.
    """
    try:
        pdfmetrics.registerFont(TTFont("Resume", str(_FONT_DIR / "SourceSans3-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Resume-Bold", str(_FONT_DIR / "SourceSans3-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("Resume-Italic", str(_FONT_DIR / "SourceSans3-It.ttf")))
        pdfmetrics.registerFont(TTFont("Resume-BoldItalic", str(_FONT_DIR / "SourceSans3-BoldIt.ttf")))
        pdfmetrics.registerFontFamily(
            "Resume",
            normal="Resume",
            bold="Resume-Bold",
            italic="Resume-Italic",
            boldItalic="Resume-BoldItalic",
        )
        return {
            "normal": "Resume",
            "bold": "Resume-Bold",
            "italic": "Resume-Italic",
        }
    except Exception:
        return {
            "normal": "Helvetica",
            "bold": "Helvetica-Bold",
            "italic": "Helvetica-Oblique",
        }


FONTS = _register_fonts()

# Matches: 30%, 1.5M+, 200+, 75+, 3x, $12K, 40%
# Ends with (?!\w) instead of \b: tokens ending in % or + sit next to
# non-word characters, where \b can never match.
_METRIC_RE = re.compile(r'\b(\d+(?:\.\d+)?(?:[KMBkmb]\+?|\+(?!\d)|(?:\s*[%x])))(?!\w)')
_BOLD_MD_RE = re.compile(r'\*\*(.*?)\*\*')


def _convert_bold(text: str) -> str:
    """Convert **markdown bold** to <b>HTML bold</b> for ReportLab."""
    return _BOLD_MD_RE.sub(r'<b>\1</b>', text)


def _bold_metrics(text: str) -> str:
    """Wrap numeric metrics in <b> tags, skipping content already inside <b> tags."""
    parts = re.split(r'(<b>.*?</b>)', text, flags=re.DOTALL)
    return ''.join(
        part if part.startswith('<b>') else _METRIC_RE.sub(r'<b>\1</b>', part)
        for part in parts
    )


def _format_bullet(text: str) -> str:
    """Convert markdown bold labels and bold metrics for a bullet string."""
    return _bold_metrics(_convert_bold(text))

# Page geometry — single source of truth
H_MARGIN = 0.60 * inch
V_MARGIN = 0.60 * inch
TEXT_WIDTH = 8.5 * inch - 2 * H_MARGIN  # 7.3"


def _safe_filename(text: str) -> str:
    return re.sub(r"[^\w\-]", "_", text.strip())


def _build_styles():
    name_style = ParagraphStyle(
        "NameStyle",
        fontName=FONTS["bold"],
        fontSize=16,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    contact_style = ParagraphStyle(
        "ContactStyle",
        fontName=FONTS["normal"],
        fontSize=9.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        fontName=FONTS["bold"],
        fontSize=10.5,
        leading=13,
        spaceBefore=5,
        spaceAfter=1,
        textColor=colors.black,
    )
    body_style = ParagraphStyle(
        "BodyText",
        fontName=FONTS["normal"],
        fontSize=9.5,
        leading=12,
        leftIndent=0,
        alignment=TA_JUSTIFY,
        textColor=colors.black,
    )
    bullet_style = ParagraphStyle(
        "BulletItem",
        fontName=FONTS["normal"],
        fontSize=9.5,
        leading=12,
        leftIndent=12,
        firstLineIndent=-9,
        alignment=TA_JUSTIFY,
        textColor=colors.black,
    )
    sub_style = ParagraphStyle(
        "SubLine",
        fontName=FONTS["italic"],
        fontSize=9.5,
        leading=11,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#444444"),
    )
    exp_date_style = ParagraphStyle(
        "ExpDate",
        fontName=FONTS["italic"],
        fontSize=9.5,
        leading=12,
        alignment=TA_RIGHT,
        textColor=colors.black,
    )
    exp_company_style = ParagraphStyle(
        "ExpCompany",
        fontName=FONTS["italic"],
        fontSize=9.5,
        leading=11,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#444444"),
    )
    tagline_style = ParagraphStyle(
        "TaglineStyle",
        fontName=FONTS["normal"],
        fontSize=9.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.black,
    )

    return {
        "name": name_style,
        "contact": contact_style,
        "tagline": tagline_style,
        "section": section_header_style,
        "body": body_style,
        "bullet": bullet_style,
        "sub": sub_style,
        "exp_date": exp_date_style,
        "exp_company": exp_company_style,
    }


def _section(title: str, styles: dict, story: list):
    story.append(Spacer(1, 3))
    story.append(Paragraph(title.upper(), styles["section"]))
    story.append(HRFlowable(width="100%", thickness=0.7, color=colors.black, spaceAfter=2))


def _two_col_row(left_para, right_para, left_frac=0.62):
    """Single-row borderless table for left+right aligned content."""
    row = Table(
        [[left_para, right_para]],
        colWidths=[TEXT_WIDTH * left_frac, TEXT_WIDTH * (1 - left_frac)],
        hAlign="LEFT",
    )
    row.setStyle(TableStyle([
        ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return row


def generate_pdf(tailored: dict, company: str, output_dir: Path = OUTPUT_DIR) -> tuple[str, bytes]:
    """
    Generate an ATS-safe PDF from the tailored resume dict.
    Returns (filepath_str, pdf_bytes).
    """
    name = tailored.get("name", "Candidate")
    safe_name = _safe_filename(name.replace(" ", "_"))
    safe_company = _safe_filename(company)
    role_raw = (
        tailored.get("experience", [{}])[0].get("title", "Role")
        if tailored.get("experience") else "Role"
    )
    safe_role = _safe_filename(role_raw.replace(" ", "_"))

    filename = f"{safe_name}_{safe_company}_{safe_role}.pdf"
    filepath = output_dir / filename

    styles = _build_styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(name, styles["name"]))
    if tailored.get("contact"):
        story.append(Paragraph(tailored["contact"], styles["contact"]))
    if tailored.get("tagline"):
        story.append(Paragraph(tailored["tagline"], styles["tagline"]))
    story.append(Spacer(1, 4))

    # ── Summary ───────────────────────────────────────────────────────────────
    if tailored.get("summary"):
        _section("Professional Summary", styles, story)
        story.append(Paragraph(tailored["summary"], styles["body"]))

    # ── Skills ────────────────────────────────────────────────────────────────
    if tailored.get("skills"):
        _section("Core Skills", styles, story)
        for skill_group in tailored["skills"]:
            cat = skill_group.get("category", "")
            items = skill_group.get("items", "")
            text = f"<b>{cat}:</b> {items}" if cat else items
            story.append(Paragraph(text, styles["body"]))

    # ── Experience ────────────────────────────────────────────────────────────
    if tailored.get("experience"):
        _section("Professional Experience", styles, story)
        for i, job in enumerate(tailored["experience"]):
            if i > 0:
                story.append(Spacer(1, 4))
            bullets = job.get("bullets", [])
            # Keep title row + company line + first bullet together to prevent orphan headers
            header_block = [
                _two_col_row(
                    Paragraph(f"<b>{job.get('title', '')}</b>", styles["body"]),
                    Paragraph(f"<i>{job.get('dates', '')}</i>", styles["exp_date"]),
                ),
                Paragraph(
                    f"{job.get('company', '')} — {job.get('location', '')}",
                    styles["exp_company"],
                ),
            ]
            if bullets:
                header_block.append(
                    Paragraph(f"• {_format_bullet(bullets[0])}", styles["bullet"])
                )
            story.append(KeepTogether(header_block))
            for bullet in bullets[1:]:
                story.append(Paragraph(f"• {_format_bullet(bullet)}", styles["bullet"]))

    # ── Education ─────────────────────────────────────────────────────────────
    if tailored.get("education"):
        _section("Education", styles, story)
        for i, edu in enumerate(tailored["education"]):
            if i > 0:
                story.append(Spacer(1, 3))
            edu_dates = edu.get("dates", edu.get("year", ""))
            # Degree + date on top row (mirrors experience title row)
            degree_para = Paragraph(f"<b>{edu.get('degree', '')}</b>", styles["body"])
            date_para = Paragraph(f"<i>{edu_dates}</i>", styles["exp_date"])
            story.append(_two_col_row(degree_para, date_para, left_frac=0.72))
            # School + GPA on italic sub-line (mirrors company/location line)
            gpa_part = f" | GPA: {edu['gpa']}" if edu.get("gpa") else ""
            story.append(Paragraph(f"{edu.get('school', '')}{gpa_part}", styles["exp_company"]))

    # ── Projects ──────────────────────────────────────────────────────────────
    if tailored.get("projects"):
        _section("Projects", styles, story)
        all_links = [p.get("link", "") for p in tailored["projects"]]
        unique_links = {l for l in all_links if l and l.strip()}
        is_generic_portfolio = len(unique_links) == 1
        for proj in tailored["projects"]:
            raw_link = (proj.get("link") or "").strip()
            show_link = (
                raw_link
                and not is_generic_portfolio
                and (raw_link.startswith("http") or "." in raw_link.split("/")[0])
            )
            if show_link:
                href = raw_link if raw_link.startswith("http") else f"https://{raw_link}"
                link_str = f"  <a href='{href}' color='blue'>{raw_link}</a>"
            else:
                link_str = ""
            tech_str = f"  [{proj.get('tech', '')}]" if proj.get("tech") else ""
            proj_text = f"<b>{proj.get('name', '')}:</b> {proj.get('description', '')}{tech_str}{link_str}"
            story.append(Paragraph(f"• {proj_text}", styles["bullet"]))

    # ── Certifications & Leadership ───────────────────────────────────────────
    if tailored.get("certifications"):
        _section("Certifications & Leadership", styles, story)
        for cert in tailored["certifications"]:
            story.append(Paragraph(f"• {cert}", styles["bullet"]))

    # ── Languages ─────────────────────────────────────────────────────────────
    if tailored.get("languages"):
        _section("Languages", styles, story)
        story.append(Paragraph(
            "  |  ".join(tailored["languages"]),
            styles["body"],
        ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
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
        raise RuntimeError(f"PDF generation failed: {exc}") from exc

    return str(filepath), pdf_bytes
