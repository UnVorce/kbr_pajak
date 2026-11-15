# Laporan Fase 1 — Korpus & Kualitas (v3.1)

> Mengambil dokumen bolong dari peraturan.bpk.go.id, konversi korpus
> tim ke JSON kanonik, enrich metadata, dedupe, dan cek kualitas (OCR).

## Ringkasan

- Total dokumen di registry: **56**
- Baru diambil dari BPK: **12**
- Pasal kosong (0 pasal): **9**
- Terindikasi OCR/pindaian: **0**
- Duplikat (hash sama): **1**
- Judul rusak (diperbaiki dari BPK): **4**
- Tidak ditemukan di BPK: **0**

## Dokumen baru yang diambil

| document_id | judul | status_sumber | pasal | flags |
|---|---|---|---|---|
| `UU-1983-7` | Undang-undang (UU)  Nomor 7 Tahun 1983 tentang Pajak Penghasilan | Berlaku | 36 | ok |
| `UU-1994-9` | Undang-undang (UU)  Nomor 9 Tahun 1994 tentang Perubahan atas Undang-U | Berlaku | 4 | ok,structure=AMENDING_ROMAN |
| `UU-2000-16` | Undang-undang (UU)  Nomor 16 Tahun 2000 tentang Perubahan Kedua atas U | Berlaku | 3 | ok,structure=AMENDING_ROMAN |
| `UU-2007-28` | Undang-undang (UU)  Nomor 28 Tahun 2007 tentang Perubahan Ketiga atas  | Berlaku | 1 | ok,structure=AMENDING_ROMAN |
| `UU-2009-16` | Undang-undang (UU)  Nomor 16 Tahun 2009 tentang Penetapan Peraturan Pe | Berlaku | 2 | ok |
| `UU-1994-12` | Undang-undang (UU)  Nomor 12 Tahun 1994 tentang Perubahan atas Undang- | Berlaku | 4 | ok,structure=AMENDING_ROMAN |
| `PMK-2022-112` | Peraturan Menteri Keuangan  Nomor 112/PMK.03/2022 Tahun 2022 tentang N | Berlaku | 8 | ok |
| `PMK-2010-68` | Peraturan Menteri Keuangan  Nomor 68/PMK.03/2010 Tahun 2010 tentang Ba | Berlaku | 9 | ok |
| `PMK-2013-197` | Peraturan Menteri Keuangan  Nomor 197/PMK.03/2013 Tahun 2013 tentang P | Berlaku | 2 | ok,structure=AMENDING_ROMAN |
| `PMK-2025-53` | Peraturan Menteri Keuangan  Nomor 53 Tahun 2025 tentang Perubahan atas | Berlaku | 2 | ok,structure=AMENDING_ROMAN |
| `PMK-2025-54` | Peraturan Menteri Keuangan  Nomor 54 Tahun 2025 tentang Perubahan Keti | Berlaku | 2 | ok,structure=AMENDING_ROMAN |
| `PMK-2026-1` | Peraturan Menteri Keuangan  Nomor 1 Tahun 2026 tentang Perubahan Keemp | Berlaku | 2 | ok,structure=AMENDING_ROMAN |

## Masalah kualitas

- `UU-2021-7`: garbled_title
- `UU-2021-7`: garbled_title, duplicate_of=UU-2021-7
- `PP-2022-55`: garbled_title
- `PP-2022-44`: garbled_title
- `PMK-2025-105`: zero_pasal
- `PER-DJP-2015-17-LAMPIRAN-1`: zero_pasal
- `PER-DJP-2015-17-LAMPIRAN-2`: zero_pasal
- `PER-DJP-2015-17-LAMPIRAN-3`: zero_pasal
- `PER-DJP-2015-17-LAMPIRAN-4`: zero_pasal
- `CORETAX-buku-manual-coretax-2024-seri-pembayaran`: zero_pasal
- `CORETAX-buku-manual-coretax-2024-taxpayer-account-management`: zero_pasal
- `CORETAX-kt-10-kebijakan-penghapusan-sanksi-administratif-sehubungan-denganimplementasi-coretax-djp`: zero_pasal
- `CORETAX-panduan-ringkas-coretax-djp`: zero_pasal
- `UU-1994-9`: structure=AMENDING_ROMAN
- `UU-2000-16`: structure=AMENDING_ROMAN
- `UU-2007-28`: structure=AMENDING_ROMAN
- `UU-1994-12`: structure=AMENDING_ROMAN
- `PMK-2013-197`: structure=AMENDING_ROMAN
- `PMK-2025-53`: structure=AMENDING_ROMAN
- `PMK-2025-54`: structure=AMENDING_ROMAN
- `PMK-2026-1`: structure=AMENDING_ROMAN

## Registry

Lihat `data/fase1_registry.csv` (56 baris).

## Langkah berikutnya

- Review G1: periksa sampel dokumen baru + status flags.
- Fase 2: parse struktur + konsolidasi-lite teks terbaru.

*Agent berhenti di sini (G1).*