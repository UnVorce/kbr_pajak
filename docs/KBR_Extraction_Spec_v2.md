# KBR Knowledge Extraction — Spesifikasi untuk AI Agent (v2)

> **Proyek:** Sistem Informasi Prosedur dan Mitigasi Risiko Perpajakan di Indonesia (Knowledge-Based Reasoning)
> **Tahap dokumen ini:** Akuisisi dan ekstraksi pengetahuan hukum perpajakan, **termasuk rantai riwayat perubahan di level pasal**, dan penyiapan data untuk ontology.
> **Pembaca utama:** AI coding agent (OpenCode) yang membangun dan menjalankan pipeline, serta tim manusia (3 mahasiswa Sains Data) yang mengawasinya.
> **Versi:** v2. **Menggantikan seluruh `KBR_Extraction_Spec.md` (v1).** Jika ada konflik, v2 yang berlaku.
> **Bahasa:** Narasi Bahasa Indonesia. Nama field, tabel, status, dan modul tetap seperti tertulis. Jangan diterjemahkan.

---

## 0. Cara Memakai Dokumen Ini (BACA DULU)

Dokumen ini adalah **sumber kebenaran tunggal** untuk arsitektur, skema data, aturan, dan urutan kerja. Jika instruksi pengguna dalam percakapan bertentangan dengan dokumen ini, tanyakan dulu sebelum bertindak.

**Aturan kerja agent:**

1. Kerjakan **satu fase pada satu waktu** (Bagian 17). Jangan lompat ke fase berikutnya sebelum gerbang persetujuan (*gate*) manusia terpenuhi.
2. Sebelum menulis parser untuk suatu sumber, **periksa struktur halaman/dokumen yang sebenarnya** (ambil sampel dan lihat HTML/teksnya). Dokumen ini menyebut hal yang *kemungkinan* ada dan menandainya "(perlu diverifikasi)". Jangan berasumsi.
3. Selalu uji pada **sampel kecil** dulu (default: 20 dokumen atau 50 potongan teks), laporkan hasilnya, baru naikkan skala.
4. Semua pekerjaan harus **dapat dilanjutkan** (resumable): simpan progres setelah setiap unit kerja. Jangan memproses ulang yang sudah selesai kecuali isi sumbernya berubah (hash berbeda).
5. Jika menemukan ketidakpastian, **catat di `ISSUES.md` dan tandai `NEEDS_REVIEW`**. Jangan menebak, jangan mengarang, jangan menutupi.
6. Setelah menyelesaikan tiap fase, tulis `reports/phase_<N>.md` (format Bagian 17.11), lalu **berhenti dan minta persetujuan**.
7. Jangan menghapus atau menimpa **data sumber** (events). Data **turunan** (derived) boleh dibangun ulang (Bagian 9.11).
8. Tulis tes otomatis untuk semua logika deterministik. Gunakan *fixture* dari sampel nyata (Bagian 10.7).
9. Satu script untuk semua domain. Perbedaan domain hanya di kartu lingkup (Bagian 7).

**Prompt pembuka yang disarankan untuk pengguna:**

> Baca `KBR_Extraction_Spec_v2.md` sampai selesai. Kerjakan **hanya Fase 0**. Setelah selesai, buat `reports/phase_0.md` dan berhenti untuk persetujuan. Jangan mengerjakan fase lain.

---

## 1. Konteks, Tujuan, dan Cakupan

### 1.1 Latar

Proyek ini membangun sistem berbasis pengetahuan (ontology + rule-based reasoning + case-based reasoning) agar wajib pajak non-konsultan dapat memahami kewajiban, risiko, dan dasar hukum perpajakan. Dokumen ini hanya mencakup **akuisisi dan ekstraksi pengetahuan hukum**, bukan reasoning engine.

### 1.2 Tujuan tahap ini

1. Mengumpulkan peraturan perpajakan yang relevan dengan **kelengkapan yang terukur**.
2. Memecah tiap peraturan menjadi **pasal, ayat, dan huruf** yang dapat dirujuk.
3. Membangun **rantai riwayat perubahan di level pasal** sehingga sistem dapat menjawab: *berapa kali pasal ini diubah*, *bunyinya sekarang*, dan *bunyinya pada tanggal tertentu*.
4. Mengekstrak isi ketentuan (kondisi, kewajiban, hak, larangan, pengecualian, konsekuensi, batas waktu, tarif) **dengan kutipan sumber yang dapat diverifikasi**.
5. Menjaga **provenance**: setiap data dapat ditelusuri ke dokumen, pasal, ayat, dan URL sumber.
6. Menyiapkan **ekspor ke format ontologi** (RDF/OWL dalam Turtle) untuk tahap berikutnya.

### 1.3 Arahan dosen: kelengkapan

Dosen meminta peraturan dikumpulkan selengkap mungkin. Tim menerjemahkannya menjadi **kriteria yang dapat diuji** (Bagian 14): penutupan graf relasi (*closure*) per domain, nol kutipan yang belum terselesaikan, rekonsiliasi antar-sumber, dan rantai versi lengkap. Kelengkapan tidak diukur dari jumlah dokumen yang kebetulan ditemukan.

### 1.4 Di luar cakupan (jangan dikerjakan)

- Perancangan kelas dan definisi ontologi (TBox), reasoning engine, case-based reasoning.
- Ekstraksi putusan Pengadilan Pajak dan Mahkamah Agung. Jika kelak dikerjakan, data pribadi harus diminimalkan.
- Kalkulator pajak dan antarmuka pengguna.
- Penentuan keabsahan hukum final dan penyelesaian konflik antar-aturan. Sistem hanya **menandai** konflik (Bagian 15.5).

---

## 2. Prinsip yang Tidak Boleh Dilanggar

| # | Prinsip | Konsekuensi praktis |
|---|---|---|
| P1 | **Deterministik dulu, LLM belakangan.** | Struktur teratur (relasi di metadata, pasal/ayat, pola kalimat perubahan) dikerjakan script. LLM hanya untuk yang butuh memahami bahasa. |
| P2 | **Output LLM hanyalah kandidat.** | Tidak masuk data tervalidasi tanpa lolos validator script (dan review manusia untuk kategori berisiko). |
| P3 | **Jangan mengarang.** | Informasi yang tidak tertulis di sumber diisi `null` atau `[]`. Dasar hukum, nomor pasal, tarif, dan tanggal **tidak boleh** berasal dari ingatan model. |
| P4 | **Provenance wajib.** | Setiap rekaman substantif punya `source_url`, `document_id`, `source_locator`, dan `source_quote` yang merupakan **substring persis** dari teks sumber. |
| P5 | **Pisahkan: identitas dokumen, versi pasal, keberlakuan hukum.** | Jangan digabung dalam satu kolom status (Bagian 15). |
| P6 | **Jangan timpa teks lama.** | Perubahan = versi baru dengan interval `valid_from`/`valid_to`. |
| P7 | **Dapat dilanjutkan.** | Checkpoint, ID deterministik, hash isi, manifest, status per item. |
| P8 | **Status sumber ≠ status terverifikasi.** | `status_sumber` disimpan apa adanya. Itu bukan `legal_status` kita. |
| P9 | **Kelengkapan harus terukur.** | Metrik Bagian 14 dilaporkan setiap fase. |
| P10 | **Hormati sumber.** | Patuhi `robots.txt` dan ketentuan penggunaan, batasi laju, cache (Bagian 16). |
| P11 | **Dunia terbuka.** | "Tidak ditemukan" berarti *tidak diketahui*, bukan *tidak ada*. Jangan menyimpulkan tidak ada perubahan hanya karena perubahan belum ditemukan. |
| P12 | **Event sourcing.** | Peristiwa perubahan (`amendments`) adalah data sumber. Riwayat versi pasal (`provision_versions`) adalah **turunan yang selalu dapat dibangun ulang** dengan memutar ulang peristiwa. Jangan mengedit versi secara langsung. |
| P13 | **Berhenti saat prasyarat gagal.** | Jika satu langkah pemutaran ulang gagal prasyarat, hentikan rantai di titik itu, catat ke `chain_issues`, jangan menebak. |

---

## 3. Arsitektur dan Pembagian Tugas

### 3.1 Empat pelaku

| Pelaku | Berjalan di | Tugas | Bukan tugasnya |
|---|---|---|---|
| **Script deterministik (Python)** | Laptop | Menjelajah graf, mengelola registry, mengambil teks, memecah struktur, mendeteksi pola perubahan, mendeteksi lubang, memutar ulang rantai, memvalidasi, mengekspor, menghitung metrik | Memahami kalimat bebas |
| **Model LLM (Google Colab Pro)** | Colab | Tiga tugas sempit: T1 (instruksi perubahan tidak baku), T2 (isi ketentuan), T3 (label domain kasus abu-abu) | Menjelajah, memilih dokumen, memutuskan keabsahan hukum, menentukan urutan perubahan |
| **OpenCode (agent)** | Laptop | Menulis, menguji, memperbaiki script. Menyetel prompt dan skema. Mengawasi batch. Membuat laporan. | Ekstraksi massal lewat percakapan. Mengubah data tervalidasi. Mengisi gold standard. |
| **Manusia (tim)** | – | Seed dan kartu lingkup, review antrean, pemeriksaan ketentuan berisiko, gold standard, perancangan ontologi, persetujuan gerbang | – |

### 3.2 Keputusan yang sudah diambil

| Keputusan | Pilihan | Catatan |
|---|---|---|
| Bahasa implementasi | **Python** | |
| Penyimpanan data kerja | **SQLite** (satu berkas) | Mendukung query temporal, join, integritas, dan transaksi. Dapat dimigrasi ke PostgreSQL. |
| Format pertukaran | **JSONL** | Antar-tahap dan laptop ↔ Colab via Google Drive. |
| Format ontologi | **RDF/OWL dalam Turtle (`.ttl`)** | Hanya ekspor dari data tervalidasi (Bagian 12). |
| Tempat model | **Hanya Google Colab Pro** | Tidak ada model lokal. |
| OpenCode untuk ekstraksi massal | **Tidak** | Opsional untuk kasus sulit dalam jumlah kecil lewat mode non-interaktif. |
| SDK, RPC, plugin OpenCode | **Tidak dipakai** | |
| Hermes Agent | **Tidak dipakai** | Hanya satu agent. |

### 3.3 Tiga lapisan penyimpanan (jangan dicampur)

| Lapisan | Format | Isi | Aturan |
|---|---|---|---|
| **Data kerja** | SQLite | Registry, relasi, pasal, versi, amendment, antrean, status, log | **Sumber kebenaran.** Semua yang lain diturunkan darinya. |
| **Pertukaran** | JSONL | Chunk teks, hasil LLM, ekspor tabel | Append-only dan mudah dilanjutkan. |
| **Ontologi** | Turtle | Individu (ABox) dari data tervalidasi + kosakata `kbr:` | Dapat dibangun ulang kapan saja dari SQLite. Tidak berisi data proses (antrean, status crawl, output mentah LLM). |

### 3.4 Diagram alur (teks)

```
SEED (kartu lingkup, manual)
   │
   ▼
[S1 Penjelajah graf relasi] ──► documents + relations (lapis bukti A)
   ▼
[S2 Gerbang relevansi & kepemilikan]
   ▼
[S3 Ingest teks] ──► teks + content_hash
   ▼
[S4 Parser struktur] ──► provisions
   ▼
[S5 Pendeteksi perubahan]
   │  pola baku ──► amendments (lapis bukti B)
   │  sisanya ──► chunks T1 ──► [Colab LLM] ──► kandidat ──► validator
   ▼
[S6 Pendeteksi lubang] ──► unresolved_citations ──┐ (dokumen baru kembali ke S1)
   ▲                                              │
   └──────────────────────────────────────────────┘
   ▼
[S7 Ekstraksi isi ketentuan T2] ──► kandidat aturan ──► [S8 Validator + review]
   ▼
[S9 Rantai riwayat: urutan → putar ulang → pemeriksaan silang]
   │   ──► chain_order, provision_versions, chain_issues
   ▼
[S10 Ekspor ontologi + data] ──► JSONL, Turtle
   ▼
[S11 Laporan cakupan & kualitas]
```

Putaran **S1 → S6 → S1** berulang sampai tidak ada dokumen baru. Itulah dasar klaim kelengkapan.

---

## 4. Struktur Proyek

```
kbr-extraction/
├── AGENTS.md                      # ringkasan Bagian 0 dan 2
├── KBR_Extraction_Spec_v2.md      # dokumen ini
├── ISSUES.md
├── config/
│   ├── sources.yaml               # sumber, URL dasar, selector (diisi setelah inspeksi)
│   ├── crawl.yaml                 # laju, retry, user-agent, batas per run, shared_core_documents
│   ├── relation_map.yaml          # label sumber -> tipe relasi internal
│   ├── patterns_amendment.yaml    # pola kalimat perubahan (Bagian 8.5, 5.3)
│   ├── scope_cards/
│   │   ├── DOMAIN_A.yaml
│   │   ├── DOMAIN_B.yaml
│   │   └── DOMAIN_C.yaml
│   ├── model_config.yaml          # diisi setelah pilot (Bagian 11.6)
│   └── ontology.yaml              # base IRI, prefix, aturan ekspor (Bagian 12)
├── ontology/
│   └── kbr-core.ttl               # kosakata kelas dan properti (TBox), DIMILIKI MANUSIA
├── data/
│   ├── kbr.sqlite
│   ├── cache/html/                # boleh dibuang
│   ├── cache/pdf_tmp/             # dihapus setelah diproses
│   ├── reference/                 # naskah rujukan teknik (UU 12/2011 dan Lampiran II) dan konsolidasi
│   ├── text/                      # <document_id>.txt + indeks
│   ├── chunks/{pending,done}/
│   ├── llm_results/
│   ├── validation/
│   │   ├── gold_standard.jsonl
│   │   ├── validation_results.csv
│   │   └── extraction_error_log.csv
│   ├── review/review_queue.csv
│   ├── export/
│   │   ├── jsonl/                 # satu berkas per tabel + data_dictionary.md
│   │   └── ttl/kbr-data.ttl
│   └── manifests/{batch_manifest.jsonl,checkpoint.json}
├── src/kbr/
│   ├── ids.py                     # normalisasi document_id dan locator
│   ├── db.py                      # DDL, koneksi, transaksi
│   ├── cli.py                     # perintah per tahap (Bagian 10.3)
│   ├── crawl.py                   # S1
│   ├── scope.py                   # S2
│   ├── ingest.py                  # S3
│   ├── parse_structure.py         # S4
│   ├── amendments.py              # S5
│   ├── gaps.py                    # S6
│   ├── chunking.py                # pembuatan chunks T1/T2/T3
│   ├── validate.py                # S8
│   ├── chain_order.py             # S9 langkah 1
│   ├── replay.py                  # S9 langkah 2
│   ├── chain_checks.py            # S9 langkah 3
│   ├── export_jsonl.py            # S10
│   ├── export_ttl.py              # S10
│   └── report.py                  # S11
├── notebooks/colab_extract.ipynb
├── tests/
│   ├── fixtures/
│   └── test_*.py
└── reports/
    ├── phase_0.md ...
    ├── source_coverage.md
    ├── extraction_quality.md
    ├── chain_report.md
    └── known_limitations.md
```

---

## 5. Referensi Hukum Dasar: UU 12/2011 (Pembentukan Peraturan Perundang-undangan)

### 5.1 Mengapa ini penting

Struktur dan teknik penulisan peraturan perundang-undangan diatur oleh **UU Nomor 12 Tahun 2011 tentang Pembentukan Peraturan Perundang-undangan** (UU P3/PPP). Parser struktur (S4), pola perubahan (S5), dan pendeteksi lubang (S6) harus **berpijak pada aturan ini**, bukan pada tebakan.

### 5.2 Status (teramati dari hasil pencarian. Agent wajib memverifikasi di sumber primer)

- UU 12/2011 diubah dengan **UU 15/2019** dan **UU 13/2022** (Perubahan Kedua), dan mencabut UU 10/2004. Halaman BPK untuk UU 12/2011 menampilkan relasi ini.
- Beberapa dokumen instansi menyebut UU 13/2022 sebagai perubahan terakhir. **Cek apakah ada perubahan lebih baru.**
- Teknik penyusunan ada di **Lampiran II** (bagian tak terpisahkan dari UU). **Lampiran I** memuat teknik penyusunan Naskah Akademik.
- Perubahan terhadap teknik penyusunan dilakukan dengan Peraturan Presiden (menurut UU 13/2022). Versi Lampiran II yang berlaku harus **sesuai tanggal penetapan dokumen** yang diparse.
- UU 13/2022 menambahkan ketentuan **metode omnibus** (disebut Pasal 42A, dicantumkan sejak tahap perencanaan). Pasal 97A juga dibahas sebagai ketentuan peralihannya.
- Setahu penulis dokumen ini, peraturan pelaksananya adalah Perpres 87/2014 **(belum diverifikasi)**.

### 5.3 Pemetaan ke komponen proyek

| Ketentuan | Dipakai untuk |
|---|---|
| Pasal tentang jenis dan hierarki peraturan (setahuku Pasal 7 dan 8, **verifikasi nomor pasal**) | `hierarchy_level`, relasi `MELAKSANAKAN` |
| Lampiran II: kerangka peraturan (judul, pembukaan dengan Menimbang dan Mengingat, batang tubuh, penutup, penjelasan, lampiran) | `role` pasal dan parser S4 |
| Lampiran II: rumusan perubahan baku (contoh teramati: "Ketentuan Pasal … diubah sehingga berbunyi sebagai berikut", angka 233) | `patterns_amendment.yaml` (S5) |
| Lampiran II: ketentuan bagian Mengingat (angka 28 dan 39) | S6 (kutipan dasar hukum) |
| Struktur UU perubahan (contoh teramati: **Pasal I** memuat "Beberapa ketentuan dalam Undang-Undang … diubah sebagai berikut", pasal berikutnya memuat mulai berlaku) | Pembagian instruksi, `effective_from` |
| Ketentuan omnibus | Deteksi dokumen pengubah banyak target |
| Lampiran II: ketentuan tentang akibat perubahan terhadap sistematika dan materi (teramati: angka 237 membahas konsekuensi perubahan atas sistematika/materi, **baca isi lengkapnya**) | Aturan "kapan peraturan diganti, bukan diubah" |

### 5.4 Tugas agent

1. Daftarkan UU 12/2011, UU 15/2019, dan UU 13/2022 di registry dengan `scope_status=REFERENCE` (dokumen rujukan teknik, bukan sumber hukum pajak).
2. **Baca Lampiran II** (versi berlaku) dan ekstrak **daftar rumusan baku** untuk perubahan: ubah, sisip, hapus, cabut, tambah, perubahan frasa, perubahan penjelasan. Simpan di `config/patterns_amendment.yaml` beserta **nomor angka Lampiran II sebagai rujukan**.
3. Tetapkan juga aturan penomoran dari Lampiran II: pasal sisipan (mis. `4A`), pasal yang dihapus tetap mempertahankan nomor, dan seterusnya. **Catat aturan yang benar-benar tertulis**, bukan dugaan.

### 5.5 Peringatan

- **Tidak semua dokumen patuh.** Mahkamah Konstitusi (Putusan 91/PUU-XVIII/2020) mempermasalahkan bahwa UU Cipta Kerja mengabaikan teknik baku Lampiran I dan II. Parser **harus diuji pada dokumen omnibus**, tidak boleh mengandalkan kepatuhan.
- **Dokumen lama berformat lain.** Peraturan sebelum UU 12/2011 (dan sebelum UU 10/2004) tunduk pada aturan format sebelumnya. Jangan memaksakan satu pola.
- **PMK dan PER-DJP** mengikuti kerangka umum tetapi memiliki variasi internal. Verifikasi pada sampel.

---

## 6. Model Data

> SQLite kecuali dinyatakan lain. Tanggal: ISO `YYYY-MM-DD`. Boolean: 0/1. Kolom `*_json` berisi JSON. Tabel bertanda **[SUMBER]** adalah data sumber (peristiwa). Tabel bertanda **[TURUNAN]** dapat dibangun ulang (P12).

### 6.1 Normalisasi ID dan locator

**`document_id`** kanonik: `{JENIS}-{TAHUN}-{NOMOR}`.

| Jenis dokumen | `JENIS` | Contoh |
|---|---|---|
| Undang-Undang | `UU` | `UU-1983-6` |
| Perpu | `PERPU` | `PERPU-2022-2` |
| Peraturan Pemerintah | `PP` | `PP-2022-55` |
| Peraturan Presiden | `PERPRES` | `PERPRES-2014-87` |
| Peraturan Menteri Keuangan | `PMK` | `PMK-2024-81` |
| Peraturan Dirjen Pajak | `PER-DJP` | `PER-DJP-2013-14` (dari "PER-14/PJ/2013") |
| Surat Edaran, KMK, dll. | `SE-DJP`, `KMK`, … | |
| Putusan Mahkamah Konstitusi | `PUTUSAN-MK` | `PUTUSAN-MK-2020-91` (simpan nomor mentah di `nomor_raw`) |

Aturan:

- Simpan `nomor_raw` (persis sumber) dan `nomor_norm`.
- Fungsi normalisasi **idempoten** dan **diuji** dengan kasus nyata ("UU No. 7 Tahun 1983", "Undang-Undang Nomor 7 Tahun 1983", "PP No. 55/2022", "PMK-81/PMK.03/2024").
- Dua `document_id` yang ternyata dokumen sama digabung lewat `document_aliases(alias_id, document_id)`. Jangan duplikasi baris.

**`locator`** kanonik: `<document_id>#<bagian>/<pasal>[/<ayat>[/<huruf>[/<angka>]]]`. Contoh: `UU-1983-7#BT/17/1/a` (`BT` = batang tubuh, `PJ` = penjelasan). Sufiks sisipan dipertahankan (`4A`). Teks lokator manusiawi ("Pasal 17 ayat (1) huruf a") disimpan di `locator_text`.

### 6.2 `documents` [SUMBER]

| Kolom | Keterangan |
|---|---|
| `document_id` PK | Format 6.1 |
| `jenis`, `nomor_raw`, `nomor_norm`, `tahun`, `judul` | Judul lengkap, jangan dipotong |
| `title_ordinal` | Hasil parse "Perubahan (Kedua/Ketiga/…) atas …" dari judul, `NULL` jika bukan (dipakai pemeriksaan C1, Bagian 9.8) |
| `tempat_penetapan`, `tanggal_penetapan`, `tanggal_pengundangan` | Jika ada |
| `ln_tahun`, `ln_nomor`, `tln_nomor` | Rujukan Lembaran Negara/Tambahan jika tersedia (kunci urutan K4) |
| `tanggal_berlaku_sumber` | Dari metadata sumber, **bukan** hasil verifikasi |
| `effective_from_derived` | Tanggal mulai berlaku hasil **membaca ketentuan penutup** dokumen (Bagian 15.2), `NULL` jika tak terbaca |
| `subjek_sumber`, `bidang_sumber` | Metadata sumber, sinyal relevansi |
| `status_sumber` | Mentah ("Berlaku"/"Tidak Berlaku"/…) |
| `hierarchy_level` | UU=1, Perpu=1, PP=2, Perpres=3, PMK=4, PER-DJP=5, SE=6 (default) |
| `source_urls_json`, `primary_source` | |
| `content_hash` | SHA-256 teks ternormalisasi |
| `scope_status`, `owner_domain`, `claimed_by`, `claimed_at` | Bagian 7 |
| `discovery_status`, `ingestion_status`, `extraction_status`, `validation_status` | Enum 6.10 |
| `legal_status` | **Terverifikasi**, bukan `status_sumber` |
| `first_seen_at`, `last_checked_at`, `notes` | |

### 6.3 `relations` [SUMBER]

| Kolom | Keterangan |
|---|---|
| `relation_id` PK | |
| `from_document_id`, `to_document_id` | Arah **bentuk aktif** |
| `relation_type` | `MENGUBAH`, `MENCABUT`, `MELAKSANAKAN`, `MERUJUK`, `MENETAPKAN_PERPU` |
| `origin` | `SOURCE_METADATA`, `TEXT_PATTERN`, `LLM`, `MANUAL` |
| `evidence` | URL atau kutipan + lokator |
| `confidence`, `verified` | |
| `discovered_at` | |

**Konvensi arah:** simpan hanya bentuk aktif. "A *diubah dengan* B" → `from=B, to=A, MENGUBAH`. "A *dicabut dengan* B" → `from=B, to=A, MENCABUT`. Unique index `(from, to, relation_type)`. Relasi dari dua asal digabung dengan kedua asal dicatat di `evidence`. Petakan label sumber di `config/relation_map.yaml` (label yang **kemungkinan** ada, perlu diverifikasi: "Mengubah", "Diubah dengan", "Mencabut", "Dicabut dengan").

### 6.4 `provisions` [SUMBER, hasil parsing]

| Kolom | Keterangan |
|---|---|
| `provision_id` PK | = `locator` kanonik |
| `document_id`, `part` | `part`: `BATANG_TUBUH` / `PENJELASAN` |
| `level` | `BAB`, `BAGIAN`, `PARAGRAF`, `PASAL`, `AYAT`, `HURUF`, `ANGKA` |
| `nomor` | `17`, `4A`, `a`, … |
| `parent_provision_id`, `ordinal` | Hierarki dan urutan asli |
| `sort_key` | Kunci urutan leksikografis agar sisipan dapat diletakkan di antara tetangga (Bagian 9.7) |
| `locator_text`, `heading` | |
| `role` | `SUBSTANTIVE`, `AMENDING_INSTRUCTION`, `TRANSITIONAL`, `EFFECTIVITY`, `DEFINITION`, `CLOSING` |
| `origin` | `PARSED` (dari teks dokumen) atau `INSERTED_BY_AMENDMENT` |

Penjelasan (pasal demi pasal) juga dapat diubah, jadi dimodelkan terpisah (`part=PENJELASAN`) dengan rantai sendiri.

### 6.5 `amendments` [SUMBER]

| Kolom | Keterangan |
|---|---|
| `amendment_id` PK | |
| `amending_document_id`, `amending_locator` | Dokumen pengubah (UU, Perpu, PP, PMK, Putusan MK) dan lokasi instruksi |
| `instruction_ordinal` | Urutan kemunculan instruksi di dokumen pengubah (kunci urutan K5) |
| `target_document_id` | Bisa bukan dokumen pajak |
| `target_locator`, `target_part` | Pasal/ayat/huruf target |
| `action` | `UBAH`, `SISIP`, `HAPUS`, `CABUT_PASAL`, `CABUT_SELURUH`, `TAMBAH`, `GANTI_FRASA`, `HAPUS_FRASA` |
| `new_text` | Teks pengganti penuh (UBAH/SISIP/TAMBAH) |
| `find_text`, `replace_text` | Untuk `GANTI_FRASA` / `HAPUS_FRASA` |
| `insert_after_locator`, `insert_before_locator` | Untuk `SISIP` (tetangga yang disebut instruksi) |
| `effective_from`, `effective_basis` | Dari ketentuan mulai berlaku/peralihan, jika terbaca |
| `parse_method` | `RULE`, `LLM`, `MANUAL` |
| `confidence`, `source_quote` | `source_quote` substring persis dari teks pengubah |
| `review_status` | `PENDING`, `APPROVED`, `REJECTED` |

Satu UU omnibus menghasilkan **banyak baris** dengan `target_document_id` berbeda. Perubahan pada dokumen di luar cakupan tetap dicatat. Aksi `GANTI_FRASA`/`HAPUS_FRASA` adalah bentuk perubahan tingkat kata atau frasa yang **kemungkinan** ada pada dokumen nyata (perlu diverifikasi, V10). Jangan menolak instruksi itu, catat sebagai `NEEDS_REVIEW` jika bentuknya tidak dikenali.

### 6.6 `chain_order` [TURUNAN]

| Kolom | Keterangan |
|---|---|
| `target_document_id`, `amendment_id` | |
| `seq_no` | Nomor urut penerapan per dokumen target (mulai 1) |
| `key_k1` … `key_k5` | Nilai kunci urutan yang dipakai (Bagian 9.2) |
| `key_used` | Kunci pertama yang menentukan posisi |

### 6.7 `provision_versions` [TURUNAN]

| Kolom | Keterangan |
|---|---|
| `version_id` PK | `{provision_id}@v{version_no}` |
| `provision_id`, `version_no` | `0` = teks asli |
| `text` | `NULL` jika dihapus |
| `text_hash`, `is_deleted` | |
| `valid_from`, `valid_to` | `valid_to NULL` = masih berlaku menurut data yang ada |
| `created_by_document_id`, `created_by_amendment_id` | `NULL` untuk versi 0 |
| `seq_no` | Posisi dalam `chain_order` |
| `reconstruction_method` | `ENACTED_TEXT`, `APPLIED_AMENDMENT`, `CONSOLIDATED_REFERENCE` |
| `verification_status` | `UNVERIFIED`, `MATCHES_CONSOLIDATED`, `MISMATCH`, `HUMAN_VERIFIED` |
| `effective_basis`, `applicability_notes` | |

**Invarian:** per `provision_id`, interval `[valid_from, valid_to)` tidak tumpang tindih dan tidak berlubang antar-versi berurutan (kecuali ditandai di `chain_issues`).

### 6.8 `chain_issues` [TURUNAN]

| Kolom | Keterangan |
|---|---|
| `issue_id` PK | |
| `target_document_id`, `amendment_id`, `provision_id` | Yang relevan |
| `issue_type` | Daftar 9.9 |
| `severity` | `BLOCKING` (rantai berhenti di titik ini) atau `WARNING` |
| `detail` | Penjelasan konkret (nilai kunci, kutipan, selisih) |
| `status` | `OPEN`, `RESOLVED`, `ACCEPTED` |
| `created_at`, `resolved_at`, `resolution_note` | |

Setiap `chain_issues` berstatus `OPEN` otomatis menghasilkan entri `review_queue`.

### 6.9 Tabel pendukung

**`domain_tags`:** `entity_type` (`DOCUMENT`/`PROVISION`), `entity_id`, `domain_id`, `score`, `method` (`SOURCE_METADATA`/`KEYWORD`/`LLM`/`MANUAL`), `review_status` (`AUTO_ACCEPTED`/`PENDING`/`APPROVED`/`REJECTED`). Domain adalah **tag** (banyak per entitas). Kepemilikan pemrosesan tunggal (Bagian 7).

**`unresolved_citations`:** `citation_id`, `in_document_id`, `in_locator`, `raw_text`, `parsed_jenis`, `parsed_nomor`, `parsed_tahun`, `context_type` (`MENGINGAT`, `MENIMBANG`, `JUDUL`, `BATANG_TUBUH`, `PENJELASAN`, `SEBAGAIMANA_DIUBAH`), `resolved_document_id`, `status` (`UNRESOLVED`, `RESOLVED`, `NOT_FOUND_AT_SOURCE`, `IGNORED_OUT_OF_SCOPE`), `resolved_at`.

**`crawl_queue`:** `item_id`, `document_id_or_url`, `depth`, `origin_document_id`, `status`, `attempts`, `last_error`.

**`review_queue`:** `item_id`, `entity_type`, `entity_id`, `reason` (mis. `LOW_CONFIDENCE`, `QUOTE_NOT_FOUND`, `CHAIN_ISSUE`, `AMBIGUOUS_OWNER`, `POSSIBLE_CONFLICT`), `priority` (1–3), `assigned_to`, `status`, `created_at`, `resolved_at`, `resolution_note`. Ekspor ke `data/review/review_queue.csv`.

**`run_log`:** `run_id`, `stage`, `params_json`, `started_at`, `finished_at`, `items_ok`, `items_failed`, `notes`. Setiap eksekusi tahap menulis satu baris.

### 6.10 Enumerasi status

| Kolom | Nilai |
|---|---|
| `scope_status` | `UNDECIDED`, `IN_SCOPE`, `BOUNDARY`, `OUT_OF_SCOPE`, `REFERENCE` |
| `discovery_status` | `DISCOVERED`, `METADATA_FETCHED`, `METADATA_VERIFIED`, `FAILED`, `NEEDS_REVIEW` |
| `ingestion_status` | `PENDING`, `INGESTED`, `FAILED`, `NEEDS_REVIEW` |
| `extraction_status` | `PENDING`, `EXTRACTED`, `FAILED`, `NEEDS_REVIEW` |
| `validation_status` | `PENDING`, `SCHEMA_VALID`, `SOURCE_VERIFIED`, `REVIEW_REQUIRED`, `VALIDATED`, `REJECTED` |
| `legal_status` | `NEEDS_VERIFICATION` (default), `BERLAKU`, `DIUBAH_SEBAGIAN`, `DICABUT`, `TIDAK_DIKETAHUI` |
| `review_status` | `PENDING`, `APPROVED`, `REJECTED` |

Jangan membuat nilai status baru tanpa persetujuan manusia. Jangan menulis variasi seperti "done" atau "selesai".

### 6.11 Chunks, hasil LLM, dan aturan hasil ekstraksi (JSONL)

**`chunks`:** `chunk_id` = `sha256(document_id + locator + text_hash + task_type)`; `task_type` (`T1_AMENDMENT`, `T2_RULE`, `T3_DOMAIN`); `document_id`; `locator`; `text` (utuh, tidak dipotong di tengah ayat); `context` (judul peraturan, judul bab/bagian, pasal induk, rujukan silang singkat); `domain_hint` (untuk T3); `text_hash`; `created_at`.

**`llm_results`** (append-only dari Colab): `result_key` = `chunk_id + task_type + prompt_version + model_id`; `chunk_id`; `task_type`; `model_id`; `prompt_version`; `raw_output`; `parsed_output`; `parse_error`; `latency_s`, `tokens_in`, `tokens_out`; `created_at`. Validasi dihitung **di laptop**, bukan oleh model.

**`legal_rules.jsonl` (hasil T2):**

| Field | Wajib? | Keterangan |
|---|---|---|
| `rule_id` | Ya | |
| `document_id`, `source_locator` | Ya | |
| `rule_type` | Ya | `eligibility`, `obligation`, `right`, `prohibition`, `exception`, `sanction`, `deadline`, `rate`, `definition`, `procedure`, `other` |
| `subject` | Jika ada | |
| `condition` | Daftar | `{attribute, operator, value, raw}` |
| `obligation`, `right`, `prohibition`, `exception` | Daftar | Jangan kosongkan `exception` jika teks menyebut pengecualian |
| `consequence`, `deadline` | Objek/null | Hanya yang **tertulis** |
| `rate_or_value` | Daftar | Angka dengan satuan |
| `cross_references` | Daftar | Sebagaimana tertulis |
| `source_quote` | Ya | Substring persis |
| `effective_period_hint` | Objek/null | Hanya jika tertulis di chunk |
| `validation_status` | Ya | Default `PENDING` |
| `extraction_method` | Ya | `{model_id, prompt_version}` |

---

## 7. Domain dan Kartu Lingkup

Pekerjaan dibagi per domain, satu pemilik tiap domain. **Satu script, tiga kartu lingkup.**

### 7.1 Format kartu lingkup (`config/scope_cards/<DOMAIN_ID>.yaml`)

```yaml
domain_id: DOMAIN_A                 # diisi tim
owner: "<nama anggota>"
description: "<satu paragraf tentang domain>"
include_topics:
  - topic: "<topik>"
    examples: ["<contoh peraturan atau pasal>"]
exclude_topics:
  - topic: "<topik>"
    examples: ["<contoh>"]
seeds:                              # diverifikasi manual
  - document_id: "UU-xxxx-n"
    rationale: "<alasan>"
follow_relations: [MENGUBAH, MENCABUT, MELAKSANAKAN]
follow_direction: both              # forward | backward | both
subject_hints: []
keyword_hints: []
thresholds:                         # default, WAJIB dikalibrasi di Fase 2
  auto_in: 0.80
  review_min: 0.40
boundary_policy: record_and_stop
max_depth: null
notes: ""
```

### 7.2 Gerbang relevansi (S2)

Untuk tiap dokumen baru:

1. Hitung sinyal: (a) `subjek_sumber`/`bidang_sumber` cocok dengan `subject_hints`, (b) kata kunci judul, (c) relasi langsung ke dokumen `IN_SCOPE`, (d) bila perlu skor LLM (T3).
2. Skor ≥ `auto_in` → `IN_SCOPE` dan dijelajahi.
3. `review_min` ≤ skor < `auto_in` → `UNDECIDED`, masuk `review_queue`, **tidak** dijelajahi sampai diputuskan.
4. Skor < `review_min` → `BOUNDARY` (dicatat dengan asal temuan, tidak dijelajahi). **Jangan dibuang.**
5. Jelas tidak berkaitan dengan perpajakan → `OUT_OF_SCOPE` (dicatat dengan alasan).

> UU induk seperti KUP terhubung ke hampir semua hal. Tanpa gerbang ini penjelajahan "bocor". Relasi hanya diikuti dari dokumen `IN_SCOPE`.

### 7.3 Dokumen inti lintas domain

Dokumen yang menyentuh banyak domain (mis. UU KUP, UU omnibus) masuk `shared_core_documents` di `config/crawl.yaml`. Pemiliknya `SHARED`, diproses **sekali** oleh orang yang ditunjuk. Setelah terparsing, tiap pasal diberi **tag domain**. "Tampilan domain" tiap anggota adalah filter atas tag.

### 7.4 Kepemilikan dan invarian

- Satu dokumen punya **tepat satu** `owner_domain` (atau `SHARED`). Banyak `domain_tags` itu boleh.
- Dokumen cocok dengan lebih dari satu domain: pemilik = skor tertinggi. Selisih < 0,1 atau seri → `AMBIGUOUS_OWNER` di `review_queue`. Pemecah seri ditentukan manusia.
- **Kunci pemrosesan:** isi `claimed_by` dan `claimed_at` sebelum memproses. Dokumen yang di-claim domain lain tidak boleh diproses.
- **Invarian (diperiksa otomatis tiap laporan):**
  - **I1:** tidak ada dokumen `IN_SCOPE` tanpa pemilik.
  - **I2:** tidak ada dokumen dengan lebih dari satu pemilik atau `claimed_by`.
  - **I3:** tiap `BOUNDARY` mencatat domain asal temuannya.

---

## 8. Pipeline per Tahap

Setiap tahap: tujuan → input → proses → output → aturan → kriteria selesai (DoD).

### 8.1 S1 — Penjelajah graf relasi

**Tujuan:** mengumpulkan dokumen dan relasinya lewat metadata terstruktur, **tanpa LLM**.

| Sumber (perlu diverifikasi sebelum dipakai) | Peran |
|---|---|
| `peraturan.bpk.go.id` | **Primer untuk relasi.** Halaman peraturan tampaknya memuat blok relasi (mengubah / diubah dengan / mencabut / dicabut dengan) dan metadata (tanggal penetapan, pengundangan, berlaku, status, subjek, bidang). Struktur harus **diinspeksi langsung**. |
| `jdih.kemenkeu.go.id` | Sumber kedua untuk rekonsiliasi dan teks peraturan Kemenkeu. |
| Portal peraturan DJP (`pajak.go.id`) | Sumber ketiga untuk rekonsiliasi dan peraturan DJP. |

**Catatan penting:** relasi di JDIH diinput **manual** oleh tiap instansi, dan standar JDIH menyebut tautan ke peraturan target hanya dibuat jika target sudah diinput. **Metadata relasi pasti tidak lengkap.** Itu sebabnya ada S5 (teks pengubah), S6 (lubang), dan S9 (pemeriksaan silang).

**Proses:**

1. Muat kartu lingkup. Masukkan `seeds` ke `crawl_queue`.
2. Ambil satu item. Cek cache. Ambil halaman bila belum ada atau kedaluwarsa.
3. Parse metadata dan relasi. Normalkan label lewat `relation_map.yaml` ke bentuk aktif.
4. Simpan `documents` dan `relations`.
5. Jalankan S2 pada dokumen baru. Tambahkan tetangga ke antrean **hanya** jika `IN_SCOPE` dan tipe relasinya ada di `follow_relations`.
6. Ulangi sampai antrean kosong (*closure*) atau batas per-run tercapai.
7. Arah "ke bawah" (peraturan pelaksana): dicari lewat bagian "Mengingat" di S6.

**Aturan:** patuhi `crawl.yaml` (jeda ≥ 1,5 detik default, User-Agent jelas, retry dengan backoff, batas per-run, **dry-run**); hormati `robots.txt` dan ketentuan penggunaan (Bagian 16); resumable; gagal fetch → `FAILED` dengan alasan, jangan dilewati diam-diam; simpan `status_sumber` mentah.

**DoD:** antrean kosong atau batas run tercapai dengan log jelas; tiap dokumen punya `document_id` kanonik, URL, metadata yang tersedia, dan relasi.

### 8.2 S2 — Gerbang relevansi dan kepemilikan

Lihat Bagian 7.2 dan 7.4. Output: `scope_status`, `owner_domain`, `domain_tags` tingkat dokumen, entri `review_queue`.

### 8.3 S3 — Ingest teks

**Input:** dokumen `IN_SCOPE` (dan `REFERENCE`) yang di-claim.
**Proses:** ambil teks dari HTML/API bila ada. Jika hanya PDF: unduh **sementara** ke `cache/pdf_tmp/`, ekstrak teks, **hapus PDF**. Simpan `data/text/<document_id>.txt` dan `content_hash`.
**Aturan:**

- Perbaiki karakter rusak **tanpa mengubah makna hukum**. Dilarang stemming, menghapus semua tanda baca, atau menggabungkan pasal menjadi satu paragraf.
- Bedakan PDF teks vs pindaian. OCR dituntut → `NEEDS_REVIEW` (angka, nomor pasal, tanda baca rentan salah).
- Teks hasil ekstraksi **disimpan** sebagai bukti verifikasi. PDF mentah tidak.
- `content_hash` berubah → semua turunan ditandai `STALE` dan masuk antrean ulang.

**DoD:** teks tersimpan, hash tercatat, status jelas.

### 8.4 S4 — Parser struktur pasal

**Tujuan:** memecah teks menjadi `provisions`.

Hierarki umum: Dokumen → Bab → Bagian → Paragraf → Pasal → Ayat → Huruf → Angka. Tidak semua dokumen memiliki semua tingkat. Pola umum (**perlu diverifikasi pada dokumen nyata**): `BAB I`, `Bagian Kesatu`, `Paragraf 1`, `Pasal 17`, `Pasal 4A`, `(1)`, `a.`, `1.`. Dokumen pengubah memiliki struktur sendiri (mis. `Pasal I`, `Pasal II`, atau bab per UU target pada omnibus). Kerangka dokumen mengikuti Lampiran II (Bagian 5).

**Aturan:**

- Pertahankan `ordinal`, hierarki induk-anak, dan isi `sort_key`.
- Tetapkan `role`. **Ketentuan peralihan** dan **ketentuan mulai berlaku** wajib dikenali karena menentukan `valid_from` (15.2). Isi `documents.effective_from_derived` bila terbaca.
- Pisahkan `PENJELASAN` dari `BATANG_TUBUH`.
- Parse `title_ordinal` dari judul.
- Struktur tidak dikenali → `NEEDS_REVIEW`, jangan menebak.
- **Parser S4 juga dipakai ulang oleh S9** untuk mem-parse `new_text` pasal yang diubah (Bagian 9.6). Rancang sebagai fungsi murni yang menerima teks dan menghasilkan pohon.

**DoD:** sampel 10 dokumen dari jenis berbeda diperiksa manusia; tes otomatis lulus pada fixture.

### 8.5 S5 — Pendeteksi perubahan (amendments)

**Langkah A — Pola baku (script).** Pola berasal dari Lampiran II (Bagian 5.4) dan disimpan di `config/patterns_amendment.yaml`. Contoh pola **indikatif** (konfirmasi pada dokumen nyata):

| Aksi | Pola umum |
|---|---|
| Lingkup | "Beberapa ketentuan dalam Undang-Undang Nomor … diubah sebagai berikut" (menetapkan **UU target** untuk butir-butir berikutnya) |
| `UBAH` | "Ketentuan Pasal X diubah sehingga berbunyi sebagai berikut" |
| `SISIP` | "Di antara Pasal X dan Pasal Y disisipkan … Pasal XA" |
| `HAPUS` | "Pasal X dihapus" |
| `CABUT_PASAL` / `CABUT_SELURUH` | "… dicabut dan dinyatakan tidak berlaku" |
| `TAMBAH` | "Ditambahkan … ayat …" |
| `GANTI_FRASA` / `HAPUS_FRASA` | Bentuk perubahan tingkat kata atau frasa (**verifikasi**, V10) |
| Penjelasan | "Penjelasan Pasal X diubah …" |

**Cara memecah dokumen pengubah:**

1. Cari kalimat lingkup → tetapkan `target_document_id` (pada omnibus, kalimat ini muncul berkali-kali, sekali per UU target).
2. Pecah butir bernomor di bawahnya. Tiap butir adalah satu instruksi. Isi `instruction_ordinal`.
3. Kenali aksi dan target dari kalimat pembuka butir.
4. Ambil `new_text` dari blok setelah "berbunyi sebagai berikut".
5. Ubah target menjadi `target_locator` kanonik. Untuk `SISIP`, isi `insert_after_locator` dan `insert_before_locator` dari tetangga yang disebut.
6. Isi `effective_from` dari ketentuan mulai berlaku/peralihan jika terbaca (per instruksi bila dokumen menyatakannya bertahap).

UU non-pajak yang mengubah UU pajak **harus tertangkap**. Jangan menyaring pengubah dari judulnya.

**Langkah B — Fallback LLM (T1):** instruksi yang tidak cocok pola dikirim ke Colab sebagai chunk `T1_AMENDMENT`. Hasil → validator → `review_queue`.

**Langkah C — Validasi:** target ada di registry atau dicatat sebagai dokumen baru untuk S6; `source_quote` ada di teks pengubah; `new_text` tidak kosong untuk UBAH/SISIP/TAMBAH; `find_text` terisi untuk aksi frasa.

**Sumber perubahan non-UU:** Putusan MK dan penetapan Perpu dicatat sebagai amendment dengan jenis pengubah masing-masing dan **selalu** `review_status=PENDING`.

**DoD:** semua dokumen pengubah di registry diproses; rasio instruksi tertangkap pola vs LLM tercatat; tidak ada instruksi tanpa status.

### 8.6 S6 — Pendeteksi lubang

**Tujuan:** menemukan dokumen yang seharusnya ada tetapi belum ada di registry.

1. Dari semua teks tersimpan, kumpulkan kutipan peraturan (Mengingat, Menimbang, judul "Perubahan atas …", "sebagaimana telah diubah dengan …", rujukan di batang tubuh).
2. Normalkan ke `document_id`, cocokkan dengan registry.
3. Yang tidak ditemukan → `unresolved_citations` berstatus `UNRESOLVED`.
4. Untuk tiap `UNRESOLVED`: cari di sumber (S1). Ketemu → ke registry/antrean, `RESOLVED`. Tidak ada di sumber → `NOT_FOUND_AT_SOURCE` (tetap dilaporkan). Di luar domain → `IGNORED_OUT_OF_SCOPE` dengan alasan.
5. **Rekonsiliasi antar-sumber:** bandingkan daftar dokumen dari sumber A, B, dan C. Selisih → to-do.
6. **Judul "Perubahan atas X":** jika X ada di registry tetapi tidak ada relasi `MENGUBAH`, buat relasi `origin=TEXT_PATTERN`.

**Putaran:** dokumen baru kembali ke S1 → S5. Berhenti jika satu putaran penuh tidak menambah dokumen.

**DoD:** `UNRESOLVED` kosong atau tiap sisa punya status terminal beralasan; laporan lubang tersedia.

### 8.7 S7 — Ekstraksi isi ketentuan (T2)

Hanya untuk pasal `IN_SCOPE` dengan `role` `SUBSTANTIVE` atau `DEFINITION`. Pasal instruksi perubahan tidak diekstrak isinya, melainkan lewat S5.

**Chunking:** pecah menurut struktur hukum (pasal → ayat). Jangan memotong di tengah ayat. Ayat panjang → pecah per huruf dengan `context` induk. Sertakan teks rujukan silang yang singkat bila perlu. **Gunakan versi teks yang berlaku** menurut S9 bila tersedia, dan catat `provision_version_id` di chunk agar aturan terikat pada versi.

Eksekusi T2 lewat Colab (Bagian 11). Hasil → `llm_results` → S8.

### 8.8 S8 — Validator dan antrean review

**Pemeriksaan otomatis, urut:**

1. **Struktur:** JSON dapat di-parse, field sesuai skema, tipe benar, ID unik.
2. **Sumber:** `document_id` ada di registry; `source_locator` ada di `provisions`; `source_quote` adalah **substring persis** dari teks chunk (hanya boleh normalisasi spasi dan baris baru); nomor pasal/ayat yang disebut ada di teks.
3. **Logika:** angka, tarif, dan tanggal pada hasil harus muncul di teks chunk; token angka/entitas pada output yang tidak ada di input → tandai; duplikasi; rujukan ke dokumen/pasal yang belum tersedia → `unresolved_citations`.
4. **Waktu:** `valid_from`/`effective_period` hanya dari teks atau S9, tidak dari model.

**Status:** `EXTRACTED` → `SCHEMA_VALID` → `SOURCE_VERIFIED` → `VALIDATED` atau `REVIEW_REQUIRED`/`REJECTED`.

**Wajib review manusia (selain yang gagal validator):** tarif, angka, ambang batas; syarat kelayakan fasilitas; pengecualian; batas waktu; sanksi; pasal yang pernah diubah; amendment dari Putusan MK/Perpu; semua `confidence < 0.8`; sampel acak ≥ 10% dari yang lolos otomatis.

---

## 9. Arsitektur Rantai Riwayat (S9)

### 9.1 Prinsip

Rantai riwayat dibangun dengan **event sourcing** (P12):

- **Peristiwa** = baris `amendments` berstatus `APPROVED`. Ini data sumber.
- **Riwayat** = `provision_versions`, hasil **memutar ulang** peristiwa secara berurutan. Ini turunan.
- Koreksi dilakukan dengan memperbaiki **peristiwa**, lalu memutar ulang. Jangan mengedit versi.
- Dibangun dari **tiga lapis bukti** yang saling mengecek:

| Lapis | Sumber | Menjawab | Kelemahan |
|---|---|---|---|
| A | Metadata relasi sumber | *Siapa* yang mengubah | Tidak lengkap (diinput manual) |
| B | Teks dokumen pengubah | *Pasal mana*, *diubah menjadi apa* | Perlu parsing, omnibus rumit |
| C | Naskah konsolidasi, matriks perubahan | *Apakah hasil akhir benar* | Sumber sekunder, belum tentu ada |

### 9.2 Kunci urutan (order keys)

Untuk tiap amendment pada satu dokumen target, kumpulkan kunci berikut (`NULL` bila tak tersedia):

| Kunci | Nilai | Sumber |
|---|---|---|
| **K1** | Tanggal berlaku amendment | `amendments.effective_from`, jika kosong `amending document.effective_from_derived` |
| **K2** | Tanggal pengundangan dokumen pengubah | `documents.tanggal_pengundangan` |
| **K3** | Tanggal penetapan dokumen pengubah | `documents.tanggal_penetapan` |
| **K4** | (`ln_tahun`, `ln_nomor`) dokumen pengubah | `documents` |
| **K5** | `instruction_ordinal` dalam dokumen pengubah | `amendments` |

**Aturan pengurutan:**

1. Urutkan memakai tuple (K1, K2, K3, K4, K5). Bandingkan dua amendment pada **kunci pertama yang tersedia pada keduanya**. Jika setara, lanjut ke kunci berikutnya.
2. Dua amendment dari **dokumen pengubah yang sama** hanya dibedakan oleh K1 (bila instruksinya bertahap) lalu K5.
3. **Pemeriksaan konsistensi:** untuk setiap pasangan amendment, jika dua kunci yang sama-sama tersedia menghasilkan urutan **berlawanan**, catat `ORDER_KEY_DISAGREEMENT` (severity `WARNING`) dan jangan memilih diam-diam. Gunakan urutan K1 jika tersedia, tandai untuk review.
4. Jika **semua** kunci setara untuk dua amendment pada pasal yang sama → `SAME_ORDER_CONFLICT` (`BLOCKING`).
5. **Urutan dipisahkan dari tanggal berlaku.** Bila K1 tidak terbaca, urutan tetap bisa ditentukan dari K2–K5, dan `valid_from` dibiarkan `NULL` dengan `EFFECTIVE_DATE_MISSING` (`WARNING`). **Jangan menebak tanggal dari tahun peraturan.**

Hasil ditulis ke `chain_order` dengan `seq_no` per dokumen target.

### 9.3 Algoritma pemutaran ulang (per dokumen target)

1. **Inisialisasi state:** peta `locator → versi terkini`. Buat **versi 0** dari teks asli (`ENACTED_TEXT`) untuk semua `provisions` dokumen target. `valid_from` versi 0 dari `effective_from_derived` dokumen target (atau `NULL` + `EFFECTIVE_DATE_MISSING`).
2. Ambil amendment `APPROVED` untuk dokumen target menurut `seq_no`.
3. Untuk tiap amendment: **periksa prasyarat** (9.4). Jika gagal → tulis `chain_issues` berseverity `BLOCKING`, **hentikan rantai untuk locator/dokumen itu**, dan lanjutkan ke dokumen target lain.
4. Jika lolos: tutup versi lama (`valid_to` = `valid_from` versi baru), buat versi baru, perbarui state.
5. Tulis semua versi dalam **satu transaksi** per dokumen target.
6. Jalankan pemeriksaan silang (9.8).

### 9.4 Aksi dan prasyarat

| Aksi | Prasyarat | Efek |
|---|---|---|
| `UBAH` | Target ada dan belum dihapus | Tutup versi lama, buat versi baru dengan `new_text`. Jika target punya anak, lihat 9.6 |
| `SISIP` | Locator baru **belum ada**, dan tetangga (`insert_after`/`insert_before`) ada | Buat `provisions` baru (`origin=INSERTED_BY_AMENDMENT`) dengan `sort_key` di antara tetangga (9.7), lalu versi pertamanya |
| `TAMBAH` | Induk ada | Buat anak baru (mis. ayat tambahan) di ujung, dengan aturan yang sama seperti `SISIP` |
| `HAPUS` / `CABUT_PASAL` | Target ada dan belum dihapus | Buat versi `is_deleted=1`. Nomor tetap dipertahankan (sesuai aturan Lampiran II yang diverifikasi, Bagian 5.4) |
| `CABUT_SELURUH` | Dokumen target ada | Tutup semua versi yang masih berlaku pada tanggal efektif. Pengecualian peralihan hanya **ditandai** di `applicability_notes` |
| `GANTI_FRASA` | `find_text` muncul **tepat satu kali** di teks versi terkini target | Buat versi baru dengan `find_text` diganti `replace_text` |
| `HAPUS_FRASA` | Sama seperti `GANTI_FRASA` | Buat versi baru tanpa `find_text` |

Kegagalan prasyarat menghasilkan salah satu `issue_type`: `TARGET_NOT_FOUND`, `TARGET_ALREADY_DELETED`, `INSERT_ALREADY_EXISTS`, `NEIGHBOR_NOT_FOUND`, `FIND_TEXT_NOT_FOUND`, `FIND_TEXT_AMBIGUOUS`.

### 9.5 Satuan versi

Versi disimpan pada **unit terkecil yang disebut instruksi** (pasal, ayat, atau huruf). Teks utuh sebuah pasal pada tanggal tertentu **dirangkai** dari versi terkini anak-anaknya (fungsi perangkaian `assemble_text(provision, at_date)`), bukan disimpan ganda.

### 9.6 Mengubah pasal induk yang punya anak

Jika `UBAH` menarget **pasal utuh** yang sebelumnya punya ayat dan huruf:

1. Tutup versi pasal dan **semua keturunannya**.
2. **Parse `new_text` dengan parser S4** menjadi pohon pasal/ayat/huruf baru.
3. Buat versi baru untuk pasal dan keturunan hasil parse.
4. Ayat yang tidak ada lagi di `new_text` dianggap **dihapus oleh penggantian** (versi `is_deleted=1`, dengan `created_by_amendment_id` yang sama).
5. Hasil parse yang tidak dapat dipercaya (struktur tidak dikenali) → simpan `new_text` utuh sebagai satu versi, tandai `NEEDS_REVIEW`.

### 9.7 Posisi sisipan

Pasal sisipan (mis. `4A`) tidak bisa diberi nomor urut bulat. Gunakan `sort_key` leksikografis (mis. string yang dapat disisipi di antara dua kunci tetangga tanpa mengubah kunci lain). Aturan:

- Kunci baru harus **tepat di antara** `insert_after` dan `insert_before`. Jika tidak disebutkan, di setelah `insert_after`.
- Jangan menomori ulang pasal lain.
- Urutan ditampilkan dengan `ORDER BY sort_key`, bukan nomor pasal.

### 9.8 Pemeriksaan silang (chain_checks)

Dijalankan setelah pemutaran ulang. Setiap kegagalan menjadi `chain_issues`.

| Kode | Pemeriksaan | Cara | Issue type jika gagal |
|---|---|---|---|
| **C1** | **Ordinal judul** | Jika judul dokumen pengubah berbentuk "Perubahan (Kedua/Ketiga/…) atas X", `title_ordinal` harus konsisten dengan urutan pengubah murni X di rantai. Rantai yang hanya punya satu pengubah padahal ada "Perubahan Kedua" berarti ada dokumen hilang. Tidak berlaku untuk omnibus atau pengubah non-murni | `ORDINAL_MISMATCH` |
| **C2** | **Daftar dasar hukum (Menimbang/Mengingat)** | Dokumen pengubah lebih baru biasanya menyebut pengubah sebelumnya ("sebagaimana telah diubah dengan …"). Daftar itu harus cocok dengan rantai yang dibangun. Selisih → kandidat dokumen hilang (juga masuk S6) | `CONSIDERANT_MISMATCH` |
| **C3** | **Pasal harus ada saat diubah** | Dijamin oleh prasyarat 9.4. Jika gagal, urutan atau rantai salah | `TARGET_NOT_FOUND`, `INSERT_ALREADY_EXISTS` |
| **C4** | **Interval versi** | Tidak boleh tumpang tindih atau berlubang antar-versi berurutan | `INTERVAL_OVERLAP`, `INTERVAL_GAP` |
| **C5** | **Konsolidasi/matriks** | Teks versi terkini sampel pasal dibandingkan dengan naskah konsolidasi atau matriks perubahan (jika ada). Set `verification_status` | `CONSOLIDATED_MISMATCH` |
| **C6** | **Relasi metadata vs teks** | Relasi `MENGUBAH` dari metadata sumber tanpa amendment yang ditemukan di teks → kandidat parsing gagal. Amendment ditemukan tetapi tidak ada relasi di metadata → tambahkan relasi `origin=TEXT_PATTERN` | `RELATION_WITHOUT_AMENDMENT` |

Naskah konsolidasi dari pihak swasta adalah **sumber sekunder**: alat uji, bukan dasar hukum.

### 9.9 Daftar `issue_type`

`TARGET_NOT_FOUND`, `TARGET_ALREADY_DELETED`, `INSERT_ALREADY_EXISTS`, `NEIGHBOR_NOT_FOUND`, `FIND_TEXT_NOT_FOUND`, `FIND_TEXT_AMBIGUOUS`, `ORDER_KEY_DISAGREEMENT`, `SAME_ORDER_CONFLICT`, `EFFECTIVE_DATE_MISSING`, `INTERVAL_OVERLAP`, `INTERVAL_GAP`, `CONSOLIDATED_MISMATCH`, `ORDINAL_MISMATCH`, `CONSIDERANT_MISMATCH`, `RELATION_WITHOUT_AMENDMENT`, `UNKNOWN_TARGET_DOCUMENT`, `UNPARSEABLE_NEW_TEXT`.

### 9.10 Kasus yang tidak boleh diurutkan atau diselesaikan otomatis

- **Putusan MK dan Perpu:** waktu efektif bisa berbeda dari tertulis di dokumen lain dan mungkin bersyarat. Selalu masuk review sebelum ikut diputar ulang.
- **Ketentuan peralihan:** aturan lama bisa tetap berlaku untuk situasi tertentu. Catat di `applicability_notes`, jangan diselesaikan otomatis.
- **Tanggal berlaku tak terbaca:** biarkan `NULL`.
- **Dua pengubah pada pasal yang sama dengan urutan setara.**
- **Pengubah yang pasal pengubahnya sendiri direvisi:** diperlakukan sebagai dokumen target biasa, bukan kasus khusus.

### 9.11 Idempotensi dan pembangunan ulang

Prosedur `rebuild(document_id)`: **kosongkan** `chain_order`, `provision_versions`, dan `chain_issues` milik dokumen target → hitung ulang urutan → putar ulang dari amendment `APPROVED` → tulis ulang, dalam satu transaksi. Dengan begitu koreksi satu amendment tidak merusak data setengah-setengah. Perubahan `content_hash` pada dokumen pengubah atau target memicu `rebuild` dokumen terkait.

### 9.12 Query riwayat yang harus tersedia

| Pertanyaan | Definisi |
|---|---|
| Berapa kali pasal P diubah? | Jumlah amendment `APPROVED` dengan `target_locator = P` (aksi apa pun selain pembuatan awal) |
| Berapa kali UU U diubah? | Jumlah dokumen pengubah **distinct** yang punya amendment `APPROVED` ke U. Tampilkan juga angka per pasal. Keduanya berbeda |
| Bunyi pasal P sekarang? | Versi dengan `valid_to IS NULL` dan `is_deleted=0` |
| Bunyi pasal P pada tanggal T? | Versi dengan `valid_from <= T AND (valid_to IS NULL OR T < valid_to)` (`valid_from NULL` berarti tak dapat dijawab, jangan ditebak) |
| Siapa yang mengubah P dan kapan? | `amendments` + `created_by_document_id` + `seq_no` |
| Peraturan pelaksana yang perlu ditinjau jika UU U berubah? | Relasi `MELAKSANAKAN` ke U (hanya **ditandai**) |
| Pasal mana yang rantainya bermasalah? | `chain_issues` berstatus `OPEN` |

### 9.13 Contoh ilustratif (placeholder)

Target UU A. Pengubah B (berlaku T1) dan C (berlaku T2), T1 < T2.

| seq | Peristiwa | Pasal 5 | Pasal 5A |
|---|---|---|---|
| 0 | Teks asli UU A | v0 | tidak ada |
| 1 | B mengubah Pasal 5 | v1, berlaku T1 → T2 | – |
| 2 | B menyisipkan Pasal 5A | – | v0 (sisipan), berlaku T1 → T2 |
| 3 | C mengubah Pasal 5 ayat (2) | v2, berlaku T2 → sekarang | – |
| 4 | C menghapus Pasal 5A | – | dihapus, berlaku T2 → sekarang |

Jika seq 2 dan 4 tertukar, prasyarat gagal (menghapus pasal yang belum disisipkan): inilah cara urutan salah terdeteksi.

---

## 10. Arsitektur Kode

### 10.1 Prinsip

- **Python.** Satu paket `kbr` dengan satu modul per tahap.
- **Digerakkan status di database**, bukan oleh agent yang memutuskan apa yang dikerjakan. Tiap tahap mengambil item "pending", mengerjakannya, menulis hasil, dan mengubah status.
- LLM dipanggil **hanya** dari notebook Colab. Seluruh modul lain deterministik dan bisa diuji.
- OpenCode **menulis** kode ini. Ia bukan bagian dari alur runtime.

### 10.2 Modul dan alur

| Tahap | Modul | Pakai LLM? | Input → Output |
|---|---|---|---|
| S1 | `crawl.py` | Tidak | `crawl_queue` + halaman sumber → `documents`, `relations` |
| S2 | `scope.py` | Hanya kasus abu-abu (T3) | `documents` baru → `scope_status`, `owner_domain`, `domain_tags` |
| S3 | `ingest.py` | Tidak | dokumen `IN_SCOPE` → `data/text/*`, `content_hash` |
| S4 | `parse_structure.py` | Tidak | teks → `provisions` |
| S5 | `amendments.py` | Hanya sisa non-pola (T1) | teks pengubah → `amendments` |
| S6 | `gaps.py` | Tidak | semua teks → `unresolved_citations`, antrean S1 |
| — | `chunking.py` | Tidak | `provisions`/instruksi → `chunks/pending/*.jsonl` |
| S7 | Notebook Colab | **Ya** | `chunks/pending` → `llm_results/*.jsonl` |
| S8 | `validate.py` | Tidak | `llm_results` → `amendments` / `legal_rules.jsonl` / `review_queue` |
| S9a | `chain_order.py` | Tidak | `amendments` → `chain_order` |
| S9b | `replay.py` | Tidak | `chain_order` + `provisions` → `provision_versions` |
| S9c | `chain_checks.py` | Tidak | hasil pemutaran → `chain_issues` |
| S10 | `export_jsonl.py`, `export_ttl.py` | Tidak | data tervalidasi → `data/export/*` |
| S11 | `report.py` | Tidak | seluruh DB → `reports/*.md` |

Putaran: **S1 → S6 berulang** sampai tidak ada dokumen baru.

### 10.3 Perintah CLI (satu perintah per tahap)

| Perintah | Fungsi |
|---|---|
| `kbr init` | Buat database dan struktur folder |
| `kbr crawl --domain D --limit N [--dry-run]` | S1 + S2 |
| `kbr ingest --domain D --limit N` | S3 |
| `kbr parse --domain D` | S4 |
| `kbr amendments --domain D` | S5 langkah A dan C |
| `kbr gaps` | S6 |
| `kbr chunks --task T1\|T2\|T3 --limit N` | Buat chunk untuk Colab |
| `kbr import-results --path ...` | Impor hasil Colab ke staging |
| `kbr validate` | S8 |
| `kbr chain --document ID \| --domain D` | S9 (urutan, putar ulang, pemeriksaan) |
| `kbr rebuild --document ID` | Bangun ulang rantai satu dokumen |
| `kbr export --format jsonl\|ttl` | S10 |
| `kbr report --phase N` | S11 |
| `kbr status` | Ringkasan progres dan invarian |

### 10.4 Pola implementasi tiap tahap

1. Pilih item dengan status pending untuk tahap itu. Lakukan *claim* (`claimed_by`/`claimed_at`) bila relevan.
2. Kerjakan satu item. **Satu transaksi per item** (atau per dokumen untuk S9).
3. Tulis hasil dan ubah status. Jika gagal: status `FAILED`/`NEEDS_REVIEW`, simpan alasan, **lanjut** ke item berikutnya.
4. Tulis satu baris `run_log` di akhir.
5. Jangan swallow exception diam-diam. Setiap kegagalan tercatat dengan alasan.
6. Tahap boleh dijalankan ulang kapan saja (idempoten).

### 10.5 Pustaka yang disarankan (boleh diganti dengan alasan)

| Kebutuhan | Pustaka |
|---|---|
| Ambil halaman | `requests` atau `httpx` |
| Parse HTML | `BeautifulSoup` (`lxml`) |
| Parse PDF | `PyMuPDF` |
| Pola teks | `re` bawaan |
| Pencocokan kutipan mirip | `rapidfuzz` |
| Database | `sqlite3` bawaan |
| Validasi skema | `pydantic` |
| Laporan dan metrik | `pandas` |
| Ekspor RDF | `rdflib` |
| Tes | `pytest` |
| Konfigurasi | `PyYAML` |

### 10.6 Konfigurasi

Semua parameter (laju crawl, ambang skor, selector sumber, path, base IRI) di `config/*.yaml`. **Jangan menghardcode** nilai tersebut di kode.

### 10.7 Pengujian

- **Fixture** dari sampel nyata: halaman metadata tiap sumber, teks UU biasa, UU perubahan tunggal, UU omnibus, PMK, PER-DJP.
- **Tes unit wajib:** normalisasi `document_id`; parser pasal/ayat/huruf (termasuk `4A`); tiap pola perubahan; pengurutan kunci K1–K5 dan konfliknya; tiap aksi dan prasyaratnya di `replay`; perakitan teks pasal; `rebuild` idempoten; validator `source_quote`.
- **Tes golden:** satu rantai perubahan sederhana dengan hasil yang **diverifikasi manusia** dari sumber resmi.
- Tes alur penuh (crawl → chain) dengan **keluaran LLM palsu** agar tidak memakai kuota Colab.

### 10.8 Urutan membangun (agar dapat diuji sedini mungkin tanpa LLM)

1. `ids`, `db`, `cli` (kerangka).
2. `crawl`, `scope` (pilot kecil).
3. `ingest`, `parse_structure`.
4. `amendments` (pola baku), `gaps`.
5. `chain_order`, `replay`, `chain_checks`, `report`. **Sudah dapat diuji tanpa LLM** pada dokumen dengan pola bersih.
6. `chunking`, notebook Colab, `validate`.
7. `export_jsonl`, `export_ttl`.

Riwayat satu UU nyata harus sudah bisa dilihat **sebelum menyentuh model**.

### 10.9 Peran OpenCode

Menulis modul sesuai fase, menjalankan tes, memperbaiki bug, menyetel pola dan prompt, menjalankan perintah CLI, dan membuat laporan fase. Tidak mengekstrak massal lewat percakapan. Untuk jumlah kecil kasus sulit, boleh memakai mode non-interaktif dengan sesi baru per kasus.

---

## 11. Kontrak Model LLM (Google Colab Pro)

### 11.1 Prinsip

- Model hanya berjalan di **notebook Colab**. Script dan model berada **di notebook yang sama**. Jangan menjadikan Colab server yang dipanggil dari laptop.
- Serah-terima **lewat berkas Google Drive**: laptop menaruh `chunks/pending/*.jsonl`, Colab menulis `llm_results/*.jsonl`.
- Model dan parameter ditentukan di `config/model_config.yaml` **setelah pilot** (11.6).

### 11.2 Perilaku notebook (urutan)

1. **Cek lingkungan:** catat jenis GPU, VRAM, versi pustaka. Jika GPU tidak ada atau tidak memenuhi syarat minimum di config, **berhenti dengan pesan jelas** (jangan jalan di CPU diam-diam).
2. Mount Google Drive.
3. Muat konfigurasi dan model.
4. Baca `chunks/pending`, **lewati** `result_key` yang sudah ada di `llm_results`.
5. Proses per chunk atau batch kecil. Tulis hasil **segera** (append, flush rutin).
6. Kegagalan: OOM → kecilkan batch dan coba lagi; bukan JSON → catat `parse_error`, retry maksimal 2; lalu tandai gagal dan lanjut.
7. Catat `latency_s`, `tokens_in`, `tokens_out`.
8. Di akhir: ringkasan (diproses, gagal, rata-rata waktu, taksiran compute unit).

### 11.3 Keterbatasan Colab

- Sesi dapat terputus kapan saja. Rancang agar tahan terputus.
- GPU yang didapat tidak dijamin. Ketersediaan, batas sesi, dan kuota compute unit berubah (**verifikasi di akun pengguna**, V6). Jangan menghardcode asumsi.
- Eksekusi latar belakang kemungkinan tidak tersedia di tier Pro. Anggap **tab harus tetap terbuka**.
- Kuota terbatas. Hanya pemanggilan model di Colab. Semua lainnya di laptop.
- Sebelum batch besar: estimasi = (waktu per chunk dari pilot) × (jumlah chunk yang butuh LLM). Laporkan bila melebihi kuota.

### 11.4 Tiga tugas dan kontrak keluarannya

**Aturan umum prompt:**

- Memuat peran, tugas, **skema keluaran**, aturan anti-mengarang, dan 1–3 contoh dari teks nyata gold standard.
- Model **hanya** memakai `text` dan `context` chunk.
- Keluaran **JSON saja**.
- Tidak ada di teks → `null` atau `[]`.
- `source_quote` disalin **persis** dari `text`.
- Tidak memuat ketentuan yang dimaksud → `{"found": false}`.
- `prompt_version` dicatat. Setiap perubahan prompt menaikkan versi.

**T1 — Instruksi perubahan (fallback)**

Input: blok instruksi + konteks (judul pengubah, kalimat lingkup yang menyebut UU target). Keluaran:

```json
{
  "found": true,
  "target_document_ref": "rujukan UU target sebagaimana tertulis",
  "target_locator_text": "Pasal 17 ayat (1)",
  "target_part": "BATANG_TUBUH",
  "action": "UBAH",
  "new_text": "teks pengganti penuh sebagaimana tertulis, atau null",
  "find_text": null,
  "replace_text": null,
  "insert_after_locator_text": null,
  "insert_before_locator_text": null,
  "effective_hint": "frasa waktu berlaku jika tertulis, atau null",
  "source_quote": "kutipan persis dari input",
  "confidence": 0.0
}
```

**T2 — Isi ketentuan**

Input: teks pasal/ayat + konteks. Keluaran mengikuti Bagian 6.11 (tanpa `rule_id`, `document_id`, `validation_status`, yang diisi script). Satu chunk boleh menghasilkan beberapa aturan (`"rules": [...]`). Pisahkan kondisi, kewajiban, pengecualian, dan konsekuensi.

```json
{
  "found": true,
  "rules": [
    {
      "rule_type": "eligibility",
      "subject": null,
      "condition": [],
      "obligation": [],
      "right": [],
      "prohibition": [],
      "exception": [],
      "consequence": null,
      "deadline": null,
      "rate_or_value": [],
      "cross_references": [],
      "source_quote": "kutipan persis",
      "effective_period_hint": null,
      "confidence": 0.0
    }
  ]
}
```

**T3 — Label domain**

Input: judul/ringkasan dokumen atau teks pasal + definisi domain dari kartu lingkup (termasuk contoh masuk dan keluar). Keluaran:

```json
{
  "domain_id": "DOMAIN_A",
  "label": "IN",
  "score": 0.0,
  "reason": "alasan singkat yang merujuk pada bagian teks"
}
```

(`label`: `IN`, `OUT`, `UNSURE`).

### 11.5 Penanganan hasil di laptop

1. Impor `llm_results` ke **staging**. Jangan langsung ke tabel utama.
2. Jalankan validator (8.8). Hanya yang lolos masuk `legal_rules.jsonl` atau `amendments` dengan status sesuai.
3. Catat `model_id` dan `prompt_version` di setiap rekaman turunan.
4. Hasil dari `prompt_version` lama **tidak dihapus**, tandai versi lama.
5. Amendment dari T1 hanya ikut diputar ulang setelah `review_status=APPROVED`.

### 11.6 Pilot pemilihan model (wajib sebelum ekstraksi massal)

1. Ambil **30–50 pasal/instruksi** dari `gold_standard.jsonl` (dianotasi manusia dari sumber resmi).
2. Jalankan pada 2–3 kandidat model yang cocok dengan memori GPU yang didapat di Colab dan mendukung bahasa Indonesia serta keluaran JSON.
3. Ukur: akurasi kutipan, kelengkapan kondisi dan pengecualian, kepatuhan format, waktu per chunk, token.
4. Laporkan di `reports/extraction_quality.md`. **Manusia memilih model** (gerbang G6).
5. Jika semua model lemah, periksa prompt, skema, dan chunking sebelum menyimpulkan masalahnya di model.

---

## 12. Ekspor Ontologi

### 12.1 Pembagian tanggung jawab

| | Siapa | Isi |
|---|---|---|
| **TBox** (kelas, properti, definisi) | **Manusia**, di `ontology/kbr-core.ttl` (dirancang di Protégé) | `kbr:Regulasi`, `kbr:Pasal`, `kbr:VersiPasal`, `kbr:PeristiwaPerubahan`, `kbr:Domain`, `kbr:AturanHukum`, properti, dan definisi |
| **ABox** (individu) | **Pipeline** (`export_ttl.py`) | Individu dari data tervalidasi |

Agent **tidak boleh** mengubah `kbr-core.ttl` tanpa persetujuan. Agent boleh **mengusulkan** penambahan kelas atau properti di `ISSUES.md`.

### 12.2 Pemetaan SQLite → ontologi

| Data di SQLite | Menjadi di ontologi |
|---|---|
| `documents` | Individu `kbr:Regulasi` (subkelas per jenis) |
| `provisions` | Individu `kbr:Pasal`, `kbr:Ayat`, dst. (`kbr:bagianDari` ke induk) |
| `provision_versions` | Individu `kbr:VersiPasal` (`kbr:versiDari`, `kbr:validFrom`, `kbr:validTo`, `kbr:dihasilkanOleh`) |
| `amendments` | Individu `kbr:PeristiwaPerubahan` (`kbr:pengubah`, `kbr:target`, `kbr:aksi`) |
| `relations` | Object property `kbr:mengubah`, `kbr:mencabut`, `kbr:melaksanakan`, `kbr:merujuk` |
| `domain_tags` | `kbr:bertag` ke individu `kbr:Domain` |
| `legal_rules` (tervalidasi) | Individu `kbr:AturanHukum` dengan `kbr:sourceQuote`, `kbr:sourceURL`, `kbr:extractionMethod` |

### 12.3 Aturan ekspor

- Base IRI dan prefix di `config/ontology.yaml`. IRI individu **deterministik**, diturunkan dari `document_id`/`locator` (mengganti `#` dan `/` dengan `_`).
- Ekspor **hanya** data yang memenuhi: amendment `APPROVED`, aturan `VALIDATED`, versi pasal yang **tidak** memiliki `chain_issues` `BLOCKING` berstatus `OPEN`. Sisanya **dihitung dan dilaporkan** sebagai "tidak diekspor beserta alasannya" (M11).
- Tanggal sebagai `xsd:date`. `valid_to` yang kosong **tidak** ditulis (jangan memakai tanggal sentinel).
- **Jangan** mengekspor data proses: antrean crawl, status pemrosesan, output mentah LLM.
- Ekspor dapat dibangun ulang kapan saja dari SQLite. SQLite tetap sumber kebenaran.
- Turtle (`.ttl`) adalah format utama. Format lain hanya bila diminta.
- Verifikasi hasil dengan memuatnya kembali (`rdflib`) dan menjalankan beberapa query uji, misalnya "versi pasal P pada tanggal T" dan "jumlah pengubah UU U".

### 12.4 Contoh (ilustratif)

```turtle
kbr:UU-AAAA-N_BT_5_v1 a kbr:VersiPasal ;
    kbr:versiDari      kbr:UU-AAAA-N_BT_5 ;
    kbr:validFrom      "0000-00-00"^^xsd:date ;
    kbr:validTo        "0000-00-00"^^xsd:date ;
    kbr:dihasilkanOleh kbr:amend_12 .

kbr:amend_12 a kbr:PeristiwaPerubahan ;
    kbr:pengubah kbr:UU-BBBB-M ;
    kbr:target   kbr:UU-AAAA-N_BT_5 ;
    kbr:aksi     "UBAH" .
```

---

## 13. Output Akhir

| Keluaran | Isi | Pengguna |
|---|---|---|
| `data/kbr.sqlite` | Seluruh data kerja | Tim, script |
| `data/export/jsonl/*.jsonl` + `data_dictionary.md` | Ekspor tiap tabel (`documents`, `relations`, `provisions`, `provision_versions`, `amendments`, `legal_rules`, `domain_tags`) | Tahap ontologi |
| `data/export/ttl/kbr-data.ttl` | ABox ontologi | Protégé, reasoner |
| `data/validation/gold_standard.jsonl` | Anotasi manual | Evaluasi |
| `data/review/review_queue.csv` | Daftar yang perlu diperiksa manusia | Tim |
| `reports/source_coverage.md` | Kelengkapan peraturan (M1–M8) | Dosen, tim |
| `reports/extraction_quality.md` | Akurasi ekstraksi vs gold standard | Dosen, tim |
| `reports/chain_report.md` | Kualitas rantai riwayat (M4, M5, M9, M10) | Dosen, tim |
| `reports/known_limitations.md` | Dokumen belum ditemukan dan hal belum tervalidasi | Dosen, tim |

**Tampilan fitur riwayat (contoh bentuk):**

```
Pasal X · UU Contoh (UU-AAAA-N)
Diubah 2 kali · Versi saat ini: v2

v0  Teks asli                       berlaku: [tgl A] → [tgl B]
v1  Diubah oleh UU-BBBB-M Pasal Y   berlaku: [tgl B] → [tgl C]
v2  Diubah oleh UU-CCCC-K Pasal Z   berlaku: [tgl C] → sekarang
    ⚠ Catatan peralihan: lihat Pasal Z
    ✔ Cocok dengan naskah konsolidasi (sampel)
```

Yang **bukan** output tahap ini: ontologi final beserta definisi kelasnya, reasoning engine, rekomendasi pajak untuk pengguna, case-based reasoning, dan keputusan hukum final.

---

## 14. Metrik Kelengkapan dan Kualitas

Hitung dan laporkan di tiap fase.

### 14.1 Kelengkapan dan rantai

| Kode | Metrik | Target |
|---|---|---|
| M1 | Antrean kunjungan tersisa per domain (closure) | 0 |
| M2 | `unresolved_citations` berstatus `UNRESOLVED` | 0, atau semua punya status terminal beralasan |
| M3 | Selisih daftar dokumen antar-sumber | Dijelaskan satu per satu |
| M4 | Pasal dengan rantai versi lengkap / total pasal pajak | Dilaporkan, tren naik |
| M5 | Pasal sampel yang cocok dengan konsolidasi/matriks | Dilaporkan, mismatch diselidiki |
| M6 | Pelanggaran invarian I1–I3 | 0 |
| M7 | Dokumen `FAILED`/`NEEDS_REVIEW` per tahap | Dilaporkan dengan alasan |
| M8 | `BOUNDARY`/`UNDECIDED` belum ditinjau | Dilaporkan |
| M9 | `chain_issues` per `issue_type` dan statusnya | Semua `BLOCKING` punya penanganan |
| M10 | Pemeriksaan C1 dan C2 yang gagal | Dijelaskan satu per satu |
| M11 | Data yang **tidak diekspor** ke ontologi dan alasannya | Dilaporkan |
| M12 | Rasio instruksi perubahan tertangkap pola vs LLM vs manual | Dilaporkan |

### 14.2 Kualitas ekstraksi (vs gold standard)

- *Precision, recall, F1* per field (kondisi, kewajiban, pengecualian, konsekuensi, tarif, batas waktu).
- *Citation accuracy*: persentase `source_quote` cocok persis dan `locator` benar.
- *Field completeness* untuk field relevan.
- Laporkan **terpisah**, tidak digabung ke skor agregat: akurasi nomor pasal, pengecualian yang terlewat, dan periode berlaku.
- *Error rate* dan taksonomi kesalahan di `extraction_error_log.csv`: kutipan tidak ada, pengecualian hilang, angka salah, dasar hukum dikarang, struktur salah.

### 14.3 Gold standard

- Disusun **manusia** dari sumber resmi. Awal 30–50 butir, mewakili jenis dokumen berbeda dan kasus sulit.
- Format `gold_standard.jsonl`: `document_id`, `locator`, `task_type`, nilai benar per field, `annotator`.
- Tambahkan **butir rantai**: untuk beberapa pasal, urutan perubahan dan bunyi tiap versi yang benar.
- Agent **tidak boleh** mengisi atau mengubah gold standard.

---

## 15. Catatan Hukum dan Temporal

### 15.1 Tiga hal yang dipisah

1. **Identitas dokumen** (`document_id`).
2. **Versi ketentuan** (`provision_versions`).
3. **Keberlakuan hukum** (`legal_status`, `valid_from/valid_to`).

Satu peraturan bisa masih berlaku tetapi sebagian pasalnya sudah diubah. Dokumen lama tetap penting untuk periode sebelumnya.

### 15.2 Tanggal berlaku

- `valid_from` **tidak selalu sama** dengan tanggal pengundangan. Suatu ketentuan dapat berlaku mulai periode tertentu (mis. tahun pajak tertentu) atau bertahap. Contoh: UU HPP disahkan 29 Oktober 2021 tetapi berlaku mulai tahun pajak 2022 menurut sumber yang diteliti. **Verifikasi dari teks.**
- Baca **ketentuan mulai berlaku** dan **ketentuan peralihan** (`role=EFFECTIVITY`/`TRANSITIONAL`). Simpan basisnya di `effective_basis`.
- Tidak dapat dipastikan dari teks → `NULL` dan `NEEDS_REVIEW`. **Jangan menebak dari tahun peraturan.**
- Ketentuan peralihan yang mempertahankan aturan lama dicatat di `applicability_notes`, **tidak** diselesaikan otomatis.

### 15.3 Hierarki

UU/Perpu → PP → Perpres → PMK → PER-DJP → SE. Simpan relasi `MELAKSANAKAN`. Jika UU induk berubah, peraturan pelaksana **ditandai** untuk ditinjau, tidak otomatis dinyatakan tidak berlaku.

### 15.4 Sumber perubahan lain

UU yang mengubah UU pajak tidak harus UU pajak (mis. UU omnibus lintas sektor). Putusan MK dan penetapan Perpu juga dapat mengubah norma.

### 15.5 Konflik antar-aturan

Tahap ini **tidak menyelesaikan** konflik (*lex superior*, *lex specialis*, *lex posterior* adalah urusan reasoning). Yang dilakukan: **menandai** pasangan ketentuan yang tampak bertentangan atau tumpang tindih ke `review_queue` dengan alasan `POSSIBLE_CONFLICT`. Jangan otomatis memilih dokumen terbaru.

### 15.6 Disclaimer

Output tahap ini adalah data pendukung sistem informasi dan mitigasi risiko, **bukan nasihat hukum**. Hasil yang belum `VALIDATED` tidak boleh diperlakukan sebagai aturan final.

---

## 16. Etika dan Ketentuan Teknis Pengambilan Data

1. Cek `robots.txt` dan ketentuan penggunaan setiap sumber **sebelum** menjelajah. Catat hasilnya di `config/sources.yaml` (`robots_checked`, `tos_notes`). Jika pengambilan otomatis dilarang, **berhenti dan tanya pengguna**.
2. Jeda antar-permintaan, retry dengan backoff, dan cache. Jangan mengambil ulang halaman yang tidak berubah. Jelajah besar sebaiknya di luar jam sibuk.
3. Jangan mencoba menembus autentikasi atau pembatasan akses.
4. Cache HTML boleh dibuang. PDF sementara **dihapus** setelah ekstraksi. Yang disimpan: teks hasil ekstraksi, metadata, hash, URL sumber.
5. Jangan menyimpan data pribadi yang tidak diperlukan.
6. Jangan mengambil dokumen dari sumber yang tidak jelas keaslian atau izinnya.

---

## 17. Rencana Kerja Bertahap dan Gerbang

Tiap fase memiliki tugas, output, dan **gerbang (G)** persetujuan manusia. Agent berhenti di setiap gerbang.

### Fase 0 — Fondasi dan skema

- [ ] Buat struktur proyek (Bagian 4), `AGENTS.md`, `ISSUES.md`.
- [ ] DDL SQLite untuk semua tabel di Bagian 6 dan `db.py`.
- [ ] `ids.py` dengan tes menggunakan contoh nyata.
- [ ] Kerangka `cli.py` (`kbr init`, `kbr status`).
- [ ] Template `scope_cards/`, `crawl.yaml`, `relation_map.yaml`, `ontology.yaml` (tanpa seed).
- [ ] Kerangka `report.py` (M1–M12 pada DB kosong).

**G0:** ketiga anggota menyetujui skema (terutama `amendments`, `provision_versions`, `chain_issues`).

### Fase 1 — Pilot penjelajahan (1 seed, ≤ 20 dokumen)

Prasyarat: satu kartu lingkup terisi.

- [ ] Cek `robots.txt` dan ketentuan penggunaan sumber, catat hasilnya.
- [ ] **Inspeksi** struktur halaman sumber primer pada 3–5 contoh, simpan sebagai fixture, dokumentasikan selector di `sources.yaml`.
- [ ] `crawl.py` + `scope.py`. Dry-run dulu, lalu jalankan dengan batas 20 dokumen.
- [ ] Laporan: jumlah dokumen dan relasi, distribusi `scope_status`, kasus aneh.

**G1:** manusia memeriksa **semua** dokumen pilot dan relasinya terhadap sumber asli.

### Fase 2 — Closure per domain

- [ ] Kalibrasi `thresholds` kartu lingkup dari hasil Fase 1.
- [ ] Closure penuh tiap domain (resumable).
- [ ] Rekonsiliasi dengan sumber kedua (dan ketiga).
- [ ] Daftarkan dokumen `REFERENCE` (UU 12/2011, UU 15/2019, UU 13/2022).
- [ ] `source_coverage.md` (M1, M3, M6, M7, M8).

**G2:** tim meninjau `UNDECIDED`/`BOUNDARY`, memastikan invarian I1–I3 = 0.

### Fase 3 — Ingest dan parsing struktur

- [ ] `ingest.py`. OCR → `NEEDS_REVIEW`.
- [ ] `parse_structure.py` dengan fixture tiap jenis dokumen, termasuk omnibus.
- [ ] Baca Lampiran II dan tulis `patterns_amendment.yaml` awal berserta rujukan angka (Bagian 5.4).
- [ ] Laporan kualitas parsing pada sampel 10 dokumen.

**G3:** manusia memeriksa sampel parsing (nomor pasal, urutan, `role` peralihan dan mulai berlaku, `title_ordinal`).

### Fase 4 — Amendment pola baku dan putaran lubang

- [ ] `amendments.py` (langkah A dan C) dengan tes dari dokumen nyata (UU perubahan tunggal dan omnibus).
- [ ] `gaps.py` dan putaran balik ke S1.
- [ ] Hitung rasio instruksi tertangkap pola (M12). Siapkan chunk `T1_AMENDMENT` untuk sisanya (belum dijalankan).
- [ ] Perbarui `source_coverage.md` (M2).

**G4:** manusia mereview sampel amendment (semua dari Putusan MK/Perpu) dan menyetujui pola.

### Fase 5 — Rantai riwayat tanpa LLM

- [ ] `chain_order.py`, `replay.py`, `chain_checks.py` dengan tes sesuai 10.7.
- [ ] Jalankan pada **dokumen dengan pola bersih** (amendment berstatus `APPROVED` oleh manusia).
- [ ] Query riwayat (9.12) dan `chain_report.md` (M4, M5, M9, M10).
- [ ] **Kasus uji penerimaan:** tarif Pasal 17 UU PPh **sebelum dan sesudah** UU HPP. Nilai benar harus berasal dari sumber resmi yang dibaca manusia dan dicatat di `gold_standard.jsonl`. Agent tidak boleh mengisi nilai harapan dari ingatan.

**G5:** manusia memverifikasi sampel riwayat dan kasus uji terhadap sumber resmi.

### Fase 6 — Pilot LLM di Colab

- [ ] `gold_standard.jsonl` awal (**manusia**, 30–50 butir termasuk butir rantai).
- [ ] `colab_extract.ipynb` (Bagian 11). Uji alur dengan **keluaran palsu** di laptop.
- [ ] `chunking.py` untuk T1, T2, T3.
- [ ] Jalankan pilot 30–50 chunk pada 2–3 kandidat model.
- [ ] `validate.py` dan metrik (14.2). Estimasi kuota ekstraksi massal.

**G6:** manusia memilih model dan prompt, dan menyetujui estimasi kuota.

### Fase 7 — Ekstraksi massal dan validasi

- [ ] Batch per domain dan per dokumen dengan checkpoint dan manifest.
- [ ] Impor hasil, validasi, isi `review_queue`.
- [ ] Jalankan ulang yang gagal atau berubah (hash).
- [ ] Amendment hasil T1 masuk review.

**G7:** manusia menyelesaikan antrean review berisiko tinggi.

### Fase 8 — Lengkapi rantai dan verifikasi

- [ ] Putar ulang rantai dengan amendment tambahan yang sudah `APPROVED`.
- [ ] Tangani `chain_issues` `BLOCKING` (perbaiki peristiwa atau catat `ACCEPTED` beralasan).
- [ ] Verifikasi sampel dengan konsolidasi/matriks (M5), laporan C1, C2 (M10).

**G8:** manusia memverifikasi sampel riwayat tambahan.

### Fase 9 — Ekspor dan serah ke tahap ontology

- [ ] `export_jsonl.py` dan `data_dictionary.md`.
- [ ] `export_ttl.py` terhadap `ontology/kbr-core.ttl` buatan manusia. Verifikasi dengan memuat ulang dan query uji (12.3).
- [ ] `known_limitations.md` dan laporan akhir cakupan dan kualitas.

**Output:** paket data siap dipakai untuk pembangunan ontology dan reasoning.

### 17.10 Definition of Done per dokumen

- [ ] Terdaftar dengan `document_id`, URL sumber, metadata, dan `scope_status` jelas.
- [ ] Relasi dicatat sejauh diketahui. Ketidakpastian ditandai.
- [ ] Teks berhasil diambil (atau kegagalannya tercatat) dan `content_hash` tersimpan.
- [ ] Struktur pasal/ayat terparsing dan sampelnya diperiksa.
- [ ] Jika dokumen pengubah: semua instruksi tercatat sebagai amendment dengan status review.
- [ ] Jika dokumen target: rantai versi dibangun dan `chain_issues` `BLOCKING` tertangani atau terlacak.
- [ ] Hasil ekstraksi sesuai skema, `source_quote` terverifikasi persis, `model_id` dan `prompt_version` tercatat.
- [ ] Kategori berisiko sudah direview manusia.
- [ ] Kutipan peraturan dalam teks sudah terselesaikan atau punya status terminal beralasan.
- [ ] `legal_status` terverifikasi atau tetap `NEEDS_VERIFICATION` secara eksplisit.
- [ ] Hasil yang belum tervalidasi **tidak** diperlakukan sebagai aturan final dan **tidak** diekspor sebagai data tervalidasi.

### 17.11 Format laporan fase (`reports/phase_<N>.md`)

1. Apa yang dikerjakan (tugas dan statusnya).
2. Berkas dan modul yang dibuat atau diubah.
3. Hasil tes otomatis.
4. Metrik relevan (Bagian 14) dengan angka.
5. Contoh keluaran nyata (3–5 sampel, termasuk yang gagal).
6. Masalah dan ketidakpastian (juga di `ISSUES.md`).
7. Asumsi yang diambil.
8. Usulan langkah berikutnya dan hal yang menunggu persetujuan manusia.

---

## 18. Peran Tim

| Peran | Tanggung jawab |
|---|---|
| **Pemilik domain (×3)** | Mengisi dan memelihara kartu lingkup, menentukan seed, meninjau `UNDECIDED`/`BOUNDARY` domainnya, reviewer utama tag domain |
| **Pemegang dokumen inti bersama (`SHARED`)** | Satu orang (bergiliran bila perlu) mengawasi dokumen lintas domain (KUP, UU omnibus) dan rantainya |
| **Penyusun gold standard** | Manusia, dari sumber resmi, disarankan lintas anggota untuk pemeriksaan silang |
| **Perancang ontologi (TBox)** | Mengelola `ontology/kbr-core.ttl` |
| **Penyetuju gerbang** | Ketiganya untuk G0. Minimal dua anggota untuk gerbang lain |

Agent tidak menggantikan peran di atas.

---

## 19. Hal yang Belum Diverifikasi (agent wajib memeriksa, lalu mencatat di `ISSUES.md`)

| # | Hal | Mengapa penting |
|---|---|---|
| V1 | API resmi atau izin pengambilan otomatis tiap sumber (`robots.txt`, ketentuan penggunaan) | Menentukan boleh tidaknya penjelajahan otomatis |
| V2 | Struktur HTML sebenarnya di `peraturan.bpk.go.id`, `jdih.kemenkeu.go.id`, portal DJP | Parser tidak boleh berdasarkan asumsi |
| V3 | Seberapa lengkap metadata relasi di sumber (dugaan: tidak lengkap) | Menentukan beban S5, S6, dan C6 |
| V4 | Teks tersedia sebagai HTML/teks atau hanya PDF, dan apakah PDF teks atau pindaian | Menentukan kebutuhan OCR |
| V5 | Ketersediaan naskah konsolidasi atau matriks perubahan untuk UU pajak, dan status lisensinya | Menentukan skala verifikasi M5 |
| V6 | Batas sesi, jenis GPU, dan kuota compute unit akun Colab Pro saat ini | Menentukan model dan skala batch |
| V7 | Kandidat model yang cocok dengan GPU yang didapat, dan kualitas bahasa hukum Indonesia | Ditentukan lewat pilot |
| V8 | Definisi "lengkap" dari dosen dalam bentuk daftar kategori dokumen | Agar kelengkapan dapat diuji |
| V9 | Pola kalimat perubahan sebenarnya pada dokumen nyata (UU perubahan tunggal vs omnibus) | Dasar `patterns_amendment.yaml` |
| V10 | Ada tidaknya perubahan tingkat frasa ("kata X diubah menjadi Y") dan rumusan bakunya di Lampiran II | Dasar aksi `GANTI_FRASA`/`HAPUS_FRASA` |
| V11 | Status terbaru UU 12/2011 (ada perubahan setelah UU 13/2022?) dan versi Lampiran II yang berlaku | Dasar pola dan struktur |
| V12 | Peraturan pelaksana UU 12/2011 (Perpres 87/2014?) dan isinya | Rujukan tambahan teknik penyusunan |
| V13 | Ketersediaan kunci urutan di sumber (`ln_tahun`, `ln_nomor`, tanggal pengundangan, tanggal berlaku) | Menentukan seberapa kuat K1–K4 |
| V14 | Aturan penomoran pasal dihapus dan disisipkan menurut Lampiran II | Menentukan perilaku `HAPUS` dan `SISIP` |

---

## 20. Larangan (Anti-Pattern)

- Menyimpan "UU" sebagai satu blok teks. Selalu di level pasal/ayat.
- Menimpa teks pasal lama saat ada perubahan, atau mengedit `provision_versions` secara langsung.
- Menganggap `status_sumber` = `legal_status`.
- Menganggap relasi di metadata sumber sudah lengkap.
- Menerima nomor pasal, tarif, atau tanggal dari ingatan model.
- Menebak tanggal berlaku dari tahun peraturan, atau memilih urutan perubahan diam-diam saat kunci bertentangan.
- Melanjutkan pemutaran ulang setelah prasyarat gagal.
- Mengabaikan perubahan non-UU (Putusan MK, Perpu) atau perubahan pada penjelasan.
- Menjalankan ekstraksi massal lewat percakapan OpenCode.
- Menjalankan model di CPU Colab secara diam-diam atau tanpa cek GPU.
- Membuat salinan script per domain.
- Mengikuti relasi tanpa melewati gerbang relevansi.
- Membuang dokumen di luar domain (catat sebagai `BOUNDARY`/`OUT_OF_SCOPE`).
- Memilih "dokumen terbaru" otomatis saat ada konflik.
- Mengisi atau mengubah `gold_standard.jsonl`, atau mengubah `ontology/kbr-core.ttl` tanpa persetujuan.
- Memasukkan hasil LLM ke data tervalidasi tanpa validator.
- Mengekspor data proses atau data yang belum tervalidasi ke ontologi sebagai fakta.
- Menyimpan PDF mentah permanen atau data pribadi yang tidak perlu.
- Mengabaikan `robots.txt`/ketentuan penggunaan, atau memadati server sumber.
- Melompati gerbang persetujuan.

---

## 21. Glosarium

| Istilah | Arti |
|---|---|
| **ABox / TBox** | Individu (ABox) vs kelas dan properti (TBox) dalam ontologi |
| **Amendment** | Peristiwa perubahan suatu pasal oleh peraturan lain |
| **Boundary node** | Dokumen di luar lingkup domain yang dicatat tetapi tidak dijelajahi |
| **Chunk** | Potongan teks (pasal/ayat + konteks) yang dikirim ke model |
| **Closure** | Kondisi ketika penjelajahan tidak lagi menemukan dokumen baru |
| **Dangling reference** | Kutipan peraturan di teks yang belum ada di registry |
| **Event sourcing** | Menyimpan peristiwa sebagai data sumber, dan membangun keadaan akhir dengan memutar ulangnya |
| **Gerbang (Gate)** | Titik berhenti yang membutuhkan persetujuan manusia |
| **Gold standard** | Anotasi manual dari sumber resmi sebagai tolok ukur |
| **Konsolidasi** | Naskah gabungan satu peraturan dengan semua perubahannya (sekunder bila dari pihak swasta) |
| **Locator** | Alamat kanonik sebuah ketentuan dalam dokumen |
| **Omnibus** | Peraturan yang mengubah banyak peraturan lain sekaligus |
| **Order key** | Kunci (K1–K5) untuk mengurutkan peristiwa perubahan |
| **Provenance** | Asal-usul data (dokumen, pasal, URL, metode, model, versi prompt) |
| **Reification** | Memperlakukan peristiwa (mis. perubahan) sebagai entitas tersendiri |
| **Replay** | Memutar ulang peristiwa perubahan berurutan untuk membangun versi pasal |
| **Staging** | Area penampungan hasil yang belum divalidasi |
| **Valid time** | Rentang waktu berlakunya suatu versi (`valid_from` s.d. `valid_to`) |
| **Aktif/pasif (relasi)** | Relasi disimpan hanya dalam bentuk aktif ("B mengubah A") |

---

## 22. Lampiran: Contoh Rekaman (ilustratif)

> Semua nilai **hanya memperlihatkan bentuk data**. Bukan data nyata dan bukan interpretasi hukum. Jangan disalin ke dataset.

**`documents` (ringkas):**

```json
{
  "document_id": "XX-0000-0",
  "jenis": "XX",
  "nomor_raw": "0",
  "tahun": 0,
  "judul": "…",
  "title_ordinal": null,
  "status_sumber": "…",
  "scope_status": "IN_SCOPE",
  "owner_domain": "DOMAIN_A",
  "discovery_status": "METADATA_FETCHED",
  "ingestion_status": "PENDING",
  "extraction_status": "PENDING",
  "validation_status": "PENDING",
  "legal_status": "NEEDS_VERIFICATION"
}
```

**`relations`:**

```json
{
  "from_document_id": "XX-0000-1",
  "to_document_id": "XX-0000-0",
  "relation_type": "MENGUBAH",
  "origin": "SOURCE_METADATA",
  "evidence": "<url sumber>",
  "confidence": 1.0,
  "verified": 0
}
```

**`amendments` (UBAH):**

```json
{
  "amending_document_id": "XX-0000-1",
  "amending_locator": "XX-0000-1#BT/I/3",
  "instruction_ordinal": 3,
  "target_document_id": "XX-0000-0",
  "target_locator": "XX-0000-0#BT/17",
  "target_part": "BATANG_TUBUH",
  "action": "UBAH",
  "new_text": "…teks pengganti penuh…",
  "effective_from": null,
  "effective_basis": null,
  "parse_method": "RULE",
  "confidence": 0.95,
  "source_quote": "…kutipan persis…",
  "review_status": "PENDING"
}
```

**`amendments` (SISIP):**

```json
{
  "amending_document_id": "XX-0000-1",
  "instruction_ordinal": 4,
  "target_document_id": "XX-0000-0",
  "target_locator": "XX-0000-0#BT/5A",
  "action": "SISIP",
  "insert_after_locator": "XX-0000-0#BT/5",
  "insert_before_locator": "XX-0000-0#BT/6",
  "new_text": "…",
  "review_status": "PENDING"
}
```

**`amendments` (GANTI_FRASA):**

```json
{
  "target_locator": "XX-0000-0#BT/9/2",
  "action": "GANTI_FRASA",
  "find_text": "…frasa lama…",
  "replace_text": "…frasa baru…",
  "review_status": "PENDING"
}
```

**`chain_order`:**

```json
{
  "target_document_id": "XX-0000-0",
  "amendment_id": 12,
  "seq_no": 3,
  "key_k1": null,
  "key_k2": "0000-00-00",
  "key_k3": "0000-00-00",
  "key_k4": [0, 0],
  "key_k5": 3,
  "key_used": "K2"
}
```

**`provision_versions`:**

```json
{
  "version_id": "XX-0000-0#BT/5@v1",
  "provision_id": "XX-0000-0#BT/5",
  "version_no": 1,
  "text": "…",
  "valid_from": null,
  "valid_to": null,
  "created_by_document_id": "XX-0000-1",
  "created_by_amendment_id": 12,
  "seq_no": 3,
  "reconstruction_method": "APPLIED_AMENDMENT",
  "verification_status": "UNVERIFIED"
}
```

**`chain_issues`:**

```json
{
  "target_document_id": "XX-0000-0",
  "amendment_id": 14,
  "provision_id": "XX-0000-0#BT/5A",
  "issue_type": "TARGET_NOT_FOUND",
  "severity": "BLOCKING",
  "detail": "HAPUS menarget Pasal 5A, tetapi tidak ada versi sebelum seq_no 4",
  "status": "OPEN"
}
```

**Entri manifest (`batch_manifest.jsonl`):**

```json
{
  "batch_id": "BATCH-0001",
  "task_type": "T2_RULE",
  "model_id": "<dari model_config>",
  "prompt_version": "v1",
  "chunks_total": 0,
  "chunks_done": 0,
  "chunks_failed": 0,
  "gpu": "<terdeteksi di notebook>",
  "started_at": null,
  "finished_at": null
}
```

---

*Akhir dokumen. Mulai dari Fase 0 dan berhenti di G0.*
