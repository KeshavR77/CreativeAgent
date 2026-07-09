# AI Creative Agency Platform — root Makefile
# Repo root: /Users/chetanraghavan/Desktop/Projects/CreativeAgent
# Conventions: backend venv at backend/.venv (uv), frontend in frontend/ (npm).

.PHONY: setup dev-backend dev-frontend test e2e fmt

# Create backend venv + install (uv), then install frontend deps.
# Idempotent from a clean checkout.
setup:
	uv venv backend/.venv --python 3.12
	uv pip install --python backend/.venv -e "backend[dev]"
	cd frontend && npm install

# Run the FastAPI backend with autoreload from the backend venv.
# Port 8000 is reserved for a locally-tunneled Conceptial server (see
# CONCEPTIAL_BASE_URL in .env.example) — the backend runs on 8080 instead.
dev-backend:
	PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --port 8080

# Run the Vite dev server for the frontend.
dev-frontend:
	cd frontend && npm run dev

# Run backend pytest THEN frontend vitest. The whole target fails if either
# suite fails: each recipe line runs in its own shell and a non-zero exit
# halts make (non-zero exit is NOT swallowed).
test:
	backend/.venv/bin/python -m pytest backend/tests -q
	cd frontend && npm run test

# Golden-path end-to-end on mocks (image lanes enabled). Exits 0/1.
e2e:
	backend/.venv/bin/python backend/scripts/e2e_golden.py

# Best-effort formatters. Never fails if a formatter is absent — each
# invocation is guarded with `command -v` and the whole target is prefixed `-`.
fmt:
	-command -v ruff  >/dev/null 2>&1 && ruff format backend || true
	-command -v black >/dev/null 2>&1 && black backend       || true
	-cd frontend && (command -v npx >/dev/null 2>&1 && npx --no-install prettier --write "src/**/*.{ts,tsx,css}" 2>/dev/null || true)
