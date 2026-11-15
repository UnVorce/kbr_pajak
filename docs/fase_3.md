# Laporan Fase 3 — Gap & Kelengkapan, Audit Metadata, dan Koreksi Konsolidasi (G3)

> S6: pendeteksi lubang kutipan (`src/gaps.py`) + putaran crawl berbasis gap (`scripts/fase3.py`), audit & perbaikan metadata BPK (`scripts/repair_metadata.py`), serta perbaikan krusial konsolidasi-lite untuk UU 7/2021 HPP & amandemen bertingkat.

## 1. Ringkasan Eksekutif (Gate G3: Kutipan Terminal)

- **Total dokumen di registry (`data/documents/`):** **78** (43 dari korpus tim + 35 hasil fetch BPK; 67 file TXT di `data/text/`).
- **Total kutipan diekstrak (`data/citations.jsonl`):** **1.053** kutipan (mengabaikan kutipan diri sendiri pada judul/menimbang dan dokumen `MANUAL`/`LAMPIRAN`).
- **Total dokumen unik yang dikutip:** **129** dokumen.
- **Status kutipan akhir (`data/gaps.json`):**

| Status | Jumlah Dokumen | Keterangan |
|---|---:|---|
| `RESOLVED` | 43 | Ada di registry `data/documents/` |
| `RESOLVED_EQUIVALENT` | 21 | Diwakili dokumen pengganti/terbaru di registry (PP/UU yang dicabut, penetapan Perpu, atau salah ketik OCR) |
| `IGNORED_OUT_OF_SCOPE` | 39 | Dasar hukum umum (UUD/P3/Keuangan Negara) atau domain di luar fokus (KUHAP, Pasar Modal, P2SK, Cukai, Kepabeanan, Bea Meterai, OSS, PPh tanah/bangunan, Pemda, dll.) |
| `DEFERRED_CK` | 26 | Hanya dikutip oleh `UU-2023-6` (omnibus Cipta Kerja); lapisan CK ditunda (`PENDING_CK`) |
| `UNRESOLVED` | **0** | Seluruh kutipan sudah terminal |

- **Gate G3 tercapai:** `unresolved_citations.json` = `[]` (0 dokumen menggantung).

## 2. Putaran Crawl Berbasis Gap (17 Dokumen Baru)

### Putaran 1 (12 dokumen)

| document_id | Peran / Ringkasan Isi | Struktur & Pasal | Status Sumber |
|---|---|---|---|
| `PERPU-2008-5` | Teks Perubahan Keempat UU KUP (UU 16/2009 hanya penetapan 2 pasal) | `AMENDING_ROMAN` (2 pasal) | Berlaku |
| `PMK-2025-11` | Nilai lain DPP & besaran tertentu PPN + mengubah PMK 81/2024 Pasal 313 & PMK 48/2023 | `NUMERIC` (24 pasal) | Berlaku |
| `PP-2010-94` | Penghitungan PKP & pelunasan PPh dalam tahun berjalan (induk angsuran PPh) | `NUMERIC` (35 pasal) | Berlaku |
| `PP-2019-45` | Perubahan atas PP 94/2010 | `AMENDING_ROMAN` (2 pasal) | Berlaku |
| `PP-2015-18` | Fasilitas PPh penanaman modal bidang usaha tertentu | `NUMERIC` (13 pasal) | Tidak Berlaku *(diganti PP 78/2019)* |
| `PP-2016-9` | Perubahan atas PP 18/2015 (hanya Lampiran I & II) | `AMENDING_ROMAN` (2 pasal) | Tidak Berlaku |
| `PP-2000-20` | Perlakuan perpajakan di Kawasan Pengembangan Ekonomi Terpadu (KAPET) | `NUMERIC` (5 pasal) | Berlaku |
| `PP-2000-147` | Perubahan atas PP 20/2000 (KAPET) | `AMENDING_ROMAN` (3 pasal) | Berlaku |
| `PP-2022-50` | Tata cara pelaksanaan hak dan pemenuhan kewajiban perpajakan (mencabut PP 74/2011) | `NUMERIC` (10 pasal) | Berlaku |
| `PP-2015-40` | PPN air bersih dibebaskan | `NUMERIC` (7 pasal) | Tidak Berlaku *(dicabut PP 49/2022)* |
| `PP-2015-81` | PPN/PPnBM BKP strategis dibebaskan | `NUMERIC` (8 pasal) | Tidak Berlaku *(dicabut PP 49/2022)* |
| `PMK-2020-96` | Perubahan atas PMK 11/PMK.010/2020 (pelaksanaan PP 78/2019 fasilitas PPh) | `AMENDING_ROMAN` (2 pasal) | Berlaku |

### Putaran 2 (5 dokumen dari kutipan putaran 1)

| document_id | Peran / Ringkasan Isi | Struktur & Pasal | Status Sumber |
|---|---|---|---|
| `PMK-2024-131` | Perlakuan PPN impor/penyerahan BKP & JKP (nilai lain 11/12) | `NUMERIC` (6 pasal) | Berlaku |
| `PMK-2023-48` | PPh dan/atau PPN atas emas perhiasan & emas batangan (diubah PMK 11/2025) | `NUMERIC` (28 pasal) | Berlaku |
| `PMK-2023-41` | PPN atas penyerahan agunan yang diambil alih kreditur | `NUMERIC` (10 pasal) | Berlaku |
| `PMK-2024-79` | Perlakuan perpajakan dalam Kerja Sama Operasi (KSO) | `NUMERIC` (4 pasal*) | Berlaku |
| `PP-2021-9` | Perlakuan perpajakan mendukung kemudahan berusaha (mengubah PP 94/2010; mencabut PP 19/2009) | `NUMERIC` (12 pasal) | Berlaku |

*\*Catatan `PMK-2024-79`: PDF asli menggunakan tata letak 2 kolom sehingga ekstraksi PyMuPDF mengeluarkan beberapa heading kolom kanan sebelum kolom kiri (`Pasal 4` sebelum `Pasal 3`); parser berurutan berhenti di Pasal 4 sementara teks penuh 26 halaman tetap utuh di `data/text/PMK-2024-79.txt`.*

## 3. Audit & Perbaikan Metadata (`scripts/repair_metadata.py`)

Audit metadata menemukan **6** anomali akibat hasil pencarian BPK Fase 1 yang salah dokumen dan 1 file tim yang salah label (`data/metadata_repair_log.json`):

1. **`UU-2009-42`**: judul sebelumnya Perbup Kubu Raya → diperbaiki dari `/Details/38787/uu-no-42-tahun-2009` (UU Perubahan Ketiga UU PPN).
2. **`UU-2022-1`**: judul sebelumnya Perpu Pemilu → diperbaiki dari `/Details/195696/uu-no-1-tahun-2022` (UU HKPD).
3. **`PMK-2026-6`**: judul sebelumnya POJK → diperbaiki dari `/Details/345004/pmk-no-6-tahun-2026` (PMK PPh Pasal 21 magang).
4. **`PP-2016-55`**: judul sebelumnya Perbup Tasikmalaya → diperbaiki dari `/Details/5776/pp-no-55-tahun-2016` (PP Ketentuan Umum Pemungutan Pajak Daerah).
5. **`PMK-2024-69` → re-key ke `PMK-2024-127`**: file korpus tim `2024pmkeuangan069.json` ternyata berisi **PMK 127/2024** (Peta Kapasitas Fiskal). File diganti nama, `document_id` + seluruh `locator` diperbarui ke `PMK-2024-127`, dan metadata diambil dari `/Details/313088/pmk-no-127-tahun-2024`.
6. **`PER-DJP-2015-17`**: judul sebelumnya Perwali Salatiga + URL Perda Pangandaran → judul ditetapkan manual (`PER-17/PJ/2015 tentang Norma Penghitungan Penghasilan Neto`), URL salah dihapus (`metadata_manual: true`). Dokumen ini hanya referensi (domain Orang Pribadi rekan tim).

### Gap Manual yang Diketahui (`data/gaps_attempts.json`)

- **`PMK-2024-69` (asli — perubahan PMK 130/2020 tentang tax holiday):** setelah re-key di atas, PMK 69/2024 yang asli masih belum ada di korpus. Pencarian BPK tidak mengindeks dokumen ini dan JDIH Kemenkeu timeout. Dicatat sebagai gap manual (`PMK-2020-130` di `config/consolidation.yaml` mencatat `unparsed: dokumen pengubah tidak ada`) untuk tindak lanjut pengunduhan manual di luar pipeline otomatis.

## 4. Temuan Krusial & Perbaikan Konsolidasi-lite (`src/consolidate.py`)

Pada pemeriksaan Fase 2 ditemukan bahwa **perubahan UU 7/2021 (HPP) belum masuk ke teks konsolidasi UU KUP, UU PPh, dan UU PPN** (mis. `Pasal 17` UU PPh masih menampilkan tarif 2008 Rp50 juta dan `Pasal 7` UU PPN masih 10%). Penyebab & perbaikannya:

1. **Pemecahan omnibus (`split_top_level_pasals`):** dokumen omnibus seperti HPP memuat pasal kutipan di dalam butir amandemen sehingga parser S4 biasa memotong blok di tengah pasal. Konsolidasi kini membaca ulang dari `data/text/*.txt` bila kalimat `"Beberapa ketentuan dalam"` muncul ≥ 2 kali.
2. **Fallback kalimat lingkup OCR (`scope_target`):** pada HPP Pasal 3 (PPh), OCR membaca `"Nomor T Tahun 1983"`. Ditambahkan pemetaan topik + cek tahun (`TOPIC_TARGET`).
3. **Pemisah butir tanpa nomor & artefak PDF (`_paragraph_items`, `split_amendment_items`):** PDF HPP kehilangan sebagian besar nomor butir (mis. 2–9 pada PPh dan sebagian besar pada PPN); ditambahkan mode paragraf yang dipakai ketika mode bernomor hanya menangkap sebagian kecil butir.
4. **Frasa 1994 & lintas-baris (`BERBUNYI_RE`, `SISIP2_RE`, `SISIP_BEFORE_RE`, `_split_multi_sisip`):**
   - Mendukung `"berbunyi berikut :"` (tanpa `"sebagai"`, mis. `UU-1994-9` Pasal 44A–44B) dan jeda baris di dalam `"berbunyi sebagai\nberikut"`.
   - Mendukung sisipan jamak (`Pasal 16A, 16B, 16C, 16D` pada `UU-1994-11`; `Pasal 44A, 44B` pada `UU-1994-9`) dan sisipan `"Sebelum Pasal Y"` (`Pasal 43A` pada `UU-2007-28`) serta `"Di antara Pasal X dan BAB Y"` (`Pasal 47A` pada `UU-2000-16`).
5. **Amandemen bertingkat & Perppu tunggal (`_is_outer_nested`, `_nested_instructions`):**
   - `PMK-2025-53` mengubah Pasal 20 `PMK-2025-11` yang di dalamnya memuat perubahan atas `PMK-2024-81` (`Pasal 343`, `Pasal 354` dihapus). Kini keduanya terapply dengan benar: `PMK-2025-11` mendapat Pasal 20 baru, dan `PMK-2024-81` menerima perubahan nested-nya.
   - `PERPU-2008-5` (1 butir panjang sebelum `diubah`) kini ikut terparsing pada `Pasal 37A`.
6. **Normalisasi OCR tarif & nomor pasal (`fix_ocr_rates`, `_pasal_pattern`, `16E}`/`168`→`16B`, `1 1A`→`11A`):**
   - Tarif `5o/o`, `l5%`, `Rp25O.000.000,0O` dibersihkan menjadi `5%`, `15%`, `Rp250.000.000,00`.
   - Heading `Pasal 16E}`/`Pasal 168` (HPP PPN) dan `Pasal 1 1A` (HPP PPh) kini cocok dan terapply penuh.

### Perbandingan Hasil Konsolidasi (Fase 2 lama vs Fase 3 terbaru)

| Target | Rantai Pengubah | Fase 2 (applied / unparsed / pasal) | Fase 3 (applied / unparsed / pasal) | Verifikasi Kunci |
|---|---|---:|---:|---|
| `UU-1983-6` (KUP) | `UU-1994-9 → UU-2000-16 → UU-2007-28 → PERPU-2008-5 → UU-2021-7` | 39 / 5 / 56 | **158 / 0 / 75** | Pasal 1, 8, 13, 37A, 43A, 44A, 44B, 47A versi HPP |
| `UU-1983-7` (PPh) | `UU-1991-7 → UU-1994-10 → UU-2000-17 → UU-2008-36 → UU-2021-7` | 33 / 13 / 32 | **92 / 2 / 42** | Pasal 17 tarif Rp60 jt & 35%, Pasal 11A, 32C |
| `UU-1983-8` (PPN) | `UU-1994-11 → UU-2000-18 → UU-2009-42 → UU-2021-7` | 24 / 6 / 19 | **66 / 0 / 31** | Pasal 1A, 7 (11%/12%), 8A, 16B, 16G |
| `UU-1985-12` (PBB) | `UU-1994-12` | 3 / 0 / 29 | **4 / 0 / 29** | — |
| `PP-2022-55` | `PP-2026-20` | 1 / 0 / 70 | **5 / 0 / 71** | Catatan: base `articles` tim 74/131 pasal |
| `PMK-2024-81` | `PMK-2025-11 → PMK-2025-53 → PMK-2025-54 → PMK-2026-1` | 47 / 4 / 426 | **47 / 4 / 427** | Pasal 313 diubah, 343 & 354 dihapus (4 unparsed = ayat-level) |
| `PMK-2025-11` | `PMK-2025-53` | — | **1 / 0 / 24** | Pasal 20 terupdate |
| `PMK-2023-48` | `PMK-2025-11` | — | **2 / 0 / 28** | Pasal 14 & 15 terupdate |
| `PMK-2010-68` | `PMK-2013-197` | 3 / 0 / 9 | **4 / 0 / 9** | — |
| `PP-2010-94` | `PP-2019-45 → PP-2021-9` | — | **5 / 0 / 37** | Catatan: Pasal 2A dicabut sebagian oleh PP 55/2022 Pasal 72b |
| `PP-2000-20` | `PP-2000-147` | — | **1 / 0 / 5** | Pasal 1 KAPET terupdate |
| `PP-2015-18` | `PP-2016-9` | — | **0 / 1 / 13** | Pengubah hanya lampiran; rezim sudah diganti PP 78/2019 |
| `PMK-2020-130` | `PMK-2024-69` *(hilang)* | — | **0 / 1 / 25** | Menunggu file asli PMK 69/2024 |

## 5. Pengujian & Artefak Output

- **Suite uji (`pytest -v`):** **102 / 102 lulus** (termasuk `tests/test_gaps.py` baru dan uji regresi konsolidasi omnibus/nested/multi-sisip/OCR).
- **Artefak JSON yang dihasilkan untuk tahap selanjutnya (Fase 4 — ekstraksi aturan & ontology oleh tim):**
  - `data/documents/*.json` (78 dokumen kanonik ber-locator)
  - `data/consolidated/*.json` (13 dokumen teks terbaru pasca-amandemen)
  - `data/citations.jsonl`, `data/gaps.json`, `data/unresolved_citations.json`, `data/gaps_attempts.json`
  - `data/metadata_repair_log.json`

## 6. Checklist Gate G3 (Berhenti untuk Review Manusia)

- [x] Seluruh 129 dokumen yang dikutip memiliki status terminal (`UNRESOLVED = 0`).
- [x] Dokumen yang dikutip hanya oleh `UU-2023-6` dicatat eksplisit sebagai `DEFERRED_CK` (26 dokumen).
- [x] Anomali metadata BPK pada 6 dokumen korpus sudah diperbaiki & diaudit ulang.
- [x] Gap non-kutipan (`PMK-2024-69` asli) tercatat transparan di `data/gaps_attempts.json`.
- [x] Konsolidasi HPP (KUP, PPh, PPN) dan amandemen bertingkat PMK 81/2024 sudah diverifikasi isi pasalnya.
- [x] Semua test (`102 passed`) hijau.

*Pipeline berhenti di akhir Fase 3 (JSON korpus + konsolidasi siap untuk review manusia & dilanjutkan ke Fase 4).*
