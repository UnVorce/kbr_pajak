# kbr_pajak — Korpus Hukum, Ontologi `SROIQ(D)`, Reasoning HermiT & Backend API KBR Perpajakan Indonesia

Sistem berbasis pengetahuan (*Knowledge-Based Reasoning*) untuk kewajiban, tarif, fasilitas, dan mitigasi risiko perpajakan Indonesia (**Fase 0–8 selesai — Gerbang G8 tercapai**).

> **Dokumentasi Lengkap:** baca [`docs/fase_8.md`](docs/fase_8.md) (arsitektur menyeluruh & alur kerja) dan [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) (kamus data korpus, `legal_rules.jsonl`, 59 kelas/properti ontologi, 28 aturan SWRL, & kontrak API).

---

## Ringkasan Sistem

```text
[Korpus Resmi BPK/JDIH/MK/MA/SetPP]
   ├── 165 regulasi pusat (97 active_for_rules) + 32 consolidated (UU CK & HPP)
   ├── 524 Perda PDRD (2023–2026) + 284 Putusan SetPP + 15 Putusan MK + 78 SEMA TUN
   └── 12.907 aturan atomik tervalidasi (legal_rules.jsonl, 9 domain pajak)
         │
         ├──► ontology/kbr_pajak_reasoning.owl (59 kelas SROIQ(D) · 28 SWRL · 322 individu)
         │       └─► Reasoner HermiT (World() terisolasi per request)
         │
         └──► knowledge_json/rules/kbr-data.ttl (9,9 MB ekspor RDF penuh 12.907 aturan)
                 └─► Engine SPARQL lokal (rdflib)
                         │
                         ▼
               [backend/main.py — FastAPI + Uvicorn]
         POST /reason · GET /sparql/provenance · GET /catalog · GET /health
```

**Prinsip utama:** **0% logika pajak di-hardcode di Python.** Klasifikasi ambang numerik (`> Rp4,8M` PKP, `≤ Rp4,8M` UMKM PP 55, `≥ 40%` saham publik Tbk, 6 tier Tax Holiday `PMK-2020-130`, PKB progresif `1..5+`) dikerjakan oleh aksioma `OWL 2 ConstrainedDatatype` + `28` aturan SWRL lewat **HermiT**, dan setiap hasil selalu membawa jejak `rule_id`, `Pasal`, `source_quote`, serta referensi `PutusanMK`/`SEMA_TUN`.

---

## Quickstart Backend API (`backend/`)

Prasyarat: Python 3.10+, Java JRE/JDK (untuk HermiT), dan dependensi di `backend/requirements.txt`.

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- **Swagger UI interaktif:** `http://localhost:8000/docs`
- **Panduan & contoh `curl`:** lihat [`backend/README.md`](backend/README.md)

| Endpoint | Fungsi |
|---|---|
| `GET /health` | Status `.owl`, `.ttl`, jumlah kelas, individu, dan aturan SWRL |
| `POST /reason` | Evaluasi profil `WajibPajak` via HermiT + justifikasi pasal/MK/SEMA (`TK-A2-1`..`TK-E1`) |
| `GET /catalog` | Peta 31 item katalog tarif/fasilitas/kewajiban/sanksi (`ontology/rule_map.json`) |
| `GET /scenarios` | Hasil inferensi 8 skenario demonstrasi bawaan |
| `GET /sparql/provenance` | Query SPARQL pada 12.907 aturan (`rule_id`, `document_id`, `domain`, `rule_type`, `q`) |
| `GET /sparql/stats` | Agregasi jumlah aturan per domain & kelas RDF |

---

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology awal tim (referensi)
├── backend/                               # Service FastAPI (Fase 7)
│   ├── __init__.py
│   ├── engine.py                          # HermiT isolated World() + cache RDF SPARQL
│   ├── main.py                            # Endpoint FastAPI + skema Pydantic + CORS
│   ├── requirements.txt
│   └── README.md
├── ontology/                              # Artefak Ontologi SROIQ(D) (Fase 5–6)
│   ├── kbr-core.ttl                       # TBox murni (Turtle, 59 kelas + properti + aksioma)
│   ├── kbr_pajak_tbox.owl                 # TBox murni (RDF/XML untuk Protégé)
│   ├── kbr_pajak_reasoning.owl            # TBox + 28 SWRL + 322 individu + 8 skenario uji
│   ├── rule_map.json                      # Peta 31 konsep katalog -> rule_id & source_quote
│   └── ontology_build_report.json         # Ringkasan build & hasil inferensi HermiT
├── docs/                                  # Dokumentasi & Laporan Fase 1–8
│   ├── fase_8.md                          # Dokumentasi sistem menyeluruh & serah terima (G8)
│   ├── DATA_DICTIONARY.md                 # Kamus data korpus, rules, ontologi & API
│   ├── fase_1.md .. fase_7.md             # Laporan tiap fase & gerbang G1–G7
│   ├── fase7_eval_results.json            # Hasil evaluasi 12/12 skenario & boundary tests
│   ├── corpus_directory.xlsx              # Direktori korpus 7 tab
│   └── ISSUES.md                          # Catatan anomali sumber (#A7 PER-DJP-2015-17)
├── notebooks/
│   └── colab_extract_t2.ipynb             # Notebook ekstraksi T2_RULE vLLM (Qwen2.5-32B-AWQ)
└── knowledge_json/
    ├── rules/
    │   ├── legal_rules.jsonl              # 12.907 aturan atomik (8.717 VALIDATED, 474 HUMAN_FIXED, 117 HUMAN_APPROVED, 3.599 REVIEW_REQUIRED)
    │   └── kbr-data.ttl                   # Ekspor RDF Turtle penuh seluruh 12.907 aturan
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

1. **Frontend (`yoeke-front`):** jalankan `uvicorn backend.main:app --port 8000`, panggil `POST /reason` untuk evaluasi profil WP dan tampilkan `tarif`/`fasilitas`/`kewajiban`/`sanksi` beserta `justifikasi` (`source_locator`, `source_quote`, `mk_refs`, `sema_refs`).
2. **RAG (`daRAG`):** gunakan `knowledge_json/rules/legal_rules.jsonl` atau `GET /sparql/provenance` serta `knowledge_json/consolidated/<id>.json` (cek `recommended_source` dan `active_for_rules == true` di `metadata/manifest.json`).
3. **Inspeksi Ontologi di Protégé:** buka `ontology/kbr_pajak_reasoning.owl`, pilih **Reasoner → HermiT → Start reasoner**.

---

## Batasan Penting

- **Anomali `PER-DJP-2015-17` (dikarantina — `docs/ISSUES.md #A7`):** file PDF BPK ternyata berisi Perda Kab. Pangandaran tentang Lingkungan Hidup; diblokir di validator sehingga **0 aturan** darinya masuk ke `legal_rules.jsonl`.
- **`PMK-2008-253`:** PDF awal belum tersedia di BPK; perubahan berlakunya (`PMK-2015-90`, `PMK-2019-92`) sudah masuk.
- **Putusan MK & SEMA TUN:** disimpan sebagai lapisan anotasi interpretatif (`terdampakPutusanMK`, `merujukSEMA`) dalam justifikasi tanpa menimpa naskah UU konsolidasi.
- **`sources/` lokal (PDF mentah):** tidak di-track di Git dan **jangan** pernah di-commit.
