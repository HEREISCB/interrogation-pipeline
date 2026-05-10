# Convenience wrapper for the install script + common dev tasks.
# `make install` works on macOS / Linux. Windows users: run `install.ps1` directly.

.PHONY: install backend-install frontend-install build run test lint clean

install:
	@bash ./install.sh

backend-install:
	cd backend && python3 -m venv .venv && \
	  .venv/bin/python -m pip install --upgrade pip setuptools wheel && \
	  .venv/bin/python -m pip install -e ".[dev]"

frontend-install:
	cd frontend && npm install

build:
	cd frontend && npm run build

run:
	cd backend && ./.venv/bin/python -m interrogation_pipeline

test:
	cd backend && ./.venv/bin/python -m pytest

lint:
	cd backend && ./.venv/bin/ruff check .

clean:
	rm -rf backend/.venv backend/data/state.db* backend/data/transcripts/* \
	       backend/interrogation_pipeline/static frontend/node_modules
	@echo "cleaned"
