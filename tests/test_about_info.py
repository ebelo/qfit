import os
import sys
import tempfile
import unittest
from types import ModuleType, SimpleNamespace

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

    def test_read_about_info_uses_default_plugin_metadata_path(self):
        info = read_about_info()

        self.assertEqual(info.name, "qfit")
        self.assertNotEqual(info.version, "unknown")
        self.assertEqual(info.author, "Emmanuel Belo")

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

    def test_build_about_html_escapes_metadata_values(self):
        info = AboutInfo(
            name='qfit <demo>',
            version='1.0 "beta"',
            author="Emmanuel & contributors",
            repository_url='https://github.com/ebelo/qfit?x="demo"',
            issues_url='https://github.com/ebelo/qfit/issues?tag=<bug>',
            discussions_url="https://github.com/ebelo/qfit/discussions?a=1&b=2",
            mastodon_url='https://mastodon.social/@ebelo?name="qfit"',
            x_url="https://x.com/Emmanuel_Belo?topic=qfit&kind=feedback",
            linkedin_url="https://ch.linkedin.com/in/emmanuelbelo?x=<profile>",
        )

        html = build_about_html(info)

        self.assertIn("qfit &lt;demo&gt;", html)
        self.assertIn("1.0 &quot;beta&quot;", html)
        self.assertIn("Emmanuel &amp; contributors", html)
        self.assertIn('href="https://github.com/ebelo/qfit?x=&quot;demo&quot;"', html)
        self.assertIn(
            'href="https://github.com/ebelo/qfit/issues?tag=&lt;bug&gt;"',
            html,
        )
        self.assertIn(
            'href="https://github.com/ebelo/qfit/discussions?a=1&amp;b=2"',
            html,
        )
        self.assertNotIn("<demo>", html)


class QfitAboutDockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._module_names = {
            "qgis",
            "qgis.PyQt",
            "qgis.PyQt.QtCore",
            "qgis.PyQt.QtWidgets",
            "qfit.ui.about_dock",
        }
        cls._saved_modules = {
            name: sys.modules.get(name) for name in cls._module_names
        }
        for name, module in cls._stub_modules().items():
            sys.modules[name] = module
        sys.modules.pop("qfit.ui.about_dock", None)

        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtWidgets import QLabel, QDockWidget
        from qfit.ui.about_dock import QfitAboutDock

        cls.QfitAboutDock = QfitAboutDock
        cls.QLabel = QLabel
        cls.QDockWidget = QDockWidget
        cls.Qt = Qt

    @classmethod
    def tearDownClass(cls):
        for name in cls._module_names:
            original = cls._saved_modules.get(name)
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    @staticmethod
    def _stub_modules():
        qgis = ModuleType("qgis")
        qgis_pyqt = ModuleType("qgis.PyQt")
        qgis_qtcore = ModuleType("qgis.PyQt.QtCore")
        qgis_qtcore.Qt = SimpleNamespace(
            TextBrowserInteraction=1,
            TextSelectableByMouse=2,
        )
        qgis_qtwidgets = ModuleType("qgis.PyQt.QtWidgets")

        class FakeWidget:
            def __init__(self, parent=None):
                self.parent = parent
                self._children = []
                if hasattr(parent, "_children"):
                    parent._children.append(self)

            def deleteLater(self):
                pass

        class FakeLabel(FakeWidget):
            def __init__(self, text="", parent=None):
                super().__init__(parent)
                self._text = text
                self._object_name = ""
                self._word_wrap = False
                self._open_external_links = False
                self._text_flags = 0

            def setObjectName(self, name):
                self._object_name = name

            def objectName(self):
                return self._object_name

            def setWordWrap(self, value):
                self._word_wrap = value

            def wordWrap(self):
                return self._word_wrap

            def setOpenExternalLinks(self, value):
                self._open_external_links = value

            def openExternalLinks(self):
                return self._open_external_links

            def setTextInteractionFlags(self, flags):
                self._text_flags = flags

            def textInteractionFlags(self):
                return self._text_flags

            def text(self):
                return self._text

        class FakeDockWidget(FakeWidget):
            DockWidgetClosable = 1
            DockWidgetMovable = 2
            DockWidgetFloatable = 4

            def __init__(self, title="", parent=None):
                super().__init__(parent)
                self._object_name = ""
                self._window_title = title
                self._features = 0
                self._minimum_width = 0
                self._widget = None

            def setObjectName(self, name):
                self._object_name = name

            def objectName(self):
                return self._object_name

            def setWindowTitle(self, title):
                self._window_title = title

            def windowTitle(self):
                return self._window_title

            def setFeatures(self, features):
                self._features = features

            def features(self):
                return self._features

            def setMinimumWidth(self, width):
                self._minimum_width = width

            def minimumWidth(self):
                return self._minimum_width

            def setWidget(self, widget):
                self._widget = widget

            def findChild(self, cls, object_name):
                stack = []
                if self._widget is not None:
                    stack.append(self._widget)
                while stack:
                    child = stack.pop()
                    if (
                        isinstance(child, cls)
                        and getattr(child, "objectName", lambda: None)() == object_name
                    ):
                        return child
                    stack.extend(getattr(child, "_children", []))
                return None

        class FakeVBoxLayout:
            def __init__(self, parent=None):
                self.parent = parent

            def addWidget(self, _widget):
                pass

            def addStretch(self, _stretch):
                pass

        qgis_qtwidgets.QDockWidget = FakeDockWidget
        qgis_qtwidgets.QLabel = FakeLabel
        qgis_qtwidgets.QVBoxLayout = FakeVBoxLayout
        qgis_qtwidgets.QWidget = FakeWidget

        return {
            "qgis": qgis,
            "qgis.PyQt": qgis_pyqt,
            "qgis.PyQt.QtCore": qgis_qtcore,
            "qgis.PyQt.QtWidgets": qgis_qtwidgets,
        }

    def test_about_dock_builds_floating_linkable_content(self):
        info = AboutInfo(
            name="qfit",
            version="0.51",
            author="Emmanuel Belo",
            repository_url="https://github.com/ebelo/qfit",
            issues_url="https://github.com/ebelo/qfit/issues",
            discussions_url="https://github.com/ebelo/qfit/discussions",
            mastodon_url="https://mastodon.social/@ebelo",
            x_url="https://x.com/Emmanuel_Belo",
            linkedin_url="https://ch.linkedin.com/in/emmanuelbelo",
        )

        dock = self.QfitAboutDock(info=info)
        self.addCleanup(dock.deleteLater)

        self.assertEqual(dock.objectName(), "qfitAboutDock")
        self.assertIn("qfit", dock.windowTitle())
        self.assertIn("About", dock.windowTitle())
        self.assertTrue(dock.features() & self.QDockWidget.DockWidgetClosable)
        self.assertTrue(dock.features() & self.QDockWidget.DockWidgetMovable)
        self.assertTrue(dock.features() & self.QDockWidget.DockWidgetFloatable)
        self.assertGreaterEqual(dock.minimumWidth(), 420)

        label = dock.findChild(self.QLabel, "qfitAboutContentLabel")
        self.assertIsNotNone(label)
        self.assertTrue(label.wordWrap())
        self.assertTrue(label.openExternalLinks())
        self.assertTrue(label.textInteractionFlags() & self.Qt.TextBrowserInteraction)
        self.assertTrue(label.textInteractionFlags() & self.Qt.TextSelectableByMouse)
        self.assertIn("Version:</b> 0.51", label.text())
        self.assertIn("https://github.com/ebelo/qfit/issues", label.text())
        self.assertIn("Enjoy using qfit", label.text())


if __name__ == "__main__":
    unittest.main()
