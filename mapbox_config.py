from __future__ import annotations

import json
from urllib.parse import quote, unquote
from urllib.request import urlopen


class MapboxConfigError(ValueError):
    """Raised when the configured Mapbox background settings are incomplete."""


BACKGROUND_LAYER_PREFIX = "qfit background"
DEFAULT_BACKGROUND_PRESET = "Outdoor"
DEFAULT_MAPBOX_TILE_SIZE = 512
DEFAULT_MAPBOX_RETINA = False
DEFAULT_MAPBOX_TILE_PIXEL_RATIO = 2

_BACKGROUND_PRESETS = {
    "Outdoor": {
        "style_owner": "mapbox",
        "style_id": "outdoors-v12",
        "description": "Mapbox Outdoors",
        "requires_custom_style": False,
    },
    "Light": {
        "style_owner": "mapbox",
        "style_id": "light-v11",
        "description": "Mapbox Light",
        "requires_custom_style": False,
    },
    "Satellite": {
        "style_owner": "mapbox",
        "style_id": "satellite-streets-v12",
        "description": "Mapbox Satellite Streets",
        "requires_custom_style": False,
    },
    "Winter (custom style)": {
        "style_owner": "",
        "style_id": "",
        "description": "Your own winter-themed Mapbox Studio style",
        "requires_custom_style": True,
    },
    "Custom": {
        "style_owner": "",
        "style_id": "",
        "description": "Any Mapbox Studio style owner/style_id",
        "requires_custom_style": True,
    },
}


def background_preset_names() -> list[str]:
    return list(_BACKGROUND_PRESETS.keys())


def get_background_preset(name: str | None) -> dict[str, object]:
    return _BACKGROUND_PRESETS.get(name or DEFAULT_BACKGROUND_PRESET, _BACKGROUND_PRESETS[DEFAULT_BACKGROUND_PRESET])


def preset_requires_custom_style(name: str | None) -> bool:
    preset = get_background_preset(name)
    return bool(preset["requires_custom_style"])


def preset_defaults(name: str | None) -> tuple[str, str]:
    preset = get_background_preset(name)
    return str(preset["style_owner"]), str(preset["style_id"])


def resolve_background_style(
    preset_name: str | None,
    style_owner: str = "",
    style_id: str = "",
) -> tuple[str, str]:
    preset = get_background_preset(preset_name)
    if not preset_requires_custom_style(preset_name):
        return preset_defaults(preset_name)

    owner = style_owner.strip()
    resolved_style_id = style_id.strip()
    if not owner or not resolved_style_id:
        raise MapboxConfigError(
            "Enter a Mapbox style owner and style ID for the selected background preset."
        )
    return owner, resolved_style_id


def build_mapbox_tiles_url(
    access_token: str,
    style_owner: str,
    style_id: str,
    *,
    tile_size: int = DEFAULT_MAPBOX_TILE_SIZE,
    retina: bool = DEFAULT_MAPBOX_RETINA,
) -> str:
    token = access_token.strip()
    owner = style_owner.strip()
    resolved_style_id = style_id.strip()

    if not token:
        raise MapboxConfigError("Enter a Mapbox access token to load the selected background map.")
    if not owner or not resolved_style_id:
        raise MapboxConfigError("Enter a Mapbox style owner and style ID first.")

    retina_suffix = "@2x" if retina else ""
    return (
        "https://api.mapbox.com/styles/v1/{owner}/{style_id}/tiles/{tile_size}/{{z}}/{{x}}/{{y}}{retina}"
        "?access_token={token}"
    ).format(
        owner=quote(owner, safe=""),
        style_id=quote(resolved_style_id, safe=""),
        tile_size=tile_size,
        retina=retina_suffix,
        token=quote(token, safe=""),
    )


TILE_MODE_RASTER = "Raster"
TILE_MODE_VECTOR = "Vector"
TILE_MODES = [TILE_MODE_RASTER, TILE_MODE_VECTOR]


def build_xyz_layer_uri(access_token: str, style_owner: str, style_id: str) -> str:
    url = build_mapbox_tiles_url(access_token, style_owner, style_id)
    return "type=xyz&url={url}&zmin=0&zmax=22&tilePixelRatio={tile_pixel_ratio}".format(
        url=quote(url, safe=":/?{}=%@"),
        tile_pixel_ratio=DEFAULT_MAPBOX_TILE_PIXEL_RATIO,
    )


def _validated_mapbox_style_parts(access_token: str, style_owner: str, style_id: str) -> tuple[str, str, str]:
    token = access_token.strip()
    owner = style_owner.strip()
    resolved_style_id = style_id.strip()

    if not token:
        raise MapboxConfigError("Enter a Mapbox access token to load the selected background map.")
    if not owner or not resolved_style_id:
        raise MapboxConfigError("Enter a Mapbox style owner and style ID first.")
    return token, owner, resolved_style_id


def fetch_mapbox_style_definition(
    access_token: str,
    style_owner: str,
    style_id: str,
) -> dict[str, object]:
    """Fetch and parse the Mapbox style JSON for a style."""
    style_url = build_mapbox_style_json_url(access_token, style_owner, style_id)
    with urlopen(style_url, timeout=20) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def extract_mapbox_vector_source_ids(style_definition: dict[str, object]) -> list[str]:
    """Extract vector tileset IDs from a Mapbox style definition.

    Supports sources declared like: {"url": "mapbox://tilesetA,tilesetB"}
    """
    sources = style_definition.get("sources") if isinstance(style_definition, dict) else None
    if not isinstance(sources, dict):
        raise MapboxConfigError("Mapbox style JSON does not declare any sources.")

    tileset_ids: list[str] = []
    for source in sources.values():
        if not isinstance(source, dict) or source.get("type") != "vector":
            continue
        url = str(source.get("url") or "").strip()
        if not url.startswith("mapbox://"):
            continue
        raw_ids = url.removeprefix("mapbox://")
        for tileset_id in raw_ids.split(","):
            normalized = tileset_id.strip()
            if normalized and normalized not in tileset_ids:
                tileset_ids.append(normalized)

    if not tileset_ids:
        raise MapboxConfigError("Mapbox style JSON does not expose a vector tileset source for QGIS.")
    return tileset_ids


def build_mapbox_vector_tiles_url(
    access_token: str,
    style_owner: str,
    style_id: str,
    *,
    tileset_ids: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Return the Mapbox vector tile endpoint URL for a given style/source."""
    token, owner, resolved_style_id = _validated_mapbox_style_parts(access_token, style_owner, style_id)

    if tileset_ids:
        joined_tilesets = ",".join(quote(tileset_id.strip(), safe=".,-_") for tileset_id in tileset_ids if tileset_id.strip())
    else:
        joined_tilesets = "{owner}.{style_id}".format(
            owner=quote(owner, safe=""),
            style_id=quote(resolved_style_id, safe=""),
        )

    return (
        "https://api.mapbox.com/v4/{tilesets}/{{z}}/{{x}}/{{y}}.mvt"
        "?access_token={token}"
    ).format(
        tilesets=joined_tilesets,
        token=quote(token, safe=""),
    )


def build_mapbox_style_json_url(
    access_token: str,
    style_owner: str,
    style_id: str,
) -> str:
    """Return the Mapbox style JSON URL for use with QGIS vector tile styling."""
    token, owner, resolved_style_id = _validated_mapbox_style_parts(access_token, style_owner, style_id)

    return (
        "https://api.mapbox.com/styles/v1/{owner}/{style_id}?access_token={token}"
    ).format(
        owner=quote(owner, safe=""),
        style_id=quote(resolved_style_id, safe=""),
        token=quote(token, safe=""),
    )


def build_vector_tile_layer_uri(
    access_token: str,
    style_owner: str,
    style_id: str,
    *,
    tileset_ids: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Return a QGIS-compatible vector tile layer URI for a Mapbox style."""
    tiles_url = build_mapbox_vector_tiles_url(
        access_token,
        style_owner,
        style_id,
        tileset_ids=tileset_ids,
    )
    style_url = build_mapbox_style_json_url(access_token, style_owner, style_id)
    return "type=xyz&url={url}&styleUrl={style_url}&zmin=0&zmax=22".format(
        url=quote(tiles_url, safe=":/?{}=%@,"),
        style_url=quote(style_url, safe=":/?{}=%@"),
    )


def build_background_layer_name(preset_name: str | None, style_owner: str, style_id: str) -> str:
    label = (preset_name or DEFAULT_BACKGROUND_PRESET).strip() or DEFAULT_BACKGROUND_PRESET
    if label == "Custom":
        if style_owner and style_id:
            return f"{BACKGROUND_LAYER_PREFIX} — {style_owner}/{style_id}"
        return BACKGROUND_LAYER_PREFIX
    return f"{BACKGROUND_LAYER_PREFIX} — {label}"
