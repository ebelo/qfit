from __future__ import annotations


class AtlasCoverComposer:
    """Dedicated seam for atlas cover-page composition."""

    def build_layout(
        self,
        atlas_layer,
        *,
        project=None,
        map_layers=None,
        cover_data=None,
    ):
        from .export_task import build_cover_layout

        return build_cover_layout(
            atlas_layer,
            project=project,
            map_layers=map_layers,
            cover_data=cover_data,
        )
