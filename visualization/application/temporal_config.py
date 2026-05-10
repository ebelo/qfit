DEFAULT_TEMPORAL_MODE_LABEL = "Disabled"
UTC_TEMPORAL_MODE_LABEL = "UTC time"
TEMPORAL_MODE_LABELS = [DEFAULT_TEMPORAL_MODE_LABEL]


def temporal_mode_labels():
    return list(TEMPORAL_MODE_LABELS)


def normalize_temporal_mode(mode_label):
    _ = mode_label
    return DEFAULT_TEMPORAL_MODE_LABEL


def is_temporal_mode_enabled(mode_label):
    _ = mode_label
    return False


def build_temporal_plan(layer_key, available_fields, mode_label):
    _ = (layer_key, available_fields, mode_label)
    return None


def describe_temporal_configuration(plans, mode_label):
    _ = (plans, mode_label)
    return ""
