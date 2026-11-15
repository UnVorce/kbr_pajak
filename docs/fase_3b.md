# Laporan Fase 3B — Perluasan Korpus Nasional, Tambahan Manual, & Yurisprudensi Pengadilan Pajak

> Eksekusi lanjutan untuk melengkapi seluruh bidang perpajakan nasional (`49` regulasi BPK + `4` PMK manual + `29` konsolidasi teks terbaru + `199` putusan Pengadilan Pajak SetPP).

## 1. Ringkasan Hasil Fase 3B

- **Crawl BPK otomatis (`scripts/fase3b_crawl_regulasi.py`):** **49 / 49** regulasi target berhasil diambil dengan `0` gagal dan verifikasi `page_document_id == target_id` (mencakup PPh 22/23/26/Final, penyusutan, DER, piutang tak tertagih, BUT, fintech, jasa konstruksi, obligasi/koperasi/saham/undian, Pengadilan Pajak, konsultan pajak, PPnBM, pajak rokok, KEK/KPBPB, hulu migas & batubara, serta Kepabeanan & Cukai).
- **Ingest 4 PDF pajak tambahan (`scripts/ingest_extra_regulasi.py`):**
  - `PMK-2024-118` (`NUMERIC`, 64 pasal / 1.673 provisions — Pembetulan, Keberatan, Pengurangan/Pembatalan)
  - `PMK-2024-136` (`NUMERIC`, 74 pasal / 1.100 provisions — Pajak Minimum Global / Pilar Dua)
  - `PMK-2010-2` (`NUMERIC`, 8 pasal / 13 provisions — Biaya Promosi; `sort=True` blok PDF)
  - `PMK-2025-114` (`NUMERIC`, 25 pasal / 232 provisions — Bantuan/Sumbangan/Zakat/Hibahan + metadata BPK)
  - *(Catatan: `UU Nomor 27 Tahun 2026.pdf` tentang Pelindungan Ketenagakerjaan dilewati karena bukan regulasi pajak.)*
- **Total dokumen regulasi kanonik:** **`142` dokumen** (**`80`** `active_for_rules: true` + **`29`** konsolidasi teks terbaru di `data/consolidated/`).
- **Audit kutipan S6 (`src/gaps.py`):** **`3.004` kutipan** terhadap **`343` dokumen unik**, ditambah deteksi otomatis pasal pencabutan (`revocations_from_corpus`):
  - `RESOLVED = 78`, `RESOLVED_EQUIVALENT = 187`, `IGNORED_OUT_OF_SCOPE = 56`, `DEFERRED_CK = 21`, `NOT_FOUND_AT_SOURCE = 1` (`PMK-2008-253`, satu-satunya PMK non-BPK yang belum tersedia PDF-nya), **`UNRESOLVED = 0`**.
- **Korpus Yurisprudensi Pengadilan Pajak (`scripts/download_putusan_pdf.py` + `scripts/ingest_putusan.py`):**
  - **`199` putusan SetPP Kemenkeu** dikonversi dari PDF ke JSON terstruktur di `knowledge_json/jurisprudence/` (`0` `ocr_suspect`), lengkap dengan `pokok_sengketa`, `pertimbangan_majelis`, `amar_kategori` (`KABUL_SELURUHNYA=112`, `KABUL_SEBAGIAN=33`, `TOLAK=53`, `LAINNYA=1`), `cited_regulations`, dan `jurisprudence_manifest.json`.
  - Distribusi klaster: `ppn=40`, `kup_gugatan=40`, `pph_badan=39`, `kepabeanan_cukai=30`, `pph_potput=25`, `pbb=25`.
- **Pengujian (`pytest -q`):** **`108 / 108` lulus**.

## 2. Arsip PDF Lokal (`fatih/download-pdf/`, di luar Git)

- `download-pdf/regulasi/` (`~442 MB`): arsip PDF regulasi + `index.json`.
- `download-pdf/putusan/` (`~200 MB`): `199` PDF putusan Pengadilan Pajak + `index.json`.
- *(Sisa opsional yang belum masuk: `PMK 253/PMK.03/2008` tentang PPh 22 barang sangat mewah — perubahannya `PMK 90/2015` & `PMK 92/2019` sudah ada.)*
