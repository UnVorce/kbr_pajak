# Data Dictionary — Sistem KBR Perpajakan Indonesia

> **Cakupan:** Kamus data lengkap untuk seluruh artefak korpus JSON, aturan hukum atomik (`legal_rules.jsonl`), ontologi OWL 2 `SROIQ(D)` (`kbr-core.ttl`, `kbr_pajak_reasoning.owl`, `kbr-data.ttl`), dan kontrak JSON API (`backend/`).

---

## 1. Konvensi Penamaan & ID Kanonik (`src/ids.py`)

| Entitas | Pola ID | Contoh |
|---|---|---|
| Regulasi Pusat | `{JENIS}-{TAHUN}-{NOMOR}` | `UU-1983-7`, `UU-2023-6`, `PP-2022-55`, `PMK-2024-131`, `PER-DJP-2025-11`, `PERPU-2022-2` |
| Peraturan Daerah | `PERDA-{TINGKAT}-{DAERAH}-{TAHUN}-{NOMOR}` | `PERDA-PROV-DKI-JAKARTA-2024-1`, `PERDA-KOTA-SURABAYA-2023-7` |
| Putusan Pengadilan Pajak | `PP-PUT-{NOMOR_PUTUSAN}` | `PP-PUT-000123-16-2023` |
| Putusan Mahkamah Konstitusi | `MK-{TAHUN}-{NOMOR}-PUU-{MASA}` | `MK-2024-19-PUU-XXII` |
| Butir SEMA Kamar TUN | `SEMA-{TAHUN}-{NOMOR}-TUN-{SUB}` | `SEMA-2024-2-TUN-4` |
| Source Locator Pasal | `{DOC_ID}#{BAGIAN}/{PASAL}[/{AYAT}[/{HURUF}]]` | `UU-1983-6#BT/27/1..5d`, `PERDA-PROV-DKI-JAKARTA-2024-1#BT/53` |
| Rule ID Atomik | `R-{DOC_ID}-{HASH10}` | `R-UU-1983-7-fcd99f0036` |

Kode bagian (`BAGIAN`) pada `source_locator`:
- `BT`: Batang Tubuh
- `PJ`: Penjelasan
- `LM`: Lampiran

---

## 2. Skema Korpus JSON (`knowledge_json/`)

### 2.1 Regulasi Terstruktur (`documents/*.json`, `consolidated/*.json`, `perda/*.json`)

| Field | Tipe | Keterangan |
|---|---|---|
| `document_id` | `string` | ID kanonik dokumen |
| `jenis` | `string` | `UU`, `PERPU`, `PP`, `PMK`, `PER-DJP`, `PERDA`, dll. |
| `nomor`, `tahun` | `string / int` | Nomor dan tahun penetapan |
| `judul` | `string` | Judul resmi peraturan |
| `status_sumber` | `string` | Status mentah dari situs BPK/JDIH (bukan verifikasi hukum final, Prinsip P8) |
| `source_urls` | `list[string]` | Daftar URL sumber resmi |
| `content_hash` | `string` | SHA-256 teks dokumen |
| `articles` / `provisions` | `list[object]` | Daftar pasal ter-parse (`locator`, `nomor`, `text`, `sub_provisions`) |
| `amendment_history` | `list[object]` | *(khusus `consolidated/`)* Rantai perubahan yang diterapkan per pasal |

### 2.2 Yurisprudensi & Tafsir Yudisial (`jurisprudence/`, `putusan_mk/`, `sema_tun/`)

| Folder | Field Kunci |
|---|---|
| `jurisprudence/*.json` (`284` file) | `case_id`, `nomor_putusan`, `klaster_pajak`, `amar_kategori`, `pokok_sengketa`, `pertimbangan_majelis`, `cited_regulations` |
| `putusan_mk/*.json` (`15` file) | `case_id`, `nomor_perkara`, `amar_kategori` (`KABUL` / `KABUL_SEBAGIAN` / `BERSYARAT`), `amar_lengkap`, `uu_diuji`, `pasal_diuji`, `impacted_corpus_docs` |
| `sema_tun/*.json` (`78` file, `14` pajak) | `sema_id`, `tahun`, `is_pajak_terkait`, `klaster_pajak`, `status_kaidah` (`AKTIF` / `DIUBAH_SEMA_LAIN`), `judul_rumusan`, `teks`, `cited_regulations` |

### 2.3 Indeks Manifest (`metadata/manifest.json`)

| Field | Tipe | Keterangan |
|---|---|---|
| `document_id` | `string` | ID kanonik |
| `active_for_rules` | `bool` | `true` untuk `97` regulasi aktif bersih (mengecualikan dokumen dicabut, pengubah murni, dan lampiran) |
| `recommended_source` | `string` | Mengarah ke `consolidated/<id>.json` bila tersedia, atau `documents/<id>.json` |

---

## 3. Skema Aturan Hukum Atomik (`legal_rules.jsonl` — `12.907` baris)

| Field | Tipe | Nilai / Contoh |
|---|---|---|
| `rule_id` | `string` | ID unik deterministik (`R-UU-1983-7-fcd99f0036`) |
| `chunk_id` | `string` | ID potongan teks sumber |
| `document_id` | `string` | ID regulasi sumber (`100` dokumen unik) |
| `source_locator` | `string` | Lokasi pasal/ayat (`UU-1983-6#BT/27/1..5d`) |
| `domain` | `enum` | `D_ADMIN_SANKSI` (`3.417`), `B_PPN` (`2.122`), `PERDA_PDRD` (`1.694`), `A2_PPH_BADAN` (`1.618`), `C_PBB_HKPD` (`1.204`), `FASILITAS_SEKTOR` (`1.128`), `KEPABEANAN_CUKAI` (`969`), `PPH_OP_POTPUT` (`600`), `PPH_FINAL_SEKTOR` (`155`) |
| `rule_type` | `enum` | `definition` (`4.193`), `obligation` (`3.103`), `procedure` (`2.733`), `prohibition` (`808`), `rate` (`653`), `deadline` (`436`), `exception` (`331`), `sanction` (`314`), `right` (`276`), `eligibility` (`37`), `other` (`23`) |
| `subject` | `string` | Subjek hukum yang dikenai ketentuan |
| `condition` | `string / null` | Syarat berlakunya aturan |
| `action_or_effect` | `string` | Kewajiban, hak, tarif, atau akibat hukum |
| `rate_or_value` | `list[object]` | Nilai numerik terverifikasi (`{"value": "22%", "unit": "%", "raw": "22% (dua puluh dua persen)"}`) |
| `source_quote` | `string` | Substring persis dari teks sumber (Prinsip P4) |
| `validation_status` | `enum` | `VALIDATED` (`8.717`), `REVIEW_REQUIRED` (`3.599`), `HUMAN_FIXED` (`474`), `HUMAN_APPROVED` (`117`) |
| `mk_review_refs` | `list[string]` | Daftar ID Putusan MK terkait (`45` aturan tertaut) |
| `sema_tun_refs` | `list[string]` | Daftar ID SEMA TUN terkait (`33` aturan tertaut) |
| `human_notes` | `string / null` | Catatan audit manusia (`P1`–`P6`) |

---

## 4. Kamus Ontologi OWL 2 `SROIQ(D)` (`http://www.semanticweb.org/ontology/kbr_pajak#`)

### 4.1 Hirarki Kelas (`59` Kelas)

| Kelompok | Kelas & Subkelas |
|---|---|
| **Subjek Wajib Pajak (`WajibPajak`)** | `OrangPribadi`, `OP_PemilikKendaraanDKI` (`OP_KendaraanKe1_DKI`..`OP_KendaraanKe5Plus_DKI`), `Badan` (`PT`, `CV`, `Koperasi`, `Yayasan`, `BadanUsahaTetap` -> `BUT`), `UMKM`, `SubjekPajakAktif`, `PengusahaKenaPajak`, `WajibPajakUMKM`, `WajibPajakNonUMKM`, `BadanTerbukaTbk`, `BadanNonTbk`, `LayakTaxHoliday` (`LayakTaxHoliday_50Pct_5Thn`, `LayakTaxHoliday_100Pct_5Thn`, `7Thn`, `10Thn`, `15Thn`, `20Thn`) |
| **Katalog Output** | `TarifPajak` (`TarifProgresif`, `TarifFinal`), `FasilitasPerpajakan` (`PP55UMKM`), `KewajibanPajak`, `SanksiAdministratif`, `DomainPajak` (`9` nominal), `ObjekPajak` |
| **Dokumen & Tafsir (`DokumenHukum`)** | `Regulasi` (`UndangUndang`, `PeraturanPemerintah`, `PeraturanMenteriKeuangan`, `PeraturanDirjenPajak`, `PeraturanDaerah`), `Pasal`, `PutusanMK`, `SEMA_TUN` |
| **Aturan Reifikasi (`AturanHukum`)** | `Kewajiban`, `Hak`, `Larangan`, `Pengecualian`, `Sanksi`, `BatasWaktu`, `AturanTarif`, `Definisi`, `Prosedur`, `Kelayakan` |

### 4.2 Object Properties (`15` Properti)

| Properti | Domain | Range | Karakteristik `SROIQ` |
|---|---|---|---|
| `diaturDalam` | `AturanHukum` | `Regulasi` | Inverse `mengatur`; **PropertyChain** `[diaturDalamPasal, bagianDariRegulasi]` ($\mathcal{R},\mathcal{I}$) |
| `diaturDalamPasal` | `AturanHukum` | `Pasal` | Inverse `memuatAturan`; `Asymmetric`, `Irreflexive` ($\mathcal{R},\mathcal{I}$) |
| `bagianDariRegulasi` | `Pasal` | `Regulasi` | Inverse `memilikiPasal`; `Asymmetric`, `Irreflexive` ($\mathcal{R},\mathcal{I}$) |
| `merujukDokumen` | `DokumenHukum` | `DokumenHukum` | `TransitiveProperty` ($\mathcal{S}$) |
| `didasarkanPadaAturan` | `Thing` | `AturanHukum` | — |
| `terdampakPutusanMK` | `AturanHukum` | `PutusanMK` | — |
| `merujukSEMA` | `AturanHukum` | `SEMA_TUN` | — |
| `termasukDomain` | `Thing` | `DomainPajak` | — |
| `dikenaiTarif` | `WajibPajak` | `TarifPajak` | — |
| `memilikiFasilitas` | `WajibPajak` | `FasilitasPerpajakan` | — |
| `memilikiKewajiban` | `WajibPajak` | `KewajibanPajak` | — |
| `berisikoSanksi` | `WajibPajak` | `SanksiAdministratif` | — |

### 4.3 Data Properties (`30` Properti Fungsional)

| Kelompok | Properti | Tipe | Makna |
|---|---|---|---|
| **Profil Kuantitatif WP** | `hasOmzetTahunan` | `float` | Peredaran bruto tahunan (Rp) |
| | `hasNilaiInvestasi` | `float` | Rencana nilai penanaman modal baru (Rp) |
| | `hasPersentaseSahamPublik` | `float` | Kepemilikan saham publik (`%`) |
| | `hasJumlahKendaraan` | `int` | Urutan kepemilikan kendaraan bermotor pribadi |
| **Profil Status & Aktivitas WP** | `isPerseroanTerbuka` | `bool` | Status PT Terbuka (`Tbk`) |
| | `isIndustriPionir`, `isPenanamanModalBaru` | `bool` | Kriteria sektor & investasi baru Tax Holiday (`PMK 130/2020`) |
| | `isUMKM_PP55` | `bool` | Memilih/memenuhi skema PPh Final UMKM PP 55/2022 |
| | `hasNPWP`, `isPendudukIndonesia` | `bool` | Kepemilikan NPWP & status penduduk (NIK-NPWP `PMK 112/2022`) |
| | `isDomisiliDKI`, `isMilikPribadi`, `isMemilikiObjekPBB` | `bool` | Kriteria PKB progresif & PBB-P2 Perda DKI `1/2024` |
| | `isPenyerahanNonMewahPPN`, `isPenyerahanBKPStrategis` | `bool` | Kriteria DPP Nilai Lain `11/12` (`PMK 131/2024`) & pembebasan PPN (`PP 49/2022`) |
| | `isUsahaSpaKesehatanTradisional`, `isUsahaHiburanSpaUmum` | `bool` | Pembeda PBJT Hiburan vs kesehatan tradisional pasca `MK-2024-19-PUU-XXII` |
| | `isTerlambatLaporSPT`, `isKeberatanDitolak`, `isBandingDitolak` | `bool` | Fakta pemicu risiko sanksi KUP (`Pasal 7`, `25(9)`, `27(5d)`) |
| **Provenance & Katalog** | `hasTarifPersen` | `float` | Nilai tarif/pengurangan (`%`) pada individu `TarifPajak` |
| | `hasRuleId`, `hasSourceLocator`, `hasSourceQuote`, `hasStatusValidasi`, `hasCatatanMKSEMA` | `str` | Jejak sumber hukum pada `AturanHukum` / `Pasal` |
| | `hasDocumentId`, `hasJudul`, `hasAmarKategori`, `hasKaidahStatus` | `str` | Metadata pada `DokumenHukum`, `PutusanMK`, dan `SEMA_TUN` |

### 4.4 Daftar `28` Aturan SWRL DL-Safe

| Kelompok Task | Nama Rule SWRL | Implikasi |
|---|---|---|
| `TK-A2-1` | `SWRL_TK_A2_1_TH_50_5`, `100_5`, `100_7`, `100_10`, `100_15`, `100_20` | `LayakTaxHoliday_* -> memilikiFasilitas(..., Fasilitas_TaxHoliday_*)` |
| `TK-A2-2` | `SWRL_TK_A2_2_Badan_Tbk`, `Badan_Umum`, `UMKM_PP55`, `UMKM_Lewat_4_8M` | Tarif `19%` Tbk / `22%` umum / PP 55 `0,5%` / kewajiban transisi `> Rp4,8M` |
| `TK-B1` & `TK-B2` | `SWRL_TK_B1_PKP_PPN`, `B2_PPN_NonMewah_Efektif11`, `B2_PPN_Strategis_Bebas` | Daftar PKP + tarif `12%`, efektif `11%`, pembebasan BKP strategis |
| `TK-C1` & `TK-C2` | `SWRL_TK_C1_PBB_DKI`, `C2_PKB_DKI_1..5Plus`, `Spa_Kesehatan_MK`, `Spa_Hiburan_Umum` | PBB `0,5%`, PKB `2%..6%`, PBJT `40%` vs pengecualian `MK-2024-19-PUU-XXII` |
| `TK-D1` & `TK-D2` | `SWRL_TK_D1_NIK_NPWP_OP`, `WajibSPT`, `TenggatSPT_OP/Badan`, `D2_Sanksi_*` | NIK-NPWP, tenggat 3/4 bln, sanksi SPT, Keberatan `30%`, Banding `60%` |

---

## 5. Kontrak API FastAPI (`backend/main.py`)

### Request `POST /reason`
```json
{
  "wp_id": "PT_Contoh_01",
  "wp_kind": "PT",
  "properties": {
    "hasOmzetTahunan": 60000000000,
    "isPerseroanTerbuka": false,
    "isUMKM_PP55": false,
    "hasNPWP": true
  }
}
```

### Response `POST /reason`
```json
{
  "wp_id": "PT_Contoh_01",
  "wp_kind": "PT",
  "applied_properties": { "...": "..." },
  "direct_classes": ["BadanNonTbk", "PT", "PengusahaKenaPajak"],
  "inferred_classes": ["Badan", "BadanNonTbk", "PT", "PengusahaKenaPajak", "SubjekPajakAktif", "WajibPajak", "WajibPajakNonUMKM"],
  "tarif": [{ "id": "Tarif_PPhBadan_22Pct", "label": "...", "tarif_persen": 22.0, "justifikasi": [{ "rule_id": "...", "source_locator": "...", "source_quote": "...", "regulasi": ["UU-1983-7"], "mk_refs": [], "sema_refs": [] }] }],
  "fasilitas": [],
  "kewajiban": ["..."],
  "sanksi": [],
  "reasoner": "HermiT (OWL 2 SROIQ(D) + SWRL DL-safe)",
  "elapsed_ms": 2340.5
}
```
