# kbr_pajak — Korpus JSON Regulasi Pajak, Yurisprudensi & Ontology KBR

Korpus JSON terstruktur dan terkonsolidasi (s.d. **Fase 4A/4B / Gate G3**, mencakup seluruh bidang perpajakan nasional: PPh Badan & Fasilitas, PPh Potput/Final, PPN & PPnBM, PBB & HKPD, KUP/Coretax/Penagihan/Keberatan/Pengadilan Pajak, Pajak Minimum Global, KEK/KPBPB, Migas/Batubara, Kepabeanan & Cukai, ditambah **284 Putusan Pengadilan Pajak**, **15 Putusan MK pajak yang dikabulkan/bersyarat**, dan **14 butir SEMA Pleno Kamar TUN (Pajak)**) untuk kebutuhan **Ontology & Reasoning**, **RAG**, dan **Fase 4**.

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology tim (tidak diubah)
├── docs/
│   ├── corpus_directory.xlsx              # Direktori & riwayat pergerakan seluruh korpus (7 tab siap Google Sheets)
│   ├── fase_1.md                          # Laporan Fase 1 — registry & ID kanonik
│   ├── fase_2.md                          # Laporan Fase 2 — parser struktur & konsolidasi-lite
│   ├── fase_3.md                          # Laporan Fase 3 — S6, audit metadata, ingest manual & HPP
│   └── fase_3b.md                         # Laporan Fase 3B — 49 regulasi nasional + 4 PMK manual + 199 putusan
└── knowledge_json/
    ├── documents/                         # 165 JSON regulasi pusat kanonik (termasuk pph_op/ + PMK 96/2023 & PMK 8/2024)
    ├── consolidated/                      # 32 JSON teks TERBARU pasca-amandemen (termasuk UU 6/2023 CK)
    ├── perda/                             # 524 JSON Perda PDRD 2023-2026 (493 digital + 31 OCR Tesseract = 524 terbaca)
    ├── jurisprudence/                     # 284 JSON Putusan Pengadilan Pajak (PP-PUT-<id>.json)
    ├── putusan_mk/                        # 15 JSON Putusan MK (hanya amar dikabulkan/bersyarat)
    ├── sema_tun/                          # 78 JSON butir SEMA Pleno Kamar TUN (14 di antaranya pajak)
    ├── pph_op/                            # Korpus domain PPh OP milik rekan
    └── metadata/
        ├── manifest.json                  # Indeks 165 regulasi pusat (97 active_for_rules + recommended_source)
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

## Cara Pakai untuk Tim (Ontology, RAG, Fase 4)

1. **Untuk aturan hukum normatif (`knowledge_json/metadata/manifest.json`):**
   - Filter **`active_for_rules == true`** (`97` regulasi aktif bersih — otomatis mengecualikan dokumen yang sudah dicabut/tidak berlaku, pengubah yang sudah masuk ke `consolidated/`, panduan/lampiran, dan file non-pajak).
   - Ambil teks dari **`recommended_source`**: otomatis mengarah ke **`knowledge_json/consolidated/<id>.json`** (`32` regulasi, termasuk lapisan **UU 6/2023 Cipta Kerja**, **UU 7/2021 HPP**, **`PMK-2024-118`**, dan lengkap dengan `sub_provisions` level ayat/huruf) bila tersedia, atau ke **`knowledge_json/documents/<id>.json`**.
   - Untuk indeks visual lengkap dalam bentuk Excel, buka **`docs/corpus_directory.xlsx`**.
2. **Untuk preseden sengketa & mitigasi risiko (`knowledge_json/metadata/jurisprudence_manifest.json`):**
   - Tersedia **`284` Putusan Pengadilan Pajak** di `knowledge_json/jurisprudence/` (`pph_badan`, `ppn`, `kup_gugatan`, `pph_potput`, `pbb`, `kepabeanan_cukai`) lengkap dengan `pokok_sengketa`, `pertimbangan_majelis`, `amar_kategori`, dan `cited_regulations` yang tertaut ke `document_id` kanonik.
3. **Untuk Perda Pajak Daerah & Retribusi Daerah (`knowledge_json/metadata/perda_manifest.json`):**
   - Tersedia **`524` Perda PDRD (`2023–2026`)** di `knowledge_json/perda/` dengan `document_id` unik per pemda (`PERDA-<DAERAH>-<TAHUN>-<NOMOR>.json`): **`493` `DIGITAL_OK`** + **`31` `OCR_DONE`** (Tesseract `ind+eng`) → `418` `NUMERIC`, `95` `AMENDING_ROMAN`, `11` `UNKNOWN` (**97,9%** ter-parse ke `provisions`).
4. **Untuk lapisan interpretasi konstitusional & putusan pleno (`putusan_mk/`, `sema_tun/`):**
   - **`15` Putusan MK** di `knowledge_json/putusan_mk/` — hanya amar **dikabulkan / dikabulkan sebagian / konstitusional bersyarat** (`12` bersyarat, `2` kabul seluruhnya, `1` kabul sebagian). Field penting: `uu_diuji`, `impacted_corpus_docs` (dipetakan ke `document_id` induk, mis. `UU-2007-28` → `UU-1983-6`), `pasal_diuji`, `amar_lengkap`, `pertimbangan_inti`.
   - **`14` butir SEMA Pleno Kamar TUN** di `knowledge_json/sema_tun/` (`2012–2025`) dengan `klaster_pajak`, `status_kaidah` (`AKTIF` / `DIUBAH_SEMA_LAIN`), dan `cited_regulations`.
   - Keduanya **tidak menimpa teks UU**; ia menjadi penanda `mk_review_refs` / `sema_tun_refs` pada `scope_manifest.jsonl`, ikut ke `context` chunk T2, dan memaksa status `REVIEW_REQUIRED` di `src/validate.py` (`mk_constitutional_review`, `sema_tun_guidance`).

---

## Batasan yang Perlu Diketahui Tim

- **Lapisan Cipta Kerja (`PENDING_CK`):** `UU-2020-11`, `PERPU-2022-2`, dan `UU-2023-6` (`21` kutipan `DEFERRED_CK`) belum diterapkan ke `consolidated/` hingga penggabungan korpus tim (termasuk `pph_op/`).
- **1 PMK opsional non-BPK (`PMK-2008-253`):** `PMK 253/PMK.03/2008` (PPh 22 barang sangat mewah) belum tersedia PDF-nya; perubahannya (`PMK-2015-90`, `PMK-2019-92`) sudah masuk.
- **`PMK-2024-81`:** memakai `articles` dasar tim (`466` pasal) pada konsolidasi (`427` pasal).
- **Instruksi `ayat_level` tersisa (`unparsed`):** tercatat transparan di field `unparsed` pada masing-masing JSON konsolidasi.
- **Putusan MK & SEMA Kamar TUN = lapisan interpretasi, bukan sumber teks UU:** amar bersyarat belum diterapkan ke `consolidated/`; penanda `mk_review_refs` / `sema_tun_refs` wajib ditinjau manusia sebelum aturan hasil Fase 4 dipakai. Putusan MK yang **ditolak** dan **Tidak Dapat Diterima** sengaja tidak dimasukkan.
