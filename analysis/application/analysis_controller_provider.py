from .analysis_workflow_port import AnalysisWorkflowPort


def build_analysis_controller() -> AnalysisWorkflowPort:
    from .analysis_controller import AnalysisController

    return AnalysisController()
