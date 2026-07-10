"""
Unit tests for the pure (non-API) logic.

Run with:  python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzer import check_sponsorship, keyword_coverage
from claude_client import describe_api_error
from pdf_generator import _safe_filename, _format_bullet
from tailor import _abbreviate_months_in_resume, audit_skills, detect_role_focus


class TestSponsorship(unittest.TestCase):
    def test_positive(self):
        res = check_sponsorship("We offer visa sponsorship for exceptional candidates.")
        self.assertEqual(res["status"], "positive")

    def test_negative_explicit(self):
        res = check_sponsorship("This role is not eligible for visa sponsorship.")
        self.assertEqual(res["status"], "negative")

    def test_negative_now_or_future(self):
        res = check_sponsorship(
            "Applicants must not require sponsorship for employment visa status now or in the future."
        )
        self.assertEqual(res["status"], "negative")

    def test_negative_clearance(self):
        res = check_sponsorship("Must hold an active Secret clearance.")
        self.assertEqual(res["status"], "negative")

    def test_neutral(self):
        res = check_sponsorship("We are looking for a great engineer to join our team.")
        self.assertEqual(res["status"], "neutral")


class TestKeywordCoverage(unittest.TestCase):
    def test_counts_matches_case_insensitive(self):
        cov = keyword_coverage(["React", "SQL Server", "Kubernetes"],
                               "Built dashboards in react backed by sql server.")
        self.assertEqual(cov["matched"], ["React", "SQL Server"])
        self.assertEqual(cov["missing"], ["Kubernetes"])
        self.assertEqual(cov["pct"], 67)

    def test_empty_keywords(self):
        cov = keyword_coverage([], "anything")
        self.assertEqual(cov["pct"], 0)


class TestAuditSkills(unittest.TestCase):
    MASTER = "Experience with C#, ASP.NET Core, React, SQL Server and Azure DevOps."

    def test_keeps_real_skills(self):
        tailored = {"skills": [{"category": "Backend", "items": "C#, ASP.NET Core"}]}
        cleaned, removed = audit_skills(tailored, self.MASTER)
        self.assertEqual(removed, [])
        self.assertEqual(cleaned["skills"][0]["items"], "C#, ASP.NET Core")

    def test_removes_fabricated_skills(self):
        tailored = {"skills": [{"category": "Backend", "items": "C#, Kubernetes, Terraform"}]}
        cleaned, removed = audit_skills(tailored, self.MASTER)
        self.assertIn("Kubernetes", removed)
        self.assertIn("Terraform", removed)
        self.assertEqual(cleaned["skills"][0]["items"], "C#")

    def test_drops_group_when_everything_fabricated(self):
        tailored = {"skills": [{"category": "Cloud", "items": "GCP, Cloudflare Workers"}]}
        cleaned, removed = audit_skills(tailored, self.MASTER)
        self.assertEqual(cleaned["skills"], [])
        self.assertEqual(len(removed), 2)


class TestRoleFocus(unittest.TestCase):
    def test_healthcare_detected(self):
        jd = "FHIR HL7 integration with Epic EHR for clinical workflows. " * 3
        self.assertIn("HEALTHCARE", detect_role_focus(jd))

    def test_generic_fallback(self):
        self.assertIn("general software engineering", detect_role_focus("A job."))


class TestMonthAbbreviation(unittest.TestCase):
    def test_abbreviates_experience_and_education(self):
        data = {
            "experience": [{"dates": "January 2023 – September 2024"}],
            "education": [{"dates": "July 2016 – May 2024"}],
        }
        out = _abbreviate_months_in_resume(data)
        self.assertEqual(out["experience"][0]["dates"], "Jan 2023 – Sep 2024")
        self.assertEqual(out["education"][0]["dates"], "Jul 2016 – May 2024")


class TestDescribeApiError(unittest.TestCase):
    def test_plain_text_403_flagged_as_proxy_block(self):
        exc = SimpleNamespace(status_code=403, body="Your request was blocked.")
        msg = describe_api_error(exc, "claude-sonnet-4-5", "https://proxy.example.com")
        self.assertIn("proxy or firewall", msg)
        self.assertNotIn("MASTER RESUME", msg)

    def test_401_hints_at_key(self):
        exc = SimpleNamespace(status_code=401, body={"type": "error"})
        msg = describe_api_error(exc, "claude-sonnet-4-5", None)
        self.assertIn("API key", msg)

    def test_404_hints_at_model(self):
        exc = SimpleNamespace(status_code=404, body={"type": "error"})
        msg = describe_api_error(exc, "claude-x", None)
        self.assertIn("claude-x", msg)


class TestPdfHelpers(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(_safe_filename("Workday, Inc."), "Workday__Inc_")

    def test_format_bullet_bolds_labels_and_metrics(self):
        out = _format_bullet("**Dashboard:** Cut alerts by 60% for 200+ users")
        self.assertIn("<b>Dashboard:</b>", out)
        self.assertIn("<b>60%</b>", out)
        self.assertIn("<b>200+</b>", out)


if __name__ == "__main__":
    unittest.main()
