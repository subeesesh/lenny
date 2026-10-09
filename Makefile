.PHONY: up down ingest test eval

up:
	docker compose up -d --build

down:
	docker compose down

ingest:
	docker compose exec api python -m app.ingest

test:
	docker compose exec api pytest

eval:
	python eval/run_eval.py
