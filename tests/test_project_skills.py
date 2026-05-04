from pathlib import Path

from tests import _path  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill_text(skill_name: str) -> str:
    return (REPO_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")


def test_qt_workflow_ux_skill_has_required_metadata():
    text = _skill_text("qt-workflow-ux")

    assert text.startswith("---\n")
    assert "\n---\n" in text
    assert "name: qt-workflow-ux" in text
    assert "description:" in text


def test_qt_workflow_ux_skill_keeps_core_contract():
    text = _skill_text("qt-workflow-ux")

    assert "Navigation" in text
    assert "Action" in text
    assert "Status" in text
    assert "At most one primary action per section" in text
    assert "Do not use `QPushButton`, `QToolButton`, or button-like chrome" in text
