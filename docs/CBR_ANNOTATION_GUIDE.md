# Panduan Anotasi CBR (B4.1)

Dokumen ini untuk **Pilar 3 (kurator hukum)** dan praktisi yang menganotasi 60 putusan
Pengadilan Pajak. Tujuannya: mengisi field yang belum ada di korpus sehingga formula CBR
penuh PRD §8 dapat dijalankan.

> **Bukan pekerjaan coding.** Semua perintah di bawah sudah disiapkan backend.
> **Jangan mengarang label** di luar taksonomi — validator akan menolak.

---

## 1. Ruang lingkup

| Item | Nilai |
|---|---|
| Kasus dianotasi | **60** (10 per klaster) |
| Klaster | `pph_badan`, `pph_potput`, `kup_gugatan`, `ppn`, `kepabeanan_cukai`, `pbb` |
| Distribusi amar (worksheet) | 21 `TOLAK`, 15 `KABUL_SEBAGIAN`, 24 `KABUL_SELURUHNYA` |
| Field wajib | `jenis_koreksi`, `fakta_kunci`, `rasio_decidendi`, `rezim_hukum`, `annotator` |
| Field kondisional | `argumen_menang` (wajib bila amar `KABUL_*`), `bukti_penentu`, `quotes_json` |

Berkas kerja:

```text
config/cbr_taxonomy.json                                   # taksonomi (jangan diubah tanpa versi baru)
data/jurisprudence/annotations/worksheet_60.csv            # 60 kasus, kolom anotasi kosong
data/jurisprudence/annotations/worksheet_60_meta.json      # ringkasan seleksi
```

---

## 2. Taksonomi

Semua kode ada di `config/cbr_taxonomy.json`. Anotator **wajib memilih minimal satu kode daun**
(kode yang tidak punya anak), boleh menambah kode induk untuk konteks.

- `jenis_koreksi`: hirarki 2 level (contoh `KOR_OMZET` → `KOR_OMZET_EKUALISASI`, `KOR_OMZET_TRANSFER_PRICING`).
- `fakta_kunci`: fakta determinan (pembukuan, rekonsiliasi bank, daftar nominatif, bukti potong, saksi/ahli, dll.).
- `bukti_penentu`: jenis alat bukti yang benar-benar dipertimbangkan majelis.
- `rezim_hukum`: `AKTIF` / `DIUBAH` / `DICABUT` / `PERLU_VERIFIKASI`.
- `amar`: `KABUL_SELURUHNYA` / `KABUL_SEBAGIAN` / `TOLAK` / `TIDAK_DAPAT_DITERIMA` / `LAINNYA` / `BATAL`.

Bila taksonomi terasa tidak memadai: **catat di kolom `catatan`** dan ajukan usulan kode baru.
Jangan memakai kode yang belum ada.

---

## 2a. Pembagian tugas & jadwal

Lihat **[`CBR_ANNOTATION_CHECKLIST.md`](CBR_ANNOTATION_CHECKLIST.md)**. Ringkasnya:

| Peran | Kasus | Berkas |
|---|---|---|
| Anotator A (Pilar 3) | 38 (30 utama + 8 overlap) | `assignment_A.csv` |
| Anotator B (praktisi) | 37 (30 utama + 7 overlap) | `assignment_B.csv` |
| Reviewer | 60 (sign-off) | `worksheet_60.csv` |

15 kasus overlap dikerjakan dua orang secara independen untuk menghitung Cohen's κ.

## 3. Cara mengisi worksheet

Buka `worksheet_60.csv` di spreadsheet. Kolom `pokok_sengketa` dan `pertimbangan_majelis`
sudah terisi sebagai konteks.

| Kolom | Isi | Aturan |
|---|---|---|
| `jenis_koreksi` | satu/lebih kode, dipisah `;` | minimal 1 kode daun |
| `fakta_kunci` | satu/lebih kode, dipisah `;` | minimal 1 kode daun |
| `rasio_decidendi` | 1–2 kalimat **kutipan persis** dari `pertimbangan_majelis` | **substring persis** (validator menolak parafrase) |
| `argumen_menang` | kutipan persis alasan pemohon menang | wajib untuk amar `KABUL_*` |
| `bukti_penentu` | kode bukti, dipisah `;` | opsional |
| `rezim_hukum` | salah satu nilai | wajib |
| `quotes_json` | `[{"field":"rasio_decidendi","halaman":4,"quote":"..."}]` | opsional; tiap kutipan divalidasi |
| `catatan` | ketidakpastian / usulan taksonomi | opsional |
| `annotator` / `reviewer` | inisial/nama | wajib `annotator` |

**Contoh baris terisi**

```csv
...;KOR_OMZET;KOR_OMZET_EKUALISASI;FK_ADA_PEMBUKUAN;FK_REKONSILIASI_BANK;"bahwa koreksi peredaran bruto tidak dapat dibuktikan oleh Terbanding karena rekonsiliasi bank menunjukkan jumlah yang sama dengan SPT";...
```

---

## 4. Validasi & impor

```bash
# cek progres + error (boleh dijalankan kapan saja)
python3 scripts/validate_cbr_annotations.py

# wajib 60/60 sebelum dianggap selesai
python3 scripts/validate_cbr_annotations.py --strict

# uji kesepakatan antar-anotator (15 kasus double-annotate)
python3 scripts/validate_cbr_annotations.py --second worksheet_60_annotatorB.csv

# impor ke bentuk kanonik + rebuild indeks CBR
python3 scripts/import_cbr_annotations.py --strict
```

Hasil impor:
- `data/jurisprudence/annotations/annotations_v1.json`
- `backend/cbr_index.json` (field anotasi menempel pada 60 kasus)

Raw JSON di `data/jurisprudence/*.json` **tidak diubah**.

---

## 5. Mutu & gerbang

| Metrik | Target |
|---|---|
| Kelengkapan | 60/60 kasus, 0 error validator |
| Kesepakatan antar-anotator (15 kasus) | Cohen's κ ≥ 0,60 untuk `jenis_koreksi` & `fakta_kunci` |
| Kutipan verbatim | 100% `rasio_decidendi`/`argumen_menang` substring persis |
| Relevansi CBR (setelah B4.3) | Precision@3 ≥ 0,60 pada 20 kueri praktisi |

Bila κ < 0,60: adakan adjudikasi taksonomi sebelum melanjutkan, jangan memaksakan label.

---

## 6. Setelah anotasi selesai (B4.3 — backend)

1. Aktifkan formula penuh: `0,20 klaster + 0,30 WuPalmer(jenis_koreksi) + 0,25 Jaccard(fakta_kunci) + 0,10 Jaccard(regulasi) + 0,15 BM25` + penalti `0,85` untuk regulasi yang telah dicabut/diubah.
2. Evaluasi 20 kueri praktisi (`Precision@3`, `nDCG@3`).
3. Perbarui label UI dari "CBR tahap 1" menjadi "CBR penuh".

Sebelum itu, API tetap menyajikan **CBR tahap 1** dan UI wajib menyebutkannya.
