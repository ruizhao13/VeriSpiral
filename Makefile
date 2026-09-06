PYTHON ?= python3
.DEFAULT_GOAL := workflow

.PHONY: workflow
workflow:
	PYTHONPATH=src $(PYTHON) -B -m verispiral case --help

# Only the two generated public workflow directories may be replaced. Generation
# finishes in a fresh directory first; ordinary workflow CLI outputs stay immutable.
define REGENERATE_PUBLIC_WORKFLOW
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from verispiral.research_workflow import run_workflow_demo
target = Path(sys.argv[1])
if target not in (Path("demo/output/workflow"), Path("examples/expected/workflow")):
    raise ValueError("only declared public workflow outputs may be regenerated")
if target.resolve() != Path.cwd() / target:
    raise ValueError("generated workflow output must not traverse symlinks")
target.parent.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(prefix=".workflow-stage-", dir=target.parent) as temporary:
    staged, previous = Path(temporary) / "workflow", Path(temporary) / "previous"
    run_workflow_demo(staged)
    if target.exists():
        target.rename(previous)
    try:
        staged.rename(target)
    except OSError:
        if previous.exists():
            previous.rename(target)
        raise
print("Regenerated public workflow:", target / "demo_summary.json")
endef
export REGENERATE_PUBLIC_WORKFLOW

.PHONY: demo minimax-demo evolution-demo research-loop-demo diagnosis-demo path-trial workflow-demo test audit golden-check golden-update verify

demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral demo --candidate examples/candidate.json --output demo/output

minimax-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral minimax --scenario examples/minimax_scenario.json --output demo/output/minimax

evolution-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral evolve --feedback examples/evolution/feedback_event.json --output demo/output/evolution

research-loop-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral research-loop --scenario examples/research_spec/minimax_coevolution_scenario.json --output demo/output/research-specification

diagnosis-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral diagnose --output demo/output/diagnosis

path-trial:
	PYTHONPATH=src $(PYTHON) -B -m verispiral path-trial --output demo/output/path-trial

workflow-demo:
	PYTHONPATH=src $(PYTHON) -B -c "$$REGENERATE_PUBLIC_WORKFLOW" demo/output/workflow

test:
	PYTHONPATH=src $(PYTHON) -B -m unittest discover -s tests -v

audit:
	PYTHONPATH=src $(PYTHON) -B -m verispiral audit .

golden-check:
	PYTHONPATH=src $(PYTHON) -B -m unittest discover -s tests -p 'test_*golden*.py' -v

golden-update:
	PYTHONPATH=src $(PYTHON) -B -m verispiral demo --candidate examples/candidate.json --output examples/expected
	PYTHONPATH=src $(PYTHON) -B -m verispiral minimax --scenario examples/minimax_scenario.json --output examples/expected/minimax
	PYTHONPATH=src $(PYTHON) -B -m verispiral evolve --feedback examples/evolution/feedback_event.json --output examples/expected/evolution
	PYTHONPATH=src $(PYTHON) -B -m verispiral research-loop --scenario examples/research_spec/minimax_coevolution_scenario.json --output examples/expected/research-specification
	PYTHONPATH=src $(PYTHON) -B -m verispiral diagnose --output examples/expected/diagnosis
	PYTHONPATH=src $(PYTHON) -B -m verispiral path-trial --output examples/expected/path-trial
	PYTHONPATH=src $(PYTHON) -B -c "$$REGENERATE_PUBLIC_WORKFLOW" examples/expected/workflow

verify: test demo minimax-demo evolution-demo research-loop-demo diagnosis-demo path-trial workflow-demo audit
