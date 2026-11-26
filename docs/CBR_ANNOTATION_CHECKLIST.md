# Checklist Pelaksanaan Anotasi CBR (B4.2)

Dokumen kerja untuk **Anotator A**, **Anotator B**, dan **Reviewer**. Pasangan dari
`docs/CBR_ANNOTATION_GUIDE.md` (aturan pengisian) dan `config/cbr_taxonomy.json` (kode label).

---

## 1. Peran & pembagian

| Peran | Siapa | Tugas | Jumlah kasus |
|---|---|---|---|
| **Anotator A** | Pilar 3 (kurator hukum) | Anotasi klaster `pph_badan`, `pph_potput`, `kup_gugatan` + 8 kasus overlap dari B | **38** |
| **Anotator B** | Praktisi/anggota tim | Anotasi klaster `ppn`, `kepabeanan_cukai`, `pbb` + 7 kasus overlap dari A | **37** |
| **Reviewer** | Pilar 3 / praktisi senior | Menandatangani 100% baris, memimpin adjudikasi | 60 |

Berkas penugasan:

```text
data/jurisprudence/annotations/assignment_A.csv     # 38 kasus
data/jurisprudence/annotations/assignment_B.csv     # 37 kasus
data/jurisprudence/annotations/assignment_summary.json
data/jurisprudence/annotations/worksheet_60.csv     # lembar kerja utama
```

**Aturan overlap:** 15 kasus dikerjakan **dua orang secara independen** (tanpa saling melihat).
Daftar `overlap_ids` ada di `assignment_summary.json`; kolom `is_overlap` pada CSV menandai `YA/TIDAK`
(`peran = UTAMA` untuk pemilik klaster, `OVERLAP` untuk peninjau silang). Jangan berdiskusi sebelum kedua berkas selesai.

---

## 2. Jadwal (4 minggu, ±10 kasus/orang/minggu)

| Minggu | Anotator A | Anotator B | Gate |
|---|---|---|---|
| 1 | 10 kasus (`pph_badan`) | 10 kasus (`ppn`) | validator: 0 error untuk 20 kasus |
| 2 | 10 kasus (`pph_potput`) | 10 kasus (`kepabeanan_cukai`) | progres ≥ 40 kasus |
| 3 | 10 kasus (`kup_gugatan`) + 4 overlap | 10 kasus (`pbb`) + 3 overlap | progres ≥ 60 kasus |
| 4 | 4 overlap sisa | 4 overlap sisa | κ dihitung, adjudikasi, sign-off |

> Jika hanya satu orang yang tersedia: kerjakan 60 kasus (±4–6 minggu) dan **wajib** minta
> satu praktisi mengerjakan 15 kasus overlap untuk κ.

---

## 3. Checklist per kasus (centang di kolom `catatan` bila perlu)

- [ ] Baca `pokok_sengketa` sampai jelas objek koreksinya.
- [ ] Baca `pertimbangan_majelis`; tandai kalimat yang menjadi **ratio decidendi**.
- [ ] Isi `jenis_koreksi` (1–3 kode, **minimal 1 kode daun**).
- [ ] Isi `fakta_kunci` (minimal 1 kode daun).
- [ ] Salin `rasio_decidendi` **persis** dari pertimbangan (tanpa parafrase).
- [ ] Bila amar `KABUL_*`: isi `argumen_menang` (kutipan persis).
- [ ] Isi `bukti_penentu` bila majelis menyebut alat bukti.
- [ ] Isi `rezim_hukum` (cek apakah dasar hukum masih berlaku).
- [ ] Isi `quotes_json` untuk 1–2 kutipan kunci (opsional tapi disarankan).
- [ ] Isi `annotator`; kosongkan `reviewer` sampai ditinjau.
- [ ] Bila ragu/teks OCR rusak: tulis `catatan`, **jangan mengarang**.

---

## 4. Validasi berkala

```bash
# setiap selesai 10 kasus
python3 scripts/validate_cbr_annotations.py

# sebelum hitung kappa
python3 scripts/validate_cbr_annotations.py --json hasil_validasi.json
```

Target sementara: `errors = 0`. Baris `pending` boleh ada sampai minggu ke-4.

---

## 5. Double-annotation & Cohen's κ

1. Simpan hasil B sebagai `worksheet_60_annotatorB.csv` (hanya 15 kasus overlap, kolom sama).
2. Jalankan:

```bash
python3 scripts/validate_cbr_annotations.py --second ../annotations/worksheet_60_annotatorB.csv
```

3. Target: **κ ≥ 0,60** untuk `jenis_koreksi` dan `fakta_kunci`.
4. Jika κ < 0,60:
   - kumpulkan kasus yang berbeda,
   - tentukan apakah masalahnya **definisi taksonomi** atau **pemahaman kasus**,
   - perbaiki definisi (via versi taksonomi baru) lalu uji ulang 5 kasus.

---

## 6. Adjudikasi (1 hari)

Agenda:

1. Bahas setiap kasus yang berbeda label (maks 10 menit/kasus).
2. Putuskan label final + alasan (catat di `catatan`).
3. Bila taksonomi kurang: usulkan kode baru — **jangan** langsung dipakai sebelum versi taksonomi diperbarui.
4. Tandatangani berita acara.

Template log adjudikasi:

| case_id | Label A | Label B | Keputusan | Alasan | Diputuskan oleh |
|---|---|---|---|---|---|
| PP-PUT-xxxxx | KOR_... | KOR_... | KOR_... | ... | ... |

---

## 7. Sign-off

| Item | Kriteria | Status |
|---|---|---|
| Kelengkapan | 60/60, `pending = 0` | ☐ |
| Validator | 0 error, 0 peringatan kode induk | ☐ |
| Kutipan verbatim | 100% substring persis | ☐ |
| κ | ≥ 0,60 (15 kasus) | ☐ |
| Reviewer | 100% baris ditinjau | ☐ |
| Impor | `import_cbr_annotations.py --strict` sukses | ☐ |
| Indeks | `annotated_cases = 60` | ☐ |

| Peran | Nama | Tanda tangan | Tanggal |
|---|---|---|---|
| Anotator A | | | |
| Anotator B | | | |
| Reviewer | | | |

---

## 8. Setelah sign-off

```bash
python3 scripts/import_cbr_annotations.py --strict
python3 scripts/build_risk_cbr.py        # rebuild indeks (annotated_cases=60)
```

Lanjut **B4.3** (backend): aktifkan formula penuh PRD §8, evaluasi `Precision@3 ≥ 0,60` pada 20 kueri praktisi, dan ubah label UI menjadi "CBR penuh".
