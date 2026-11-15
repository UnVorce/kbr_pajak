# Laporan Fase 2 — Parse Struktur & Konsolidasi-lite (v3.1)

> S4: parser Bab/Bagian/Paragraf/Pasal/Ayat/Huruf/Angka + dokumen pengubah
> (Pasal I/II/...). S5-lite: konsolidasi teks TERBARU per pasal (tanpa riwayat).

## Keputusan arah (disetujui tim)

- Pipeline **berhenti di JSON** — tidak ada ekspor OWL dari pipeline.
  Masing-masing anggota membangun ontology domainnya sendiri dari JSON ini,
  agar struktur ontology tetap seragam sesuai kesepakatan tim.

## Statistik parsing

| document_id | struktur | pasal | ayat | penjelasan |
|---|---|---|---|---|
| `PER-DJP-2015-17` | TXT_HILANG | 0 | 0 | 0 |
| `PMK-2010-68` | NUMERIC | 9 | 7 | 0 |
| `PMK-2013-197` | AMENDING_ROMAN | 2 | 0 | 0 |
| `PMK-2016-101` | NUMERIC | 5 | 0 | 0 |
| `PMK-2018-109` | NUMERIC | 29 | 109 | 0 |
| `PMK-2018-151` | NUMERIC | 17 | 63 | 0 |
| `PMK-2019-121` | NUMERIC | 1 | 0 | 0 |
| `PMK-2019-56` | NUMERIC | 1 | 0 | 0 |
| `PMK-2020-130` | NUMERIC | 5 | 28 | 0 |
| `PMK-2022-112` | NUMERIC | 8 | 39 | 0 |
| `PMK-2023-142` | NUMERIC | 6 | 5 | 0 |
| `PMK-2023-164` | NUMERIC | 25 | 137 | 0 |
| `PMK-2023-168` | NUMERIC | 25 | 99 | 0 |
| `PMK-2023-172` | NUMERIC | 25 | 147 | 0 |
| `PMK-2024-69` | TXT_HILANG | 0 | 0 | 0 |
| `PMK-2024-78` | UNKNOWN | 0 | 0 | 0 |
| `PMK-2024-81` | UNKNOWN | 0 | 0 | 0 |
| `PMK-2025-105` | NUMERIC | 9 | 26 | 0 |
| `PMK-2025-53` | AMENDING_ROMAN | 2 | 0 | 0 |
| `PMK-2025-54` | AMENDING_ROMAN | 2 | 0 | 0 |
| `PMK-2026-1` | AMENDING_ROMAN | 2 | 0 | 0 |
| `PMK-2026-6` | NUMERIC | 12 | 24 | 0 |
| `PP-2016-55` | NUMERIC | 10 | 20 | 35 |
| `PP-2018-40` | NUMERIC | 10 | 15 | 10 |
| `PP-2019-78` | NUMERIC | 10 | 25 | 12 |
| `PP-2022-3` | NUMERIC | 7 | 17 | 6 |
| `PP-2022-44` | NUMERIC | 20 | 46 | 30 |
| `PP-2022-49` | NUMERIC | 9 | 39 | 34 |
| `PP-2022-55` | NUMERIC | 10 | 22 | 68 |
| `PP-2023-35` | NUMERIC | 20 | 63 | 132 |
| `PP-2026-20` | AMENDING_ROMAN | 2 | 0 | 5 |
| `UU-1983-6` | NUMERIC | 50 | 97 | 50 |
| `UU-1983-7` | NUMERIC | 36 | 141 | 64 |
| `UU-1983-8` | NUMERIC | 21 | 55 | 21 |
| `UU-1985-12` | NUMERIC | 31 | 62 | 31 |
| `UU-1991-7` | AMENDING_ROMAN | 2 | 0 | 10 |
| `UU-1994-10` | AMENDING_ROMAN | 3 | 0 | 39 |
| `UU-1994-11` | AMENDING_ROMAN | 4 | 0 | 20 |
| `UU-1994-12` | AMENDING_ROMAN | 4 | 0 | 2 |
| `UU-1994-9` | AMENDING_ROMAN | 4 | 0 | 40 |
| `UU-2000-16` | AMENDING_ROMAN | 3 | 0 | 44 |
| `UU-2000-17` | AMENDING_ROMAN | 3 | 0 | 17 |
| `UU-2000-18` | AMENDING_ROMAN | 3 | 0 | 17 |
| `UU-2007-28` | AMENDING_ROMAN | 2 | 0 | 0 |
| `UU-2008-36` | AMENDING_ROMAN | 2 | 0 | 0 |
| `UU-2009-16` | NUMERIC | 2 | 0 | 3 |
| `UU-2009-28` | NUMERIC | 185 | 494 | 185 |
| `UU-2009-42` | AMENDING_ROMAN | 2 | 0 | 18 |
| `UU-2020-10` | NUMERIC | 10 | 26 | 31 |
| `UU-2021-7` | NUMERIC | 11 | 111 | 55 |
| `UU-2022-1` | NUMERIC | 20 | 78 | 188 |
| `UU-2023-6` | NUMERIC | 2 | 0 | 2494 |

- NUMERIC: 32 · AMENDING_ROMAN: 16 · UNKNOWN: 2 · TXT hilang: 2

## Konsolidasi-lite

| target | rantai | diterapkan | tak terparsing | pasal akhir |
|---|---|---|---|---|
| `UU-1983-6` | UU-1994-9 → UU-2000-16 → UU-2007-28 → UU-2009-16 → UU-2021-7 | 39 | 5 | 56 |
| `UU-1983-7` | UU-1991-7 → UU-1994-10 → UU-2000-17 → UU-2008-36 → UU-2021-7 | 33 | 13 | 32 |
| `UU-1983-8` | UU-1994-11 → UU-2000-18 → UU-2009-42 → UU-2021-7 | 24 | 6 | 19 |
| `UU-1985-12` | UU-1994-12 | 3 | 0 | 29 |
| `PP-2022-55` | PP-2026-20 | 1 | 0 | 70 |
| `PMK-2024-81` | PMK-2025-53 → PMK-2025-54 → PMK-2026-1 | 47 | 4 | 426 |
| `PMK-2010-68` | PMK-2013-197 | 3 | 0 | 9 |

## Catatan & batasan

- Lapisan Cipta Kerja **DITUNDA**: UU-2020-11, PERPU-2022-2, UU-2023-6 — teks konsolidasi belum mencakup perubahan dari UU Cipta Kerja/Perpu (perlu penanganan khusus). Tercatat sebagai PENDING_CK, bukan diabaikan.
- Instruksi `ayat_level` (hanya sebagian ayat dikutip tanpa pasal utuh) dicatat di `unparsed` — ditangani di fase berikutnya atau review manusia.
- **TXT tidak ditemukan (NEEDS_REVIEW, cari manual):** `PER-DJP-2015-17` (NPPN) dan `PMK-2024-69` — pencarian BPK tidak menemukan halamannya; tim bisa mencarikan URL detailnya.
- **Kualitas korpus tim:** `PP-2022-55` articles tim mengandung nomor OCR (`3O` → sudah dinormalisasi ke `30`) dan hanya mencakup 74 dari 131 pasal — konsolidasi PP-55 sebagian; perlu re-ekstraksi teks penuh.
- `PMK-2022-112` & `UU-2023-6` punya heading yang belum sepenuhnya terpetakan (flag `rough_split`) — parser S4 akan disempurnakan bila domainnya diproses.
- Hasil konsolidasi di `data/consolidated/<target>.json` (teks TERBARU per pasal).

## Langkah berikutnya (G2)

- Manusia memeriksa sampel hasil parsing + konsolidasi terhadap sumber resmi,
  mis. tarif Pasal 17 UU PPh versi terkini.

*Agent berhenti di sini (G2).*

> **Koreksi Fase 3:** Pada audit Fase 3 ditemukan bahwa perubahan UU 7/2021 (HPP) belum masuk ke hasil konsolidasi Fase 2 di atas, dan `PMK-2024-69` ternyata berisi `PMK-2024-127` (plus 5 anomali metadata BPK lainnya). Seluruh perbaikan konsolidasi, metadata, dan gap detector dicatat lengkap di `reports/fase_3.md`.