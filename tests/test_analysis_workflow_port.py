import unittest

from tests import _path  # noqa: F401

from qfit.analysis.application.analysis_controller import AnalysisController
from qfit.analysis.application.analysis_controller_provider import build_analysis_controller
from qfit.analysis.application.analysis_workflow_port import AnalysisWorkflowPort


class TestAnalysisWorkflowPort(unittest.TestCase):
    def test_analysis_controller_implements_workflow_port(self):
        self.assertIsInstance(AnalysisController(), AnalysisWorkflowPort)

    def test_provider_returns_workflow_port(self):
        self.assertIsInstance(build_analysis_controller(), AnalysisWorkflowPort)


if __name__ == "__main__":
    unittest.main()
