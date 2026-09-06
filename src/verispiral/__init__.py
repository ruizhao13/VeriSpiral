"""VeriSpiral: problem-first research with replaceable executable components."""

from .case_workflow import create_case, submit_design, audit_design, record_decision, execute_round, submit_diagnosis, inspect_case
from .evolution import EvolutionRunResult, run_evolution_feedback
from .pipeline import RunResult, run_demo
from .research_spec import ResearchSpecRunResult, run_research_specification_loop

__all__ = [
    "create_case",
    "submit_design",
    "audit_design",
    "record_decision",
    "execute_round",
    "submit_diagnosis",
    "inspect_case",
    "EvolutionRunResult",
    "RunResult",
    "ResearchSpecRunResult",
    "run_demo",
    "run_evolution_feedback",
    "run_research_specification_loop",
    "__version__",
]

__version__ = "0.3.0"
