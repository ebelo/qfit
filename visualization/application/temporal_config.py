from dataclasses import dataclass

DEFAULT_TEMPORAL_MODE_LABEL = "Local activity time"
UTC_TEMPORAL_MODE_LABEL = "UTC time"
TEMPORAL_MODE_LABELS = [DEFAULT_TEMPORAL_MODE_LABEL]


@dataclass(frozen=True)
class TemporalLayerPlan:
    layer_key: str
    field_name: str
    field_kind: str
    label: str

    @property
    def expression(self):
        return 'to_datetime("{field}")'.format(field=self.field_name)


_LAYER_CANDIDATES = {
    "activity_points": {
        DEFAULT_TEMPORAL_MODE_LABEL: ["point_timestamp_local", "point_timestamp_utc"],
        UTC_TEMPORAL_MODE_LABEL: ["point_timestamp_utc", "point_timestamp_local"],
    },
    "activity_tracks": {
        DEFAULT_TEMPORAL_MODE_LABEL: ["start_date_local", "start_date"],
        UTC_TEMPORAL_MODE_LABEL: ["start_date", "start_date_local"],
    },
    "activity_starts": {
        DEFAULT_TEMPORAL_MODE_LABEL: ["start_date_local", "start_date"],
        UTC_TEMPORAL_MODE_LABEL: ["start_date", "start_date_local"],
    },
}


def temporal_mode_labels():
    return list(TEMPORAL_MODE_LABELS)


def normalize_temporal_mode(mode_label):
    label = (mode_label or "").strip()
    if label == UTC_TEMPORAL_MODE_LABEL:
        return DEFAULT_TEMPORAL_MODE_LABEL
    return DEFAULT_TEMPORAL_MODE_LABEL


def is_temporal_mode_enabled(mode_label):
    return normalize_temporal_mode(mode_label) == DEFAULT_TEMPORAL_MODE_LABEL


def build_temporal_plan(layer_key, available_fields, mode_label):
    mode_label = normalize_temporal_mode(mode_label)

    field_names = {name for name in (available_fields or []) if name}
    candidates = _LAYER_CANDIDATES.get(layer_key, {}).get(mode_label, [])
    for field_name in candidates:
        if field_name in field_names:
            return TemporalLayerPlan(
                layer_key=layer_key,
                field_name=field_name,
                field_kind=_field_kind(field_name),
                label=_plan_label(layer_key, field_name),
            )
    return None


def describe_temporal_configuration(plans, mode_label):
    normalized_mode = normalize_temporal_mode(mode_label)
    active_plans = [plan for plan in (plans or []) if plan is not None]
    if not active_plans:
        return "Temporal playback uses {mode}, but no timestamp fields were available".format(
            mode=normalized_mode.lower()
        )
    labels = ", ".join(plan.label for plan in active_plans)
    return "Temporal playback wired for {labels}".format(labels=labels)


def _field_kind(field_name):
    return "local" if field_name.endswith("_local") else "utc"


def _plan_label(layer_key, field_name):
    field_kind = _field_kind(field_name).upper()
    if layer_key == "activity_points":
        return "activity points ({kind})".format(kind=field_kind)
    if layer_key == "activity_tracks":
        return "activity tracks ({kind})".format(kind=field_kind)
    if layer_key == "activity_starts":
        return "activity starts ({kind})".format(kind=field_kind)
    return "{layer} ({kind})".format(layer=layer_key.replace("_", " "), kind=field_kind)
