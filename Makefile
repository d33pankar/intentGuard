.PHONY: run test lint

run:
	PYTHONPATH=./.deps uvicorn app.main:app --reload --port 8001

test:
	PYTHONPATH=./.deps python -m pytest tests/ -q
