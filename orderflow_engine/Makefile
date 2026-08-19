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

# Parts cleanup — DRY-RUN (default, deletes nothing): make parts-cleanup DAY=2026-07-15
# To actually delete: set parts_cleanup.enabled=true in config.yaml, then: make parts-cleanup-apply DAY=...
parts-cleanup:
	docker compose exec recorder python -m recorder.parts_cleanup data/$(DAY)
parts-cleanup-apply:
	docker compose exec recorder python -m recorder.parts_cleanup data/$(DAY) --apply

# Auto-evening analysis pipeline — one-shot, SEPARATE 2G-capped container (NOT the
# recorder's cgroup). Runs the full chain + sends the Daily Pulse. --date defaults to
# today IST. Optionally: make evening-pipeline DATE=2026-07-16
evening-pipeline:
	@BR=$$(git rev-parse --abbrev-ref HEAD 2>/dev/null); \
	  case "$$BR" in \
	    feat/orderflow-r7-alerts|feat/expiry-rollover-n5) ;; \
	    *) echo "ABORT evening-pipeline: host tree on '$$BR', expected feat/orderflow-r7-alerts or feat/expiry-rollover-n5 (2026-07-21 branch-guard, widened 2026-08-19)"; exit 1 ;; \
	  esac
	$(COMPOSE) --profile manual run --rm evening_pipeline \
		python -m recorder.evening_pipeline $(if $(DATE),--date $(DATE),)
# HOST CRON (install on the host; runs ~15:50 IST — host clock is UTC, so 10:20 UTC Mon-Fri):
#   20 10 * * 1-5 cd /home/ubuntu/trading-bridge/orderflow_engine && \
#     make evening-pipeline >> /home/ubuntu/oe_evening_pipeline.log 2>&1
# (or a systemd timer). It is deliberately host-triggered, NOT recorder-triggered, so no
# docker.sock is mounted in a live-money container.

venv:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	.venv/bin/pip install -q -r requirements.txt

test:
	$(PY) -m pytest tests/ -q
