# orderflow_engine / recorder — operator shortcuts
# Usage: make <target>
.PHONY: help build up down logs verify test venv fmt-check

COMPOSE := docker compose
PY := .venv/bin/python

help:
	@echo "Targets:"
	@echo "  build   - build the recorder docker image"
	@echo "  up      - start the recorder (detached)"
	@echo "  down    - stop the recorder"
	@echo "  logs    - follow recorder logs"
	@echo "  verify  - run session verification for today (in-container)"
	@echo "  test    - run the unit test suite (local .venv)"
	@echo "  venv    - create local .venv and install deps for tests"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d
	@echo "recorder started. Follow logs with: make logs"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200 recorder

# Verify today's session (runs inside the container so it sees the data volume).
verify:
	$(COMPOSE) exec recorder python verify_session.py

# Verify a specific day on the host (needs local .venv): make verify-day DAY=2026-07-09
verify-day:
	$(PY) verify_session.py data/$(DAY)

# Re-run S3 backup for a specific day on demand: make backup-day DAY=2026-07-09
backup-day:
	$(PY) -m recorder.s3_backup data/$(DAY)

venv:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	.venv/bin/pip install -q -r requirements.txt

test:
	$(PY) -m pytest tests/ -q
