from pathlib import Path

from tests import _path  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill_text(skill_name: str) -> str:
    return (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")


def _assert_skill_frontmatter(text: str, skill_name: str) -> None:
    lines = text.splitlines()

    assert lines[0] == "---"
    assert lines[1] == f"name: {skill_name}"
    assert lines[2].startswith("description: ")
    assert lines[3] == "---"


def test_qt_workflow_ux_skill_has_required_metadata():
    text = _skill_text("qt-workflow-ux")

    _assert_skill_frontmatter(text, "qt-workflow-ux")


def test_qt_workflow_ux_skill_keeps_core_contract():
    text = _skill_text("qt-workflow-ux")

    assert "Navigation" in text
    assert "Action" in text
    assert "Status" in text
    assert "At most one primary action per section" in text
    assert "Do not use `QPushButton`, `QToolButton`, or button-like chrome" in text


def test_qt_ui_enforcement_skill_has_required_metadata():
    text = _skill_text("qt-ui-enforcement")

    _assert_skill_frontmatter(text, "qt-ui-enforcement")
    assert "strict PR review or audit gate" in text.splitlines()[2]


def test_qt_ui_enforcement_skill_keeps_review_gates():
    text = _skill_text("qt-ui-enforcement")

    assert "Core classification rule" in text
    assert "Navigation" in text
    assert "Action" in text
    assert "Status" in text
    assert "Input" in text
    assert "more than one primary button" in text
    assert "destructive action separated" in text
    assert "Request changes" in text
