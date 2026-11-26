# Perintah harian backend KBR Pajak.
# Semua target dijalankan dari root repo (yang memuat backend/ dan ontology/).

PY ?= python3
PORT ?= 8000

.PHONY: help install install-dev api smoke test test-api docker-up docker-down docker-logs contract

help:  ## Tampilkan daftar perintah
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Pasang dependensi runtime
	$(PY) -m pip install -r backend/requirements.txt

install-dev:  ## Pasang dependensi runtime + testing
	$(PY) -m pip install -r backend/requirements-dev.txt

api:  ## Jalankan API (development, auto-reload)
	$(PY) -m uvicorn backend.main:app --host 0.0.0.0 --port $(PORT) --reload

smoke:  ## Verifikasi kontrak API tanpa server (CI)
	$(PY) scripts/smoke_test.py --in-process

test-api:  ## Tes FastAPI (11 tes, ~2 menit)
	$(PY) -m pytest tests/test_api.py -q

test:  ## Seluruh tes (167 tes, ~7 menit — HermiT)
	$(PY) -m pytest -q

contract:  ## Ekspor OpenAPI untuk tim frontend
	curl -fsS http://127.0.0.1:$(PORT)/api/openapi.json -o openapi.json && echo "openapi.json tersimpan"

docker-up:  ## Build & jalankan API (port 8000)
	docker compose up -d --build

docker-down:  ## Hentikan stack
	docker compose down

docker-logs:  ## Ikuti log API
	docker compose logs -f api
