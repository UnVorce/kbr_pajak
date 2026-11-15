# kbr_pajak — Korpus JSON Regulasi Pajak & Ontology KBR

Korpus JSON terstruktur dan terkonsolidasi (s.d. **Fase 3 / Gate G3**) untuk kebutuhan pembangunan **Ontology & Reasoning** serta **RAG / Frontend** tim.

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology tim (tidak diubah)
├── docs/
│   ├── fase_1.md                          # Laporan Fase 1 — registry & ID kanonik
│   ├── fase_2.md                          # Laporan Fase 2 — parser struktur & konsolidasi-lite
│   └── fase_3.md                          # Laporan Fase 3 — S6 gap detector, perbaikan metadata & HPP
└── knowledge_json/
    ├── documents/                         # 78 JSON dokumen kanonik (JENIS-TAHUN-NOMOR.json)
    ├── consolidated/                      # 13 JSON teks TERBARU pasca-amandemen
    ├── text_fallback/
    │   └── PMK-2024-79.txt                # Teks penuh PMK 79/2024 (PDF asli 2 kolom)
    └── metadata/
        ├── manifest.json                  # Indeks seluruh dokumen + path rekomendasi
        ├── consolidation.yaml             # Konfigurasi rantai pengubahan + pending_ck
        ├── gaps.json                      # Status terminal 129 dokumen dikutip (UNRESOLVED = 0)
        ├── citations.jsonl                # 1.053 kutipan lintas-peraturan
        ├── unresolved_citations.json      # [] (Gate G3 tercapai)
        ├── gaps_attempts.json             # Gap manual (PMK-2024-69 asli)
        └── metadata_repair_log.json       # Log perbaikan 6 anomali metadata BPK
```

> **Catatan migrasi struktur:** Folder lama (`1_UU_Laws/` s.d. `5_Coretax_Manuals/`) yang berisi 45 JSON mentah (termasuk duplikat `Salinan UU Nomor 7 Tahun 2021.json`, `UU Nomor 12 Tahun 1994.json` 0 pasal, dan `2024pmkeuangan069.json` yang keliru label) digantikan dengan skema kanonik datar `documents/` + `consolidated/` + `metadata/manifest.json` agar lebih stabil untuk script tim, RAG, maupun penggabungan Fase 4.

---

## Cara Pakai untuk Tim (Ontology, RAG, Fase 4)

1. **Mulai dari `knowledge_json/metadata/manifest.json`** — setiap entri sudah menyediakan `recommended_source`:
   - Jika `has_consolidated == true`, gunakan file di **`knowledge_json/consolidated/<id>.json`** (berisi teks pasal **terbaru**, misalnya UU KUP, UU PPh Pasal 17 tarif Rp60 juta/35%, UU PPN Pasal 7 tarif 11%/12% & Pasal 16B pasca-UU HPP `UU-2021-7`, serta `PMK-2024-81` termasuk nested `PMK-2025-53`).
   - Jika `has_consolidated == false`, gunakan **`knowledge_json/documents/<id>.json`**:
     - Baca `provisions` (ber-locator `DOC#BT/pasal/ayat/huruf`), dan gunakan `articles` sebagai pelengkap/fallback pada dokumen yang `provisions`-nya berhenti lebih awal akibat artefak OCR atau `structure == "UNKNOWN"` (mis. `PMK-2024-78`, `PP-2022-55`, `PP-2023-35`, `UU-2022-1`).
2. **Filter dokumen berlaku vs historis** melalui field `status_sumber` (`Berlaku` vs `Tidak Berlaku`) di `manifest.json` (dokumen pengubah dan PP yang sudah dicabut tetap disimpan untuk keterlacakan kutipan S6).

---

## Batasan yang Perlu Diketahui Tim

- **Lapisan Cipta Kerja (`PENDING_CK`):** `UU-2020-11`, `PERPU-2022-2`, dan `UU-2023-6` (serta `26` kutipan `DEFERRED_CK`) belum diterapkan ke `consolidated/` karena format omnibus ribuan pasal memerlukan pemrosesan khusus saat penggabungan korpus tim.
- **Gap manual (`PMK-2024-69` asli):** file tim `2024pmkeuangan069.json` ternyata berisi **PMK 127/2024** (sudah di-re-key menjadi `PMK-2024-127.json`). PMK 69/2024 asli (perubahan *tax holiday* `PMK-2020-130`) tidak terindeks di BPK & timeout di JDIH Kemenkeu → perlu unduh manual.
- **Pencabutan parsial & PDF 2 kolom:**
  - `PP-2010-94` Pasal 2A dicabut sebagian oleh `PP-2022-55` Pasal 72 huruf b (perlu dieksklusi saat ekstraksi aturan).
  - `PMK-2024-79` berformat 2 kolom; teks penuh tersedia di `knowledge_json/text_fallback/PMK-2024-79.txt`.
- **Instruksi `ayat_level` tersisa (`unparsed`):** `2` butir lama (`UU-1991-7`) dan `4` butir di `PMK-2024-81` tetap dicatat di field `unparsed` pada JSON konsolidasi masing-masing.
