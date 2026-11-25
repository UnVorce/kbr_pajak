# RENCANA KNOWLEDGE ACQUISITION SYSTEM (v2)

## Sistem Informasi Prosedur dan Mitigasi Risiko Perpajakan di Indonesia

> **Versi:** v2 — ditulis ulang agar selaras penuh dengan `KBR_Extraction_Spec.md`.
> **Sumber kebenaran tunggal:** `KBR_Extraction_Spec.md`. Jika ada pertentangan
> antara dokumen ini dan spec, **spec yang menang** — tanyakan dulu.
> **Perubahan besar dari v1:** Hermes Agent, Ollama, Google Sheets (registry),
> dan PostgreSQL **tidak lagi dipakai**. Penggantinya: **OpenCode** (agent),
> **LLM hanya di Google Colab Pro**, **SQLite** (penyimpanan inti), **JSONL**
> via Google Drive (pertukaran dengan Colab).

---

## 1. Tujuan Tahap Akuisisi & Ekstraksi

Mengubah peraturan perpajakan resmi menjadi pengetahuan terstruktur yang dapat
ditelusuri (provenance) sampai ke pasal/ayat dan URL sumber:

1. Mengumpulkan peraturan perpajakan yang relevan dengan **kelengkapan yang
   terukur** (closure graf relasi, nol kutipan menggantung, rekonsiliasi
   antar-sumber) — bukan sekadar "sebanyak yang ketemu".
2. Memecah tiap peraturan menjadi **pasal, ayat, huruf** yang dapat dirujuk.
3. Menangkap **riwayat perubahan di level pasal** (diubah, disisipkan, dihapus,
   dicabut) sehingga bisa menjawab "pasal ini diubah berapa kali?" dan "bunyi
   pasal ini pada tanggal tertentu?".
4. Mengekstrak isi ketentuan menjadi struktur (kondisi, kewajiban, hak,
   larangan, pengecualian, konsekuensi, batas waktu, tarif) dengan
   **kutipan sumber yang dapat diverifikasi**.
5. Menjaga keterlacakan (provenance) setiap data.
6. Pipeline **resumable** (tahan Colab terputus).

---

## 2. Cakupan

### 2.1 Domain pilot (keputusan tim, satu domain dulu)

> **DOMAIN_A — Kepatuhan dan mitigasi risiko perpajakan Wajib Pajak Orang
> Pribadi yang melakukan kegiatan usaha (termasuk UMKM).**

Domain B dan C menyusul dengan kartu lingkup masing-masing. **Satu script yang
sama dijalankan dengan kartu lingkup berbeda** — jangan membuat salinan script
per domain.

### 2.2 Empat proses utama (fokus pekerjaan)

| # | Proses | Tahapan spec | Fase kerja |
|---|---|---|---|
| 1 | Mencari UU/regulasi yang **lengkap** | S1 penjelajah graf relasi, S2 gerbang relevansi, S6 pendeteksi lubang | Fase 1 → 2 → 4 |
| 2 | Memastikan struktur **bisa dipetakan** | S3 ingest teks, S4 parser pasal/ayat, S5 deteksi perubahan, S9 rekonstruksi versi | Fase 3 → 4 → 7 |
| 3 | Ekstraksi yang **maksimal & sesuai** | S7 chunking + T1/T2/T3 di Colab, S8 validator + review manusia | Fase 5 → 6 |
| 4 | Cara **menyimpan** hasil ekstraksi | Skema Bagian 5 (SQLite), JSONL append-only, manifest | Fase 0 → 8 |

---

## 3. Keputusan Teknologi

| Komponen | Dipakai | Tidak dipakai (v1 lama) |
|---|---|---|
| Agent pengawas/penulis script | **OpenCode** | Hermes Agent |
| Model LLM (ekstraksi) | **Notebook Google Colab Pro** (script + model di notebook yang sama) | Ollama / LLM lokal |
| Penyimpanan inti | **SQLite** satu berkas (`data/kbr.sqlite`) | PostgreSQL (boleh kelak, jangan sekarang) |
| Pertukaran laptop ↔ Colab | **JSONL via Google Drive** (append-only) | API/RPC, Google Sheets API |
| Registry/tracking | **Tabel SQLite** + ekspor CSV review ke Google Sheets | Google Sheets sebagai registry |
| Storage artefak | `data/` lokal + Google Drive untuk serah-terima Colab | Google Drive penuh |
| Ekstraksi massal via percakapan | **Dilarang** (khusus kasus sulit kecil, mode non-interaktif) | — |
| SDK/RPC/plugin OpenCode | Tidak dipakai | — |

Prioritas sumber hukum: **JDIH BPK (primer untuk relasi)** → JDIH Kemenkeu
(rekonsiliasi + PMK) → portal DJP (rekonsiliasi + peraturan DJP). Sumber
sekunder hanya untuk discovery/cross-check, bukan source of truth.

---

## 4. Arsitektur dan Pembagian Tugas (empat pelaku)

| Pelaku | Berjalan di | Tugas | Bukan tugasnya |
|---|---|---|---|
| **Script deterministik (Python)** | Laptop | Crawl graf relasi, registry, ingest teks, parser pasal, deteksi pola perubahan, deteksi lubang, validasi, rekonstruksi riwayat, metrik | Memahami kalimat bebas |
| **Model LLM** | Google Colab Pro | T1 instruksi perubahan tak baku, T2 isi ketentuan, T3 label domain | Menjelajah, memilih dokumen, memutuskan keabsahan |
| **OpenCode (agent)** | Laptop | Menulis/menguji script, menyetel prompt & skema, mengawasi batch, membuat laporan | Ekstraksi massal lewat percakapan; mengubah data tervalidasi |
| **Manusia (tim)** | — | Seed & kartu lingkup, review, gold standard, gerbang persetujuan | — |

Alur:

```
SEED (kartu lingkup, manual)
   │
   ▼
[S1 Penjelajah graf relasi] ──► registry + relations
   ▼
[S2 Gerbang relevansi & kepemilikan] ──► scope_status, owner_domain
   ▼
[S3 Ingest teks] ──► teks per dokumen (+ hash)
   ▼
[S4 Parser struktur pasal] ──► provisions
   ▼
[S5 Pendeteksi perubahan] ──► amendments (pola baku; sisanya T1 via Colab)
   ▼
[S6 Pendeteksi lubang] ──► unresolved_citations ──┐ (dokumen baru kembali ke S1)
   ▼                                              │
[S7 Ekstraksi isi ketentuan] ──► chunks T2 ──► Colab ──► kandidat aturan
   ▼
[S8 Validator + antrean review manusia]
   ▼
[S9 Rekonstruksi versi pasal] ──► provision_versions (riwayat)
   ▼
[S10 Laporan cakupan & kualitas]
```

Putaran **S1 → S4 → S6 → S1** berulang sampai tidak ada dokumen baru — itulah
dasar klaim kelengkapan.

---

## 5. Proses 1 — Mencari UU/Regulasi yang Lengkap

**Definisi "lengkap" (terukur):**
1. **Closure graf relasi** — tidak ada dokumen `IN_SCOPE` yang relasinya
   (`MENGUBAH`, `MENCABUT`, `MELAKSANAKAN`) belum dijelajahi (M1 = 0).
2. **Nol kutipan menggantung** — semua kutipan peraturan di teks ("Mengingat…",
   "sebagaimana telah diubah dengan…", judul "Perubahan atas X") berstatus
   terminal: `RESOLVED` / `NOT_FOUND_AT_SOURCE` / `IGNORED_OUT_OF_SCOPE` (M2).
3. **Rekonsiliasi antar-sumber** — selisih daftar dokumen BPK vs Kemenkeu vs
   DJP dijelaskan satu per satu (M3).
4. Invarian I1–I3 = 0 (M6); dokumen `FAILED`/`NEEDS_REVIEW` dilaporkan (M7);
   `BOUNDARY`/`UNDECIDED` ditinjau (M8).

**Cara kerja:**
- **Seed** diverifikasi manual oleh manusia (agent dilarang mengisi dari
  ingatan — P3). Usulan agent untuk DOMAIN_A ada di
  `config/scope_cards/DOMAIN_A.yaml`: `UU-1983-6` (KUP), `UU-1983-7` (PPh),
  `UU-2021-7` (omnibus HPP, kandidat `shared_core_documents`), `PP-2022-55`,
  `PMK-2024-81`.
- **S1**: kunjungi halaman peraturan (BPK primer) → ambil metadata + blok
  relasi → normalkan ke **bentuk aktif** ("A diubah dengan B" →
  `from=B, to=A, MENGUBAH`) → simpan `documents` + `relations`.
- **S2 (gerbang relevansi)**: skor dari subjek/bidang sumber, kata kunci judul,
  relasi langsung ke `IN_SCOPE`, opsional LLM (T3). `≥0.80` → `IN_SCOPE`;
  `0.40–0.80` → `UNDECIDED` (review queue, tidak dijelajahi dulu); `<0.40` →
  `BOUNDARY` (dicatat, tidak dijelajahi); jelas bukan pajak → `OUT_OF_SCOPE`.
  Gerbang ini mencegah kebocoran penjelajahan lewat UU induk seperti KUP.
- **S6 (pendeteksi lubang)**: kutipan di teks → normalisasi `document_id` →
  yang belum ada di registry dicari ke sumber → dokumen baru balik ke S1.
- **Etika**: `robots.txt`/ketentuan penggunaan dicek dulu; jeda ≥1,5 detik
  (boleh naik); retry backoff; cache; dry-run dulu; batas per run;
  `status_sumber` disimpan apa adanya (≠ `legal_status`).

**Output:** registry dokumen + graf relasi, `unresolved_citations`,
`reports/source_coverage.md`. **Gerbang:** G1 (pilot ≤20 dokumen diperiksa
semua oleh manusia), G2 (closure + review UNDECIDED/BOUNDARY + I1–I3 = 0).

---

## 6. Proses 2 — Memastikan Struktur Bisa Dipetakan

- **Locator kanonik:** `<document_id>#<bagian>/<pasal>[/<ayat>[/<huruf>[/<angka>]]]`
  — contoh `UU-1983-7#BT/17/1/a` (BT = batang tubuh, PJ = penjelasan).
  Nomor sisipan (`4A`) dipertahankan. Teks manusiawi disimpan di `locator_text`.
- **S3 ingest:** teks di `data/text/<document_id>.txt` + `content_hash`
  (SHA-256). HTML/API didahulukan; PDF sementara di `cache/pdf_tmp/` (dihapus
  setelah diproses); OCR → `NEEDS_REVIEW`. Perbaikan karakter **tanpa mengubah
  makna hukum**; dilarang stemming/menghapus tanda baca/menggabungkan pasal.
  Hash berubah → semua turunan ditandai `STALE` dan di-requeue.
- **S4 parser:** hierarki Bab → Bagian → Paragraf → Pasal → Ayat → Huruf →
  Angka. **Parser menyesuaikan format tiap sumber** (UU omnibus punya struktur
  berbeda: nomor pasal romawi, per-UU target), tidak memaksakan satu pola.
  `role` wajib dikenali: `SUBSTANTIVE`, `AMENDING_INSTRUCTION`,
  `TRANSITIONAL`, `EFFECTIVITY` (kunci untuk `valid_from`), `DEFINITION`,
  `CLOSING`. `BATANG_TUBUH` dan `PENJELASAN` dipisah. Gagal parse →
  `NEEDS_REVIEW`, tidak menebak.
- **S5 deteksi perubahan:** pola baku/regex dulu ("Ketentuan Pasal X diubah
  sehingga berbunyi…", "Di antara Pasal X dan Pasal Y disisipkan…", "Pasal X
  dihapus", "dicabut dan dinyatakan tidak berlaku", "Ditambahkan … ayat") →
  sisanya ke LLM (T1). Omnibus: tentukan **UU target** per bab/pasal.
  **Putusan MK & Perpu selalu `review_status=PENDING`**. UU non-pajak yang
  mengubah UU pajak tetap ditangkap.
- **S9 rekonstruksi versi:** versi 0 = teks asli (`ENACTED_TEXT`); tiap
  amendment `APPROVED` → versi baru (`APPLIED_AMENDMENT`); interval
  `[valid_from, valid_to)` tanpa tumpang tindih; verifikasi silang dengan
  naskah konsolidasi (alat uji saja, bukan dasar hukum).
- **Acceptance test wajib (Fase 7):** tarif Pasal 17 UU PPh **sebelum vs
  sesudah UU HPP** — nilai harapan dari `gold_standard.jsonl` yang ditulis
  **manusia**, bukan ingatan agent.
- **Kriteria sukses:** sampel 10 dokumen dicek manusia (pasal tidak
  hilang/duplikat, urutan benar) + tes otomatis lulus pada fixture nyata.

---

## 7. Proses 3 — Ekstraksi yang Maksimal & Sesuai

- **Prinsip:** deterministik dulu, LLM belakangan. LLM hanya 3 tugas sempit di
  **Colab Pro**: **T1** instruksi perubahan tak baku, **T2** isi ketentuan,
  **T3** label domain.
- **Skema hasil T2** (spec 5.12): `rule_type` (eligibility, obligation, right,
  prohibition, exception, sanction, deadline, rate, definition, procedure,
  other), `subject`, `condition[]`, `obligation[]`, `right[]`,
  `prohibition[]`, `exception[]`, `consequence`, `deadline`,
  `rate_or_value[]`, `cross_references[]`, `source_quote` (substring
  **persis**), `effective_period_hint`, `confidence`.
- **Anti-mengarang:** model hanya boleh memakai `text` + `context` chunk;
  yang tidak tertulis → `null`/`[]`; tarif, nomor pasal, tanggal **tidak
  boleh** dari pengetahuan model. Keluaran JSON saja; prompt memuat skema +
  aturan anti-mengarang + 1–3 contoh few-shot dari gold standard.
- **Chunking hukum:** per pasal/ayat, tidak dipotong tengah ayat; konteks
  minimal (judul UU, judul bab, ayat induk, rujukan silang singkat)
  disertakan. `chunk_id` deterministik: `sha256(document_id + locator +
  text_hash + task_type)`.
- **Validasi di laptop (bukan oleh model), berurutan:**
  1. *Struktur:* JSON valid, skema benar, ID unik.
  2. *Sumber:* `document_id` ada di registry; `source_locator` ada di
     `provisions`; `source_quote` substring persis (normalisasi spasi/baris
     saja); nomor pasal/ayat yang disebut ada di teks.
  3. *Logika:* angka/tarif/tanggal pada hasil harus muncul di teks chunk;
     token di luar teks ditandai; deteksi duplikasi; rujukan belum tersedia →
     `unresolved_citations`.
  4. *Waktu:* `valid_from`/`effective_period` hanya dari teks atau S9, tidak
     dari model.
  Status: `EXTRACTED → SCHEMA_VALID → SOURCE_VERIFIED → VALIDATED |
  REVIEW_REQUIRED | REJECTED`.
- **Wajib review manusia:** tarif/ambang batas, syarat kelayakan fasilitas,
  pengecualian, batas waktu, sanksi, pasal yang pernah diubah, amendment dari
  MK/Perpu, semua `confidence < 0.8`, + sampel acak ≥10% yang lolos otomatis.
- **Pilot sebelum massal (Fase 5):** `gold_standard.jsonl` 30–50 butir
  (**manusia**); uji alur notebook dengan keluaran palsu (tanpa kuota);
  jalankan 2–3 kandidat model; ukur precision/recall/F1 per field + citation
  accuracy + waktu/token; **manusia memilih model (G5)** + setujui estimasi
  kuota.
- **"Maksimal" artinya:** semua pasal `IN_SCOPE` ber-`role=SUBSTANTIVE` (dan
  definisi relevan) terekstrak; % instruksi amendment tertangkap pola vs LLM
  tercatat; tidak ada instruksi tanpa status; Definition of Done per dokumen
  (spec 12.8) terpenuhi.

---

## 8. Proses 4 — Cara Menyimpan Hasil Ekstraksi

- **Penyimpanan inti: satu berkas SQLite `data/kbr.sqlite`** dengan tabel:
  `documents` (registry), `document_aliases`, `relations` (bentuk aktif),
  `provisions`, `provision_versions` (riwayat), `amendments`, `domain_tags`,
  `unresolved_citations`, `chunks`, `llm_results`, `review_queue`,
  `crawl_queue`. DDL lengkap di `src/db.py`.
- **Tiga hal dipisah** (anti-pattern dilarang digabung): identitas dokumen
  (`document_id`) · versi pasal (`provision_versions` + `valid_from/to`) ·
  keberlakuan (`legal_status` — bukan `status_sumber`).
- **File pendamping (JSONL append-only):**
  - `data/text/<document_id>.txt` — bukti verifikasi (PDF mentah tidak disimpan
    permanen);
  - `data/chunks/pending/` (laptop → Colab) & `data/llm_results/` (Colab →
    laptop; idempoten via `result_key`);
  - `data/legal_rules.jsonl` — hasil T2 yang lolos validator, 1 baris = 1
    aturan (spec 5.12);
  - `data/validation/` — `gold_standard.jsonl` (hanya manusia mengisi),
    `validation_results.csv`, `extraction_error_log.csv`;
  - `data/review/review_queue.csv` — dibuka tim di Google Sheets;
  - `data/manifests/` — `batch_manifest.jsonl` + `checkpoint.json` (resumable).
- **Tidak menimpa:** hasil prompt/model lama tidak dihapus (ditandai versi
  lama); data tervalidasi tidak diubah oleh agent.
- **Provenance wajib** di setiap rekaman substantif: `source_url`,
  `document_id`, `source_locator`, `source_quote`, `model_id`,
  `prompt_version`.
- **Fase 8:** ekspor data tervalidasi (registry, relasi, provisions, versions,
  amendments, rules, tags) ke JSONL/CSV + kamus data + `known_limitations.md`
  → siap dipakai tahap ontology.

---

## 9. Model Data Ringkas

- **`document_id`**: `{JENIS}-{TAHUN}-{NOMOR}` — contoh `UU-1983-7`,
  `PP-2022-55`, `PMK-2024-81`, `PER-DJP-2013-14` (dari "PER-14/PJ/2013"),
  `PUTUSAN-MK-2022-14` (dari "14/PUU-XX/2022"; nomor mentah di `nomor_raw`).
  Normalisasi di `src/ids.py`, idempoten, diuji dengan kasus nyata.
- **`locator`**: `<document_id>#<bagian>/<pasal>[/<ayat>[/<huruf>[/<angka>]]]`.
- **Relasi** hanya bentuk aktif; unique `(from, to, type)`; asal dicatat
  (`SOURCE_METADATA` / `TEXT_PATTERN` / `LLM` / `MANUAL`) + `evidence`.
- **Enumerasi status** (spec 5.10) — jangan membuat nilai baru tanpa
  persetujuan manusia: `scope_status` (UNDECIDED/IN_SCOPE/BOUNDARY/
  OUT_OF_SCOPE), `discovery_status`, `ingestion_status`, `extraction_status`,
  `validation_status`, `legal_status` (default `NEEDS_VERIFICATION`),
  `review_status`.
- **`provision_versions` invarian:** interval `[valid_from, valid_to)` tidak
  tumpang tindih, tidak berlubang antar-versi berurutan (kecuali
  `NEEDS_REVIEW` beralasan).

---

## 10. Metrik Kelengkapan & Kualitas (spec Bagian 9)

| Kode | Metrik | Target |
|---|---|---|
| M1 | Antrean kunjungan tersisa per domain (closure) | 0 |
| M2 | `unresolved_citations` berstatus `UNRESOLVED` | 0 / semua terminal beralasan |
| M3 | Selisih daftar dokumen antar-sumber | Dijelaskan satu per satu |
| M4 | % pasal dengan rantai versi lengkap | Dilaporkan, tren naik |
| M5 | Kecocokan pasal sampel vs naskah konsolidasi | Dilaporkan, mismatch diselidiki |
| M6 | Pelanggaran invarian I1–I3 | 0 |
| M7 | Dokumen `FAILED`/`NEEDS_REVIEW` per tahap | Dilaporkan beralasan |
| M8 | `BOUNDARY`/`UNDECIDED` belum ditinjau | Dilaporkan |

Kualitas ekstraksi (terhadap gold standard): precision/recall/F1 per field
(kondisi, kewajiban, pengecualian, konsekuensi, tarif, batas waktu); citation
accuracy; error rate + taksonomi kesalahan. Laporkan **terpisah**: akurasi
nomor pasal, pengecualian terlewat, periode berlaku (tiga kesalahan paling
berbahaya).

---

## 11. Roadmap Implementasi — Fase & Gerbang

Aturan: **satu fase pada satu waktu; berhenti di tiap gerbang** (G) dan minta
persetujuan manusia. Setelah tiap fase: `reports/phase_<N>.md` (format 12.9).

| Fase | Tugas utama | Output | Gerbang |
|---|---|---|---|
| **0 — Fondasi** | Struktur proyek, `AGENTS.md`, `ISSUES.md`; DDL SQLite (`db.py`); `ids.py` + tes; template scope card & `crawl.yaml`; `report.py` kerangka (M1–M8) | Repo jalan, tes lulus | **G0: ketiga anggota setuju skema** |
| **1 — Pilot crawl** | Cek robots.txt/TOS; inspeksi 3–5 halaman sumber → fixture + selector; `crawl.py` + `scope.py`; dry-run → 1 seed, batas 20 dokumen | `reports/phase_1.md` + data pilot | **G1: manusia periksa SEMUA dokumen & relasi pilot** |
| **2 — Closure DOMAIN_A** | Kalibrasi thresholds; crawl penuh resumable; rekonsiliasi sumber 2 & 3; `source_coverage.md` v0 | Registry domain + graf relasi | **G2: review UNDECIDED/BOUNDARY, I1–I3 = 0** |
| **3 — Ingest & parsing** | `ingest.py` (S3) + `parse_structure.py` (S4) + fixture tiap jenis; laporan sampel 10 dokumen | Teks + hash + `provisions` | **G3: manusia periksa sampel parsing** |
| **4 — Amendment & lubang** | `patterns_amendment.yaml` + `amendments.py` (S5A) dengan tes omnibus & perubahan tunggal; `gaps.py` (S6) + putaran balik ke S1; chunk T1 dibuat (belum dijalankan) | `amendments` kandidat + `unresolved_citations` | **G4: review sampel amendment (semua MK/Perpu)** |
| **5 — Pilot LLM** | Gold standard 30–50 butir (**manusia**); `colab_extract.ipynb` + uji alur output palsu (tanpa kuota); `chunking.py`; pilot 2–3 model; `validate.py` + metrik 9.2; estimasi kuota | `reports/extraction_quality.md` | **G5: manusia pilih model/prompt + setujui kuota** |
| **6 — Ekstraksi massal** | Batch per dokumen + checkpoint/manifest; impor → validasi → `review_queue`; rerun gagal/berubah; laporan kualitas | `legal_rules.jsonl` tervalidasi sebagian | **G6: manusia selesaikan review risiko tinggi** |
| **7 — Riwayat** | `reconstruct.py` (S9) + query riwayat; verifikasi konsolidasi (M5); acceptance test Pasal 17 UU PPh vs UU HPP; laporan rantai versi (M4) | Fitur riwayat terquery | **G7: manusia verifikasi sampel riwayat** |
| **8 — Konsolidasi** | Ekspor data tervalidasi + kamus data; `known_limitations.md`; laporan akhir | Paket data untuk ontology | Serah ke tahap ontology |

**Definition of Done per dokumen** (spec 12.8): terdaftar dengan ID/URL/
metadata/scope; relasi tercatat (ketidakpastian ditandai); teks + hash; struktur
terparsing & sampel diperiksa; semua instruksi perubahan tercatat bila dokumen
pengubah; hasil ekstraksi sesuai skema dengan `source_quote` terverifikasi;
kategori berisiko direview; kutipan terselesaikan/terminal; `legal_status`
terverifikasi atau eksplisit `NEEDS_VERIFICATION`; yang belum tervalidasi
tidak diperlakukan sebagai aturan final.

---

## 12. Peran Tim

| Peran | Tanggung jawab |
|---|---|
| **Pemilik domain (×3)** | Isi & pelihara kartu lingkup, tentukan seed, review UNDECIDED/BOUNDARY domainnya, reviewer utama tag domain |
| **Pemegang dokumen `SHARED`** | Satu orang mengawasi dokumen lintas domain (mis. KUP, UU omnibus) |
| **Penyusun gold standard** | Manusia, dari sumber resmi; disarankan lintas anggota (pemeriksaan silang) |
| **Penyetuju gerbang** | G0: ketiganya. Gerbang lain: minimal dua anggota |

Agent tidak menggantikan peran di atas.

---

## 13. Prinsip Utama (spec Bagian 2)

Deterministik dulu, LLM belakangan (P1) · Output LLM hanyalah kandidat (P2) ·
Jangan mengarang (P3) · Provenance wajib (P4) · Pisahkan identitas/versi/
keberlakuan (P5) · Jangan timpa teks lama (P6) · Resumable (P7) ·
`status_sumber` ≠ `legal_status` (P8) · Kelengkapan terukur (P9) · Hormati
sumber (P10) · Dunia terbuka — "tidak ditemukan" ≠ "tidak ada" (P11).

**Anti-pattern (dilarang):** menyimpan UU sebagai satu blok teks · menimpa teks
pasal lama · menganggap relasi metadata lengkap · menerima nomor pasal/tarif/
tanggal dari ingatan model · ekstraksi massal via percakapan OpenCode · model
jalan diam-diam di CPU · salinan script per domain · mengikuti relasi tanpa
gerbang relevansi · membuang dokumen luar domain (catat BOUNDARY/OUT_OF_SCOPE)
· memilih "dokumen terbaru" otomatis saat konflik · mengubah gold standard ·
hasil LLM masuk data tervalidasi tanpa validator · menggabungkan identitas/
versi/keberlakuan dalam satu kolom · menyimpan PDF mentah permanen ·
mengabaikan robots.txt · melompati gerbang.

---

## 14. Hal yang Belum Diverifikasi (agent wajib memeriksa)

Lihat `ISSUES.md` untuk status terkini: V1 robots.txt/TOS · V2 struktur HTML
tiga sumber · V3 kelengkapan metadata relasi · V4 HTML vs PDF vs pindaian ·
V5 naskah konsolidasi · V6 kuota/GPU Colab Pro · V7 kandidat model ·
V8 definisi "lengkap" dari dosen · V9 pola kalimat perubahan nyata.

---

## 15. Status Eksekusi

| Fase | Status |
|---|---|
| Fase 0 — Fondasi & skema | ✅ Selesai — `reports/phase_0.md`. **G0 disetujui (2026-11-09).** |
| Fase 1 — Pilot penjelajahan | ✅ Selesai — `reports/phase_1.md` (seed UU HPP, 20 dokumen, 45 relasi antar-pilot, I1–I3=0). **Menunggu G1.** |
| Fase 2 — Closure DOMAIN_A | ⏸ Belum dimulai — menunggu G1 (review manusia atas 20 dokumen + 45 relasi pilot) |
| Fase 3–8 | ⏸ Belum dimulai |

**Yang menunggu tim (G1):**
1. Periksa **20 dokumen pilot** (Lampiran A `reports/phase_1.md`) terhadap
   `peraturan.bpk.go.id` — apakah IN_SCOPE/BOUNDARY masuk akal?
2. Periksa **45 relasi antar-dokumen-pilot** (Lampiran B) — apakah arah/tipe benar?
3. Putuskan apakah gerbang relevansi (skor subjek/keyword/relasi + exclude_keywords)
   boleh dipakai untuk Fase 2 (closure penuh).

Keputusan & pertanyaan lain tercantum di `ISSUES.md`.

---

*Dokumen ini adalah ringkasan rencana kerja; detail normatif selalu mengacu ke
`KBR_Extraction_Spec.md`.*
