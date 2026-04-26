from __future__ import annotations

from pathlib import Path

from qfit.ui.tokens import COLOR_MUTED, COLOR_SEPARATOR, pill_tone_palette

from ._qt_compat import import_qt_module

_qtwidgets = import_qt_module(
    "qgis.PyQt.QtWidgets",
    "PyQt5.QtWidgets",
    (
        "QHBoxLayout",
        "QLabel",
        "QWidget",
    ),
)

QHBoxLayout = _qtwidgets.QHBoxLayout
QLabel = _qtwidgets.QLabel
QWidget = _qtwidgets.QWidget


class FooterStatusBar(QWidget):
    """Compact persistent status footer for the #609 wizard shell.

    The widget exposes the explicit pill/path API from the wizard spec while
    retaining a tiny ``set_status_text`` compatibility seam for the existing
    placeholder shell composition. That lets the dock keep using render-neutral
    summary text until the final production swap wires live counts and paths.
    """

    def __init__(self, parent=None, *, footer_text: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("qfitWizardFooterBar")
        self.setFixedHeight(28)
        self._summary_text = footer_text
        self._path_label_owned_by_status = True
        self.strava_pill = _make_footer_pill(
            "● Strava",
            "muted",
            object_name="qfitWizardFooterStravaPill",
            parent=self,
        )
        self.activity_pill = _make_footer_pill(
            "— activities",
            "muted",
            object_name="qfitWizardFooterActivityPill",
            parent=self,
        )
        self.layer_pill = _make_footer_pill(
            "0 layers",
            "muted",
            object_name="qfitWizardFooterLayerPill",
            parent=self,
        )
        self.path_label = QLabel("", self)
        self.path_label.setObjectName("qfitWizardFooterPath")
        self.path_label.setStyleSheet(
            "QLabel#qfitWizardFooterPath { "
            f"color: {COLOR_MUTED}; "
            "font-family: monospace; "
            "font-size: 10.5pt; "
            "}"
        )
        self._layout = self._build_layout()
        self.set_status_text(footer_text)
        self.setStyleSheet(
            "QWidget#qfitWizardFooterBar { "
            f"border-top: 1px solid {COLOR_SEPARATOR}; "
            "padding: 4px 10px; "
            "background: #f7f7f7; "
            "}"
        )

    def set_status_text(self, text: str) -> None:
        """Store compatibility footer text and expose it as a tooltip."""

        self._summary_text = text
        if hasattr(self, "setToolTip"):
            self.setToolTip(text)
        if self._path_label_owned_by_status:
            self.path_label.setText(text)

    def text(self) -> str:
        """Return the compatibility footer summary text."""

        return self._summary_text

    def set_strava(self, connected: bool) -> None:
        """Update the Strava connection pill."""

        self.strava_pill.setText("● Strava")
        _set_footer_pill_tone(
            self.strava_pill,
            "ok" if connected else "danger",
            object_name="qfitWizardFooterStravaPill",
        )

    def set_activity_count(self, n: int | None) -> None:
        """Update the activity-count pill, using muted state for unknown counts."""

        if n is None:
            self.activity_pill.setText("— activities")
            tone = "muted"
        else:
            count = max(int(n), 0)
            noun = "activity" if count == 1 else "activities"
            self.activity_pill.setText(f"{count} {noun}")
            tone = "info" if count else "muted"
        _set_footer_pill_tone(
            self.activity_pill,
            tone,
            object_name="qfitWizardFooterActivityPill",
        )

    def set_layer_count(self, m: int) -> None:
        """Update the qfit layer-count pill."""

        count = max(int(m), 0)
        noun = "layer" if count == 1 else "layers"
        self.layer_pill.setText(f"{count} {noun}")
        _set_footer_pill_tone(
            self.layer_pill,
            "neutral" if count else "muted",
            object_name="qfitWizardFooterLayerPill",
        )

    def set_gpkg_path(self, path: str | None) -> None:
        """Display only the GeoPackage basename while keeping the full path in a tooltip."""

        self._path_label_owned_by_status = False
        if not path:
            self.path_label.setText("qfit.gpkg")
            self.path_label.setToolTip("")
            return
        self.path_label.setText(Path(path).name)
        self.path_label.setToolTip(path)

    def outer_layout(self):
        """Expose the footer layout for adapter wiring and pure tests."""

        return self._layout

    def _build_layout(self):
        layout = QHBoxLayout(self)
        if hasattr(layout, "setObjectName"):
            layout.setObjectName("qfitWizardFooterLayout")
        layout.setContentsMargins(4, 4, 10, 4)
        layout.setSpacing(6)
        layout.addWidget(self.strava_pill)
        layout.addWidget(self.activity_pill)
        layout.addWidget(self.layer_pill)
        if hasattr(layout, "addStretch"):
            layout.addStretch(1)
        layout.addWidget(self.path_label)
        return layout


def _make_footer_pill(text: str, tone: str, *, object_name: str, parent=None):
    label = QLabel(text, parent)
    _set_footer_pill_tone(label, tone, object_name=object_name)
    if hasattr(label, "setMinimumHeight"):
        label.setMinimumHeight(18)
    return label


def _set_footer_pill_tone(widget, tone: str, *, object_name: str) -> None:
    background, foreground = pill_tone_palette(tone)
    widget.setObjectName(object_name)
    widget.setProperty("tone", tone)
    widget.setStyleSheet(
        f"QLabel#{object_name} {{ "
        f"background: {background}; "
        f"color: {foreground}; "
        "border: 0; "
        "border-radius: 8px; "
        "padding: 1px 6px; "
        "font-size: 10.5pt; "
        "font-weight: 600; "
        "}"
    )


__all__ = ["FooterStatusBar"]
