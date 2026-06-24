"""
ResumeAgent — premium SaaS Streamlit UI
"""
import io
from pathlib import Path
import streamlit as st

from scraper import scrape_job_posting
from analyzer import check_sponsorship, score_fit
from tailor import tailor_resume, resume_to_text
from pdf_generator import generate_pdf
from cover_letter import generate_cover_letter, generate_cover_letter_pdf


st.set_page_config(
    page_title="ResumeAgent",
    page_icon="✦",
    layout="centered",
)

# ── Fonts ────────────────────────────────────────────────────────────────────
st.markdown('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">', unsafe_allow_html=True)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>

*, html, body, .stApp, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
.stApp { background: #F7F7F8 !important; }
.block-container { padding: 1.5rem 2.5rem 5rem !important; }

/* ── Hide Streamlit chrome ── */
header[data-testid="stHeader"],
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stStatusWidget"],
[data-testid="stAppToolbarActions"],
[data-testid="stSidebar"],
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
#MainMenu, footer {
    display: none !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* ── Popover (settings gear) ───────────────────────────────────── */
[data-testid="stPopover"] > div {
    min-width: 320px !important;
}
/* Scale down ALL content inside the popover panel */
[data-testid="stPopover"] div[data-baseweb="popover"] * {
    font-size: 0.72rem !important;
}
[data-testid="stPopover"] div[data-baseweb="popover"] [data-testid="stWidgetLabel"] p,
[data-testid="stPopover"] div[data-baseweb="popover"] label {
    font-size: 0.62rem !important;
}
[data-testid="stPopover"] div[data-baseweb="popover"] input {
    height: 2rem !important;
}

/* ── Global alert / error / success font sizing ────────────────── */
[data-testid="stAlert"] p,
[data-testid="stAlert"] div,
.stAlert p {
    font-size: 0.78rem !important;
}
/* Popover button — hide everything via visibility, then show ::after */
[data-testid="stPopover"] button {
    visibility: hidden !important;
    position: relative !important;
    background: white !important;
    border: 1.5px solid #E5E7EB !important;
    border-radius: 10px !important;
    height: 2rem !important;
}
[data-testid="stPopover"] button::after {
    content: "⚙  Settings";
    visibility: visible !important;
    position: absolute !important;
    inset: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    color: #374151 !important;
}
[data-testid="stPopover"] button:hover {
    border-color: #6D5DF6 !important;
    background: #F5F3FF !important;
}
[data-testid="stPopover"] button:hover::after {
    color: #6D5DF6 !important;
}
/* Fix file uploader double-text bug globally */
[data-testid="stFileUploaderDropzone"] button {
    overflow: hidden !important;
    position: relative !important;
}
[data-testid="stFileUploaderDropzone"] button > * {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] button::after {
    content: "Browse files";
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Cards ─────────────────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: white !important;
    border-radius: 24px !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03), 0 4px 24px rgba(0,0,0,0.05) !important;
}

/* ── Buttons ────────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    height: 2rem !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0em !important;
}
.stButton > button p,
.stButton > button span,
.stDownloadButton > button p,
.stDownloadButton > button span {
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    line-height: 1 !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6D5DF6 0%, #8B5CF6 100%) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(109,93,246,0.35) !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(109,93,246,0.45) !important;
}
.stButton > button[kind="primary"]:active { transform: translateY(0px) !important; }

.stButton > button:not([kind="primary"]),
.stDownloadButton > button:not([kind="primary"]) {
    background: white !important;
    border: 1.5px solid #E5E7EB !important;
    color: #374151 !important;
}
.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:not([kind="primary"]):hover {
    border-color: #6D5DF6 !important;
    color: #6D5DF6 !important;
    background: #F5F3FF !important;
}

/* ── Text Inputs ────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
    border-radius: 10px !important;
    border: 1.5px solid #E5E7EB !important;
    color: #1D2433 !important;
    background: #FAFAFA !important;
    font-size: 0.72rem !important;
    transition: border-color 0.18s, box-shadow 0.18s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #6D5DF6 !important;
    box-shadow: 0 0 0 3px rgba(109,93,246,0.12) !important;
    background: white !important;
}
.stTextInput label, .stTextArea label,
.stTextInput [data-testid="stWidgetLabel"],
.stTextArea [data-testid="stWidgetLabel"],
.stTextInput [data-testid="stWidgetLabel"] p,
.stTextArea [data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] p {
    font-size: 0.62rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    color: #667085 !important;
    margin-bottom: 3px !important;
    line-height: 1.4 !important;
}

/* ── Mode toggle buttons (Job URL / Paste JD) ───────────────────── */
/* Secondary (inactive) mode buttons get a muted tab look */
.stButton > button[kind="secondary"] {
    background: #F3F4F6 !important;
    border: 1.5px solid #E5E7EB !important;
    color: #667085 !important;
    font-weight: 500 !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #EEEDF5 !important;
    border-color: #6D5DF6 !important;
    color: #6D5DF6 !important;
}

/* ── Tabs ───────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #F3F4F6 !important;
    border-radius: 14px !important;
    padding: 4px !important;
    gap: 2px !important;
    border-bottom: none !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    padding: 6px 18px !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
    color: #667085 !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #1D2433 !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important;
}
.stTabs [data-baseweb="tab-highlight"] { display: none !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── Metrics ────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: white !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 20px !important;
    padding: 1.25rem 1.5rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.67rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    color: #667085 !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #1D2433 !important;
    letter-spacing: -0.03em !important;
}
[data-testid="stMetricDelta"] { font-size: 0.72rem !important; }

/* ── Progress ───────────────────────────────────────────────────── */
.stProgress > div {
    background: #E5E7EB !important;
    border-radius: 99px !important;
    height: 6px !important;
}
.stProgress > div > div {
    background: linear-gradient(90deg, #6D5DF6, #8B5CF6) !important;
    border-radius: 99px !important;
}

/* ── Alerts ─────────────────────────────────────────────────────── */
.stAlert {
    border-radius: 14px !important;
    border-left-width: 4px !important;
    font-size: 0.875rem !important;
}

/* ── Expander ───────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 14px !important;
    overflow: hidden !important;
    background: white !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #374151 !important;
}

/* ── Divider ────────────────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid #E5E7EB !important;
    margin: 2rem 0 !important;
}

/* ── Spinner ────────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: #6D5DF6 !important; }

/* ── Mobile Responsive ─────────────────────────────────────────── */
@media (max-width: 768px) {
  /* Tighter page padding */
  .block-container { padding: 1rem 1rem 4rem !important; }

  /* Columns wrap into 2-per-row grid */
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.5rem !important;
  }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    min-width: 45% !important;
    flex: 1 1 45% !important;
  }

  /* Hero header stacks vertically */
  div[style*="display:flex"][style*="justify-content:space-between"] {
    flex-direction: column !important;
    gap: 0.5rem !important;
  }

  /* Bigger touch targets for buttons */
  .stButton > button, .stDownloadButton > button {
    min-height: 2.5rem !important;
    font-size: 0.78rem !important;
  }

  /* Wider tap area for inputs */
  .stTextInput input, .stTextArea textarea {
    font-size: 0.82rem !important;
    padding: 0.6rem 0.75rem !important;
  }

  /* Metric cards breathe on small screens */
  [data-testid="metric-container"] {
    padding: 0.9rem 1rem !important;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.15rem !important;
  }

  /* Tab labels fit */
  .stTabs [data-baseweb="tab"] {
    padding: 6px 10px !important;
    font-size: 0.68rem !important;
  }

  /* Cards: less border-radius on small screens */
  [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
  }

  /* Header row: keep branding + settings on one line */
  [data-testid="stHorizontalBlock"]:first-child {
    flex-wrap: nowrap !important;
  }
  [data-testid="stHorizontalBlock"]:first-child > [data-testid="stColumn"]:last-child {
    min-width: auto !important;
    flex: 0 0 auto !important;
  }

  /* Collapse popover to gear icon only on mobile */
  [data-testid="stPopover"] button::after {
    content: "⚙" !important;
    font-size: 0.9rem !important;
  }
  [data-testid="stPopover"] button {
    width: 2rem !important;
    min-width: 2rem !important;
    padding: 0 !important;
  }
}
</style>
""", unsafe_allow_html=True)


# ── Header row: branding + settings gear ─────────────────────────────────────
hdr_left, hdr_right = st.columns([8, 2])
with hdr_left:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding:0.4rem 0">
        <div style="width:34px;height:34px;background:linear-gradient(135deg,#6D5DF6,#8B5CF6);
             border-radius:10px;display:flex;align-items:center;justify-content:center;
             font-size:15px;font-weight:800;color:white;flex-shrink:0">R</div>
        <div>
            <span style="font-size:0.95rem;font-weight:700;color:#1D2433;letter-spacing:-0.02em">ResumeAgent</span>
            <span style="font-size:0.65rem;color:#9CA3AF;margin-left:8px">Powered by Claude AI</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with hdr_right:
    with st.popover("Settings", use_container_width=True):
        st.markdown('<p style="font-size:0.62rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#667085;margin-bottom:0.5rem">Settings</p>', unsafe_allow_html=True)
        api_key_input = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-api03-...",
            help="Get yours at console.anthropic.com",
        )
        base_url_input = st.text_input(
            "Base URL",
            placeholder="Optional — leave blank for Anthropic",
        )
        uploaded_resume = st.file_uploader(
            "Master Resume",
            type=["txt", "pdf"],
        )
        default_resume_path = Path(__file__).parent / "master_resume.txt"
        if uploaded_resume:
            st.success(f"✓ Resume loaded")
        elif default_resume_path.exists():
            st.caption("Using master_resume.txt")
        else:
            st.warning("Upload a resume to get started.")

api_key = api_key_input.strip() or None
base_url = base_url_input.strip() or None

if uploaded_resume:
    if uploaded_resume.type == "application/pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(uploaded_resume.read()))
            master_resume_text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            master_resume_text = ""
    else:
        master_resume_text = uploaded_resume.read().decode("utf-8", errors="ignore")
elif default_resume_path.exists():
    master_resume_text = default_resume_path.read_text(encoding="utf-8")
else:
    master_resume_text = ""


# ── Tagline ──────────────────────────────────────────────────────────────────
st.markdown("""
<p style="font-size:0.78rem;color:#9CA3AF;font-weight:400;margin:0 0 1rem;line-height:1.6">
    ATS-optimized resume, cover letter &amp; fit analysis — under 60 seconds.
</p>
""", unsafe_allow_html=True)

# ── Input card (full width) ───────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("""
    <p style="font-size:0.72rem;font-weight:700;color:#1D2433;
         letter-spacing:0;margin:0.1rem 0 0.8rem">
        What role are you targeting today?
    </p>
    """, unsafe_allow_html=True)

    # 50/50 mode toggle
    if "input_mode_radio" not in st.session_state:
        st.session_state["input_mode_radio"] = "Job URL"
    cur_mode = st.session_state["input_mode_radio"]
    mc1, mc2 = st.columns(2)
    with mc1:
        if st.button("Job URL", use_container_width=True, key="mode_url",
                     type="primary" if cur_mode == "Job URL" else "secondary"):
            st.session_state["input_mode_radio"] = "Job URL"
            st.rerun()
    with mc2:
        if st.button("Paste JD", use_container_width=True, key="mode_jd",
                     type="primary" if cur_mode == "Paste JD" else "secondary"):
            st.session_state["input_mode_radio"] = "Paste JD"
            st.rerun()
    input_mode = cur_mode

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if input_mode == "Job URL":
        job_url = st.text_input(
            "Job posting URL",
            placeholder="https://jobs.lever.co/company/abc123",
            label_visibility="collapsed",
        )
        manual_active = False
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Job Title", placeholder="e.g. Software Engineer", key="m_title")
        with c2:
            st.text_input("Company", placeholder="e.g. Stripe", key="m_company")
        st.text_area(
            "Job Description",
            placeholder="Paste the full job description here...",
            height=180,
            key="manual_jd_text",
        )
        job_url = ""
        manual_active = True

    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
    analyze_btn = st.button("Analyze & Generate  ✨", type="primary", use_container_width=True)

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)


# ── Pipeline ──────────────────────────────────────────────────────────────────
def run_pipeline(url: str, resume: str, key: str, burl: str | None = None):
    progress = st.progress(0, text="Starting...")
    status = st.empty()
    try:
        status.info("Scraping job posting...")
        progress.progress(10, text="Scraping job posting...")
        try:
            job_data = scrape_job_posting(url)
        except RuntimeError as exc:
            st.session_state["input_mode_radio"] = "Paste JD"
            st.session_state["scrape_error"] = str(exc)
            progress.empty(); status.empty()
            return

        st.session_state["job_data"] = job_data
        progress.progress(25, text="Scraped.")

        status.info("Checking sponsorship signals...")
        sponsorship = check_sponsorship(job_data["description"])
        st.session_state["sponsorship"] = sponsorship
        progress.progress(35)

        if sponsorship["status"] == "negative":
            st.session_state["skip_reason"] = (
                f"⛔ **Skipped:** {sponsorship['label']} — no resume generated."
            )
            progress.empty(); status.empty(); return

        status.info("Scoring your fit with Claude...")
        progress.progress(45, text="Scoring fit...")
        fit = score_fit(resume, job_data["description"], job_data["title"], job_data["company"], key, burl)
        st.session_state["fit"] = fit
        progress.progress(65)

        if fit.get("fit_score", 0) < 50 or "weak fit" in fit.get("recommendation", "").lower():
            st.session_state["skip_reason"] = (
                f"⚠️ **Low fit ({fit.get('fit_score',0)}/100):** "
                f"{fit.get('recommendation','Weak fit')} — not worth applying."
            )
            progress.empty(); status.empty(); return

        status.info("Tailoring resume with Claude...")
        progress.progress(70, text="Tailoring...")
        tailored = tailor_resume(resume, job_data["description"], job_data["title"], job_data["company"], key, burl)
        st.session_state["tailored"] = tailored
        progress.progress(88)

        status.info("Generating PDF...")
        progress.progress(92, text="Building PDF...")
        try:
            pdf_path, pdf_bytes = generate_pdf(tailored, job_data["company"])
            st.session_state["pdf_path"] = pdf_path
            st.session_state["pdf_bytes"] = pdf_bytes
        except RuntimeError as exc:
            st.session_state["pdf_error"] = str(exc)

        progress.progress(100, text="Done!")
        status.success("Done!")
    except RuntimeError as exc:
        progress.empty()
        status.error(f"Error: {exc}")
        st.session_state["pipeline_error"] = str(exc)
    finally:
        progress.empty(); status.empty()


# ── Trigger ───────────────────────────────────────────────────────────────────
if analyze_btn:
    if not api_key:
        st.error("Enter your Anthropic API key in Settings.")
    elif not master_resume_text or not master_resume_text.strip():
        st.error("Upload your resume in Settings first.")
    else:
        url_text    = job_url.strip()
        manual_text = st.session_state.get("manual_jd_text", "").strip()

        if not url_text and not manual_text:
            st.error("Enter a job URL or paste a job description.")
        else:
            for k in ["job_data", "sponsorship", "fit", "tailored", "pdf_path", "pdf_bytes",
                      "scrape_error", "pipeline_error", "pdf_error", "skip_reason",
                      "cl_pdf_bytes", "cl_pdf_path", "cl_error"]:
                st.session_state.pop(k, None)

            if manual_text and manual_active:
                st.session_state["job_data"] = {
                    "title":       st.session_state.get("m_title", "").strip(),
                    "company":     st.session_state.get("m_company", "").strip(),
                    "location":    "See posting",
                    "salary":      None,
                    "description": manual_text,
                    "sponsorship_hints": [],
                    "source":      "manual",
                }
                st.rerun()
            elif url_text:
                run_pipeline(url_text, master_resume_text, api_key, base_url)
                st.rerun()

# ── Manual fallback pipeline ──────────────────────────────────────────────────
if (
    "job_data" in st.session_state
    and "fit" not in st.session_state
    and "skip_reason" not in st.session_state
    and st.session_state.get("job_data", {}).get("source") == "manual"
    and api_key and master_resume_text
):
    jd = st.session_state["job_data"]
    progress = st.progress(30, text="Analyzing...")
    try:
        sp = check_sponsorship(jd["description"])
        st.session_state["sponsorship"] = sp
        progress.progress(38)
        if sp["status"] == "negative":
            st.session_state["skip_reason"] = f"⛔ **Skipped:** {sp['label']} — no resume generated."
            progress.empty(); st.rerun()

        fit = score_fit(master_resume_text, jd["description"], jd["title"], jd["company"], api_key, base_url)
        st.session_state["fit"] = fit
        progress.progress(65)
        if fit.get("fit_score", 0) < 50 or "weak fit" in fit.get("recommendation", "").lower():
            st.session_state["skip_reason"] = (
                f"⚠️ **Low fit ({fit.get('fit_score',0)}/100):** "
                f"{fit.get('recommendation','Weak fit')} — not worth applying."
            )
            progress.empty(); st.rerun()

        tailored = tailor_resume(master_resume_text, jd["description"], jd["title"], jd["company"], api_key, base_url)
        st.session_state["tailored"] = tailored
        progress.progress(88)
        pdf_path, pdf_bytes = generate_pdf(tailored, jd["company"])
        st.session_state["pdf_path"] = pdf_path
        st.session_state["pdf_bytes"] = pdf_bytes
        progress.progress(100)
    except RuntimeError as exc:
        st.error(str(exc))
    finally:
        progress.empty()
    st.rerun()


# ── Errors / warnings ─────────────────────────────────────────────────────────
if st.session_state.get("skip_reason"):
    _, c, _ = st.columns([1, 3, 1])
    with c:
        st.warning(st.session_state["skip_reason"])

if st.session_state.get("scrape_error"):
    _, c, _ = st.columns([1, 3, 1])
    with c:
        st.warning(
            f"Could not scrape this URL — {st.session_state['scrape_error']}\n\n"
            "Switch to **Paste JD** mode above and paste the job description manually."
        )
    del st.session_state["scrape_error"]

if st.session_state.get("pipeline_error"):
    _, c, _ = st.columns([1, 3, 1])
    with c:
        col_e, col_r = st.columns([4, 1])
        col_e.error(f"Something went wrong: {st.session_state['pipeline_error']}")
        if col_r.button("Retry"):
            for k in ["pipeline_error", "job_data", "sponsorship", "fit", "tailored", "pdf_path"]:
                st.session_state.pop(k, None)
            st.rerun()


# ── Results dashboard ─────────────────────────────────────────────────────────
if "job_data" in st.session_state and "fit" in st.session_state:
    jd         = st.session_state["job_data"]
    sponsorship = st.session_state.get("sponsorship", {})
    fit        = st.session_state.get("fit", {})
    tailored   = st.session_state.get("tailored", {})
    score      = fit.get("fit_score", 0)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Score cards ───────────────────────────────────────────────────────────
    strong = fit.get("strong_matches", [])
    gaps   = fit.get("gaps", [])
    total  = len(strong) + len(gaps)
    keyword_pct = round(len(strong) / total * 100) if total else 0
    exp_label = "Strong" if score >= 70 else "Moderate" if score >= 50 else "Developing"
    score_color = "#12B76A" if score >= 70 else "#F79009" if score >= 50 else "#F04438"

    st.markdown("""
    <p style="font-size:0.7rem;font-weight:700;letter-spacing:0.09em;
         text-transform:uppercase;color:#667085;margin-bottom:0.75rem">
        Analysis Results
    </p>""", unsafe_allow_html=True)

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("ATS Fit Score", f"{score}%",
               delta="Strong match" if score >= 70 else "Needs tailoring" if score >= 50 else "Weak fit")
    mc2.metric("Keyword Coverage", f"{keyword_pct}%",
               delta=f"{len(strong)} matched")
    mc3.metric("Skill Gaps", str(len(gaps)),
               delta="Low gaps" if len(gaps) <= 2 else "Review gaps",
               delta_color="normal" if len(gaps) <= 2 else "inverse")
    mc4.metric("Experience Match", exp_label)

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # ── Job context strip ─────────────────────────────────────────────────────
    role    = jd.get("title") or "—"
    company = jd.get("company") or "—"
    loc     = jd.get("location") or "—"
    sal     = jd.get("salary") or "Not listed"
    sp_color = {"green": "#12B76A", "red": "#F04438", "yellow": "#F79009"}.get(
        sponsorship.get("color", "yellow"), "#F79009"
    )
    sp_label = sponsorship.get("label", "Not mentioned")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;
         background:white;border:1px solid #E5E7EB;border-radius:16px;
         padding:0.9rem 1.25rem;margin-bottom:1.5rem">
        <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.07em;color:#9CA3AF">Role</span>
            <span style="font-size:0.875rem;font-weight:600;color:#1D2433">{role}</span>
        </div>
        <span style="color:#E5E7EB">|</span>
        <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.07em;color:#9CA3AF">Company</span>
            <span style="font-size:0.875rem;font-weight:600;color:#1D2433">{company}</span>
        </div>
        <span style="color:#E5E7EB">|</span>
        <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.07em;color:#9CA3AF">Location</span>
            <span style="font-size:0.875rem;color:#374151">{loc}</span>
        </div>
        <span style="color:#E5E7EB">|</span>
        <div style="display:flex;align-items:center;gap:6px">
            <span style="font-size:0.7rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.07em;color:#9CA3AF">Salary</span>
            <span style="font-size:0.875rem;color:#374151">{sal}</span>
        </div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:6px;
             background:{sp_color}18;border:1px solid {sp_color}40;border-radius:99px;
             padding:4px 12px">
            <div style="width:7px;height:7px;border-radius:50%;
                 background:{sp_color};flex-shrink:0"></div>
            <span style="font-size:0.78rem;font-weight:600;color:{sp_color}">{sp_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_resume, tab_cl, tab_analysis = st.tabs(["📄  Resume", "✉️  Cover Letter", "📊  Analysis"])

    # ── Resume tab ────────────────────────────────────────────────────────────
    with tab_resume:
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        pdf_bytes = st.session_state.get("pdf_bytes")
        pdf_path  = st.session_state.get("pdf_path")

        if pdf_bytes or tailored:
            dl1, dl2, _ = st.columns([1, 1, 2])
            if pdf_bytes:
                dl1.download_button(
                    "⬇  Download PDF",
                    data=pdf_bytes,
                    file_name=Path(pdf_path).name if pdf_path else "resume.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            if tailored:
                dl2.download_button(
                    "⬇  Plain Text",
                    data=resume_to_text(tailored).encode("utf-8"),
                    file_name="resume.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

        if st.session_state.get("pdf_error"):
            st.warning(f"PDF generation failed: {st.session_state['pdf_error']}")

        if tailored:
            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            with st.expander("Preview resume text"):
                st.text(resume_to_text(tailored))

    # ── Cover letter tab ──────────────────────────────────────────────────────
    with tab_cl:
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        cl_pdf_bytes = st.session_state.get("cl_pdf_bytes")

        if cl_pdf_bytes:
            cl1, _ = st.columns([1, 3])
            cl1.download_button(
                "⬇  Download Cover Letter",
                data=cl_pdf_bytes,
                file_name=Path(st.session_state.get("cl_pdf_path", "cover_letter.pdf")).name,
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        else:
            st.markdown("""
            <p style="font-size:0.9rem;color:#667085;margin-bottom:1rem">
                Generate a tailored cover letter in the same style as your resume.
            </p>""", unsafe_allow_html=True)
            gen_cl1, _ = st.columns([1, 3])
            with gen_cl1:
                gen_cl_btn = st.button("✉  Generate Cover Letter", type="primary", use_container_width=True)
            if gen_cl_btn:
                with st.spinner("Writing cover letter with Claude..."):
                    try:
                        cl_data = generate_cover_letter(
                            master_resume=master_resume_text,
                            job_description=jd["description"],
                            job_title=jd["title"],
                            company=jd["company"],
                            api_key=api_key,
                            base_url=base_url,
                        )
                        contact_line = tailored.get("contact", "") if tailored else ""
                        cl_path, cl_bytes = generate_cover_letter_pdf(
                            cl_data=cl_data,
                            contact_line=contact_line,
                            company=jd["company"],
                            job_title=jd["title"],
                        )
                        st.session_state["cl_pdf_bytes"] = cl_bytes
                        st.session_state["cl_pdf_path"] = cl_path
                        st.session_state.pop("cl_error", None)
                    except RuntimeError as exc:
                        st.session_state["cl_error"] = str(exc)
                st.rerun()

        if st.session_state.get("cl_error"):
            st.warning(f"Cover letter error: {st.session_state['cl_error']}")

    # ── Analysis tab ──────────────────────────────────────────────────────────
    with tab_analysis:
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

        rec = fit.get("recommendation", "")
        summary = fit.get("summary", "")

        st.markdown(f"""
        <div style="background:white;border:1px solid #E5E7EB;border-radius:18px;
             padding:1.25rem 1.5rem;margin-bottom:1.25rem">
            <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.08em;
                 text-transform:uppercase;color:#9CA3AF;margin-bottom:0.4rem">Recommendation</div>
            <div style="font-size:1rem;font-weight:700;color:{score_color};margin-bottom:0.5rem">{rec}</div>
            <div style="font-size:0.875rem;color:#667085;line-height:1.6">{summary}</div>
        </div>
        """, unsafe_allow_html=True)

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown("""
            <p style="font-size:0.72rem;font-weight:700;letter-spacing:0.07em;
                 text-transform:uppercase;color:#12B76A;margin-bottom:0.5rem">
                ✅  Strong Matches
            </p>""", unsafe_allow_html=True)
            for item in fit.get("strong_matches", []):
                st.markdown(f"<p style='font-size:0.875rem;color:#374151;margin:0.2rem 0'>• {item}</p>",
                            unsafe_allow_html=True)

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

            st.markdown("""
            <p style="font-size:0.72rem;font-weight:700;letter-spacing:0.07em;
                 text-transform:uppercase;color:#F79009;margin-bottom:0.5rem">
                🟡  Partial Matches
            </p>""", unsafe_allow_html=True)
            for item in fit.get("weak_matches", []):
                st.markdown(f"<p style='font-size:0.875rem;color:#374151;margin:0.2rem 0'>• {item}</p>",
                            unsafe_allow_html=True)

        with col_r:
            st.markdown("""
            <p style="font-size:0.72rem;font-weight:700;letter-spacing:0.07em;
                 text-transform:uppercase;color:#F04438;margin-bottom:0.5rem">
                ❌  Skill Gaps
            </p>""", unsafe_allow_html=True)
            for item in fit.get("gaps", []):
                st.markdown(f"<p style='font-size:0.875rem;color:#374151;margin:0.2rem 0'>• {item}</p>",
                            unsafe_allow_html=True)

            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

            st.markdown("""
            <p style="font-size:0.72rem;font-weight:700;letter-spacing:0.07em;
                 text-transform:uppercase;color:#2E90FA;margin-bottom:0.5rem">
                ⭐  Nice-to-Haves
            </p>""", unsafe_allow_html=True)
            for item in fit.get("nice_to_haves", []):
                st.markdown(f"<p style='font-size:0.875rem;color:#374151;margin:0.2rem 0'>• {item}</p>",
                            unsafe_allow_html=True)

        if sponsorship.get("matches"):
            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            with st.expander("Sponsorship — exact text found in posting"):
                for match in sponsorship["matches"]:
                    st.markdown(f'> *"...{match}..."*')
