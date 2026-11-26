# Deployment Backend KBR Pajak (API v1.1.0)

Panduan menaikkan API `backend/` ke staging/produksi, **sebelum** integrasi frontend.

---

## 1. Prasyarat

| Komponen | Versi teruji | Wajib? |
|---|---|---|
| Python | 3.13 (min 3.10) | ya |
| **Java JRE/JDK** | **OpenJDK 21** (17 juga cukup) | **ya** — HermiT via JVM |
| CPU | 2 vCPU per worker | ya |
| RAM | 2 GB per worker (rekomendasi 4 GB total) | ya |
| Disk | ± 30 MB artefak | ya |

> **Jangan pakai Pellet** bawaan `owlready2`: JAR-nya tidak kompatibel dengan JDK 21. Backend ini sudah memakai `sync_reasoner_hermit`.

---

## 2. Artefak Runtime yang Harus Ada

Backend **hanya** membaca berkas berikut (total ± 13 MB):

```text
backend/{__init__.py,engine.py,main.py}
ontology/kbr_pajak_reasoning.owl      537 KB   # HermiT (wajib)
ontology/rule_map.json                 75 KB   # /catalog
ontology/ontology_build_report.json            # /api/health & /api/scenarios
ontology/kbr_ter_pph21.ttl             42 KB   # TER PPh 21
ontology/kbr_kbli.ttl                 952 KB   # SKOS KBLI
ontology/kbr-perda-rates.ttl          1,2 MB   # 390 Pemda
knowledge_json/rules/kbr-data.ttl     9,9 MB   # /sparql/*
```

**Tidak diperlukan saat runtime:** `knowledge_json/{documents,perda,consolidated,...}` (± 490 MB), `sources/`, `tests/`, `notebooks/`. `.dockerignore` sudah mengecualikannya.

---

## 3. Environment Variable

| Variabel | Default | Fungsi |
|---|---|---|
| `KBR_PROJECT_ROOT` | direktori induk `backend/` | root yang memuat `ontology/` & `knowledge_json/` |
| `KBR_REASONING_OWL` | `<root>/ontology/kbr_pajak_reasoning.owl` | override path `.owl` |
| `KBR_RULE_MAP_JSON` | `<root>/ontology/rule_map.json` | override katalog |
| `KBR_TER_TTL` | `<root>/ontology/kbr_ter_pph21.ttl` | override TER |
| `KBR_KBLI_TTL` | `<root>/ontology/kbr_kbli.ttl` | override SKOS KBLI |
| `KBR_PERDA_TTL` | `<root>/ontology/kbr-perda-rates.ttl` | override Perda |
| `KBR_FULL_TTL` | `<root>/knowledge_json/rules/kbr-data.ttl` | override RDF 12.921 aturan |
| `KBR_CORS_ORIGINS` | `*` | origin FE, dipisah koma. **Wajib diubah di produksi** |
| `KBR_WORKERS` | `2` (Docker) | jumlah worker uvicorn |
| `KBR_API_PORT` / `KBR_EDGE_PORT` | `8000` / `8080` | port host (compose) |
| `KBR_MEMORY_LIMIT` | `4g` | batas memori container |

Salin `.env.example` → `.env` lalu sesuaikan.

---

## 4. Menjalankan Tanpa Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-keep-alive 75
```

Development (auto-reload): tambahkan `--reload`, gunakan `--workers 1`.

## 5. Menjalankan Dengan Docker

```bash
cp .env.example .env          # sunting KBR_CORS_ORIGINS
docker compose up -d --build                      # API di :8000
docker compose --profile reverse-proxy up -d      # + nginx di :8080
docker compose ps
docker compose logs -f api
```

Dockerfile memasang `openjdk-17-jre-headless`, membuat user non-root `kbr`, dan sudah punya `HEALTHCHECK`.

Reverse proxy (nginx) menaikkan `proxy_read_timeout` ke **120 s** — default 60 s terlalu mepet untuk `/api/reason` (rata-rata 5,5 s, maks 6,1 s).

---

## 6. Verifikasi Setelah Deploy (API v2)

Base path: **`/api`** (alias `/api/v1`). Swagger: `/api/docs`.

```bash
# 1. Kesiapan artefak
curl -s localhost:8000/api/health | jq
#    status=ok, swrl_rules=97, reasoning_classes=156,
#    reasoning_individuals=436, full_rules_exported=12921

# 2. Smoke test kontrak penuh (health, options, regions, kbli, perda, provenance, 7 kasus emas)
python3 scripts/smoke_test.py --base-url http://localhost:8000
```

Keduanya harus **exit 0**. Bila `503`: artefak `.owl`/`.ttl` tidak ditemukan → cek `KBR_PROJECT_ROOT`.

---

## 7. Kapasitas & Kinerja

- `/api/reason` **serial per worker** (`threading.Lock` pada `_reasoner_lock`): 1 worker ≈ 650 request/jam.
- 2 worker ≈ 1.300/jam, 4 worker ≈ 2.600/jam — ukur CPU & RAM sebelum menaikkan.
- Endpoint lookup (`/kbli`, `/perda`, `/catalog`) sangat murah; `/sparql/*` memuat TTL 9,9 MB ke memori pada akses pertama (lalu ter-cache).
- **Jangan** auto-retry `/api/reason` di klien; gunakan antrean manual bila perlu.

---

## 8. Checklist Keamanan

- [ ] `KBR_CORS_ORIGINS` diganti ke domain `yoeke-front` (bukan `*`).
- [ ] API ditempatkan di belakang gateway/API key bila dapat diakses publik.
- [ ] Rate limit di gateway (mis. 10–20 `/api/reason` per menit per IP).
- [ ] TLS dipasang di edge (nginx/load balancer).
- [ ] `.env` tidak di-commit; `sources/` & `__pycache__/` tetap di `.gitignore`.
- [ ] Healthcheck dipasang di orchestrator (compose `healthcheck` sudah aktif).

---

## 9. Runbook Singkat

| Gejala | Cek | Tindakan |
|---|---|---|
| `503` di `/api/reason` | file `.owl` ada? `KBR_PROJECT_ROOT` benar? | perbaiki path / redeploy artefak |
| `500` "Reasoning gagal" | log uvicorn; apakah input saling bertentangan (mis. `PT` + `isSubjekLuarNegeri`)? | perbaiki payload; cek `AllDisjoint` |
| `/api/reason` > 30 s | CPU jenuh / worker habis | tambah worker atau antrekan request |
| `/api/health` `degraded` | `reasoning_owl_exists=false` | artefak ontology tidak ter-copy |
| Memory naik terus | jumlah worker × graf RDF | turunkan `KBR_WORKERS`, naikkan limit |

---

## 10. Yang Belum Ada (di luar scope "sebelum integrasi")

- Autentikasi/otorisasi pengguna.
- Penyimpanan riwayat simulasi (tidak ada database; API stateless).
- Mock server `/api/reason` terpisah — FE memakai staging langsung (smoke test menjamin stabilitas).
