import os
import tempfile
import unittest

from tests import _path  # noqa: F401

from qfit.ui.about_info import (
    DEFAULT_DISCUSSIONS_URL,
    AboutInfo,
    build_about_html,
    read_about_info,
)


class AboutInfoTests(unittest.TestCase):
    def test_read_about_info_uses_plugin_metadata_and_contact_links(self):
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(
                "[general]\n"
                "name=qfit\n"
                "version=9.9\n"
                "author=Emmanuel Belo\n"
                "repository=https://github.com/ebelo/qfit\n"
                "tracker=https://github.com/ebelo/qfit/issues\n"
            )
            metadata_path = handle.name

        try:
            info = read_about_info(metadata_path)
        finally:
            os.unlink(metadata_path)

        self.assertEqual(info.name, "qfit")
        self.assertEqual(info.version, "9.9")
        self.assertEqual(info.author, "Emmanuel Belo")
        self.assertEqual(info.repository_url, "https://github.com/ebelo/qfit")
        self.assertEqual(info.issues_url, "https://github.com/ebelo/qfit/issues")
        self.assertEqual(info.discussions_url, DEFAULT_DISCUSSIONS_URL)
        self.assertEqual(info.mastodon_url, "https://mastodon.social/@ebelo")
        self.assertEqual(info.x_url, "https://x.com/Emmanuel_Belo")
        self.assertEqual(info.linkedin_url, "https://ch.linkedin.com/in/emmanuelbelo")

    def test_build_about_html_mentions_agentic_development_and_support_paths(self):
        info = AboutInfo(
            name="qfit",
            version="0.50",
            author="Emmanuel Belo",
            repository_url="https://github.com/ebelo/qfit",
            issues_url="https://github.com/ebelo/qfit/issues",
            discussions_url="https://github.com/ebelo/qfit/discussions",
            mastodon_url="https://mastodon.social/@ebelo",
            x_url="https://x.com/Emmanuel_Belo",
            linkedin_url="https://ch.linkedin.com/in/emmanuelbelo",
        )

        html = build_about_html(info)

        self.assertIn("Version:</b> 0.50", html)
        self.assertIn("useful maps, analysis layers, and publishable outputs", html)
        self.assertIn("AI coding agents", html)
        self.assertIn("open source and actively evolving", html)
        self.assertIn("Issues and feature requests", html)
        self.assertIn("collect feedback, discuss the roadmap", html)
        self.assertIn("provides the most value", html)
        self.assertIn(
            "Enjoy using qfit, and please share what would make it more useful for you.",
            html,
        )
        self.assertIn("https://github.com/ebelo/qfit/issues", html)
        self.assertIn("https://github.com/ebelo/qfit/discussions", html)
        self.assertIn("https://mastodon.social/@ebelo", html)
        self.assertIn("https://x.com/Emmanuel_Belo", html)
        self.assertIn("https://ch.linkedin.com/in/emmanuelbelo", html)


if __name__ == "__main__":
    unittest.main()
