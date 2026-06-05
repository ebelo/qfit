"""Project metadata and copy for the qfit About panel."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass


DEFAULT_PROJECT_NAME = "qfit"
DEFAULT_VERSION = "unknown"
DEFAULT_AUTHOR = "Emmanuel Belo"
DEFAULT_REPOSITORY_URL = "https://github.com/ebelo/qfit"
DEFAULT_ISSUES_URL = "https://github.com/ebelo/qfit/issues"
DEFAULT_DISCUSSIONS_URL = "https://github.com/ebelo/qfit/discussions"


@dataclass(frozen=True)
class AboutInfo:
    name: str
    version: str
    author: str
    repository_url: str
    issues_url: str
    discussions_url: str
    mastodon_url: str
    x_url: str
    linkedin_url: str


def _default_metadata_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "metadata.txt")


def read_about_info(metadata_path: str | None = None) -> AboutInfo:
    """Read About-panel metadata from the QGIS plugin metadata file."""

    metadata = configparser.ConfigParser()
    metadata.read(metadata_path or _default_metadata_path(), encoding="utf-8")
    general = metadata["general"] if metadata.has_section("general") else {}

    repository_url = general.get("repository", DEFAULT_REPOSITORY_URL).strip()
    return AboutInfo(
        name=general.get("name", DEFAULT_PROJECT_NAME).strip() or DEFAULT_PROJECT_NAME,
        version=general.get("version", DEFAULT_VERSION).strip() or DEFAULT_VERSION,
        author=general.get("author", DEFAULT_AUTHOR).strip() or DEFAULT_AUTHOR,
        repository_url=repository_url or DEFAULT_REPOSITORY_URL,
        issues_url=general.get("tracker", DEFAULT_ISSUES_URL).strip() or DEFAULT_ISSUES_URL,
        discussions_url=DEFAULT_DISCUSSIONS_URL,
        mastodon_url="https://mastodon.social/@ebelo",
        x_url="https://x.com/Emmanuel_Belo",
        linkedin_url="https://ch.linkedin.com/in/emmanuelbelo",
    )


def build_about_html(info: AboutInfo) -> str:
    """Return the rich-text body displayed by the About panel."""

    return f"""
<h2>{info.name}</h2>
<p><b>Version:</b> {info.version}<br>
<b>Author:</b> {info.author}</p>

<p>{info.name} is a QGIS plugin for exploring fitness activity data spatially, with a focus on
turning activity history into useful maps, analysis layers, and publishable outputs.</p>

<p>{info.name} is maintained by {info.author} and developed with the help of AI coding agents.
The project is open source and actively evolving. If you find a bug, miss a workflow, or have
an idea that would make {info.name} more useful, please open an issue or feature request on GitHub.</p>

<p><b>Project links:</b></p>

<ul>
  <li><a href="{info.repository_url}">Repository</a></li>
  <li><a href="{info.issues_url}">Issues and feature requests</a></li>
  <li><a href="{info.discussions_url}">Discussions</a></li>
</ul>

<p>I would also be happy to chat with {info.name} users to collect feedback, discuss the roadmap,
and validate where {info.name} provides the most value. You can reach me here:</p>

<ul>
  <li><a href="{info.mastodon_url}">Mastodon</a></li>
  <li><a href="{info.x_url}">X</a></li>
  <li><a href="{info.linkedin_url}">LinkedIn</a></li>
</ul>

<p>Enjoy using {info.name}, and please share what would make it more useful for you.</p>
""".strip()
