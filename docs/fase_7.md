# Laporan Fase 7 — Backend Reasoning API (`FastAPI` + `HermiT` + `SPARQL`) & Evaluasi Skenario

> **Status:** **SELESAI — Gerbang G7 Tercapai** (`backend/` siap pakai dengan seluruh skema Badan, OP multi-pekerjaan, PPh 23, BUT, 5 Perda & SKPKB; **`15/15` skenario evaluasi & boundary case lulus**, **`149` total `pytest` lulus** termasuk `6/6` integration test FastAPI `TestClient`).

---

## 1. Arsitektur Backend (`backend/`)

Dibuat terpisah di **`backend/`** (`fatih/backend/` dan disinkronkan ke `kbr_pajak/backend/`) agar bersih untuk integrasi frontend tim (`yoeke-front`) dan modul RAG (`daRAG`) tanpa bergantung pada skrip pipeline akuisisi (`src/`):

- **Tanpa hardcode logika pajak di Python:** `backend/engine.py` memetakan input JSON (`wp_kind`, `memilikiPekerjaan`, `berdomisiliDi`, dan properti) ke individu OWL pada `owlready2.World()` terisolasi per request, membersihkan individu skenario demo di memori agar steril & cepat, mengeksekusi **HermiT** (`sync_reasoner_hermit`), lalu mengekstrak hasil inferensi & rantai pasalnya.
- **Auto-detect path:** `resolve_paths()` otomatis mengenali struktur direktori baik saat dijalankan dari `fatih/` (`data/export/kbr-data.ttl`) maupun dari `kbr_pajak/` (`knowledge_json/rules/kbr-data.ttl`).
- **Cache graf RDF lokal:** `kbr-data.ttl` (`12.907` aturan) di-cache di memori menggunakan `threading.Lock()` sehingga endpoint SPARQL cepat setelah pemuatan awal.

### Endpoint FastAPI (`backend/main.py`)
| Method | Endpoint | Fungsi |
|---|---|---|
| `GET` | `/health` | Status `.owl`, `.ttl`, dan metrik build ontologi |
| `GET` | `/options` | Daftar `30` pilihan `JenisPekerjaan` & `6` `WilayahDaerah` langsung dari OWL |
| `GET` | `/kbli` | Pencarian `1.449` kode KBLI/KLU pada graf SKOS `kbr_kbli.ttl` |
| `GET` | `/kbli/{kode}` | Detail KBLI (persentase NPPN 3 wilayah & syarat provinsi Tax Allowance PP 78/2019) |
| `GET` | `/perda` | Daftar/cari `390` Pemda dari `524` Perda PDRD (`kbr-perda-rates.ttl`) |
| `GET` | `/perda/{pemda_id}` | Detail `2.029` item tarif pajak daerah & kutipan pasal resmi untuk 1 Pemda |
| `POST` | `/reason` | Evaluasi profil `WajibPajak` via HermiT + materialisasi `kodeKBLI` & `pemdaId` + estimasi nominal `SPARQL BIND` (TER PPh 21, NPPN, PBB lokal) + justifikasi pasal/MK/SEMA |
| `GET` | `/catalog` | Peta `83` item katalog tarif/fasilitas/kewajiban/sanksi (`rule_map.json`) |
| `GET` | `/scenarios` | Ringkasan `15` skenario demonstrasi di `kbr_pajak_reasoning.owl` |
| `GET` | `/sparql/provenance` | Query SPARQL atas `12.907` aturan (`rule_id`, `document_id`, `domain`, `rule_type`, `q`) |
| `GET` | `/sparql/stats` | Statistik aturan per domain & kelas dari RDF graph |

---

## 2. Evaluasi 15 Skenario (`scripts/fase7_eval.py`)

Hasil pengujian melalui `KBRReasoningEngine.reason()` (**`15/15` PASS**, latensi rata-rata **`4.844,55 ms`**, maks **`5.401,15 ms`** per *isolated HermiT World*):

| Kode | Skenario & Boundary Test | Hasil | Latensi (ms) |
|---|---|---|---|
| `TK-A2-1a` | Investasi pionir PT tepat Rp500M + SKF → Tax Holiday 100% 5 thn + Transisi 50% + Pasal 31E + PPN 11% | PASS | 5.143,21 |
| `TK-A2-1b` | Investasi pionir PT Rp1,5T + SKF → Tax Holiday 100% 7 thn + Transisi 50% | PASS | 4.664,01 |
| `TK-A2-2a` | PT Tbk saham publik 45%, ≥300 pihak, ≥183 hari + BKP Mewah → Tarif 19% + PPN 12% | PASS | 4.932,62 |
| `TK-A2-2b` | *Edge case* PT Tbk saham publik 30% (<40%) → tetap Tarif Umum 22% | PASS | 5.192,20 |
| `TK-A2-2c` | *Boundary* CV omzet tepat Rp4,8M → tetap `WajibPajakUMKM` (`PP55 0,5%`), belum PKP | PASS | 5.139,44 |
| `TK-B1` | *Boundary* CV omzet `Rp4.800.000.001` → PKP + transisi tarif umum + Pasal 31E + PPN 11% | PASS | 4.521,32 |
| `TK-B2` | PKP barang non-mewah (PPN Efektif 11%, tanpa 12% mewah) + BKP Strategis dibebaskan (`PP 49/2022`) | PASS | 4.624,64 |
| `TK-C1` | Domisili DKI + objek PBB-P2 → Tarif PBB 0,5% + kewajiban PBB | PASS | 4.477,75 |
| `TK-C2a` | Kontras MK: Spa Kesehatan Tradisional → Pengecualian PBJT (`MK-2024-19-PUU-XXII`) | PASS | 4.289,69 |
| `TK-C2b` | Kontras MK: Spa Hiburan Umum di DKI → Tarif PBJT Hiburan Khusus 40% | PASS | 4.591,82 |
| `TK-D1` | OP Penduduk DKI kendaraan ke-5 → PKB 6%, NIK-NPWP, tenggat SPT 3 bln | PASS | 5.145,88 |
| `TK-D2-E1` | Telat SPT Badan (denda Rp1jt) + Keberatan 30% & Banding 60% (`SEMA-2024-2-TUN-4`) | PASS | 5.401,15 |
| `TK-OP-MULTI` | OP Multi-Peran (`Dokter` + `Pegawai K/2` + `Pedagang_ECommerce 350jt`) + PBB Surabaya `0,15%` | PASS | 5.091,01 |
| `TK-BUT-23` | `BUT` kena PPh 22% + Branch Profit Tax 20% (dilarang PP 55 & Pasal 31E) | PASS | 4.792,88 |
| `TK-PPH23` | Penerima jasa PPh 23 tanpa NPWP → Tarif 2% + Sanksi kenaikan 100% | PASS | 4.660,64 |

Seluruh hasil di atas memverifikasi keberadaan minimal 1 rantai *provenance* (`rule_id`, `source_locator`, `source_quote`, `regulasi`, `mk_refs`, `sema_refs`) pada setiap kesimpulan.

---

## 3. Artefak & Cara Menjalankan

- `backend/__init__.py`, `backend/engine.py`, `backend/main.py`, `backend/requirements.txt`, `backend/README.md`
- `scripts/fase7_eval.py`, `reports/fase7_eval_results.json`, `tests/test_api.py`
- Menjalankan server:
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port 8000
  ```
