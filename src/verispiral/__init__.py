"""VeriSpiral: user-governed research-specification control primitives."""

from .evolution import EvolutionRunResult, run_evolution_feedback
from .pipeline import RunResult, run_demo
from .research_spec import ResearchSpecRunResult, run_research_specification_loop

__all__ = [
    "EvolutionRunResult",
    "RunResult",
    "ResearchSpecRunResult",
    "run_demo",
    "run_evolution_feedback",
    "run_research_specification_loop",
    "__version__",
]

__version__ = "0.3.0"
