import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "portfolio-handoff.md"


def test_handoff_relative_links_exist():
    text = DOC.read_text()
    targets = re.findall(r"\]\(([^)\s]+)\)", text)
    rel = [t.split("#")[0] for t in targets if not re.match(r"[a-z]+:", t)]
    assert rel, "expected relative links"
    for t in rel:
        assert (DOC.parent / t).exists(), t


def test_readme_links_handoff():
    assert "docs/portfolio-handoff.md" in (ROOT / "README.md").read_text()
