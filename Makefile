.PHONY: run test lint eval eval-full

run:
	PYTHONPATH=./.deps uvicorn app.main:app --reload --port 8001

test:
	PYTHONPATH=./.deps python -m pytest tests/ -q

eval:
	PYTHONPATH=./.deps python scripts/eval_benchmark.py --split test --models baseline,hf-zeroshot --styles direct

eval-full:
	PYTHONPATH=./.deps python scripts/eval_benchmark.py --split test --models baseline,hf-zeroshot --styles direct,literal,role
