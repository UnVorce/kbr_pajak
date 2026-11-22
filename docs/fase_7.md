# Laporan Fase 7 — Backend Reasoning API (`FastAPI` + `HermiT` + `SPARQL`) & Evaluasi Skenario

> **Status:** **SELESAI — Gerbang G7 Tercapai** (`backend/` siap pakai, **`12/12` skenario evaluasi & boundary case lulus**, **`146` total `pytest` lulus** termasuk `5/5` integration test FastAPI `TestClient`).

---

## 1. Arsitektur Backend (`backend/`)

Dibuat terpisah di **`backend/`** (`fatih/backend/` dan disinkronkan ke `kbr_pajak/backend/`) agar bersih untuk integrasi frontend tim (`yoeke-front`) dan modul RAG (`daRAG`) tanpa bergantung pada skrip pipeline akuisisi (`src/`):

- **Tanpa hardcode logika pajak di Python:** `backend/engine.py` hanya memetakan input JSON (`wp_kind` + properti) ke individu OWL pada `owlready2.World()` terisolasi per request, mengeksekusi **HermiT** (`sync_reasoner_hermit`), lalu mengekstrak hasil inferensi & rantai pasalnya.
- **Auto-detect path:** `resolve_paths()` otomatis mengenali struktur direktori baik saat dijalankan dari `fatih/` (`data/export/kbr-data.ttl`) maupun dari `kbr_pajak/` (`knowledge_json/rules/kbr-data.ttl`).
- **Cache graf RDF lokal:** `kbr-data.ttl` (`12.907` aturan) di-cache di memori menggunakan `threading.Lock()` sehingga endpoint SPARQL cepat setelah pemuatan awal.

### Endpoint FastAPI (`backend/main.py`)
| Method | Endpoint | Fungsi |
|---|---|---|
| `GET` | `/health` | Status `.owl`, `.ttl`, dan metrik build ontologi |
| `POST` | `/reason` | Evaluasi profil `WajibPajak` via HermiT + validasi Pydantic + justifikasi pasal/MK/SEMA |
| `GET` | `/catalog` | Peta `31` item katalog tarif/fasilitas/kewajiban/sanksi (`rule_map.json`) |
| `GET` | `/scenarios` | Ringkasan `8` skenario demonstrasi di `kbr_pajak_reasoning.owl` |
| `GET` | `/sparql/provenance` | Query SPARQL atas `12.907` aturan (`rule_id`, `document_id`, `domain`, `rule_type`, `q`) |
| `GET` | `/sparql/stats` | Statistik aturan per domain & kelas dari RDF graph |

---

## 2. Perbaikan Boundary Ambang di Ontologi (`src/ontology.py`)

Selama verifikasi boundary Fase 7, ditemukan celah presisi pada batas `Rp4.800.000.000,00`:
- Sesuai **PP 55/2022 Pasal 57(1)** (*"peredaran bruto **tidak melebihi** Rp4.800.000.000,00"*) dan **PMK 164/2023 Pasal 17(1)** (*"jumlah peredaran bruto ... **melebihi** batasan Pengusaha kecil"*):
  - `WajibPajakUMKM` memakai `max_inclusive=4800000000.0` (`≤ Rp4,8M`).
  - `PengusahaKenaPajak` diperbaiki dari `min_inclusive` menjadi **`min_exclusive=4800000000.0`** (`> Rp4,8M`).
- Hasilnya, HermiT otomatis membuktikan `PengusahaKenaPajak ⊑ WajibPajakNonUMKM` dan tidak ada lagi tumpang tindih kelas tepat pada angka `Rp4.800.000.000,00`.

---

## 3. Evaluasi 12 Skenario (`scripts/fase7_eval.py`)

Hasil pengujian melalui `KBRReasoningEngine.reason()` (**`12/12` PASS**, latensi rata-rata **`2.347,7 ms`**, maks **`2.489,39 ms`** per *isolated HermiT World*):

| Kode | Skenario & Boundary Test | Hasil | Latensi (ms) |
|---|---|---|---|
| `TK-A2-1a` | Investasi pionir tepat Rp500M → Tax Holiday 100% 5 thn + PPh 22% + PPN 12% | PASS | 2.489,39 |
| `TK-A2-1b` | Investasi pionir Rp1,5T → Tax Holiday 100% 7 thn | PASS | 2.369,03 |
| `TK-A2-2a` | PT Tbk saham publik 45% → Tarif 19% (diskon 3%) | PASS | 2.344,31 |
| `TK-A2-2b` | *Edge case* PT Tbk saham publik 30% (<40%) → tetap Tarif Umum 22% | PASS | 2.269,90 |
| `TK-A2-2c` | *Boundary* omzet tepat Rp4,8M → tetap `WajibPajakUMKM` (`PP55 0,5%`), belum PKP | PASS | 2.300,81 |
| `TK-B1` | *Boundary* omzet `Rp4.800.000.001` → `PengusahaKenaPajak` + transisi ke tarif umum | PASS | 2.341,87 |
| `TK-B2` | PKP barang non-mewah (PPN Efektif 11%) + BKP Strategis dibebaskan (`PP 49/2022`) | PASS | 2.351,42 |
| `TK-C1` | Domisili DKI + objek PBB-P2 → Tarif PBB 0,5% + kewajiban PBB | PASS | 2.271,93 |
| `TK-C2a` | Kontras MK: Spa Kesehatan Tradisional → Pengecualian PBJT (`MK-2024-19-PUU-XXII`) | PASS | 2.353,39 |
| `TK-C2b` | Kontras MK: Spa Hiburan Umum → Tarif PBJT Hiburan Khusus 40% | PASS | 2.386,75 |
| `TK-D1` | OP Penduduk DKI kendaraan ke-5 → PKB 6%, NIK-NPWP, tenggat SPT 3 bln | PASS | 2.328,46 |
| `TK-D2-E1` | Telat SPT + Keberatan & Banding ditolak → 3 sanksi KUP + `SEMA-2024-2-TUN-4` | PASS | 2.365,18 |

Seluruh hasil di atas juga memverifikasi keberadaan minimal 1 rantai *provenance* (`rule_id`, `source_locator`, `source_quote`, `regulasi`, `mk_refs`, `sema_refs`) pada setiap kesimpulan.

---

## 4. Artefak & Cara Menjalankan

- `backend/__init__.py`, `backend/engine.py`, `backend/main.py`, `backend/requirements.txt`, `backend/README.md`
- `scripts/fase7_eval.py`, `reports/fase7_eval_results.json`, `tests/test_api.py`
- Menjalankan server:
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  ```
- **Siap lanjut:** Fase 8 (*Data Dictionary*, laporan akhir & serah terima final).
