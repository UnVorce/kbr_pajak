# kbr_pajak — Korpus JSON Regulasi Pajak, Aturan Tervalidasi, Yurisprudensi & Ontology KBR

Korpus JSON terstruktur, terkonsolidasi, dan hasil ekstraksi aturan **Fase 4** (mencakup seluruh bidang perpajakan nasional: PPh Badan & Fasilitas, PPh Potput/Final, PPN & PPnBM, PBB & HKPD, KUP/Coretax/Penagihan/Pengadilan Pajak, Pajak Minimum Global, KEK/KPBPB, Migas/Batubara, Kepabeanan & Cukai, **`12.652` aturan hukum tervalidasi S8**, **`532` baris pre-audit `P1`–`P6`**, ditambah **`284` Putusan Pengadilan Pajak**, **`15` Putusan MK pajak yang dikabulkan/bersyarat**, dan **`14` butir SEMA Pleno Kamar TUN (Pajak)**) untuk kebutuhan **Ontology & Reasoning (Fase 5–6)** dan **RAG**.

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology tim (tidak diubah)
├── docs/
│   ├── corpus_directory.xlsx              # Direktori & riwayat pergerakan seluruh korpus (7 tab siap Google Sheets)
│   ├── fase_1.md                          # Laporan Fase 1 — registry & ID kanonik
│   ├── fase_2.md                          # Laporan Fase 2 — parser struktur & konsolidasi-lite
│   ├── fase_3.md                          # Laporan Fase 3 — S6, audit metadata, ingest manual & HPP
│   ├── fase_3b.md                         # Laporan Fase 3B — 49 regulasi nasional + 4 PMK manual + 199 putusan
│   ├── fase_4.md                          # Laporan Fase 4 — CK, 5.509 chunk, ekstraksi 32B, S8 & pre-audit P1-P6
│   └── ISSUES.md                          # Catatan anomali sumber (termasuk #A7 karantina PER-DJP-2015-17)
├── notebooks/
│   └── colab_extract_t2.ipynb             # Notebook ekstraksi T2_RULE vLLM (Qwen2.5-32B-Instruct-AWQ)
└── knowledge_json/
    ├── rules/
    │   └── legal_rules.jsonl              # 12.652 aturan pajak tervalidasi S8 (8.717 VALIDATED + 3.935 REVIEW_REQUIRED)
    ├── review/
    │   ├── priority_review_audited.csv    # 532 baris pre-audit P1-P6 (menunggu sign-off manusia & apply)
    │   ├── llm_audit_log.jsonl            # Log audit per batch P1-P6 (gemini-4-hydrogen-high)
    │   ├── review_queue.jsonl             # Antrean penuh 4.612 item S8
    │   ├── gold_standard_template.jsonl   # 36 sampel chunk gold standard
    │   └── gold_standard_review.csv       # Template review 36 gold standard
    ├── documents/                         # 165 JSON regulasi pusat kanonik (termasuk pph_op/ + PMK 96/2023 & PMK 8/2024)
    ├── consolidated/                      # 32 JSON teks TERBARU pasca-amandemen (termasuk UU 6/2023 CK)
    ├── perda/                             # 524 JSON Perda PDRD 2023-2026 (493 digital + 31 OCR Tesseract = 524 terbaca)
    ├── jurisprudence/                     # 284 JSON Putusan Pengadilan Pajak (PP-PUT-<id>.json)
    ├── putusan_mk/                        # 15 JSON Putusan MK (hanya amar dikabulkan/bersyarat)
    ├── sema_tun/                          # 78 JSON butir SEMA Pleno Kamar TUN (14 di antaranya pajak)
    ├── pph_op/                            # Korpus domain PPh OP milik rekan
    └── metadata/
        ├── manifest.json                  # Indeks 165 regulasi pusat (97 active_for_rules + recommended_source)
        ├── scope_manifest.jsonl           # 4.603 pasal (4.463 extract_t2 + penanda mk_review_refs & sema_tun_refs)
        ├── chunk_manifest.json            # Ringkasan 5.509 chunk T2_RULE & 17 chunk tabel
        ├── validation_report.json         # Laporan metrik S8 (12.652 lolos, 153 chunk PER-DJP-2015-17 dikarantina)
        ├── perda_manifest.json            # Indeks 524 Perda PDRD (tahun, ocr_status, structure)
        ├── jurisprudence_manifest.json    # Indeks 284 putusan (klaster, amar, cited_regulations)
        ├── mk_manifest.json               # Indeks 15 Putusan MK (amar_kategori, uu_diuji, impacted_corpus_docs)
        ├── sema_tun_manifest.json         # Indeks 78 butir SEMA Kamar TUN (14 pajak: klaster_pajak, status_kaidah)
        ├── consolidation.yaml             # Konfigurasi 32 rantai pengubahan
        ├── gaps.json                      # Status terminal 389 dokumen dikutip (UNRESOLVED = 0)
        ├── citations.jsonl                # 3.819 kutipan lintas-peraturan
        ├── unresolved_citations.json      # [] (Gate G3 tercapai)
        ├── gaps_attempts.json             # Jejak gap manual (PMK-2008-253)
        └── metadata_repair_log.json       # Log perbaikan 6 anomali metadata BPK
```

---

## Cara Pakai untuk Tim (Ontology, RAG, Fase 4–6)

1. **Untuk aturan hukum terstruktur (`knowledge_json/rules/legal_rules.jsonl`):**
   - Berisi **`12.652` aturan atomik** hasil ekstraksi `Qwen2.5-32B-Instruct-AWQ` + validasi S8 (`8.717 VALIDATED` + `3.935 REVIEW_REQUIRED`), mencakup `100` dokumen di `9` domain pajak (termasuk 5 Perda PDRD pilot dan teks konsolidasi `UU-2023-6` Cipta Kerja).
   - **Audit prioritas tinggi (`knowledge_json/review/priority_review_audited.csv`):** memuat **`532` baris** hasil pre-audit `P1_TABLE` (`7`), `P2_MK` (`44`), `P3_SEMA` (`33`), `P4_PARSE_ERROR` (`61` aturan pulih), `P5_RATE_CORE` (`257`), dan `P6_REJECTED_CORE` (`130`) — siap *sign-off* akhir manusia sebelum di-`apply` ke `legal_rules.jsonl`.
2. **Untuk teks regulasi normatif (`knowledge_json/metadata/manifest.json`):**
   - Filter **`active_for_rules == true`** (`97` regulasi aktif bersih — otomatis mengecualikan dokumen yang sudah dicabut/tidak berlaku, pengubah yang sudah masuk ke `consolidated/`, panduan/lampiran, dan file non-pajak).
   - Ambil teks dari **`recommended_source`**: otomatis mengarah ke **`knowledge_json/consolidated/<id>.json`** (`32` regulasi, termasuk lapisan **UU 6/2023 Cipta Kerja**, **UU 7/2021 HPP**, **`PMK-2024-118`**, dan lengkap dengan `sub_provisions` level ayat/huruf) bila tersedia, atau ke **`knowledge_json/documents/<id>.json`**.
   - Untuk indeks visual lengkap dalam bentuk Excel, buka **`docs/corpus_directory.xlsx`**.
3. **Untuk preseden sengketa & mitigasi risiko (`knowledge_json/metadata/jurisprudence_manifest.json`):**
   - Tersedia **`284` Putusan Pengadilan Pajak** di `knowledge_json/jurisprudence/` (`pph_badan`, `ppn`, `kup_gugatan`, `pph_potput`, `pbb`, `kepabeanan_cukai`) lengkap dengan `pokok_sengketa`, `pertimbangan_majelis`, `amar_kategori`, dan `cited_regulations` yang tertaut ke `document_id` kanonik.
4. **Untuk Perda Pajak Daerah & Retribusi Daerah (`knowledge_json/metadata/perda_manifest.json`):**
   - Tersedia **`524` Perda PDRD (`2023–2026`)** di `knowledge_json/perda/` dengan `document_id` unik per pemda (`PERDA-<DAERAH>-<TAHUN>-<NOMOR>.json`): **`493` `DIGITAL_OK`** + **`31` `OCR_DONE`** (Tesseract `ind+eng`) → `418` `NUMERIC`, `95` `AMENDING_ROMAN`, `11` `UNKNOWN` (**97,9%** ter-parse ke `provisions`).
5. **Untuk lapisan interpretasi konstitusional & putusan pleno (`putusan_mk/`, `sema_tun/`):**
   - **`15` Putusan MK** di `knowledge_json/putusan_mk/` — hanya amar **dikabulkan / dikabulkan sebagian / konstitusional bersyarat** (`12` bersyarat, `2` kabul seluruhnya, `1` kabul sebagian).
   - **`14` butir SEMA Pleno Kamar TUN** di `knowledge_json/sema_tun/` (`2012–2025`) dengan `klaster_pajak`, `status_kaidah` (`AKTIF` / `DIUBAH_SEMA_LAIN`), dan `cited_regulations`.
   - Keduanya **tidak menimpa teks UU**; ia menjadi penanda `mk_review_refs` / `sema_tun_refs` pada `scope_manifest.jsonl`, memaksa status `REVIEW_REQUIRED`, dan diaudit pada `P2_MK` & `P3_SEMA`.

---

## Batasan yang Perlu Diketahui Tim

- **Anomali sumber `PER-DJP-2015-17` (dikarantina — lihat `docs/ISSUES.md #A7`):** file PDF BPK untuk `PER-DJP-2015-17` ternyata berisi Perda Kab. Pangandaran tentang Lingkungan Hidup; sudah dikarantina di validator S8 sehingga **0 aturan** dari dokumen itu masuk ke `legal_rules.jsonl`.
- **Status `priority_review_audited.csv`:** pre-audit `P1`–`P6` (`532` baris) sudah selesai dilakukan, namun belum di-`apply` ke `legal_rules.jsonl` sambil menunggu *sign-off* akhir manusia.
- **1 PMK opsional non-BPK (`PMK-2008-253`):** `PMK 253/PMK.03/2008` (PPh 22 barang sangat mewah) belum tersedia PDF-nya; perubahannya (`PMK-2015-90`, `PMK-2019-92`) sudah masuk.
- **`PMK-2024-81`:** memakai `articles` dasar tim (`466` pasal) pada konsolidasi (`427` pasal).
- **Putusan MK & SEMA Kamar TUN = lapisan interpretasi, bukan sumber teks UU:** amar bersyarat tidak menimpa teks `consolidated/`; dampaknya dicatat pada audit `P2_MK` & `P3_SEMA`. Putusan MK yang **ditolak** dan **Tidak Dapat Diterima** sengaja tidak dimasukkan.
