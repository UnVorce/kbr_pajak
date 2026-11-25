# Laporan Fase 0 — Fondasi dan Skema

> Format sesuai spec 12.9. **Status: berhenti di G0** — menunggu persetujuan tim.

## 1. Apa yang dikerjakan

| Tugas Fase 0 (spec 12) | Status |
|---|---|
| Buat struktur proyek (Bagian 4), `AGENTS.md`, `ISSUES.md` | ✅ Selesai |
| Tulis DDL SQLite untuk semua tabel Bagian 5 dan `db.py` | ✅ Selesai |
| Implementasi `ids.py` (normalisasi `document_id` dan locator) beserta tes dengan contoh nyata | ✅ Selesai |
| Buat template `scope_cards/` dan `crawl.yaml` (nilai default, tanpa seed) | ✅ Selesai (+ template `sources.yaml`, `relation_map.yaml`, `patterns_amendment.yaml`, `model_config.yaml`) |
| Buat `report.py` kerangka (menghitung metrik M1–M8 pada DB kosong) | ✅ Selesai |

Catatan: root proyek = folder `PROJEK_KBR` (bukan subfolder `kbr-extraction/`),
karena `KBR_Extraction_Spec.md` sudah berada di sini (lihat ISSUES #1).

## 2. Berkas dan modul yang dibuat atau diubah

**Dibuat:**
- `AGENTS.md` — ringkasan aturan kerja (Bagian 0) dan prinsip P1–P11 (Bagian 2).
- `ISSUES.md` — V1–V9 + 10 keputusan/pertanyaan Fase 0.
- `src/__init__.py`, `src/ids.py`, `src/db.py`, `src/report.py`.
- `tests/__init__.py`, `tests/test_ids.py`, `tests/test_db.py`, `tests/fixtures/README.md`.
- `conftest.py` — agar `import src.*` jalan dari pytest.
- `config/sources.yaml`, `config/crawl.yaml`, `config/relation_map.yaml`,
  `config/patterns_amendment.yaml`, `config/model_config.yaml`.
- `config/scope_cards/DOMAIN_A.yaml` (pilot, usulan agent), `DOMAIN_B.yaml` &
  `DOMAIN_C.yaml` (stub).
- `data/` beserta subfolder (`cache/html`, `cache/pdf_tmp`, `text`, `chunks/`,
  `llm_results/`, `validation/`, `review/`, `manifests/`) + `data/README.md`.
- `data/kbr.sqlite` — skema dibuat, masih kosong.
- `notebooks/README.md` (notebook Colab dibuat di Fase 5).
- `reports/source_coverage.md` — hasil `report.py` (DB kosong).

**Diubah:**
- `kbr_knowledge_acquisition_plan.md` — ditulis ulang agar selaras spec
  (Hermes/Ollama/Sheets/PostgreSQL → OpenCode/Colab/SQLite/JSONL).

**Tidak diubah:** `KBR_Extraction_Spec.md` (sumber kebenaran tunggal).

## 3. Hasil tes otomatis

```
python3 -m pytest tests/ -q
37 passed in 0.43s
```

Cakupan tes:
- `test_ids.py` (33 tes): kasus nyata dari spec 5.1 — "UU No. 7 Tahun 1983",
  "Undang-Undang Nomor 7 Tahun 1983", "PP No. 55/2022", "PMK-81/PMK.03/2024",
  "PER-14/PJ/2013", "14/PUU-XX/2022", Perpu, Perpres; idempotensi; kasus
  negatif (UUD 1945, teks bukan rujukan, jenis tidak dikenal, teks kosong);
  build/parse locator + round-trip + pasal sisipan "4A" + bagian PENJELASAN.
- `test_db.py` (4 tes): semua tabel ada, versi skema tercatat, foreign_keys
  aktif, insert/query dokumen, unique index relasi menolak duplikat, `init_db`
  idempoten.

## 4. Metrik (Bagian 9) — DB kosong, nilai dasar yang diharapkan

```
M1  Antrean kunjungan tersisa              : 0 (kosong)
M2  Kutipan belum terselesaikan            : tidak ada baris
M3  Selisih daftar dokumen antar-sumber    : 0 untuk semua pasangan (BPK/KEMENKEU/DJP)
M4  Rantai versi pasal lengkap             : 0/0 (N/A%)
M5  Kecocokan naskah konsolidasi           : N/A (Fase 7)
M6  Pelanggaran invarian I1–I3             : 0 ✅
M7  Dokumen FAILED/NEEDS_REVIEW per tahap  : tidak ada
M8  BOUNDARY/UNDECIDED belum ditinjau      : 0
```

Lengkapnya di `reports/source_coverage.md` (dihasilkan `python3 -m src.report`).

## 5. Contoh keluaran nyata (termasuk yang "gagal" = ditolak benar)

Berhasil (normalisasi ke bentuk kanonik):
```
'UU No. 7 Tahun 1983'                          -> UU-1983-7
'Undang-Undang Nomor 7 Tahun 1983'             -> UU-1983-7
'PP No. 55/2022'                               -> PP-2022-55
'PMK-81/PMK.03/2024'                           -> PMK-2024-81
'PER-14/PJ/2013'                               -> PER-DJP-2013-14
'14/PUU-XX/2022'                               -> PUTUSAN-MK-2022-14
'Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022' -> PERPU-2022-2
```

Ditolak (mengembalikan `None` — pemanggil wajib menandai `NEEDS_REVIEW`,
bukan menebak):
```
'Pasal 17 ayat (1) huruf a'                    -> None  (bukan rujukan peraturan)
'Undang-Undang Dasar ... Tahun 1945'           -> None  (UUD bukan jenis registry)
'KEP-DJP-2015-7'                               -> None  (jenis di luar tabel 5.1)
```

Locator:
```
build_locator('UU-1983-7', 'BT', '17', '1', 'a') = 'UU-1983-7#BT/17/1/a'
parse_locator('UU-1983-7#BT/17/1/a') = {document_id: 'UU-1983-7', part: 'BATANG_TUBUH',
                                        pasal: '17', ayat: '1', huruf: 'a', angka: None}
normalize_document_id('PMK-2024-81') = 'PMK-2024-81'   (idempoten)
```

## 6. Masalah dan ketidakpastian

Lihat `ISSUES.md`:
- V1–V9 dari spec belum diverifikasi (robots.txt, struktur HTML, kelengkapan
  relasi, HTML vs PDF, konsolidasi, kuota Colab, model, definisi "lengkap"
  dosen, pola kalimat perubahan).
- 4 keputusan agent menunggu konfirmasi G0: root proyek, lokasi
  `data/legal_rules.jsonl` (+ pertanyaan mirror ke SQLite), konvensi asal
  BOUNDARY lewat `domain_tags`, tabel `schema_meta` + kolom resumability.
- Git belum diinisialisasi (usulan di ISSUES #5).
- Seeds & kartu lingkup DOMAIN_A masih usulan agent (P3) — wajib verifikasi manusia.

## 7. Asumsi yang diambil

1. Root proyek = `PROJEK_KBR` (spec doc berada di sini); isi struktur tetap
   mengikuti Bagian 4 spec.
2. `legal_rules.jsonl` (5.12) adalah berkas, bukan tabel; diletakkan di
   `data/legal_rules.jsonl`.
3. Asal temuan dokumen `BOUNDARY` (invarian I3) dicatat lewat `domain_tags`.
4. `nomor_raw` menyimpan token nomor seperti tertulis di sumber
   (mis. `PMK-81/PMK.03/2024`), `nomor_norm` menyimpan angka/sufiks (`81`).
5. `crawl_queue` diberi kolom resumability (`attempts`, `error`, `enqueued_at`).
6. Nilai status dibiarkan TEXT bebas di SQLite; disiplin enumerasi 5.10
   diawasi lewat laporan "Status terpakai" di `report.py` (bukan CHECK).

## 8. Usulan langkah berikutnya & yang menunggu persetujuan manusia (G0)

**G0 — semua ketiga anggota harus setuju** (spec 12):

- [ ] Tinjau skema SQLite — terutama `provision_versions` dan `amendments`
      (DDL di `src/db.py`; dokumen penjelas: spec Bagian 5).
- [ ] Putuskan 4 pertanyaan ISSUES (root proyek, legal_rules.jsonl/mirror,
      konvensi I3, `schema_meta`).
- [ ] **Verifikasi seeds DOMAIN_A** di `config/scope_cards/DOMAIN_A.yaml`
      terhadap sumber resmi (usulan agent, P3).
- [ ] Isi/konfirmasi topik masuk–keluar DOMAIN_A + nama pemilik domain.

Setelah G0 disetujui → **Fase 1** (pilot penjelajahan: cek robots.txt,
inspeksi struktur halaman, `crawl.py` + `scope.py`, dry-run 1 seed, batas
20 dokumen) — belum dikerjakan, menunggu perintah.

*Agent berhenti di sini sesuai aturan kerja (satu fase per waktu).*
