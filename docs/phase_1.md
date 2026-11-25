# Laporan Fase 1 — Pilot Penjelajahan (S1 + S2)

> Format spec 12.9. **Status: berhenti di G1** — manusia memeriksa SEMUA dokumen
> dan relasi pilot terhadap sumber asli sebelum skala dinaikkan.

## 1. Apa yang dikerjakan

| Tugas Fase 1 (spec 12) | Status |
|---|---|
| Cek robots.txt & ketentuan penggunaan sumber | ✅ Selesai — ketiganya mengizinkan konten publik (detail di `config/sources.yaml`) |
| Inspeksi struktur halaman sumber primer (3–5 contoh) → fixture + selector | ✅ Selesai — 5 fixture HTML nyata di `tests/fixtures/`; selector BPK terdokumentasi |
| Implementasi `crawl.py` (S1) + `scope.py` (S2) | ✅ Selesai + 26 tes baru (total 63) |
| Dry-run dulu, lalu run 1 seed dengan batas 20 dokumen | ✅ Selesai — seed `UU-2021-7` (UU HPP), 20 dokumen, 0 gagal |
| Laporan pilot | ✅ Dokumen ini |

**Catatan ekstra (di luar daftar spec, demi kualitas pilot):** verifikasi 8 seed
DOMAIN_A langsung dari halaman resmi BPK (judul/status/URL tercatat di kartu
lingkup), perbaikan normalisasi ID untuk judul yang menyebut peraturan lain
(A4), pemetaan label relasi baru yang teramati (A2).

## 2. Berkas dan modul yang dibuat/diubah

- **Baru:** `src/crawl.py` (S1: Fetcher dengan jeda/retry/cache, parser halaman
  BPK, normalisasi relasi bentuk aktif, antrean resumable; S2: gerbang skor),
  `src/scope.py` (S2), `tests/test_crawl.py`, `tests/test_scope.py`,
  fixture `bpk__UU-2021-7`, `bpk__UU-1983-6`, `bpk__UU-2023-6`, `bpk__PP-2018-23`,
  `bpk__PP-2022-55` (HTML nyata).
- **Diubah:** `config/sources.yaml` (robots + selector BPK terverifikasi),
  `config/relation_map.yaml` (label teramati), `config/scope_cards/DOMAIN_A.yaml`
  (seed terverifikasi + `exclude_keywords`), `src/ids.py` (deteksi jenis/nomor
  posisi terawal), `ISSUES.md`, `data/kbr.sqlite` (data pilot).

## 3. Hasil tes otomatis

```
python3 -m pytest tests/ -q
63 passed in 0.64s
```

Baru di Fase 1: tanggal ("29 Oktober 2021" → ISO), normalisasi label relasi
(aktif/pasif, "Mencabut sebagian", "Menetapkan"), parser metadata & relasi dari
fixture nyata, bentuk aktif relasi, gerbang skor (termasuk topik keluar),
hierarki dokumen.

## 4. Metrik (Bagian 9) — kondisi setelah pilot

```
M1  Antrean tersisa            : 18 (6 milik DOMAIN_A, 12 UNASSIGNED) — batas pilot 20 tercapai; closure = Fase 2
M2  Kutipan belum terselesaikan: 0 baris (S6 belum berjalan — Fase 4)
M3  Selisih antar-sumber       : 0 (Kemenkeu/DJP belum direkonsiliasi — Fase 2)
M4  Rantai versi               : 0/0 (S9 — Fase 7)
M5  Konsolidasi                : N/A (Fase 7)
M6  Pelanggaran invarian       : I1=0 ✅  I2=0 ✅  I3=0 ✅
M7  FAILED/NEEDS_REVIEW        : tidak ada
M8  BOUNDARY/UNDECIDED         : 9 BOUNDARY, 109 placeholder UNDECIDED (putusan Fase 2)
```

## 5. Contoh keluaran nyata

**a. Dokumen IN_SCOPE (skor 1.0, subjek PERPAJAKAN + kata kunci judul):**
```
[IN_SCOPE] UU-1983-7 skor=1.0 status_sumber='Berlaku'
           'Undang-undang (UU) Nomor 7 Tahun 1983 tentang Pajak Penghasilan'
```

**b. Gerbang menolak topik keluar (skor 0.0, exclude_match):**
```
[BOUNDARY] UU-1983-8 skor=0.0 sinyal={'exclude_match': True}
           '... Nomor 8 Tahun 1983 tentang Pajak Pertambahan Nilai ...'   (PPN → BOUNDARY)
```

**c. Gerbang menolak non-pajak lewat relasi omnibus (skor 0.3):**
```
[BOUNDARY] UU-2020-11 skor=0.3 sinyal={'relation_to_in_scope': True}
           status_sumber='Tidak Berlaku' '... Nomor 11 Tahun 2020 tentang Cipta Kerja'
```

**d. Relasi dinormalkan ke bentuk AKTIF** ("Diubah dengan" → arah dibalik):
```
UU-2023-6 -[MENGUBAH]-> UU-2021-7      (di halaman HPP tertulis "Diubah dengan: UU 6/2023")
UU-2020-2 -[MENETAPKAN_PERPU]-> PERPU-2020-1
PERPU-2022-2 -[MENCABUT]-> UU-2020-11
```

**e. Kasus yang tadinya SALAH lalu diperbaiki (regresi A4):** halaman
"UU No. 6 Tahun 2023 tentang Penetapan PERPU No. 2 Tahun 2022" sempat terparse
sebagai `PERPU-2023-6`; kini benar `UU-2023-6` (tes `test_page_uu_2023_6_penetapan_perpu`).

## 6. Masalah dan ketidakpastian

Lihat `ISSUES.md` (A1–A6, status V1–V9). Ringkas:
- **A1/V3:** relasi metadata BPK terbukti tidak lengkap → beban kelengkapan di S6 (Fase 4).
- **A3:** blok "Putusan MK/Uji Materi" di halaman Detail belum dipetakan (Fase 4).
- **A6:** 109 placeholder `UNDECIDED` menunggu putusan gerbang di Fase 2.
- Struktur Kemenkeu & DJP belum diinspeksi (V2) — rekonsiliasi Fase 2.

## 7. Asumsi yang diambil

1. Skor gerbang deterministik: subjek +0.7, kata kunci judul +0.2, relasi
   langsung +0.3; `exclude_keywords` → skor 0 (BOUNDARY). Kalibrasi di Fase 2.
2. Bentuk relasi disimpan aktif; label pasif dibalik arah; "Mencabut sebagian"
   dipetakan ke MENCABUT dengan label asli di `evidence` (tidak membuat tipe baru).
3. Target relasi yang belum diambil halamannya dibuat baris placeholder
   (`DISCOVERED`/`UNDECIDED`) agar FK terpenuhi; metadata diisi saat diproses.
4. `status_sumber` ("Berlaku"/"Tidak Berlaku") disimpan apa adanya (P8).
5. Cache HTML 7 hari; jeda 1,5 detik; dry-run tidak menyentuh DB.

## 8. Usulan langkah berikutnya & menunggu persetujuan (G1)

**Manusia memeriksa SEMUA data pilot berikut terhadap `peraturan.bpk.go.id`:**

- 20 dokumen (Lampiran A): apakah klasifikasi IN_SCOPE/BOUNDARY masuk akal?
- 45 relasi antar-dokumen-pilot (Lampiran B): apakah arah/tipe benar?
- Putusan: apakah gerbang relevansi boleh dipakai untuk Fase 2 (closure)?

Setelah G1 → **Fase 2**: kalibrasi `thresholds`, closure penuh DOMAIN_A
(antrean 18 + seterusnya), rekonsiliasi Kemenkeu/DJP, review UNDECIDED/BOUNDARY.

## Lampiran A — 20 dokumen pilot (urut kunjungan)

| # | document_id | scope | status_sumber | subjek | asal | judul (singkat, tautan ke sumber) |
|---|---|---|---|---|---|---|
| 1 | `UU-2021-7` | IN_SCOPE | Berlaku | PERPAJAKAN | SEED | [Undang-undang (UU)  Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan P…](https://peraturan.bpk.go.id/Details/185162/uu-no-7-tahun-2021) |
| 2 | `UU-2023-6` | BOUNDARY | Berlaku | CIPTA KERJA | UU-2021-7 | [Undang-undang (UU)  Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pem…](https://peraturan.bpk.go.id/Details/246523/uu-no-6-tahun-2023) |
| 3 | `UU-2020-2` | BOUNDARY | Berlaku | APBD - APBN - KESEHATAN - PENGELOLAAN KEUANGAN NEGARA / DAERAH - BANTUAN, SUMBANGAN, BENCANA / KEBENCANAAN, DAN PENANGGULANGAN BENCANA - KEBIJAKAN PEMERINTAH - COVID-19 / CORONA | UU-2021-7 | [Undang-undang (UU)  Nomor 2 Tahun 2020 tentang Penetapan Peraturan Pem…](https://peraturan.bpk.go.id/Details/137323/uu-no-2-tahun-2020) |
| 4 | `PERPU-2020-1` | IN_SCOPE | Berlaku | APBD - APBN - KESEHATAN - PENGELOLAAN KEUANGAN NEGARA / DAERAH - BANTUAN, SUMBANGAN, BENCANA / KEBENCANAAN, DAN PENANGGULANGAN BENCANA - PERPAJAKAN - COVID-19 / CORONA | UU-2021-7 | [Peraturan Pemerintah Pengganti Undang-Undang (Perpu)  Nomor 1 Tahun 20…](https://peraturan.bpk.go.id/Details/135060/perpu-no-1-tahun-2020) |
| 5 | `UU-2009-42` | BOUNDARY | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 42 Tahun 2009 tentang Perubahan Ketiga Atas …](https://peraturan.bpk.go.id/Details/38787/uu-no-42-tahun-2009) |
| 6 | `UU-2009-16` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 16 Tahun 2009 tentang Penetapan Peraturan Pe…](https://peraturan.bpk.go.id/Details/38624/uu-no-16-tahun-2009) |
| 7 | `UU-2008-36` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 36 Tahun 2008 tentang Perubahan Keempat Atas…](https://peraturan.bpk.go.id/Details/39704/uu-no-36-tahun-2008) |
| 8 | `UU-2007-39` | BOUNDARY | Berlaku | OTONOMI DAERAH DAN PEMERINTAH DAERAH | UU-2021-7 | [Undang-undang (UU)  Nomor 39 Tahun 2007 tentang Perubahan atas Undang-…](https://peraturan.bpk.go.id/Details/39962/uu-no-39-tahun-2007) |
| 9 | `UU-1995-11` | BOUNDARY | Berlaku | BEA CUKAI, EKSPOR-IMPOR, KEPABEANAN | UU-2021-7 | [Undang-undang (UU)  Nomor 11 Tahun 1995 tentang Cukai…](https://peraturan.bpk.go.id/Details/46203/uu-no-11-tahun-1995) |
| 10 | `UU-1983-8` | BOUNDARY | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 8 Tahun 1983 tentang Pajak Pertambahan Nilai…](https://peraturan.bpk.go.id/Details/46990/uu-no-8-tahun-1983) |
| 11 | `UU-1983-7` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 7 Tahun 1983 tentang Pajak Penghasilan…](https://peraturan.bpk.go.id/Details/46988/uu-no-7-tahun-1983) |
| 12 | `UU-1983-6` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2021-7 | [Undang-undang (UU)  Nomor 6 Tahun 1983 tentang Ketentuan Umum dan Tata…](https://peraturan.bpk.go.id/Details/46986/uu-no-6-tahun-1983) |
| 13 | `UU-2007-28` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2009-16 | [Undang-undang (UU)  Nomor 28 Tahun 2007 tentang Perubahan Ketiga atas …](https://peraturan.bpk.go.id/Details/39916/uu-no-28-tahun-2007) |
| 14 | `UU-1994-9` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2009-16 | [Undang-undang (UU)  Nomor 9 Tahun 1994 tentang Perubahan atas Undang-U…](https://peraturan.bpk.go.id/Details/46230/uu-no-9-tahun-1994) |
| 16 | `UU-2000-17` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2008-36 | [Undang-undang (UU)  Nomor 17 Tahun 2000 tentang Perubahan Ketiga atas …](https://peraturan.bpk.go.id/Details/44968/uu-no-17-tahun-2000) |
| 17 | `UU-1994-10` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2008-36 | [Undang-undang (UU)  Nomor 10 Tahun 1994 tentang Perubahan atas Undang-…](https://peraturan.bpk.go.id/Details/46232/uu-no-10-tahun-1994) |
| 18 | `UU-1991-7` | IN_SCOPE | Berlaku | PERPAJAKAN | UU-2008-36 | [Undang-undang (UU)  Nomor 7 Tahun 1991 tentang  Perubahan atas Undang-…](https://peraturan.bpk.go.id/Details/46659/uu-no-7-tahun-1991) |
| 20 | `PERPU-2022-2` | BOUNDARY | Berlaku | CIPTA KERJA | UU-1983-7 | [Peraturan Pemerintah Pengganti Undang-Undang (Perpu)  Nomor 2 Tahun 20…](https://peraturan.bpk.go.id/Details/234926/perpu-no-2-tahun-2022) |
| 21 | `UU-2020-11` | BOUNDARY | Tidak Berlaku | PERS, POS, DAN PERIKLANAN - KEAGAMAAN, IBADAH, DAN PENYELENGGARAAN HAJI - KEHUTANAN DAN PERKEBUNAN - KESEHATAN - KETENAGAKERJAAN - KONSTRUKSI, SIPIL, ARSITEK, BANGUNAN, DAN INFRASTRUKTUR - PARIWISATA DAN KEBUDAYAAN - PENANAMAN MODAL DAN INVESTASI - PENDIDIKAN - PERIKANAN DAN KELAUTAN - PERLINDUNGAN USAHA, PERUSAHAAN, BADAN USAHA, PERDAGANGAN - PERTAMBANGAN MIGAS, MINERAL DAN ENERGI - PANGAN, PERTANIAN DAN PETERNAKAN - TELEKOMUNIKASI, INFORMATIKA, SIBER, DAN INTERNET - TRANSPORTASI DARAT / LAUT / UDARA - PERTAHANAN DAN KEAMANAN, MILITER - PERIZINAN, PELAYANAN PUBLIK - PERINDUSTRIAN - PERUMAHAN, PERMUKIMAN - CIPTA KERJA | UU-1983-7 | [Undang-undang (UU)  Nomor 11 Tahun 2020 tentang Cipta Kerja…](https://peraturan.bpk.go.id/Details/149750/uu-no-11-tahun-2020) |
| 25 | `UU-1970-12` | BOUNDARY | Tidak Berlaku | PENANAMAN MODAL DAN INVESTASI | UU-1983-7 | [Undang-undang (UU)  Nomor 12 Tahun 1970 tentang Perubahan dan Tambahan…](https://peraturan.bpk.go.id/Details/47914/uu-no-12-tahun-1970) |

## Lampiran B — 45 relasi antar dokumen pilot (bentuk aktif)

| from | tipe | to |
|---|---|---|
| `PERPU-2020-1` | MENGUBAH | `UU-1983-6` |
| `PERPU-2020-1` | MENGUBAH | `UU-2009-16` |
| `PERPU-2022-2` | MENCABUT | `UU-2020-11` |
| `PERPU-2022-2` | MENGUBAH | `UU-1983-6` |
| `PERPU-2022-2` | MENGUBAH | `UU-1983-7` |
| `PERPU-2022-2` | MENGUBAH | `UU-1983-8` |
| `UU-1983-7` | MENGUBAH | `UU-1970-12` |
| `UU-1991-7` | MENGUBAH | `UU-1983-7` |
| `UU-1994-10` | MENGUBAH | `UU-1983-7` |
| `UU-1994-10` | MENGUBAH | `UU-1991-7` |
| `UU-1994-9` | MENGUBAH | `UU-1983-6` |
| `UU-2000-17` | MENGUBAH | `UU-1983-7` |
| `UU-2000-17` | MENGUBAH | `UU-1991-7` |
| `UU-2000-17` | MENGUBAH | `UU-1994-10` |
| `UU-2007-28` | MENGUBAH | `UU-1983-6` |
| `UU-2007-28` | MENGUBAH | `UU-1994-9` |
| `UU-2007-39` | MENGUBAH | `UU-1995-11` |
| `UU-2008-36` | MENGUBAH | `UU-1983-7` |
| `UU-2008-36` | MENGUBAH | `UU-1991-7` |
| `UU-2008-36` | MENGUBAH | `UU-1994-10` |
| `UU-2008-36` | MENGUBAH | `UU-2000-17` |
| `UU-2009-16` | MENGUBAH | `UU-1983-6` |
| `UU-2009-16` | MENGUBAH | `UU-1994-9` |
| `UU-2009-16` | MENGUBAH | `UU-2007-28` |
| `UU-2009-42` | MENGUBAH | `UU-1983-8` |
| `UU-2020-11` | MENGUBAH | `UU-1983-6` |
| `UU-2020-11` | MENGUBAH | `UU-1983-7` |
| `UU-2020-11` | MENGUBAH | `UU-1983-8` |
| `UU-2020-2` | MENETAPKAN_PERPU | `PERPU-2020-1` |
| `UU-2021-7` | MENGUBAH | `PERPU-2020-1` |
| `UU-2021-7` | MENGUBAH | `UU-1983-6` |
| `UU-2021-7` | MENGUBAH | `UU-1983-7` |
| `UU-2021-7` | MENGUBAH | `UU-1983-8` |
| `UU-2021-7` | MENGUBAH | `UU-1995-11` |
| `UU-2021-7` | MENGUBAH | `UU-2007-39` |
| `UU-2021-7` | MENGUBAH | `UU-2008-36` |
| `UU-2021-7` | MENGUBAH | `UU-2009-16` |
| `UU-2021-7` | MENGUBAH | `UU-2009-42` |
| `UU-2021-7` | MENGUBAH | `UU-2020-2` |
| `UU-2023-6` | MENCABUT | `UU-2020-11` |
| `UU-2023-6` | MENETAPKAN_PERPU | `PERPU-2022-2` |
| `UU-2023-6` | MENGUBAH | `UU-1983-6` |
| `UU-2023-6` | MENGUBAH | `UU-1983-7` |
| `UU-2023-6` | MENGUBAH | `UU-1983-8` |
| `UU-2023-6` | MENGUBAH | `UU-2021-7` |

*Agent berhenti di sini (G1).*
