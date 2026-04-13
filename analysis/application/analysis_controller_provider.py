from .analysis_workflow_port import AnalysisWorkflowPort


def build_analysis_workflow() -> AnalysisWorkflowPort:
    from .analysis_controller import AnalysisController

    return AnalysisController()
