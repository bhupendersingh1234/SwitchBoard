dashboard:
	generate-dashboard -o deploy/grafana/switchboard.json deploy/grafana/switchboard.dashboard.py

demo:
	@echo "=== Eval accuracy (routing/quality.py against the hand-labeled dataset) ==="
	python -m switchboard.evals.run
	@echo
	@echo "=== Cascade cost tradeoff (simulated traffic) ==="
	python bench/cascade_cost_demo.py