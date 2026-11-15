# Dokumentasi Struktur Data Full JSON — Pajak Penghasilan (PPh) Orang Pribadi

**Lokasi Repositori:** `kbr_pajak/knowledge_json/pph_op/`  
**Subfolder Data:** `kbr_pajak/knowledge_json/pph_op/full/`  
**Total File:** 59 File JSON  
**Tanggal Penyusunan:** 15 November 2026  
**Status:** Terverifikasi 100% Valid & Lengkap

---

## 1. Pendahuluan dan Ruang Lingkup

Repositori folder `pph_op/` ini disiapkan secara khusus untuk menampung seluruh berkas data **Full JSON** yang berkaitan langsung dengan domain **Pajak Penghasilan (PPh) Orang Pribadi** beserta regulasi pendukungnya (Pemeriksaan Pajak, Pengawasan Kepatuhan Coretax, P3B Internasional, Natura/Kenikmatan, UMKM, Hibah/Sumbangan, PPh Final atas Tanah/Bangunan, Bunga Deposito, Kripto, Hadiah Undian, dan Pesangon).

Seluruh data JSON di dalam folder ini mempertahankan prinsip **integritas yuridis penuh (*full legal fidelity*)**:
- Tidak ada teks yang diringkas (*no summarization*).
- Tidak ada teks yang diparafrase (*no paraphrasing*).
- Tidak ada penghilangan klausul, konsiderans, diktum, penjelasan, maupun lampiran (*no text loss*).
- Memuat teks mentah halaman fisik PDF secara utuh (*verbatim*) di dalam array `raw_pages`.

---

## 2. Pohon Struktur Direktori di `kbr_pajak`

Folder `pph_op` ditempatkan berdampingan secara modular dengan folder data kanonik yang sudah ada, sehingga tidak mengganggu pipeline Fase 1–3:

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology KBR
├── README.md                              # Dokumentasi arsitektur umum kbr_pajak
├── docs/                                  # Laporan evaluasi fase pipeline (fase_1, 2, 3)
└── knowledge_json/
    ├── documents/                         # 89 JSON kanonik tim (skema flat articles & provisions)
    ├── consolidated/                      # 15 JSON konsolidasi teks terbaru pasca amandemen
    ├── metadata/                          # manifest.json, citations.jsonl, gaps.json
    │
    └── pph_op/                            # <--- REPOSITORI KHUSUS PPH ORANG PRIBADI
        ├── STRUKTUR_PPH_OP_FULL.md        # File dokumentasi ini
        └── full/                          # Tempat 59 berkas Full JSON PPh OP
            ├── PP_34_2016_PPh_Pengalihan_Hak_Atas_Tanah_dan_Bangunan.json
            ├── PP_34_2017_PPh_Persewaan_Tanah_dan_Bangunan.json
            ├── PMK_66_2023_Perlakuan_PPh_Natura_dan_Kenikmatan.json
            ├── PMK_164_2023_Tata_Cara_Pengenaan_PPh_Peredaran_Bruto_Tertentu_dan_PKP.json
            ├── ...
            └── UU_7_2021_Harmonisasi_Peraturan_Perpajakan.json
```

---

## 3. Komposisi Korpus PPh OP (Total 59 File JSON)

Korpus di dalam subfolder `full/` terdiri dari dua kelompok file:
1. **21 Dokumen Tambahan (Hierarchical Tree Schema):** Regulasi pelengkap PPh OP hasil ekstraksi dan penataan struktur hierarkis mendalam (Bab, Bagian, Paragraf, Pasal, Ayat, Huruf, Angka, Lampiran, Penjelasan) yang dilengkapi penanda nomor halaman fisik sumber (`halaman_sumber`).
2. **38 Dokumen Pokok Sebelumnya (Article-Based Schema):** Kumpulan undang-undang pokok (UU HPP, UU KUP, UU PPh lama), peraturan pemerintah (PP 55/2022, PP 58/2023, PP 50/2022), PMK SIAP/Coretax (PMK 81/2024, PMK 168/2023), serta buku panduan manual Coretax 2024–2025.

---

## 4. Rincian Spesifikasi Skema Data

### 4.1. Skema Kelompok A: 21 Dokumen Tambahan (*Hierarchical Tree Schema*)

Kelompok ini menggunakan representasi pohon bersarang (*nested recursive tree*) di mana hierarki hukum tercermin langsung dari susunan `children`.

#### Properti Root (*Top-Level Keys*):
```json
{
  "document_id": "PP_34_2017",
  "nama_dokumen": "Peraturan Pemerintah Republik Indonesia Nomor 34 Tahun 2017 tentang Pajak Penghasilan atas Penghasilan dari Persewaan Tanah dan/atau Bangunan",
  "nomor_peraturan": "PP Nomor 34 Tahun 2017",
  "jenis_peraturan": "PP",
  "tahun": 2017,
  "nama_file_txt": "PP_34_2017_PPh_Persewaan_Tanah_dan_Bangunan.txt",
  "nama_file_pdf": "34TAHUN2017PP.pdf",
  "jumlah_halaman": 14,
  "metode_ekstraksi": "pymupdf_pdfplumber",
  "status_keterbacaan": "LENGKAP_TERBACA",
  "isi_dokumen": [ ... ],
  "raw_pages": [ ... ]
}
```

#### Struktur Elemen di Dalam `isi_dokumen`:
Setiap simpul di dalam `isi_dokumen` memiliki format seragam:
```json
{
  "jenis_elemen": "BAB | BAGIAN | PARAGRAF | PASAL | AYAT | HURUF | ANGKA | JUDUL | PEMBUKAAN | MENIMBANG | MENGINGAT | MEMUTUSKAN | MENETAPKAN | PENGESAHAN | PENJELASAN | LAMPIRAN | CATATAN_HALAMAN",
  "nomor": "1 | I | Kesatu | (1) | a | null",
  "judul": "Judul Bab/Bagian jika ada, atau null",
  "teks": "Teks isi lengkap atau kalimat pengantar klausul",
  "children": [ /* Array rekursif elemen turunan */ ],
  "halaman_sumber": 2 // Atau rentang [start_page, end_page]
}
```

**Karakteristik Kunci Skema Hierarkis:**
- **Preservasi Kalimat Pengantar:** Jika suatu Pasal memiliki Ayat, kalimat pengantar sebelum Ayat (1) disimpan pada atribut `teks` dari simpul `PASAL`. Demikian pula untuk Ayat yang memiliki rincian Huruf (`a.`, `b.`), kalimat pengantar ayat disimpan pada atribut `teks` simpul `AYAT`.
- **Keterlacakan Halaman Fisik (`halaman_sumber`):** Setiap butir hukum terikat langsung dengan nomor halaman fisik dokumen PDF aslinya.
- **Penanganan Kasus Khusus:** Halaman kosong dokumen asli dicatat sebagai elemen eksplisit `CATATAN_HALAMAN` (contoh pada `PP_34_2016` Halaman 5), dan lampiran tabel hasil scan dicatat sebagai elemen `LAMPIRAN` hasil OCR (contoh pada `PMK_16_2010` Halaman 10–11).

---

### 4.2. Skema Kelompok B: 38 Dokumen Pokok Sebelumnya (*Article-Based Schema*)

Kelompok ini menggunakan format blok pasal:
```json
{
  "metadata": {
    "document_name": "PP Nomor 55 Tahun 2022 tentang Penyesuaian Pengaturan di Bidang Pajak Penghasilan",
    "source_file": "PP_55_2022_Penyesuaian_Pengaturan_PPh.txt",
    "total_pages": 118,
    "total_pasal": 138,
    "document_type": "regulation",
    "extraction_notes": []
  },
  "total_pasal": 138,
  "raw_pages": [
    {
      "page": 1,
      "text": "..."
    }
  ],
  "articles": [
    {
      "pasal": "1",
      "full_text": "Dalam Peraturan Pemerintah ini yang dimaksud dengan: ..."
    }
  ]
}
```

---

### 4.3. Preservasi Halaman Mentah (`raw_pages`)

Seluruh 59 file JSON di folder `full/` memiliki array `raw_pages` yang mencatat teks mentah halaman per halaman secara *verbatim*:
- Berfungsi sebagai **acuan kebenaran mutlak (*ground-truth reference*)**.
- Memungkinkan audit visual cepat terhadap halaman PDF aslinya tanpa perlu membuka file PDF fisik.
- Menjamin tidak ada data yang hilang (*zero text loss*) meskipun pada level parser struktural terdapat perbedaan segmentasi.

---

## 5. Panduan Pemetaan (*Bridge Guide*) ke Format Kanonik `kbr_pajak`

Bagi modul reasoner atau pengolah ontologi tim yang mengharapkan skema kanonik `kbr_pajak/knowledge_json/documents/` (dengan atribut `articles` dan `provisions` ber-locator), berikut adalah panduan transformasi otomatis:

### 5.1. Aturan Penamaan ID Kanonik
Ubah pemisah *underscore* (`_`) menjadi tanda hubung strip (`-`):
- `PP_34_2017` $ightarrow$ `PP-2017-34`
- `PMK_66_2023` $ightarrow$ `PMK-2023-66`
- `PER_7_PJ_2025` $ightarrow$ `PER-DJP-2025-7`

### 5.2. Aturan Pembentukan Locator
Gunakan format locator standar `kbr_pajak`:
| Tingkat Elemen | Format Locator Standar | Contoh |
|---|---|---|
| **Pasal** | `{DOC_ID}#BT/{nomor_pasal}` | `PP-2017-34#BT/2` |
| **Ayat** | `{DOC_ID}#BT/{nomor_pasal}/({nomor_ayat})` | `PP-2017-34#BT/2/(1)` |
| **Huruf** | `{DOC_ID}#BT/{nomor_pasal}/({nomor_ayat})/{huruf}` | `PP-2017-34#BT/2/(1)/a` |
| **Angka** | `{DOC_ID}#BT/{nomor_pasal}/({nomor_ayat})/{huruf}/{angka}` | `PP-2017-34#BT/2/(1)/a/1` |
| **Bab (Section)** | `{DOC_ID}#BT/BAB_{nomor_bab}` | `PP-2017-34#BT/BAB_I` |

### 5.3. Algoritma Meratakan (*Flattening*) `isi_dokumen` menjadi `provisions`
Untuk mentransformasikan pohon rekursif `children` menjadi array datar `provisions`:
1. Buat simpul `provision` untuk elemen saat ini dengan atribut:
   - `level`: nilai dari `jenis_elemen` (`"PASAL"`, `"AYAT"`, `"HURUF"`, dst.).
   - `nomor`: nilai dari `nomor`.
   - `locator`: string locator yang diakumulasikan dari path hierarki.
   - `parent`: locator dari elemen induk langsung (atau `null` jika berada di tingkat teratas).
   - `text`: isi dari `teks`.
   - `heading`: isi dari `judul` atau string kosong `""`.
   - `role`: `"DEFINITION"` (bila Pasal 1 / Ketentuan Umum) atau `"SUBSTANTIVE"`.
   - `ord`: integer urutan penelusuran (*depth-first order*).
2. Lakukan rekursi pada setiap elemen di dalam array `children`.

---

## 6. Tabel Inventaris Lengkap 59 File JSON di `pph_op/full/`

### 6.1. Kelompok Dokumen Tambahan (21 File — Hierarchical Tree)

| No | File JSON | ID Dokumen | Regulasi & Tahun | Hal | Elemen Terpetakan | Ukuran |
|:---:|---|---|---|:---:|:---:|---:|
| 1 | `PER_11_PJ_2025_Ketentuan_Pelaporan_PPh_PPN_PPnBM_Bea_Meterai_SIAP.json` | `PER_11_2025` | PER-11/PJ/2025 (2025) | 119 | 8 | 624,097 bytes |
| 2 | `PER_11_PJ_2026_Penyedia_Printer_Meterai_Teraan_Digital.json` | `PER_11_2026` | PER-11/PJ/2026 (2026) | 78 | 16 | 295,178 bytes |
| 3 | `PER_7_PJ_2025_Petunjuk_Pelaksanaan_Administrasi_NPWP_PKP_PBB_Coretax.json` | `PER_7_2025` | PER-7/PJ/2025 (2025) | 89 | 16 | 490,769 bytes |
| 4 | `PMK_111_2025_Pengawasan_Kepatuhan_Wajib_Pajak.json` | `PMK_111_2025` | PMK Nomor 111 Tahun 2025 (2025) | 91 | 10 | 386,344 bytes |
| 5 | `PMK_112_2025_Tata_Cara_Penerapan_P3B.json` | `PMK_112_2025` | PMK Nomor 112 Tahun 2025 (2025) | 51 | 13 | 321,410 bytes |
| 6 | `PMK_114_2025_Perlakuan_PPh_Bantuan_Sumbangan_Zakat_Harta_Hibahan.json` | `PMK_114_2025` | PMK Nomor 114 Tahun 2025 (2025) | 33 | 13 | 212,000 bytes |
| 7 | `PMK_15_2025_Pemeriksaan_Pajak.json` | `PMK_15_2025` | PMK Nomor 15 Tahun 2025 (2025) | 204 | 20 | 936,945 bytes |
| 8 | `PMK_164_2023_Tata_Cara_Pengenaan_PPh_Peredaran_Bruto_Tertentu_dan_PKP.json` | `PMK_164_2023` | PMK Nomor 164 Tahun 2023 (2023) | 47 | 9 | 219,595 bytes |
| 9 | `PMK_16_2010_Tata_Cara_Pemotongan_PPh21_Pesangon_Pensiun_THT_JHT.json` | `PMK_16_2010` | PMK Nomor 16/PMK.03/2010 (2010) | 11 | 25 | 57,519 bytes |
| 10 | `PMK_192_PMK.03_2018_Pengkreditan_Pajak_Luar_Negeri.json` | `PMK_192_2018` | PMK Nomor 192/PMK.03/2018 (2018) | 26 | 17 | 113,157 bytes |
| 11 | `PMK_212_PMK.03_2018_PPh_Bunga_Deposito_Tabungan_Diskonto_SBI.json` | `PMK_212_2018` | PMK Nomor 212/PMK.03/2018 (2018) | 11 | 3 | 23,991 bytes |
| 12 | `PMK_37_2025_Penunjukan_Pihak_Lain_Pemungut_PPh.json` | `PMK_37_2025` | PMK Nomor 37 Tahun 2025 (2025) | 23 | 13 | 137,864 bytes |
| 13 | `PMK_50_2025_PPN_dan_PPh_Transaksi_Perdagangan_Aset_Kripto.json` | `PMK_50_2025` | PMK Nomor 50 Tahun 2025 (2025) | 21 | 12 | 162,729 bytes |
| 14 | `PMK_66_2023_Perlakuan_PPh_Natura_dan_Kenikmatan.json` | `PMK_66_2023` | PMK Nomor 66 Tahun 2023 (2023) | 52 | 7 | 241,335 bytes |
| 15 | `PP_123_2015_Perubahan_PP_131_2000_PPh_Bunga_Deposito_Tabungan_SBI.json` | `PP_123_2015` | PP Nomor 123 Tahun 2015 (2015) | 7 | 9 | 24,555 bytes |
| 16 | `PP_131_2000_PPh_Bunga_Deposito_Tabungan_Diskonto_SBI.json` | `PP_131_2000` | PP Nomor 131 Tahun 2000 (2000) | 10 | 16 | 40,099 bytes |
| 17 | `PP_22_2024_Perlakuan_PPh_Penempatan_DHE_SDA.json` | `PP_22_2024` | PP Nomor 22 Tahun 2024 (2024) | 19 | 11 | 60,778 bytes |
| 18 | `PP_34_2016_PPh_Pengalihan_Hak_Atas_Tanah_dan_Bangunan.json` | `PP_34_2016` | PP Nomor 34 Tahun 2016 (2016) | 26 | 26 | 83,442 bytes |
| 19 | `PP_34_2017_PPh_Persewaan_Tanah_dan_Bangunan.json` | `PP_34_2017` | PP Nomor 34 Tahun 2017 (2017) | 14 | 16 | 49,505 bytes |
| 20 | `PP_42_1994_PPh_Atas_Hadiah_Undian.json` | `PP_42_1994` | PP Nomor 42 Tahun 1994 (1994) | 5 | 12 | 17,211 bytes |
| 21 | `PP_68_2009_Tarif_PPh21_Pesangon_Pensiun_THT_JHT_Sekaligus.json` | `PP_68_2009` | PP Nomor 68 Tahun 2009 (2009) | 14 | 28 | 52,949 bytes |

### 6.2. Kelompok Dokumen Pokok & Panduan Coretax (38 File — Article-Based)

| No | File JSON | Nama Regulasi / Panduan | Hal | Pasal / Butir | Ukuran |
|:---:|---|---|:---:|:---:|---:|
| 1 | `KOMPILASI_SDSN_UU_Perpajakan_Edisi_2023.json` | SDSN Edisi 2023 - Susunan Dalam Satu Naskah Undang-Undang Perpajakan | 426 | 0 | 732,169 bytes |
| 2 | `KT-10_2025_Penghapusan_Sanksi_Administratif_Coretax.json` | Keterangan Tertulis KT-10/2025 tentang Kebijakan Penghapusan Sanksi Administratif Sehubungan dengan Implementasi Coretax DJP | 2 | 0 | 5,339 bytes |
| 3 | `PANDUAN_Coretax_2024_Pelaporan_SPT_Tahunan_PPh_OP.json` | Buku Manual Coretax 2024 - Modul Pelaporan SPT Tahunan PPh Orang Pribadi (Seri Pelaporan SPT, Edisi 20240909) | 106 | 0 | 102,954 bytes |
| 4 | `PANDUAN_Coretax_2024_Pendaftaran_WP_Orang_Pribadi.json` | Buku Manual Coretax 2024 - Modul Pendaftaran Wajib Pajak Orang Pribadi (Seri Registrasi, Edisi 20240924) | 28 | 0 | 29,899 bytes |
| 5 | `PANDUAN_Coretax_2024_Seri_Bukti_Potong_PPh.json` | Buku Manual Coretax 2024 - Bukti Potong Pajak Penghasilan (PPh) dalam Coretax DJP (Versi 1.0 - 3 Februari 2025) | 9 | 0 | 7,700 bytes |
| 6 | `PANDUAN_Coretax_2024_Seri_Pembayaran.json` | Buku Manual Coretax 2024 - Seri Pembayaran | 49 | 0 | 51,828 bytes |
| 7 | `PANDUAN_Coretax_2024_Taxpayer_Account_Management.json` | Buku Manual Coretax 2024 - Taxpayer Account Management | 25 | 0 | 29,312 bytes |
| 8 | `PANDUAN_Coretax_2025_Instansi_Pemerintah.json` | Buku Panduan Coretax bagi Instansi Pemerintah 2025 | 295 | 0 | 233,652 bytes |
| 9 | `PANDUAN_Ringkas_Coretax_DJP_2025.json` | Panduan Ringkas Coretax DJP Versi 1.0 - 14 Januari 2025 | 44 | 0 | 27,281 bytes |
| 10 | `PERPRES_40_2018_Pembaruan_Sistem_Administrasi_Perpajakan.json` | Perpres Nomor 40 Tahun 2018 tentang Pembaruan Sistem Administrasi Perpajakan | 18 | 21 | 81,327 bytes |
| 11 | `PER_17_PJ_2015_Lampiran_III_NPPN_WP_Badan.json` | Lampiran III PER-17/PJ/2015 - Daftar Persentase NPPN untuk WP Badan | 343 | 0 | 645,384 bytes |
| 12 | `PER_17_PJ_2015_Lampiran_II_NPPN_WP_OP_Tanpa_Pembukuan.json` | Lampiran II PER-17/PJ/2015 - Daftar Persentase NPPN untuk WP OP Tanpa Pembukuan | 360 | 0 | 657,008 bytes |
| 13 | `PER_17_PJ_2015_Lampiran_IV_Contoh_Pemakaian_Norma.json` | Lampiran IV PER-17/PJ/2015 - Contoh Pemakaian Norma | 2 | 0 | 2,468 bytes |
| 14 | `PER_17_PJ_2015_Lampiran_I_NPPN_WP_OP.json` | Lampiran I PER-17/PJ/2015 - Daftar Persentase NPPN untuk WP Orang Pribadi | 380 | 0 | 645,331 bytes |
| 15 | `PER_17_PJ_2015_Norma_Penghitungan_Penghasilan_Neto.json` | PER-17/PJ/2015 tentang Norma Penghitungan Penghasilan Neto | 4 | 9 | 22,378 bytes |
| 16 | `PMK_101_PMK.010_2016_Penyesuaian_Besarnya_PTKP.json` | PMK Nomor 101/PMK.010/2016 tentang Penyesuaian Besarnya Penghasilan Tidak Kena Pajak | 4 | 5 | 8,206 bytes |
| 17 | `PMK_105_2025_PPh21_DTP_Stimulus_Ekonomi_TA2026.json` | PMK Nomor 105 Tahun 2025 tentang Pajak Penghasilan Pasal 21 atas Penghasilan Tertentu yang Ditanggung Pemerintah dalam Rangka Stimulus Ekonomi Tahun Anggaran 2026 | 43 | 17 | 189,681 bytes |
| 18 | `PMK_109_PMK.03_2018_Pengadaan_Barang_Jasa_Pembaruan_SAP.json` | PMK Nomor 109/PMK.03/2018 tentang Pengadaan Barang dan/atau Jasa untuk Pembaruan Sistem Administrasi Perpajakan | 33 | 30 | 160,102 bytes |
| 19 | `PMK_121_PMK.03_2019_Pengadaan_Jasa_Konsultansi_Pembaruan_SAP.json` | PMK Nomor 121/PMK.03/2019 tentang Pengadaan Jasa Konsultansi Badan Usaha untuk Pembaruan Sistem Administrasi Perpajakan | 56 | 15 | 327,208 bytes |
| 20 | `PMK_151_PMK.03_2018_Pengadaan_Agen_Pengadaan_Pembaruan_SAP.json` | PMK Nomor 151/PMK.03/2018 tentang Pengadaan Agen Pengadaan untuk Pembaruan Sistem Administrasi Perpajakan serta Standar Dokumen Pengadaan dan Standar Dokumen Kontrak | 16 | 19 | 80,074 bytes |
| 21 | `PMK_168_2023_Pemotongan_Pajak_Pekerjaan_Jasa_Orang_Pribadi.json` | PMK Nomor 168 Tahun 2023 tentang Petunjuk Pelaksanaan Pemotongan Pajak atas Penghasilan sehubungan dengan Pekerjaan, Jasa, atau Kegiatan Orang Pribadi | 69 | 50 | 427,271 bytes |
| 22 | `PMK_1_2026_Perubahan_Keempat_PMK_81_2024_Ketentuan_Perpajakan_SIAP.json` | PMK Nomor 1 Tahun 2026 tentang Perubahan Keempat atas Peraturan Menteri Keuangan Nomor 81 Tahun 2024 tentang Ketentuan Perpajakan dalam Rangka Pelaksanaan Sistem Inti Administrasi Perpajakan | 35 | 11 | 202,472 bytes |
| 23 | `PMK_56_PMK.03_2019_Pengadaan_Sistem_Informasi_Pembaruan_SAP.json` | PMK Nomor 56/PMK.03/2019 tentang Pengadaan Sistem Informasi untuk Pembaruan Sistem Administrasi Perpajakan | 58 | 45 | 331,485 bytes |
| 24 | `PMK_6_2026_PPh21_Pemagangan_Lulusan_PT_DTP_TA2026.json` | PMK Nomor 6 Tahun 2026 tentang Pajak Penghasilan Pasal 21 atas Penghasilan yang Diterima dan/atau Diperoleh Peserta Pemagangan Lulusan Perguruan Tinggi yang Ditanggung Pemerintah Tahun Anggaran 2026 | 14 | 15 | 69,454 bytes |
| 25 | `PMK_71_2026_Perubahan_PMK_118_2024_Pembetulan_Keberatan_Pengurangan_Penghapusan_Pembatalan.json` | PMK Nomor 71 Tahun 2026 tentang Perubahan atas Peraturan Menteri Keuangan Nomor 118 Tahun 2024 tentang Tata Cara Pembetulan, Keberatan, Pengurangan, Penghapusan, dan Pembatalan di Bidang Perpajakan | 265 | 11 | 1,654,728 bytes |
| 26 | `PMK_80_2023_Tata_Cara_Penerbitan_Surat_Ketetapan_Pajak_dan_Surat_Tagihan_Pajak.json` | PMK Nomor 80 Tahun 2023 tentang Tata Cara Penerbitan Surat Ketetapan Pajak dan Surat Tagihan Pajak | 36 | 39 | 265,418 bytes |
| 27 | `PMK_81_2024_Ketentuan_Perpajakan_SIAP.json` | PMK Nomor 81 Tahun 2024 tentang Ketentuan Perpajakan dalam Rangka Pelaksanaan Sistem Inti Administrasi Perpajakan | 642 | 603 | 5,320,197 bytes |
| 28 | `PP_20_2026_Perubahan_atas_PP_55_2022.json` | PP Nomor 20 Tahun 2026 tentang Perubahan atas PP Nomor 55 Tahun 2022 | 23 | 12 | 80,646 bytes |
| 29 | `PP_45_2019_Perubahan_atas_PP_94_2010.json` | PP Nomor 45 Tahun 2019 tentang Perubahan atas PP Nomor 94 Tahun 2010 | 9 | 14 | 25,511 bytes |
| 30 | `PP_50_2022_Tata_Cara_Pelaksanaan_Hak_dan_Pemenuhan_Kewajiban_Perpajakan.json` | PP Nomor 50 Tahun 2022 tentang Tata Cara Pelaksanaan Hak dan Pemenuhan Kewajiban Perpajakan | 116 | 127 | 539,318 bytes |
| 31 | `PP_55_2022_Penyesuaian_Pengaturan_PPh.json` | PP Nomor 55 Tahun 2022 tentang Penyesuaian Pengaturan di Bidang Pajak Penghasilan | 118 | 138 | 522,587 bytes |
| 32 | `PP_58_2023_Tarif_Pemotongan_PPh21_Pekerjaan_Jasa_Kegiatan_WP_OP.json` | PP Nomor 58 Tahun 2023 tentang Tarif Pemotongan Pajak Penghasilan Pasal 21 atas Penghasilan Sehubungan dengan Pekerjaan, Jasa, atau Kegiatan Wajib Pajak Orang Pribadi | 25 | 10 | 78,454 bytes |
| 33 | `PP_78_2019_Fasilitas_PPh_Penanaman_Modal.json` | PP Nomor 78 Tahun 2019 tentang Fasilitas Pajak Penghasilan untuk Penanaman Modal di Bidang-bidang Usaha Tertentu dan/atau di Daerah-daerah Tertentu | 81 | 28 | 194,701 bytes |
| 34 | `PP_94_2010_Penghitungan_PKP_Pelunasan_PPh_Tahun_Berjalan.json` | PP Nomor 94 Tahun 2010 tentang Penghitungan Penghasilan Kena Pajak dan Pelunasan Pajak Penghasilan dalam Tahun Berjalan | 34 | 70 | 137,852 bytes |
| 35 | `UU_12_2011_Pembentukan_Peraturan_Perundang_undangan.json` | UU_12_2011_Pembentukan_Peraturan_Perundang_undangan | 1 | 209 | 862,663 bytes |
| 36 | `UU_6_1983_Ketentuan_Umum_dan_Tata_Cara_Perpajakan.json` | UU Nomor 6 Tahun 1983 tentang Ketentuan Umum dan Tata Cara Perpajakan | 51 | 100 | 225,165 bytes |
| 37 | `UU_6_2023_Penetapan_Perppu_Cipta_Kerja.json` | UU Nomor 6 Tahun 2023 tentang Penetapan Perppu Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-Undang | 1127 | 2495 | 4,375,486 bytes |
| 38 | `UU_7_2021_Harmonisasi_Peraturan_Perpajakan.json` | UU Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan | 224 | 112 | 966,343 bytes |

---

## 7. Kesimpulan

Folder `kbr_pajak/knowledge_json/pph_op/` kini menjadi repositori resmi dan lengkap untuk data peraturan perpajakan Pajak Penghasilan Orang Pribadi. Dengan adanya dokumentasi ini, pengembang sistem KBR, pembangun ontologi OWL, maupun tim pengembang aturan reasoning dapat dengan mudah memahami struktur data, mengakses teks per halaman, serta menjembatani data ke format kanonik sistem kapan pun diperlukan.
