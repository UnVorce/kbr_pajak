# AGENTS.md — Aturan Kerja Agent (KBR Extraction)

> Ringkasan Bagian 0 dan 2 dari `KBR_Extraction_Spec.md`. Dokumen spec adalah
> **sumber kebenaran tunggal**. Jika ada pertentangan dengan instruksi lain,
> tanyakan dulu, jangan bertindak.

## Aturan kerja

1. **Satu fase pada satu waktu** (Bagian 12). Jangan melompat ke fase
   berikutnya sebelum **gerbang persetujuan (G0–G7)** terpenuhi. Berhenti di
   tiap gerbang, tulis `reports/phase_<N>.md`, dan minta persetujuan.
2. **Periksa struktur sumber yang sebenarnya** sebelum menulis parser (ambil
   sampel halaman/dokumen, lihat HTML/teksnya). Jangan berasumsi dari spec —
   hal yang "(perlu diverifikasi)" memang harus diverifikasi.
3. **Uji sampel kecil dulu** (default: 20 dokumen atau 50 potongan teks),
   laporkan hasilnya, baru naikkan skala.
4. **Resumable**: simpan progres setelah tiap unit kerja; jangan memproses
   ulang yang sudah selesai kecuali isi sumber berubah (hash berbeda).
5. Ketidakpastian → catat di `ISSUES.md` + tandai `NEEDS_REVIEW`.
   **Jangan menebak, jangan mengarang, jangan menutupi.**
6. Setelah tiap fase, tulis `reports/phase_<N>.md` (format 12.9), lalu berhenti.
7. **Jangan menimpa data hasil sebelumnya.** Pakai versi baru (Bagian 4, 5).
8. **Tes otomatis** untuk logika deterministik (normalisasi ID, parser pasal,
   pendeteksi pola perubahan, validator), dengan *fixture* dari sampel nyata.

## Prinsip yang tidak boleh dilanggar (Bagian 2)

| # | Prinsip |
|---|---|
| P1 | Deterministik dulu, LLM belakangan (struktur teratur dikerjakan script biasa). |
| P2 | Output LLM hanyalah kandidat — tidak masuk data tervalidasi tanpa validator + review manusia untuk kategori berisiko. |
| P3 | Jangan mengarang — yang tidak tertulis di sumber diisi `null`/`[]`; dasar hukum, nomor pasal, tarif, tanggal **tidak boleh** dari ingatan model/agent. |
| P4 | Provenance wajib: `source_url`, `document_id`, `source_locator`, dan `source_quote` (substring persis). |
| P5 | Pisahkan: identitas dokumen (`document_id`), versi pasal (`provision_versions`), keberlakuan (`legal_status`). |
| P6 | Jangan timpa teks lama — perubahan = versi baru dengan `valid_from`/`valid_to`. |
| P7 | Dapat dilanjutkan: checkpoint, ID deterministik, hash isi, manifest. |
| P8 | `status_sumber` (dari situs) ≠ `legal_status` terverifikasi. Simpan apa adanya. |
| P9 | Kelengkapan terukur (metrik M1–M8, Bagian 9) dilaporkan tiap fase. |
| P10 | Hormati sumber: `robots.txt`/ketentuan penggunaan, batasi laju, cache. |
| P11 | Dunia terbuka: "tidak ditemukan" = *tidak diketahui*, bukan *tidak ada*. |

## Konvensi

- **Bahasa**: narasi laporan/prompt dalam Bahasa Indonesia. Nama field, tabel,
  dan status dalam bahasa Inggris/istilah baku sesuai spec — jangan diterjemahkan.
- **LLM hanya di Google Colab Pro** (notebook), serah-terima lewat JSONL di
  Google Drive. Tidak ada model lokal di laptop. **Dilarang ekstraksi massal
  lewat percakapan OpenCode** (hanya kasus sulit dalam jumlah kecil,
  mode non-interaktif, sesi baru per kasus).
- **Tidak dipakai**: Hermes Agent, Ollama, Google Sheets sebagai registry,
  PostgreSQL (untuk tahap ini; storage inti = SQLite `data/kbr.sqlite`).
- Struktur proyek: lihat Bagian 4 spec; modul di `src/`, konfigurasi di
  `config/`, data di `data/`, laporan di `reports/`.
- Dokumen kunci: `KBR_Extraction_Spec.md` (sumber kebenaran),
  `kbr_knowledge_acquisition_plan.md` (rencana kerja), `ISSUES.md` (catatan
  ketidakpastian), `config/scope_cards/` (kartu lingkup per domain).
