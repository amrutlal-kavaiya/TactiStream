SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev test e2e lint contracts smoke sim-hero

help:
	@echo "Targets: install dev test e2e lint contracts smoke sim-hero"

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
	cd $(BACKEND) && uv run pytest tests/contract -q
	cd $(FRONTEND) && npm run contracts:gen
	git diff --exit-code -- $(FRONTEND)/src/contracts/generated.ts

smoke:
	cd $(BACKEND) && uv run tactistream-smoke foundry
	cd $(BACKEND) && uv run tactistream-smoke eventhubs

sim-hero:
	cd $(BACKEND) && uv run tactistream-sim generate --scenario space_creation --seed 42 --variant A --split dev --out ../data/generated/hero --force
