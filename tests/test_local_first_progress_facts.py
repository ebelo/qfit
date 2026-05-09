import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from tests import _path  # noqa: F401

from qfit.ui.application.dock_runtime_state import DockRuntimeState
from qfit.ui.application.local_first_progress_facts import (
    LocalFirstProgressFacts,
    build_current_local_first_progress_facts,
    current_local_first_activity_style_preset,
    current_local_first_atlas_output_path,
    current_local_first_background_facts,
    current_local_first_connection_configured,
    current_local_first_last_sync_date,
    current_local_first_visual_temporal_mode,
    runtime_state_with_local_first_output_path,
)
from qfit.visualization.application import DEFAULT_TEMPORAL_MODE_LABEL


class _FakeCheckBox:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class _FakeComboBox:
    def __init__(self, text):
        self._text = text

    def currentText(self):
        return self._text


class _FakeLineEdit:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _FailingComboBox:
    def currentText(self):
        raise RuntimeError("deleted widget")


class _FailingLineEdit:
    def text(self):
        raise RuntimeError("deleted widget")


class _FakeLayer:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


@dataclass(frozen=True)
class _FakeRuntimeState:
    output_path: str | None = None


class TestLocalFirstProgressFacts(unittest.TestCase):
    def test_current_progress_facts_assemble_live_local_first_state(self):
        dock = SimpleNamespace(
            runtime_state=DockRuntimeState(output_path="stored.gpkg"),
            outputPathLineEdit=_FakeLineEdit(" selected.gpkg "),
            atlasPdfPathLineEdit=_FakeLineEdit("draft.pdf"),
            backgroundMapCheckBox=_FakeCheckBox(False),
            backgroundPresetComboBox=_FakeComboBox("Outdoors"),
            stylePresetComboBox=_FakeComboBox(" Simple lines "),
            settings={"last_sync_date": " 2026-05-09 "},
            clientIdLineEdit=_FakeLineEdit("client-id"),
            clientSecretLineEdit=_FakeLineEdit("client-secret"),
            refreshTokenLineEdit=_FakeLineEdit("refresh-token"),
            _atlas_export_completed=True,
            _atlas_export_output_path="exported.pdf",
            _atlas_export_task_output_path=None,
            _widget_text=lambda name: getattr(dock, name).text(),
        )

        facts = build_current_local_first_progress_facts(dock)

        self.assertTrue(facts.connection_configured)
        self.assertEqual(facts.output_name, "selected.gpkg")
        self.assertTrue(facts.atlas_exported)
        self.assertEqual(facts.atlas_output_name, "exported.pdf")
        self.assertFalse(facts.background_enabled)
        self.assertEqual(facts.activity_style_preset, "Simple lines")
        self.assertIsInstance(facts, LocalFirstProgressFacts)
        self.assertEqual(facts.last_sync_date, "2026-05-09")

    def test_connection_configured_requires_visible_credential_text(self):
        configured_dock = SimpleNamespace(
            clientIdLineEdit=_FakeLineEdit(" client-id "),
            clientSecretLineEdit=_FakeLineEdit(" client-secret "),
            refreshTokenLineEdit=_FakeLineEdit(" refresh-token "),
        )
        missing_token_dock = SimpleNamespace(
            clientIdLineEdit=_FakeLineEdit("client-id"),
            clientSecretLineEdit=_FakeLineEdit("client-secret"),
            refreshTokenLineEdit=_FakeLineEdit("   "),
        )

        self.assertTrue(current_local_first_connection_configured(configured_dock))
        self.assertFalse(current_local_first_connection_configured(missing_token_dock))

    def test_connection_configured_handles_deleted_backing_widgets(self):
        dock = SimpleNamespace(
            clientIdLineEdit=_FakeLineEdit("client-id"),
            clientSecretLineEdit=_FailingLineEdit(),
            refreshTokenLineEdit=_FakeLineEdit("refresh-token"),
        )

        self.assertFalse(current_local_first_connection_configured(dock))

    def test_activity_style_preset_reads_trimmed_combo_text(self):
        dock = SimpleNamespace(stylePresetComboBox=_FakeComboBox(" Simple lines "))

        self.assertEqual(
            current_local_first_activity_style_preset(dock),
            "Simple lines",
        )

    def test_activity_style_preset_handles_missing_or_deleted_combo(self):
        self.assertIsNone(current_local_first_activity_style_preset(SimpleNamespace()))
        self.assertIsNone(
            current_local_first_activity_style_preset(
                SimpleNamespace(stylePresetComboBox=_FailingComboBox())
            )
        )

    def test_background_facts_report_disabled_basemap(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(False),
            backgroundPresetComboBox=_FakeComboBox("Outdoors"),
        )
        runtime_state = SimpleNamespace(background_layer=None)

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (False, False, None),
        )

    def test_background_facts_prefer_loaded_layer_over_pending_ui(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(False),
            backgroundPresetComboBox=_FakeComboBox("Outdoors"),
        )
        runtime_state = SimpleNamespace(background_layer=_FakeLayer("Satellite"))

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (True, True, "Satellite"),
        )

    def test_background_facts_report_enabled_basemap_name(self):
        dock = SimpleNamespace(
            backgroundMapCheckBox=_FakeCheckBox(True),
            backgroundPresetComboBox=_FakeComboBox(" Satellite "),
        )
        runtime_state = SimpleNamespace(background_layer=None)

        self.assertEqual(
            current_local_first_background_facts(dock, runtime_state),
            (True, False, "Satellite"),
        )

    def test_atlas_output_path_uses_visible_path_before_export(self):
        runtime_state = SimpleNamespace(atlas_export_task=None)

        self.assertEqual(
            current_local_first_atlas_output_path(
                runtime_state=runtime_state,
                atlas_pdf_path="draft.pdf",
                atlas_exported=False,
                completed_output_path="completed.pdf",
            ),
            "draft.pdf",
        )

    def test_atlas_output_path_prefers_completed_path_after_export(self):
        runtime_state = SimpleNamespace(atlas_export_task=None)

        self.assertEqual(
            current_local_first_atlas_output_path(
                runtime_state=runtime_state,
                atlas_pdf_path="draft.pdf",
                atlas_exported=True,
                completed_output_path="completed.pdf",
            ),
            "completed.pdf",
        )

    def test_atlas_output_path_freezes_task_path_during_export(self):
        runtime_state = SimpleNamespace(atlas_export_task=object())

        self.assertEqual(
            current_local_first_atlas_output_path(
                runtime_state=runtime_state,
                atlas_pdf_path="changed.pdf",
                atlas_exported=True,
                completed_output_path="completed.pdf",
                task_output_path="running.pdf",
            ),
            "running.pdf",
        )

    def test_atlas_output_path_falls_back_to_visible_path_for_running_legacy_task(self):
        runtime_state = SimpleNamespace(atlas_export_task=object())

        self.assertEqual(
            current_local_first_atlas_output_path(
                runtime_state=runtime_state,
                atlas_pdf_path="changed.pdf",
                atlas_exported=True,
                completed_output_path="completed.pdf",
            ),
            "changed.pdf",
        )

    def test_last_sync_date_reads_trimmed_settings_value(self):
        settings = {"last_sync_date": " 2026-05-09 "}

        self.assertEqual(current_local_first_last_sync_date(settings), "2026-05-09")

    def test_last_sync_date_ignores_missing_or_non_string_settings_value(self):
        self.assertIsNone(current_local_first_last_sync_date(object()))
        self.assertIsNone(current_local_first_last_sync_date({"last_sync_date": None}))
        self.assertIsNone(current_local_first_last_sync_date({"last_sync_date": "   "}))

    def test_runtime_state_with_output_path_preserves_matching_or_blank_path(self):
        runtime_state = _FakeRuntimeState(output_path="stored.gpkg")

        self.assertIs(
            runtime_state_with_local_first_output_path(runtime_state, "stored.gpkg"),
            runtime_state,
        )
        self.assertIs(
            runtime_state_with_local_first_output_path(runtime_state, "   "),
            runtime_state,
        )

    def test_runtime_state_with_output_path_reflects_visible_selection(self):
        runtime_state = _FakeRuntimeState(output_path="stored.gpkg")

        updated = runtime_state_with_local_first_output_path(
            runtime_state,
            " selected.gpkg ",
        )

        self.assertEqual(updated.output_path, "selected.gpkg")
        self.assertEqual(runtime_state.output_path, "stored.gpkg")
        self.assertIsNot(updated, runtime_state)

    def test_visual_temporal_mode_reads_trimmed_combo_text(self):
        dock = SimpleNamespace(temporalModeComboBox=_FakeComboBox(" Activity time "))

        self.assertEqual(
            current_local_first_visual_temporal_mode(dock),
            "Activity time",
        )

    def test_visual_temporal_mode_falls_back_to_default_for_missing_blank_or_deleted_combo(self):
        self.assertEqual(
            current_local_first_visual_temporal_mode(SimpleNamespace()),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )
        self.assertEqual(
            current_local_first_visual_temporal_mode(
                SimpleNamespace(temporalModeComboBox=_FakeComboBox("   "))
            ),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )
        self.assertEqual(
            current_local_first_visual_temporal_mode(
                SimpleNamespace(temporalModeComboBox=_FailingComboBox())
            ),
            DEFAULT_TEMPORAL_MODE_LABEL,
        )


if __name__ == "__main__":
    unittest.main()
