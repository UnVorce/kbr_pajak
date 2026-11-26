# kbr_pajak — Korpus Hukum, Ontologi `SROIQ(D)`, Reasoning HermiT & Backend API KBR Perpajakan Indonesia

Sistem berbasis pengetahuan (*Knowledge-Based Reasoning*) untuk kewajiban, tarif, fasilitas, dan mitigasi risiko perpajakan Indonesia (**Fase 0–8 selesai — Gerbang G8 tercapai**).

> **Dokumentasi Lengkap:** baca [`docs/fase_8.md`](docs/fase_8.md) (arsitektur menyeluruh & alur kerja) dan [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) (kamus data korpus, `legal_rules.jsonl`, `156` kelas/`18` object props/`69` data props/`97` SWRL ontologi, & kontrak API).

---

## Ringkasan Sistem

```text
[Korpus Resmi BPK/JDIH/MK/MA/SetPP]
   ├── 165 regulasi pusat (97 active_for_rules) + 32 consolidated (UU CK & HPP)
   ├── 524 Perda PDRD (2023–2026, 390 Pemda unik) + 284 SetPP + 15 MK + 78 SEMA TUN
   └── 12.921 aturan atomik tervalidasi (legal_rules.jsonl, 9 domain pajak)
         │
         ├──► ontology/kbr_pajak_reasoning.owl (156 kelas SROIQ(D) · 97 SWRL · 436 individu)
         │       └─► Reasoner HermiT (World() terisolasi) + Kalkulator SPARQL BIND
         │
         ├──► ontology/kbr_ter_pph21.ttl (127 bracket TER) + kbr_kbli.ttl (1.453 KBLI SKOS: NPPN/TA/Pionir/Padat Karya)
         ├──► ontology/kbr-perda-rates.ttl (390 Pemda · 2.029 tarif lokal dari 524 Perda)
         └──► knowledge_json/rules/kbr-data.ttl (9,9 MB ekspor RDF penuh 12.921 aturan)
                 └─► Engine SPARQL lokal (rdflib)
                         │
                         ▼
               [backend/main.py — FastAPI + Uvicorn]
  GET /options · GET /kbli · GET /perda · POST /reason · GET /sparql/provenance
```

**Prinsip utama:** **0% logika pajak di-hardcode di Python.** Klasifikasi Badan (`19%` Tbk syarat lengkap, `22%`, `Pasal 31E 11%`, `BUT 20%`, Tax Holiday `6` tier), Orang Pribadi (`30` profesi `JenisPekerjaan`, `TER A/B/C`, bebas `≤ Rp500jt`, larangan PP 55 & `NPPN` Pekerja Bebas, `5` lapis Pasal 17 `5%–35%`), **PPh Final Pasal 4(2)** (`Sewa Tanah/Bangunan 10%`, `Bunga Deposito 20%` & DHE, `7` tarif `Jasa Konstruksi PP 9/2022`, `Pengalihan Tanah/Bangunan 2,5%/1%/0%` beserta pengecualiannya), PPN (`12%` Mewah vs `11%` Efektif), PPh 23, `5` Perda pilot, dan sanksi KUP dikerjakan oleh aksioma `OWL 2 SROIQ(D)` + `97` aturan SWRL lewat **HermiT**, dan setiap hasil selalu membawa jejak `rule_id`, `Pasal`, `source_quote`, serta referensi `PutusanMK`/`SEMA_TUN`.

---

## Quickstart Backend API (`backend/`)

Prasyarat: Python 3.10+, Java JRE/JDK (untuk HermiT), dan dependensi di `backend/requirements.txt`.

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- **Swagger UI interaktif:** `http://localhost:8000/docs`
- **Panduan & contoh `curl`:** lihat [`backend/README.md`](backend/README.md)

Base path: **`/api`** (alias `/api/v1`) · Swagger: `/api/docs` · OpenAPI: `/api/openapi.json`

| Endpoint | Fungsi |
|---|---|
| `GET /api/health` | Status `.owl`/`.ttl`, `ptkp_tiers`, `regions`, cache |
| `GET /api/options` | `wp_kinds`, `ptkp` (8), `zona_nppn`, `pekerjaan_jenis`, `jobs` (32), `final_income_objects` (13) |
| `GET /api/regions` | **390 Pemda** + zona NPPN + PBB-P2 + NJOPTKP + `jumlah_perda` (total 524 Perda) |
| `GET /api/kbli` & `/api/kbli/{kode}` | `1.453` KBLI SKOS (NPPN, Tax Allowance, Pionir, Padat Karya, `is_jasa_konstruksi`) |
| `GET /api/perda` & `/api/perda/{pemda_id}` | `390` Pemda · `2.107` item tarif dari `524` Perda |
| `POST /api/reason` | Payload PRD §9.3 (multi-stream, PTKP, PBB, PPh Final 4(2)) → inferensi HermiT + TER + **komparasi 3 skema** + **rekonsiliasi PPh 29** + provenance |
| `GET /api/catalog` | Peta `103` katalog → `rule_id` |
| `GET /api/scenarios` | `15` skenario bawaan |
| `GET /api/sparql/provenance` & `/api/sparql/stats` | `12.921` aturan |

**Dokumentasi backend:**
- **Kontrak beku untuk frontend** → [`docs/API_CONTRACT_v2.md`](docs/API_CONTRACT_v2.md) (payload PRD, enum, respons, 7 kasus emas, deviasi PRD)
- **Deployment (Docker/nginx/env/kapasitas/runbook)** → [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- **Verifikasi kontrak** → `python3 scripts/smoke_test.py --base-url http://localhost:8000` (atau `--in-process` untuk CI), **78 cek**

---

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology awal tim (referensi)
├── backend/                               # Service FastAPI (Fase 7)
│   ├── __init__.py
│   ├── engine.py                          # HermiT isolated World() + cache RDF SPARQL
│   ├── main.py                            # Router /api + handler error + CORS (env)
│   ├── contract_v2.py                     # Adaptor payload PRD §9.3 + respons v2
│   ├── advisory.py                        # Evaluasi RP-01..RP-10 + CBR tahap 1
│   ├── coretax.py                         # Playbook Coretax + pencarian KAP/KJS
│   ├── coretax_playbook.json              # 54 KAP/KJS + langkah (panduan DJP)
│   ├── risk_patterns.json                 # Katalog 10 pola risiko + dasar hukum
│   ├── cbr_index.json                     # Indeks 284 putusan (BM25)
│   ├── pp55_rules.json                    # rule_id PP 55 jo. PP 20/2026
│   ├── nppn_kelompok.json                 # Pemetaan eksplisit KBLI tanpa baris NPPN
│   ├── requirements.txt
│   ├── requirements-dev.txt               # pytest/ruff untuk CI
│   ├── Dockerfile                         # Python 3.12 + OpenJDK 17, non-root, HEALTHCHECK
│   └── README.md
├── docker-compose.yml                     # api (+ nginx opsional via profile reverse-proxy)
├── Makefile                               # make api / smoke / test / docker-up / contract
├── .env.example                           # KBR_CORS_ORIGINS, KBR_WORKERS, port, memory limit
├── deploy/nginx.conf                      # Reverse proxy, timeout /reason 120s
├── ontology/                              # Artefak Ontologi SROIQ(D) (Fase 5–6)
│   ├── kbr-core.ttl                       # TBox murni (Turtle, 113 kelas + properti + aksioma)
│   ├── kbr_pajak_tbox.owl                 # TBox murni (RDF/XML untuk Protégé)
│   ├── kbr_pajak_reasoning.owl            # TBox + 97 SWRL + 446 individu + 15 skenario uji
│   ├── kbr_ter_pph21.ttl                  # 127 bracket TER PPh 21 (PP 58/2023) tervalidasi
│   ├── kbr_kbli.ttl                       # 1.453 konsep W3C SKOS KBLI/KLU (PER-17, PP 78/2019, PerBKPM 7/2020, PMK 16/2020)
│   ├── kbr-perda-rates.ttl                # 390 Pemda · 2.107 item tarif dari 524 Perda PDRD
│   ├── rule_map.json                      # Peta 103 konsep katalog -> rule_id & source_quote
│   ├── ontology_build_report.json         # Ringkasan build & hasil inferensi HermiT
│   ├── step_b_build_report.json           # Ringkasan build TER PPh 21 & KBLI SKOS
│   └── step_c_build_report.json           # Ringkasan build tarif 524 Perda / 390 Pemda
├── src/                                   # 16 modul pipeline & builder ontologi/SKOS/Perda
├── scripts/                               # 35 skrip CLI (akuisisi, validasi, audit, fase5_ontology, step_b/c, eval)
├── tests/                                 # 172 automated tests + fixtures HTML BPK (+ conftest.py)
├── config/                                # Konfigurasi crawl, konsolidasi, & scope_cards
├── docs/                                  # Dokumentasi, spesifikasi & Laporan Fase 0–8
│   ├── fase_8.md                          # Dokumentasi sistem menyeluruh & serah terima (G8)
│   ├── DATA_DICTIONARY.md                 # Kamus data korpus, rules, ontologi & API
│   ├── KBR_Extraction_Spec_v2.md          # Spesifikasi teknis pipeline ekstraksi
│   ├── AGENTS.md                          # Aturan kerja & prinsip anti-halusinasi P1-P13
│   ├── fase_1.md .. fase_7.md             # Laporan tiap fase & gerbang G1–G7
│   ├── API_CONTRACT_v2.md                 # Kontrak API beku v2.0.0 (payload PRD, 7 kasus emas, deviasi)
│   ├── PRD_CORRECTIONS.md                 # 30 koreksi angka/klaim PRD v2.0 agar selaras artefak riil
│   ├── CBR_ANNOTATION_GUIDE.md            # Panduan anotasi 60 kasus + taksonomi + validator
│   ├── DEPLOYMENT.md                      # Deployment Docker/nginx, env var, kapasitas, runbook
│   ├── fase7_eval_results.json            # Hasil evaluasi 15/15 skenario & boundary tests
│   ├── corpus_directory.xlsx              # Direktori korpus 7 tab
│   └── ISSUES.md                          # Catatan anomali sumber (#A7 PER-DJP-2015-17)
├── notebooks/
│   ├── README.md
│   └── colab_extract_t2.ipynb             # Notebook ekstraksi T2_RULE vLLM (Qwen2.5-32B-AWQ)
└── knowledge_json/
    ├── rules/
    │   ├── legal_rules.jsonl              # 12.921 aturan atomik (8.717 VALIDATED, 474 HUMAN_FIXED, 117 HUMAN_APPROVED, 3.599 REVIEW_REQUIRED)
    │   └── kbr-data.ttl                   # Ekspor RDF Turtle penuh seluruh 12.921 aturan
    ├── text_lampiran/                     # Teks sumber untuk rebuild TER (PP 58/2023) & KBLI (PER-17, PP 78, PerBKPM 7, PMK 16)
    ├── review/                            # 621 baris audit P1-P6, log audit, review queue, gold standard
    ├── documents/                         # 165 JSON regulasi pusat kanonik
    ├── consolidated/                      # 32 JSON teks TERBARU pasca-amandemen (incl. UU 6/2023 CK & UU 7/2021 HPP)
    ├── perda/                             # 524 JSON Perda PDRD 2023–2026 (493 digital + 31 OCR)
    ├── jurisprudence/                     # 284 JSON Putusan Pengadilan Pajak
    ├── putusan_mk/                        # 15 JSON Putusan MK (amar dikabulkan/bersyarat)
    ├── sema_tun/                          # 78 JSON butir SEMA Kamar TUN (14 pajak)
    ├── pph_op/                            # Korpus domain PPh OP milik rekan
    └── metadata/                          # manifest.json (97 active_for_rules), scope_manifest, gaps (0 unresolved), dll.
```

---

## Panduan Singkat Konsumsi oleh Tim

1. **Frontend (`yoeke-front`):** baca **[`docs/API_CONTRACT_v1.md`](docs/API_CONTRACT_v1.md)** lalu jalankan `uvicorn backend.main:app --port 8000`. Panggil `GET /options` (pekerjaan, wilayah, **`final_income_objects`**), `GET /kbli`, `GET /perda`, dan `POST /reason`; tampilkan `tarif`/`fasilitas`/`kewajiban`/`sanksi` beserta `justifikasi` (`source_locator`, `source_quote`, `mk_refs`, `sema_refs`) dan pisahkan `estimasi_pajak.rincian` **tarif umum** (`pph_op_pasal17_idr`/`pph_badan_idr`) dari **PPh Final Pasal 4(2)** (`total_pph_final_pasal4_2_idr`).
2. **RAG (`daRAG`):** gunakan `knowledge_json/rules/legal_rules.jsonl` atau `GET /sparql/provenance` serta `knowledge_json/consolidated/<id>.json` (cek `recommended_source` dan `active_for_rules == true` di `metadata/manifest.json`).
3. **Inspeksi Ontologi di Protégé:** buka `ontology/kbr_pajak_reasoning.owl`, pilih **Reasoner → HermiT → Start reasoner**.
4. **Rebuild Ontologi & Jalankan Tes dari Repo Ini:**
   ```bash
   python3 scripts/fase5_ontology.py build
   python3 scripts/fase_step_b.py
   python3 scripts/fase_step_c.py
   pytest -q
   ```
5. **Deploy & Verifikasi Kontrak:** lihat **[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)**, lalu:
   ```bash
   cp .env.example .env && docker compose up -d --build
   python3 scripts/smoke_test.py --base-url http://localhost:8000   # 41 cek
   ```

---

## Batasan Penting

- **Anomali `PER-DJP-2015-17` (dikarantina — `docs/ISSUES.md #A7`):** file PDF BPK ternyata berisi Perda Kab. Pangandaran tentang Lingkungan Hidup; diblokir di validator sehingga **0 aturan** darinya masuk ke `legal_rules.jsonl`.
- **`PMK-2008-253`:** PDF awal belum tersedia di BPK; perubahan berlakunya (`PMK-2015-90`, `PMK-2019-92`) sudah masuk.
- **Putusan MK & SEMA TUN:** disimpan sebagai lapisan anotasi interpretatif (`terdampakPutusanMK`, `merujukSEMA`) dalam justifikasi tanpa menimpa naskah UU konsolidasi.
- **`sources/` lokal (PDF mentah):** tidak di-track di Git dan **jangan** pernah di-commit.
