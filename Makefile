SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev test e2e lint contracts smoke image image-smoke

help:
	@echo "Targets: install dev test e2e lint contracts smoke image image-smoke"

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

IMAGE ?= tactistream:local
SMOKE_CONTAINER := tactistream-image-smoke

image:
	docker build -t $(IMAGE) .

image-smoke:
	@docker rm -f $(SMOKE_CONTAINER) >/dev/null 2>&1 || true
	docker run -d --rm --name $(SMOKE_CONTAINER) -p 8000:8000 -e TACTISTREAM_BUS=memory $(IMAGE) >/dev/null
	@trap 'docker stop $(SMOKE_CONTAINER) >/dev/null 2>&1 || true' EXIT; \
	for i in $$(seq 1 60); do curl -fsS http://127.0.0.1:8000/healthz >/dev/null 2>&1 && break; sleep 0.5; done; \
	cd $(BACKEND) && uv run tactistream-smoke deployed --base-url http://127.0.0.1:8000 --allow-memory && \
	curl -fsS http://127.0.0.1:8000/ | grep -qi '<html' && echo "SPA index served"
