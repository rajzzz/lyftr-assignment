.PHONY: up down logs test

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	python3 -m venv venv
	. venv/bin/activate && \
	pip install -r requirements.txt && \
	pip install -r requirements-dev.txt && \
	pytest
