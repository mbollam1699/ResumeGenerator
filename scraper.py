"""
Job posting scraper. Tries requests+BS4 first, falls back to Playwright for JS-heavy pages.
"""
import re
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 15


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _detect_sponsorship_hints(text: str) -> list[str]:
    keywords = [
        r"will sponsor", r"visa sponsorship", r"h[\-\s]?1[\-\s]?b",
        r"work authorization provided", r"sponsorship available",
        r"must be authorized", r"no sponsorship", r"citizens only",
        r"permanent residents only", r"us citizen", r"green card",
        r"authorized to work",
    ]
    found = []
    lower = text.lower()
    for kw in keywords:
        if re.search(kw, lower):
            found.append(kw)
    return found


def _parse_structured(soup: BeautifulSoup, url: str) -> dict:
    """Pull structured fields from known ATS platforms."""
    result = {}

    # LinkedIn
    if "linkedin.com" in url:
        title_el = soup.find("h1")
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        company_el = soup.find("a", {"class": re.compile(r"topcard__org")})
        if company_el:
            result["company"] = company_el.get_text(strip=True)

    # Greenhouse
    elif "greenhouse.io" in url or "boards.greenhouse" in url:
        title_el = soup.find("h1", {"class": re.compile(r"app-title|job-post-name", re.I)})
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        company_el = soup.find("div", {"class": re.compile(r"company-name", re.I)})
        if company_el:
            result["company"] = company_el.get_text(strip=True)

    # Lever
    elif "jobs.lever.co" in url:
        title_el = soup.find("h2")
        if title_el:
            result["title"] = title_el.get_text(strip=True)
        company_el = soup.find("a", {"class": re.compile(r"main-header-logo", re.I)})
        if company_el:
            result["company"] = company_el.get_text(strip=True)

    return result


def _scrape_with_requests(url: str) -> Optional[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc

    soup = BeautifulSoup(resp.text, "lxml")
    full_text = _extract_text(soup)

    if len(full_text) < 200:
        return None  # Likely a JS-rendered page — signal for Playwright fallback

    structured = _parse_structured(soup, url)

    # Generic fallbacks for title/company
    if "title" not in structured:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            structured["title"] = og_title["content"]
        elif soup.find("h1"):
            structured["title"] = soup.find("h1").get_text(strip=True)
        else:
            structured["title"] = "Unknown Role"

    if "company" not in structured:
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            structured["company"] = og_site["content"]
        else:
            structured["company"] = "Unknown Company"

    # Location
    location_el = soup.find(
        string=re.compile(r"(remote|hybrid|onsite|location|headquarters)", re.I)
    )
    structured["location"] = location_el.strip() if location_el else "See posting"

    # Salary — simple regex over full text
    salary_match = re.search(
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hour|hr))?",
        full_text, re.I
    )
    structured["salary"] = salary_match.group(0) if salary_match else None

    structured["description"] = full_text
    structured["sponsorship_hints"] = _detect_sponsorship_hints(full_text)
    structured["source"] = "requests"
    return structured


def _ensure_playwright_chromium():
    """Install Playwright's Chromium binary if not already present."""
    subprocess.run(
        ["playwright", "install", "chromium"],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _scrape_with_playwright(url: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    _ensure_playwright_chromium()

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(extra_http_headers=HEADERS)
            try:
                page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                time.sleep(3)  # Let JS hydrate
                html = page.content()
            except PWTimeout as exc:
                raise RuntimeError(f"Playwright timed out loading page: {exc}") from exc
            finally:
                browser.close()
    except RuntimeError:
        raise  # already a clean RuntimeError — let it propagate
    except Exception as exc:
        raise RuntimeError(
            f"Playwright could not start. Paste the job description manually instead. ({type(exc).__name__}: {exc})"
        ) from exc

    soup = BeautifulSoup(html, "lxml")
    full_text = _extract_text(soup)
    structured = _parse_structured(soup, url)

    if "title" not in structured:
        h1 = soup.find("h1")
        structured["title"] = h1.get_text(strip=True) if h1 else "Unknown Role"
    if "company" not in structured:
        og_site = soup.find("meta", property="og:site_name")
        structured["company"] = og_site["content"] if og_site else "Unknown Company"

    salary_match = re.search(
        r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*(?:yr|year|hour|hr))?",
        full_text, re.I
    )
    structured["salary"] = salary_match.group(0) if salary_match else None

    location_match = re.search(
        r"(?:location|based in|headquarters)[:\s]+([^\n|•]+)", full_text, re.I
    )
    structured["location"] = location_match.group(1).strip() if location_match else "See posting"

    structured["description"] = full_text
    structured["sponsorship_hints"] = _detect_sponsorship_hints(full_text)
    structured["source"] = "playwright"
    return structured


def scrape_job_posting(url: str) -> dict:
    """
    Scrape a job posting URL. Returns a dict with:
      title, company, location, salary, description, sponsorship_hints, source
    Raises RuntimeError with a user-facing message on failure.
    """
    try:
        result = _scrape_with_requests(url)
        if result is not None:
            return result
        # JS-rendered — fall through to Playwright
    except RuntimeError:
        pass  # Try Playwright next

    return _scrape_with_playwright(url)
