# ISSUES.md — Ketidakpastian, Pertanyaan, Temuan Anomali

> Aturan (spec Bagian 0): setiap ketidakpastian dicatat di sini dan ditandai
> `NEEDS_REVIEW` pada data terkait. Jangan menebak, jangan mengarang.

---

## Terbuka — belum diverifikasi (dari Bagian 14 spec)

| # | Hal | Catatan |
|---|---|---|
| V1 | `robots.txt` & ketentuan penggunaan tiap sumber | ✅ **SELESAI (Fase 1)** — ketiganya mengizinkan konten publik; hasil dicatat di `config/sources.yaml`. |
| V2 | Struktur HTML sebenarnya ketiga sumber | 🟡 **BPK SELESAI** (selector terverifikasi + fixture); Kemenkeu & DJP belum diinspeksi. |
| V3 | Kelengkapan metadata relasi di sumber | ✅ **TERKONFIRMASI TIDAK LENGKAP** — lihat "Anomali" #A1 di bawah. |
| V4 | Teks tersedia sebagai HTML/teks atau hanya PDF | BPK: PDF (`/Read/`, `/Download/`), tautan tercatat; ekstraksi teks = Fase 3. |
| V5 | Naskah konsolidasi sebagai alat uji (M5) | Belum; Fase 7. |
| V6 | Batas sesi, GPU, kuota Colab Pro | Belum; Fase 5. |
| V7 | Kandidat model | Belum; Fase 5. |
| V8 | Definisi "lengkap" dari dosen | **Menunggu tim** — memengaruhi kartu lingkup. |
| V9 | Pola kalimat perubahan nyata | Sebagian teramati via blok relasi BPK; pola teks pasal tetap Fase 4. |

---

## Keputusan Fase 0 yang menunggu konfirmasi G0

1. **Root proyek = folder `PROJEK_KBR`** (bukan subfolder `kbr-extraction/`),
   karena `KBR_Extraction_Spec.md` sudah berada di sini. Struktur isi tetap
   mengikuti Bagian 4 spec. — *DIPUTUSKAN agent, mohon konfirmasi.*
2. **`legal_rules.jsonl` diletakkan di `data/legal_rules.jsonl`** (spec 5.12
   menyebut file JSONL, bukan tabel). Pertanyaan untuk G0: apakah hasil aturan
   perlu *juga* di-mirror ke tabel SQLite agar mudah di-query? — *Terbuka.*
3. **Asal domain temuan `BOUNDARY`** (invarian I3) dicatat lewat `domain_tags`
   (`entity_type='DOCUMENT'`, `method='MANUAL'`/`'SOURCE_METADATA'`), karena
   tabel `documents` tidak punya kolom khusus untuk itu. — *Usulan agent.*
4. **Tabel `schema_meta`** (versi skema) dan kolom resumability di
   `crawl_queue` (`attempts`, `error`, `enqueued_at`) ditambahkan di luar teks
   eksplisit spec. — *Mohon tinjau di G0.*
5. **Git belum diinisialisasi** (folder belum repo). Usulan: `git init` +
   `.gitignore` (kecualikan `data/cache/`). — *Menunggu keputusan tim.*
6. **`kbr_knowledge_acquisition_plan.md` ditulis ulang** agar selaras spec:
   Hermes/Ollama/Google Sheets/PostgreSQL → OpenCode/Colab/SQLite/JSONL. — *Selesai Fase 0.*
7. **Seeds DOMAIN_A adalah usulan agent** (P3) — wajib verifikasi manual tim
   sebelum Fase 1. — *Menunggu tim.*
8. **Kartu lingkup DOMAIN_A** (topik masuk/keluar) perlu diedit pemilik
   domain; DOMAIN_B/C masih stub. — *Menunggu tim.*
9. **Konvensi `nomor_raw`**: untuk bentuk kode pendek disimpan token lengkap
   (`PMK-81/PMK.03/2024`, `PER-14/PJ/2013`, `14/PUU-XX/2022`), untuk bentuk
   "Nomor/No. X" disimpan token setelahnya (`55/2022`, `7`). — *Usulan agent,
   lihat `src/ids.py`.*
10. **Heuristik tahun `ids.py`**: prioritas "Tahun XXXX", selain itu angka
    4-digit terakhir. Untuk teks berisi >1 peraturan, S6 harus memotong
    substring kutipan dulu. — *Batas yang diketahui, bukan disembunyikan.*

---

## Anomali / temuan lain

- **A1 (V3 terkonfirmasi):** blok relasi JDIH BPK tidak lengkap. Halaman
  `PMK-2018-99` tidak menampilkan relasi apa pun padahal dokumennya telah
  dicabut/diganti; `PP-2018-23` menampilkan "Dicabut dengan" tetapi tidak
  menampilkan "Diubah dengan" yang seharusnya ada. Beban kelengkapan relasi ada
  di S6 (Fase 4). — *Fase 1.*
- **A2:** blok relasi halaman Detail memuat label tambahan yang belum ada di
  daftar awal: "Mencabut sebagian", "Dicabut sebagian dengan", "Menetapkan"
  (→ MENETAPKAN_PERPU), "Ditetapkan dengan". Sudah dipetakan di
  `config/relation_map.yaml`. — *Fase 1.*
- **A3:** halaman Detail juga memuat blok **"Putusan MK / Uji Materi"**
  (mis. `PUTUSAN 83/PUU-XXI/2023` di halaman UU HPP). Belum dipetakan sebagai
  relasi/amendment — dikerjakan di Fase 4 (S5) sebagai sumber perubahan
  `PUTUSAN-MK`. — *Fase 1, NEEDS_REVIEW.*
- **A4:** judul dokumen dapat menyebut peraturan lain (mis. "UU No. 6 Tahun
  2023 tentang Penetapan PERPU No. 2 Tahun 2022"). Normalisasi jenis/nomor
  memakai aturan **posisi terawal** (`src/ids.py`), dan `page_document_id`
  memprioritaskan metadata terstruktur (Bentuk Singkat+Tahun+Nomor). Diuji
  dengan fixture nyata. — *Fase 1, selesai.*
- **A5:** `UU-2020-11` (Cipta Kerja) berstatus `Tidak Berlaku` di sumber —
  disimpan apa adanya (P8); relasi ke UU pajak tetap dicatat dari halaman
  BOUNDARY. — *Fase 1.*
- **A6:** 109 dokumen placeholder `DISCOVERED`/`UNDECIDED` (tetangga dari
  halaman yang dikunjungi) menunggu putusan gerbang di Fase 2 (review queue).
  I1–I3 = 0. — *Fase 1.*
- **A7:** `PER-DJP-2015-17` (*seharusnya PER-17/PJ/2015 tentang Norma Penghitungan Penghasilan Neto*)
  memiliki PDF sumber salah unduh dari BPK yang berisi **Perda Kabupaten Pangandaran
  tentang Perlindungan dan Pengelolaan Lingkungan Hidup**. Ditemukan saat validasi
  Fase 4 (`t2_results_v2.jsonl`, sempat menghasilkan 79 aturan lingkungan).
  Dikarantina di `src/validate.py` (`QUARANTINED_DOC_IDS`) agar tidak masuk ke
  `legal_rules.jsonl`; wajib diganti dengan PDF PER-17/PJ/2015 resmi bila akan
  diekstrak. — *Fase 4, NEEDS_REVIEW.*
