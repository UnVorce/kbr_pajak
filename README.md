# kbr_pajak — Korpus JSON Regulasi Pajak, Yurisprudensi & Ontology KBR

Korpus JSON terstruktur dan terkonsolidasi (s.d. **Fase 3B / Gate G3**, mencakup seluruh bidang perpajakan nasional: PPh Badan & Fasilitas, PPh Potput/Final, PPN & PPnBM, PBB & HKPD, KUP/Coretax/Penagihan/Keberatan/Pengadilan Pajak, Pajak Minimum Global, KEK/KPBPB, Migas/Batubara, Kepabeanan & Cukai, ditambah **199 Putusan Pengadilan Pajak**) untuk kebutuhan **Ontology & Reasoning**, **RAG**, dan **Fase 4**.

## Struktur Direktori

```text
kbr_pajak/
├── ontology_pajak.owl                     # Seed ontology tim (tidak diubah)
├── docs/
│   ├── fase_1.md                          # Laporan Fase 1 — registry & ID kanonik
│   ├── fase_2.md                          # Laporan Fase 2 — parser struktur & konsolidasi-lite
│   ├── fase_3.md                          # Laporan Fase 3 — S6, audit metadata, ingest manual & HPP
│   └── fase_3b.md                         # Laporan Fase 3B — 49 regulasi nasional + 4 PMK manual + 199 putusan
└── knowledge_json/
    ├── documents/                         # 142 JSON regulasi kanonik (JENIS-TAHUN-NOMOR.json)
    ├── consolidated/                      # 29 JSON teks TERBARU pasca-amandemen
    ├── jurisprudence/                     # 199 JSON Putusan Pengadilan Pajak (PP-PUT-<id>.json)
    ├── pph_op/                            # Korpus domain PPh OP milik rekan (akan disatukan di Fase 4)
    └── metadata/
        ├── manifest.json                  # Indeks 142 regulasi (80 active_for_rules + recommended_source)
        ├── jurisprudence_manifest.json    # Indeks 199 putusan (klaster, amar, cited_regulations)
        ├── consolidation.yaml             # Konfigurasi 29 rantai pengubahan + pending_ck
        ├── gaps.json                      # Status terminal 343 dokumen dikutip (UNRESOLVED = 0)
        ├── citations.jsonl                # 3.004 kutipan lintas-peraturan
        ├── unresolved_citations.json      # [] (Gate G3 tercapai)
        ├── gaps_attempts.json             # Jejak gap manual (PMK-2008-253)
        └── metadata_repair_log.json       # Log perbaikan 6 anomali metadata BPK
```

---

## Cara Pakai untuk Tim (Ontology, RAG, Fase 4)

1. **Untuk aturan hukum normatif (`knowledge_json/metadata/manifest.json`):**
   - Filter **`active_for_rules == true`** (`80` regulasi aktif bersih — otomatis mengecualikan dokumen yang sudah dicabut/tidak berlaku, pengubah yang sudah masuk ke `consolidated/`, panduan/lampiran, dan 6 file non-pajak bawaan awal).
   - Ambil teks dari **`recommended_source`**: otomatis mengarah ke **`knowledge_json/consolidated/<id>.json`** (`29` regulasi) bila tersedia, atau ke **`knowledge_json/documents/<id>.json`**.
2. **Untuk preseden sengketa & mitigasi risiko (`knowledge_json/metadata/jurisprudence_manifest.json`):**
   - Tersedia **`199` Putusan Pengadilan Pajak** di `knowledge_json/jurisprudence/` (`pph_badan`, `ppn`, `kup_gugatan`, `pph_potput`, `pbb`, `kepabeanan_cukai`) lengkap dengan `pokok_sengketa`, `pertimbangan_majelis`, `amar_kategori`, dan `cited_regulations` yang tertaut ke `document_id` kanonik.

---

## Batasan yang Perlu Diketahui Tim

- **Lapisan Cipta Kerja (`PENDING_CK`):** `UU-2020-11`, `PERPU-2022-2`, dan `UU-2023-6` (`21` kutipan `DEFERRED_CK`) belum diterapkan ke `consolidated/` hingga penggabungan korpus tim (termasuk `pph_op/`).
- **1 PMK opsional non-BPK (`PMK-2008-253`):** `PMK 253/PMK.03/2008` (PPh 22 barang sangat mewah) belum tersedia PDF-nya; perubahannya (`PMK-2015-90`, `PMK-2019-92`) sudah masuk.
- **`PMK-2009-105`:** halaman 1 PDF aslinya scan (Pasal 1 belum terbaca di `provisions`, sedangkan Pasal 2–7 tersedia di teks sumber).
- **`PMK-2024-81`:** memakai `articles` dasar tim (`466` pasal) pada konsolidasi (`427` pasal).
- **Instruksi `ayat_level` tersisa (`unparsed`):** tercatat transparan di field `unparsed` pada masing-masing JSON konsolidasi.
