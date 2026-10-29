# VisionFlow — convenience targets. Run `make help`.
BACKEND := backend
FRONTEND := frontend
export VF_DATABASE_URL ?= postgresql://visionflow:visionflow@127.0.0.1:5432/visionflow

.PHONY: help install db-init test api worker frontend-install frontend demo reset

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend Python deps
	pip install -r $(BACKEND)/requirements.txt

db-init: ## Create the Postgres schema
	cd $(BACKEND) && python -m visionflow.cli initdb

test: ## Run the FR test suite (needs Postgres up)
	cd $(BACKEND) && VF_SIM_DELAY_MS=0 python -m pytest

api: ## Run the API + in-process worker on :8000
	cd $(BACKEND) && python -m uvicorn visionflow.api.app:app --reload --port 8000

worker: ## Run a standalone worker (for real kill -9 recovery demos)
	cd $(BACKEND) && python -m visionflow.cli run-worker

frontend-install: ## Install frontend deps
	cd $(FRONTEND) && npm install

frontend: ## Run the Vite dev server on :5173 (proxies to :8000)
	cd $(FRONTEND) && npm run dev

reset: ## Wipe all runs/events
	cd $(BACKEND) && python -m visionflow.cli reset
