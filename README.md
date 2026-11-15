# kbr_pajak — Korpus JSON Regulasi Pajak & Ontology KBR

Korpus JSON terstruktur dan terkonsolidasi (s.d. **Fase 3 / Gate G3**, termasuk 12 PDF unduhan manual) untuk kebutuhan pembangunan **Ontology & Reasoning** serta **RAG / Frontend** tim.

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology tim (tidak diubah)
├── docs/
│   ├── fase_1.md                          # Laporan Fase 1 — registry & ID kanonik
│   ├── fase_2.md                          # Laporan Fase 2 — parser struktur & konsolidasi-lite
│   └── fase_3.md                          # Laporan Fase 3 — S6, audit metadata, ingest manual & HPP
└── knowledge_json/
    ├── documents/                         # 89 JSON dokumen kanonik (JENIS-TAHUN-NOMOR.json)
    ├── consolidated/                      # 15 JSON teks TERBARU pasca-amandemen
    └── metadata/
        ├── manifest.json                  # Indeks seluruh dokumen + recommended_source
        ├── consolidation.yaml             # Konfigurasi rantai pengubahan + pending_ck
        ├── gaps.json                      # Status terminal 174 dokumen dikutip (UNRESOLVED = 0)
        ├── citations.jsonl                # 1.440 kutipan lintas-peraturan
        ├── unresolved_citations.json      # [] (Gate G3 tercapai)
        ├── gaps_attempts.json             # Jejak percobaan crawl
        └── metadata_repair_log.json       # Log perbaikan 6 anomali metadata BPK
```

> **Catatan migrasi struktur:** Folder lama (`1_UU_Laws/` s.d. `5_Coretax_Manuals/`) yang berisi 45 JSON mentah (termasuk duplikat `Salinan UU Nomor 7 Tahun 2021.json`, `UU Nomor 12 Tahun 1994.json` 0 pasal, dan `2024pmkeuangan069.json` yang keliru label) digantikan dengan skema kanonik datar `documents/` + `consolidated/` + `metadata/manifest.json`. `PMK-2024-69` asli dan 11 PDF pelengkap (`PER-DJP-2025-11`, `PMK-2019-186`, `PMK-2022-234`, `PMK-2026-28`, `PMK-2023-61`, `PMK-2019-128`, `PERPRES-2018-40`, `PERPU-2017-1`, `UU-1997-19`, `UU-2000-19`, serta re-ekstraksi 2-kolom `PMK-2024-79`) sudah teringest dan terkonsolidasi.

---

## Cara Pakai untuk Tim (Ontology, RAG, Fase 4)

1. **Mulai dari `knowledge_json/metadata/manifest.json`** — setiap entri sudah menyediakan `recommended_source`:
   - Jika `has_consolidated == true`, gunakan file di **`knowledge_json/consolidated/<id>.json`** (berisi teks pasal **terbaru**, misalnya UU KUP, UU PPh Pasal 17 tarif Rp60 juta/35%, UU PPN Pasal 7 tarif 11%/12% & Pasal 16B pasca-UU HPP `UU-2021-7`, `PMK-2024-81` incl. nested `PMK-2025-53`, `PMK-2020-130` incl. `PMK-2024-69`, `PMK-2019-186` incl. `PMK-2022-234`, dan `UU-1997-19` incl. `UU-2000-19`).
   - Jika `has_consolidated == false`, gunakan **`knowledge_json/documents/<id>.json`**:
     - Baca `provisions` (ber-locator `DOC#BT/pasal/ayat/huruf`), dan gunakan `articles` sebagai fallback hanya pada dokumen dengan `structure == "UNKNOWN"` (`PMK-2024-81` memakai 466 `articles` dan sudah punya `consolidated/PMK-2024-81.json`).
2. **Filter dokumen berlaku vs historis** melalui field `status_sumber` (`Berlaku` vs `Tidak Berlaku`) di `manifest.json`.

---

## Batasan yang Perlu Diketahui Tim

- **Lapisan Cipta Kerja (`PENDING_CK`):** `UU-2020-11`, `PERPU-2022-2`, dan `UU-2023-6` (`23` kutipan `DEFERRED_CK`) belum diterapkan ke `consolidated/` karena format omnibus ribuan pasal memerlukan pemrosesan khusus saat penggabungan korpus tim.
- **Instruksi `ayat_level` tersisa (`unparsed`):** `2` butir lama (`UU-1991-7`) dan `4` butir di `PMK-2024-81` tetap dicatat di field `unparsed` pada JSON konsolidasi masing-masing.
- **Dokumen *noise* bawaan korpus awal:** `PP-2018-40` (PNBP BSN — sudah dilengkapi `PERPRES-2018-40` Coretax), `PMK-2018-109`/`151`/`2019-56`/`2019-121` (pengadaan internal Coretax), `PMK-2024-127` (kapasitas fiskal), serta Bea Meterai (`UU-2020-10`, `PP-2022-3`, `PMK-2024-78`) disarankan ditandai saat penyusunan `scope_manifest` Fase 4.
