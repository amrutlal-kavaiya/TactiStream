SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev test e2e lint contracts smoke

help:
	@echo "Targets: install dev test e2e lint contracts smoke"

install:
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci
	cd $(FRONTEND) && npx playwright install chromium

dev:
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND) && uv run tactistream-api) & \
	(cd $(FRONTEND) && npm run dev) & \
	wait

test:
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && npm test -- --run

e2e:
	cd $(FRONTEND) && npm run e2e

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check . && uv run mypy src
	cd $(FRONTEND) && npm run lint && npm run typecheck

contracts:
	@echo "contracts: wired in T011"

smoke:
	cd $(BACKEND) && uv run tactistream-smoke foundry
	cd $(BACKEND) && uv run tactistream-smoke eventhubs
