from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from ...visualization.application import LayerRefs


@dataclass(frozen=True)
class DockRuntimeLayers:
    activities: object = None
    starts: object = None
    points: object = None
    atlas: object = None
    background: object = None
    analysis: object = None

    def with_dataset(
        self,
        *,
        activities_layer=None,
        starts_layer=None,
        points_layer=None,
        atlas_layer=None,
    ) -> "DockRuntimeLayers":
        return replace(
            self,
            activities=activities_layer,
            starts=starts_layer,
            points=points_layer,
            atlas=atlas_layer,
        )

    def clear_dataset(self) -> "DockRuntimeLayers":
        return self.with_dataset()

    def with_background(self, layer) -> "DockRuntimeLayers":
        return replace(self, background=layer)

    def with_analysis(self, layer) -> "DockRuntimeLayers":
        return replace(self, analysis=layer)

    def clear_analysis(self) -> "DockRuntimeLayers":
        return self.with_analysis(None)

    def visual_refs(self) -> LayerRefs:
        return LayerRefs(
            activities=self.activities,
            starts=self.starts,
            points=self.points,
            atlas=self.atlas,
        )


@dataclass(frozen=True)
class DockRuntimeTasks:
    fetch: object = None
    store: object = None
    atlas_export: object = None

    def with_fetch(self, task) -> "DockRuntimeTasks":
        return replace(self, fetch=task)

    def with_store(self, task) -> "DockRuntimeTasks":
        return replace(self, store=task)

    def with_atlas_export(self, task) -> "DockRuntimeTasks":
        return replace(self, atlas_export=task)

    def clear_fetch(self) -> "DockRuntimeTasks":
        return self.with_fetch(None)

    def clear_store(self) -> "DockRuntimeTasks":
        return self.with_store(None)

    def clear_atlas_export(self) -> "DockRuntimeTasks":
        return self.with_atlas_export(None)


@dataclass(frozen=True)
class DockRuntimeState:
    activities: tuple[object, ...] = field(default_factory=tuple)
    output_path: str | None = None
    last_fetch_context: dict[str, Any] = field(default_factory=dict)
    layers: DockRuntimeLayers = field(default_factory=DockRuntimeLayers)
    tasks: DockRuntimeTasks = field(default_factory=DockRuntimeTasks)

    @property
    def activities_layer(self):
        return self.layers.activities

    @property
    def starts_layer(self):
        return self.layers.starts

    @property
    def points_layer(self):
        return self.layers.points

    @property
    def atlas_layer(self):
        return self.layers.atlas

    @property
    def background_layer(self):
        return self.layers.background

    @property
    def analysis_layer(self):
        return self.layers.analysis

    @property
    def fetch_task(self):
        return self.tasks.fetch

    @property
    def store_task(self):
        return self.tasks.store

    @property
    def atlas_export_task(self):
        return self.tasks.atlas_export

    def visual_layer_refs(self) -> LayerRefs:
        return self.layers.visual_refs()


class DockRuntimeStore:
    """Own the dock runtime snapshot and expose explicit workflow transitions."""

    def __init__(self, state: DockRuntimeState | None = None) -> None:
        self._state = state or DockRuntimeState()

    @property
    def state(self) -> DockRuntimeState:
        return self._state

    def _replace_state(self, **changes) -> DockRuntimeState:
        self._state = replace(self._state, **changes)
        return self._state

    def set_activities(self, activities: Iterable[object] | None) -> DockRuntimeState:
        return self._replace_state(activities=tuple(activities or ()))

    def set_output_path(self, output_path: str | None) -> DockRuntimeState:
        return self._replace_state(output_path=output_path)

    def set_last_fetch_context(self, last_fetch_context: dict[str, Any] | None) -> DockRuntimeState:
        return self._replace_state(last_fetch_context=dict(last_fetch_context or {}))

    def set_dataset_layers(
        self,
        *,
        activities_layer=None,
        starts_layer=None,
        points_layer=None,
        atlas_layer=None,
    ) -> DockRuntimeState:
        return self._replace_state(
            layers=self._state.layers.with_dataset(
                activities_layer=activities_layer,
                starts_layer=starts_layer,
                points_layer=points_layer,
                atlas_layer=atlas_layer,
            )
        )

    def set_background_layer(self, layer) -> DockRuntimeState:
        return self._replace_state(layers=self._state.layers.with_background(layer))

    def set_analysis_layer(self, layer) -> DockRuntimeState:
        return self._replace_state(layers=self._state.layers.with_analysis(layer))

    def clear_analysis_layer(self) -> DockRuntimeState:
        return self._replace_state(layers=self._state.layers.clear_analysis())

    def set_fetch_task(self, task) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.with_fetch(task))

    def clear_fetch(self) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.clear_fetch())

    def set_store_task(self, task) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.with_store(task))

    def clear_store(self) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.clear_store())

    def set_atlas_export_task(self, task) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.with_atlas_export(task))

    def clear_atlas_export(self) -> DockRuntimeState:
        return self._replace_state(tasks=self._state.tasks.clear_atlas_export())

    def begin_fetch(self, task) -> DockRuntimeState:
        return self.set_fetch_task(task)

    def finish_fetch(
        self,
        *,
        activities: Iterable[object] | None = None,
        metadata: dict[str, Any] | None = None,
        last_fetch_context: dict[str, Any] | None = None,
    ) -> DockRuntimeState:
        context = metadata if last_fetch_context is None else last_fetch_context
        next_state = replace(self._state, tasks=self._state.tasks.clear_fetch())
        if activities is not None:
            next_state = replace(next_state, activities=tuple(activities))
        if context is not None:
            next_state = replace(next_state, last_fetch_context=dict(context))
        self._state = next_state
        return self._state

    def begin_store(self, task) -> DockRuntimeState:
        return self.set_store_task(task)

    def finish_store(self, *, output_path: str | None = None) -> DockRuntimeState:
        next_state = replace(self._state, tasks=self._state.tasks.clear_store())
        if output_path is not None:
            next_state = replace(next_state, output_path=output_path)
        self._state = next_state
        return self._state

    def load_dataset(
        self,
        *,
        output_path: str | None,
        activities_layer=None,
        starts_layer=None,
        points_layer=None,
        atlas_layer=None,
    ) -> DockRuntimeState:
        return self._replace_state(
            output_path=output_path,
            layers=self._state.layers.with_dataset(
                activities_layer=activities_layer,
                starts_layer=starts_layer,
                points_layer=points_layer,
                atlas_layer=atlas_layer,
            ),
        )

    def apply_loaded_dataset(
        self,
        *,
        output_path: str | None,
        activities_layer=None,
        starts_layer=None,
        points_layer=None,
        atlas_layer=None,
    ) -> DockRuntimeState:
        return self.load_dataset(
            output_path=output_path,
            activities_layer=activities_layer,
            starts_layer=starts_layer,
            points_layer=points_layer,
            atlas_layer=atlas_layer,
        )

    def reset_loaded_dataset(self) -> DockRuntimeState:
        return self._replace_state(
            activities=(),
            output_path=None,
            last_fetch_context={},
            layers=self._state.layers.clear_dataset(),
        )

    def clear_loaded_dataset(self) -> DockRuntimeState:
        return self.reset_loaded_dataset()

    def begin_atlas_export(self, task) -> DockRuntimeState:
        return self.set_atlas_export_task(task)

    def finish_atlas_export(self) -> DockRuntimeState:
        return self.clear_atlas_export()


__all__ = [
    "DockRuntimeLayers",
    "DockRuntimeState",
    "DockRuntimeStore",
    "DockRuntimeTasks",
]
