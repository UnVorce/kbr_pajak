# syntax=docker/dockerfile:1
# Image runtime KBR Pajak API (FastAPI + owlready2/HermiT + rdflib).
# Build context WAJIB root repo yang berisi: backend/, ontology/, knowledge_json/rules/kbr-data.ttl
#   docker build -f backend/Dockerfile -t kbr-pajak-api:1.1.0 .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KBR_PROJECT_ROOT=/app \
    KBR_WORKERS=2

# Java JRE wajib: owlready2 menjalankan reasoner HermiT lewat JVM.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY ontology/ ontology/
COPY knowledge_json/rules/kbr-data.ttl knowledge_json/rules/kbr-data.ttl

RUN useradd --create-home --uid 10001 kbr && chown -R kbr:kbr /app
USER kbr

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers ${KBR_WORKERS} --timeout-keep-alive 75"]
