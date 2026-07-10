"""
Candidate-specific configuration.

Everything personal that used to be hardcoded inside prompts lives here,
so the prompts stay generic and the tool works for any resume.
"""

# Full name -> abbreviation used on the generated resume.
SCHOOL_ABBREVIATIONS = {
    "Georgia State University": "GSU",
    "Jawaharlal Nehru Technological University Hyderabad": "JNTUH",
}


def school_abbreviation_rules() -> str:
    """Render the abbreviation mapping as a prompt-ready instruction line."""
    if not SCHOOL_ABBREVIATIONS:
        return "Use the university names as written in the master resume."
    pairs = ", ".join(f"{full} -> {abbr}" for full, abbr in SCHOOL_ABBREVIATIONS.items())
    return f"Abbreviate university names exactly as follows: {pairs}."
