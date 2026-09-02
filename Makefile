PYTHON ?= python3

.PHONY: demo minimax-demo evolution-demo research-loop-demo test audit golden-check golden-update verify

demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral demo --candidate examples/candidate.json --output demo/output

minimax-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral minimax --scenario examples/minimax_scenario.json --output demo/output/minimax

evolution-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral evolve --feedback examples/evolution/feedback_event.json --output demo/output/evolution

research-loop-demo:
	PYTHONPATH=src $(PYTHON) -B -m verispiral research-loop --scenario examples/research_spec/minimax_coevolution_scenario.json --output demo/output/research-specification

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

verify: test demo minimax-demo evolution-demo research-loop-demo audit
