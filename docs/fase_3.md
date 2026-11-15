# Laporan Fase 3 — Gap & Kelengkapan, Audit Metadata, Tambalan Manual, dan Koreksi Konsolidasi (G3)

> S6: pendeteksi lubang kutipan (`src/gaps.py`) + putaran crawl berbasis gap (`scripts/fase3.py`), audit & perbaikan metadata BPK (`scripts/repair_metadata.py`), ingest 12 PDF unduhan manual (`scripts/ingest_manual.py`), serta perbaikan krusial konsolidasi-lite untuk UU 7/2021 HPP, PMK/PER-DJP, & amandemen bertingkat.

## 1. Ringkasan Eksekutif (Gate G3: Kutipan Terminal)

- **Total dokumen di registry (`data/documents/`):** **89** (43 korpus tim + 35 fetch BPK + 11 dokumen baru dari `download-manual/`, plus re-ekstraksi 2-kolom `PMK-2024-79`; 78 file TXT di `data/text/`).
- **Total kutipan diekstrak (`data/citations.jsonl`):** **1.387** kutipan (mengabaikan kutipan diri sendiri pada judul/menimbang dan dokumen `MANUAL`/`LAMPIRAN`).
- **Total dokumen unik yang dikutip:** **163** dokumen.
- **Status kutipan akhir (`data/gaps.json`):**

| Status | Jumlah Dokumen | Keterangan |
|---|---:|---|
| `RESOLVED` | 47 | Ada di registry `data/documents/` |
| `RESOLVED_EQUIVALENT` | 48 | Diwakili dokumen pengganti/terbaru di registry (termasuk 26 PER-DJP yang dicabut `PER-DJP-2025-11`, `PMK-2024-119` yang dicabut `PMK-2026-28`, PP/UU yang dicabut, atau salah ketik OCR) |
| `IGNORED_OUT_OF_SCOPE` | 45 | Dasar hukum umum atau domain non-pajak (KUHAP, Pasar Modal, Perbankan, P2SK, Cukai, Kepabeanan, Bea Meterai, OSS, PT, Hak Tanggungan, Keimigrasian, Pemda, dll.) |
| `DEFERRED_CK` | 23 | Hanya dikutip oleh `UU-2023-6` (omnibus Cipta Kerja); lapisan CK ditunda (`PENDING_CK`) |
| `UNRESOLVED` | **0** | Seluruh kutipan sudah terminal |

- **Gate G3 tercapai:** `unresolved_citations.json` = `[]` (0 dokumen menggantung).

## 2. Putaran Crawl BPK & Ingest Manual (28 Dokumen Tambahan)

### A. Putaran Crawl BPK (17 dokumen)
- **Putaran 1 (12 dok):** `PERPU-2008-5` (isi amandemen KUP 2009), `PMK-2025-11`, `PP-2010-94`, `PP-2019-45`, `PP-2015-18`, `PP-2016-9`, `PP-2000-20`, `PP-2000-147`, `PP-2022-50`, `PP-2015-40`, `PP-2015-81`, `PMK-2020-96`.
- **Putaran 2 (5 dok):** `PMK-2024-131` (PPN nilai lain 11/12), `PMK-2023-48` (emas), `PMK-2023-41` (agunan), `PMK-2024-79` (KSO), `PP-2021-9` (mengubah `PP-2010-94` & mencabut `PP-2009-19`).

### B. Ingest Unduhan Manual (`scripts/ingest_manual.py` — 12 PDF dari `download-manual/`)

| document_id | Peran / Ringkasan Isi | Struktur & Pasal | Status Sumber |
|---|---|---|---|
| `PMK-2024-69` | Perubahan atas `PMK 130/PMK.010/2020` (*tax holiday*) — sebelumnya tidak terindeks BPK | `AMENDING_ROMAN` (2 pasal) | Berlaku |
| `PER-DJP-2025-11` | Ketentuan pelaporan PPh, PPN/PPnBM & Bea Meterai Coretax (mencabut 26 PER-DJP lama incl. `PER-03/PJ/2022`) | `NUMERIC` (147 pasal) | Berlaku |
| `PMK-2019-186` | Klasifikasi objek & penetapan NJOP **PBB-P3** | `NUMERIC` (44 pasal) | Berlaku |
| `PMK-2022-234` | Perubahan atas `PMK 186/PMK.03/2019` (PBB-P3) | `AMENDING_ROMAN` (2 pasal) | Berlaku |
| `PMK-2019-128` | *Super tax deduction* kegiatan vokasi | `NUMERIC` (11 pasal) | Berlaku |
| `PMK-2023-61` | Tata cara pelaksanaan penagihan pajak | `NUMERIC` (87 pasal) | Berlaku |
| `PMK-2026-28` | Tata cara pengembalian pendahuluan kelebihan pembayaran pajak (mencabut `PMK 39/2018` s.d. `119/2024`) | `NUMERIC` (27 pasal) | Berlaku |
| `PERPRES-2018-40` | Pembaruan Sistem Administrasi Perpajakan (Coretax) | `NUMERIC` (4 pasal) | Berlaku |
| `PERPU-2017-1` | Akses informasi keuangan untuk kepentingan perpajakan (AEoI) | `NUMERIC` (10 pasal) | Berlaku |
| `UU-1997-19` | Penagihan Pajak dengan Surat Paksa (PPSP) | `NUMERIC` (45 pasal) | Berlaku |
| `UU-2000-19` | Perubahan atas `UU 19/1997` (PPSP) | `AMENDING_ROMAN` (3 pasal) | Berlaku |
| `PMK-2024-79` *(re-ekstrak)* | Perlakuan perpajakan KSO — diekstrak ulang sadar-2-kolom sehingga seluruh **25 pasal** lengkap | `NUMERIC` (25 pasal) | Berlaku |

## 3. Audit & Perbaikan Metadata (`scripts/repair_metadata.py`)

Audit metadata menemukan dan memperbaiki **6** anomali akibat pencarian BPK Fase 1 dan 1 file tim yang keliru label (`data/metadata_repair_log.json`):
1. `UU-2009-42`, `UU-2022-1`, `PMK-2026-6`, `PP-2016-55` → diperbarui dari halaman detail BPK yang valid.
2. `PMK-2024-69` (file tim `2024pmkeuangan069.json`) → di-re-key menjadi **`PMK-2024-127`** (Peta Kapasitas Fiskal), lalu `PMK-2024-69` asli diisi dari unduhan manual JDIH Kemenkeu.
3. `PER-DJP-2015-17` (NPPN, referensi Orang Pribadi) → judul ditetapkan manual (`metadata_manual: true`), URL keliru dihapus.

## 4. Temuan Krusial & Perbaikan Konsolidasi-lite (`src/consolidate.py`, `src/textutil.py`)

- **Pemecahan omnibus & fallback OCR HPP (`UU-2021-7`):** `split_top_level_pasals`, `TOPIC_TARGET` (`"Nomor T Tahun 1983"`), `_paragraph_items` (butir tanpa nomor pada KUP/PPh/PPN), `fix_ocr_rates`, dan normalisasi nomor (`16E}`/`168`→`16B`, `1 1A`→`11A`).
- **Frasa 1994, jeda baris & sisipan jamak:** `"berbunyi berikut :"`, sisipan jamak (`Pasal 16A–16D`, `44A–44B`), `"Sebelum Pasal Y"` (`43A`), `"Di antara Pasal X dan BAB Y"` (`47A`), Perppu butir tunggal (`PERPU-2008-5`), serta heading OCR `Pasall`→`Pasal I` (`PMK-2024-69`, `PMK-2022-234`).
- **Nested amendment (`_is_outer_nested`):** `PMK-2025-53` mengubah Pasal 20 `PMK-2025-11` sekaligus meneruskan penghapusan `Pasal 343` & `354` pada `PMK-2024-81`.

### Ringkasan Hasil Konsolidasi Terbaru (15 Rantai)

| Target | Rantai Pengubah | Diterapkan / Tak Terparsing / Pasal | Verifikasi Kunci |
|---|---|---:|---|
| `UU-1983-6` (KUP) | `UU-1994-9 → UU-2000-16 → UU-2007-28 → PERPU-2008-5 → UU-2021-7` | **158 / 0 / 75** | Pasal 1, 8, 13, 37A, 43A, 44A, 44B, 47A versi HPP |
| `UU-1983-7` (PPh) | `UU-1991-7 → UU-1994-10 → UU-2000-17 → UU-2008-36 → UU-2021-7` | **92 / 2 / 42** | Pasal 17 tarif Rp60 jt & 35%, Pasal 11A, 32C |
| `UU-1983-8` (PPN) | `UU-1994-11 → UU-2000-18 → UU-2009-42 → UU-2021-7` | **66 / 0 / 31** | Pasal 1A, 7 (11%/12%), 8A, 16B, 16G |
| `UU-1985-12` (PBB) | `UU-1994-12` | **4 / 0 / 29** | — |
| `PP-2022-55` | `PP-2026-20` | **5 / 0 / 71** | Catatan: base `articles` tim 74/131 pasal |
| `PMK-2024-81` (CTAS) | `PMK-2025-11 → PMK-2025-53 → PMK-2025-54 → PMK-2026-1` | **47 / 4 / 427** | Pasal 313 diubah, 343 & 354 dihapus (4 unparsed = ayat-level) |
| `PMK-2025-11` | `PMK-2025-53` | **1 / 0 / 24** | Pasal 20 terupdate |
| `PMK-2023-48` | `PMK-2025-11` | **2 / 0 / 28** | Pasal 14 & 15 terupdate |
| `PMK-2020-130` (*Tax Holiday*) | `PMK-2024-69` | **10 / 0 / 26** | Pasal 1, 3, 4, 5, 12, 16, 21 diubah; 7 dihapus; 15A, 30A disisip |
| `PMK-2019-186` (PBB-P3) | `PMK-2022-234` | **10 / 0 / 44** | Pasal 1, 2, 8, 9, 33, 35, 36, 38, 39, 40 terupdate |
| `UU-1997-19` (PPSP) | `UU-2000-19` | **26 / 0 / 46** | Seluruh perubahan UU 19/2000 masuk |
| `PMK-2010-68` | `PMK-2013-197` | **4 / 0 / 9** | — |
| `PP-2010-94` | `PP-2019-45 → PP-2021-9` | **5 / 0 / 37** | Catatan: Pasal 2A dicabut sebagian oleh PP 55/2022 Pasal 72b |
| `PP-2000-20` | `PP-2000-147` | **1 / 0 / 5** | Pasal 1 KAPET terupdate |
| `PP-2015-18` | `PP-2016-9` | **0 / 1 / 13** | Pengubah hanya lampiran; rezim sudah diganti PP 78/2019 |

## 5. Pengujian & Checklist Gate G3

- **Suite uji (`pytest -q`):** **103 / 103 lulus**.
- [x] Seluruh 163 dokumen yang dikutip berstatus terminal (`UNRESOLVED = 0`).
- [x] Gap manual `PMK-2024-69` & dokumen pelengkap (`PER-DJP-2025-11`, `PMK-2019-186`/`2022-234`, `PMK-2019-128`, `PMK-2023-61`, `PMK-2026-28`, `PERPRES-2018-40`, `PERPU-2017-1`, `UU-1997-19`/`2000-19`, re-ekstrak 2-kolom `PMK-2024-79`) sudah teringest & terkonsolidasi.
- [x] Lapisan `PENDING_CK` (`UU-2020-11`, `PERPU-2022-2`, `UU-2023-6`) dicatat eksplisit sebagai `DEFERRED_CK` (`23` dokumen).

*Pipeline berhenti di akhir Fase 3 (JSON korpus + konsolidasi siap digabung dengan hasil anggota tim lain menuju Fase 4).*
