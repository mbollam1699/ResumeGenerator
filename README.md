# ResumeAgent

A Streamlit app that analyzes job postings, scores your fit, and generates tailored ATS-optimized PDF resumes using the Anthropic Claude API.

## Features

- Scrapes any job posting URL (LinkedIn, Greenhouse, Lever, Workday, company pages)
- Detects sponsorship signals automatically
- Scores your fit 0–100 with honest breakdown (strong matches, gaps, nice-to-haves)
- Rewrites your resume to mirror job description keywords for ATS optimization
- Generates a clean, ATS-safe PDF — no tables, no columns, no graphics
- Manual fallback if a URL can't be scraped

## Setup

### 1. Get an Anthropic API Key

Sign up at [console.anthropic.com](https://console.anthropic.com), create an API key, and copy it.

### 2. Clone and install

```bash
git clone <your-repo-url>
cd resume_agent
python -m venv .venv

# Mac/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 3. Configure your API key

```bash
cp .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY
```

Or just enter it in the app sidebar (it won't be saved to disk).

### 4. Fill in your master resume

Edit `master_resume.txt` — follow the template comments. The more detail you add, the better the tailoring.

### 5. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. Enter your Anthropic API key in the sidebar (or set it in `.env`)
2. Upload your master resume (or edit `master_resume.txt`)
3. Paste a job posting URL in the main area
4. Click **Analyze & Generate**
5. Review the fit score, sponsorship signal, and tailored resume
6. Download the PDF

## Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (make sure `.env` is in `.gitignore`)
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → point to your repo + `app.py`
3. In **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "your_key_here"
   ```
4. Deploy — Streamlit Cloud will install requirements automatically
5. Note: Playwright may not work on Streamlit Cloud. If scraping fails, the app will fall back to a manual paste text area.

## Notes

- Claude model used: `claude-sonnet-4-5`
- PDFs are saved to `output/` locally; on Streamlit Cloud they're generated in-memory and served as downloads
- The app never modifies your master resume; it only reads it
