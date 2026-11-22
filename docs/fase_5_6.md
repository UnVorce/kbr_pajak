# Laporan Fase 5 & 6 — TBox Ontologi `SROIQ(D)`, ABox, SWRL, Reasoning HermiT & SPARQL

> **Status:** **SELESAI — Gerbang G5 & G6 Tercapai** (TBox `SROIQ(D)` + `28` aturan SWRL DL-safe + `322` individu inti + ekspor penuh `12.907` aturan RDF Turtle + **`141` unit/integration tests lulus (`0` error HermiT)**).

---

## 1. Desain TBox `SROIQ(D)` & Integrasi Starter Tim (`ontology/kbr-core.ttl`, `ontology/kbr_pajak_tbox.owl`)

Dibangun melalui `src/ontology.py` (`build_tbox()`) dan dijalankan lewat `scripts/fase5_ontology.py build`:

- **Integrasi Starter UC1 & UC2:**
  - Mewarisi kelas utama `WajibPajak`, `OrangPribadi`, `UMKM`, `TarifPajak`, `TarifProgresif`, `TarifFinal`, `FasilitasPerpajakan`, `PP55UMKM` (`ontology_pajak.owl`) serta `Badan`, `PT`, `CV`, `Koperasi`, `Yayasan`, `BadanUsahaTetap` (`ontology_PPh_BadanUsaha.owl`).
  - Menambahkan lapisan hukum & *provenance*: `DokumenHukum` (`Regulasi` -> `UndangUndang`, `PeraturanPemerintah`, `PeraturanMenteriKeuangan`, `PeraturanDirjenPajak`, `PeraturanDaerah`, serta `Pasal`, `PutusanMK`, `SEMA_TUN`) dan `AturanHukum` (`Kewajiban`, `Hak`, `Larangan`, `Pengecualian`, `Sanksi`, `BatasWaktu`, `AturanTarif`, `Definisi`, `Prosedur`, `Kelayakan`).
- **Pembuktian Konstruk `SROIQ(D)` Penuh:**
  - **$\mathcal{S}$ (*Transitive*):** `merujukDokumen` (`DokumenHukum >> DokumenHukum, TransitiveProperty`) diuji HermiT (`PMK-2023-164 → PP-2022-55 → UU-2021-7 → UU-1983-7`).
  - **$\mathcal{R}$ (*Role Axioms & Property Chain*):** *property chain* `diaturDalamPasal ○ bagianDariRegulasi ⊑ diaturDalam` (`propertyChainAxiom`), serta `AsymmetricProperty` & `IrreflexiveProperty` pada `diaturDalamPasal` dan `bagianDariRegulasi`.
  - **$\mathcal{O}$ (*Nominals*):** `DomainPajak ≡ {Domain_A2_PPhBadan, ..., Domain_PPh_Final_Sektor}` (`OneOf` 9 individu).
  - **$\mathcal{I}$ (*Inverse*):** `mengatur <-> diaturDalam`, `memuatAturan <-> diaturDalamPasal`, `memilikiPasal <-> bagianDariRegulasi`.
  - **$\mathcal{Q}$ (*Qualified Cardinality*):** `Pasal ⊑ = 1 bagianDariRegulasi.Regulasi` (`qualifiedCardinality`), `AturanHukum ⊑ ≥ 1 diaturDalamPasal.Pasal`, dan `TarifPajak ⊑ ≥ 1 didasarkanPadaAturan.AturanHukum`.
  - **$\mathcal{ALC}$ & Disjointness:** `AllDisjoint([OrangPribadi, Badan])`, `AllDisjoint([Kewajiban, Hak, Larangan])`, `SubjekPajakAktif ≡ OrangPribadi ⊔ Badan`, `BadanNonTbk ≡ Badan ⊓ ¬BadanTerbukaTbk`, `WajibPajakNonUMKM ≡ WajibPajak ⊓ ¬WajibPajakUMKM` (uji negatif memicu `OwlReadyInconsistentOntologyError`).
  - **$(D)$ (*Datatype Restrictions*):** `10` `ConstrainedDatatype` untuk ambang PKP (`> 4.8e9`), UMKM PP 55 (`<= 4.8e9`), Tbk Go Public (`>= 40.0%`), 6 tier Tax Holiday `PMK-2020-130`, dan 5 tier PKB Progresif DKI `Perda 1/2024`.

---

## 2. Arsitektur Dua Lapisan ABox & Pemilihan Reasoner (HermiT vs Pellet)

- **Temuan Lingkungan (`owlready2 0.51` + OpenJDK 21):**
  - Pellet bawaan `owlready2 0.51` gagal pada OpenJDK 21 (`UnsupportedClassVersionError` / class version `69.0`), dan `Imp.set_as_rule()` menolak built-in `swrlb:greaterThanOrEqual`.
  - **Solusi bersih:** Seluruh klasifikasi ambang numerik dipindahkan ke aksioma `OWL 2 ConstrainedDatatype` (`SROIQ(D)`), sedangkan aturan implikasi objek memakai **28 aturan SWRL DL-safe murni** dan dievaluasi menggunakan **HermiT** (`sync_reasoner_hermit(world, infer_property_values=True)`).
- **Dua Lapisan Ekspor:**
  1. **Reasoning Layer (`ontology/kbr_pajak_reasoning.owl`, `329 KB`, RDF/XML):** berisi `59` kelas, `28` aturan SWRL, **`322` individu** (`31` item katalog tarif/fasilitas/kewajiban/sanksi yang tertaut ke `AturanHukum` -> `Pasal` -> `Regulasi` + `15` `PutusanMK` + `14` `SEMA_TUN` pajak + `120` aturan terkurasi `P1–P6` + `8` skenario uji `WajibPajak`). Dievaluasi HermiT dalam < 2 detik per `World()` terisolasi.
  2. **Full Knowledge Graph (`data/export/kbr-data.ttl`, `9,9 MB`, Turtle):** mengekspor seluruh **`12.907` aturan atomik** `legal_rules.jsonl` lengkap dengan `hasRuleId`, `hasSourceLocator`, `hasSourceQuote`, `hasStatusValidasi`, `termasukDomain`, `diaturDalam`, `diaturDalamPasal`, `terdampakPutusanMK`, dan `merujukSEMA` untuk query **SPARQL lokal (`rdflib`)**.

---

## 3. Verifikasi Skenario Reasoning `TK-A2-1` s.d. `TK-E1`

Seluruh skenario dievaluasi deterministik di `tests/test_ontology.py` (**`9/9` test ontologi & `141/141` total `pytest` lulus**):

| Kode | Task | Hasil Inferensi HermiT / SPARQL | Provenance Terverifikasi |
|---|---|---|---|
| **TK-A2-1** | Kelayakan Tax Holiday (`PMK-2020-130`) | Rp250M → `LayakTaxHoliday_50Pct_5Thn` (50%, 5 thn); Rp1,5T → `100Pct_7Thn`; Rp35T → `100Pct_20Thn` | `R-PMK-2020-130-a3c9ffdaa5`, `3feb2730e9`, `4777afbb39` (`#BT/2`) |
| **TK-A2-2** | Tarif PPh Badan & Transisi UMKM | Tbk ≥40% publik → `Tarif_PPhBadan_Tbk_19Pct` (19%); Non-Tbk → `22%`; UMKM ≤4,8M → `PP55` 0,5%; UMKM >4,8M → `Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum` | `R-UU-1983-7-fcd99f0036`, `795d9e9140`, `R-PP-2022-55-a9963cde88`, `R-PMK-2023-164-2ded388f17` |
| **TK-B1** | Ambang PKP | Omzet ≥ Rp4,8M → `PengusahaKenaPajak` + `Kewajiban_DaftarPKP_PungutPPN` | `R-PMK-2023-164-706302d621` |
| **TK-B2** | Tarif & Fasilitas PPN | `Tarif_PPN_12Pct`, `Tarif_PPN_Efektif_11Pct` (non-mewah DPP 11/12), `Fasilitas_PPN_Dibebaskan_Strategis` | `R-PMK-2024-131-43f37b0b3b`, `2315c9737b`, `R-PP-2022-49-27f724ae54` |
| **TK-C1** | Kewajiban PBB-P2 | Domisili DKI + objek PBB → `Tarif_PBB_DKI_0_5Pct` + `Kewajiban_LaporPBB` | `R-PERDA-PROV-DKI-JAKARTA-2024-1-a04b748190`, `675c47e425` |
| **TK-C2** | Pajak Daerah & Putusan MK | PKB progresif DKI ke-1..5+ (2%..6%); Spa Kesehatan Tradisional → `Fasilitas_Pengecualian_SpaKesehatanTradisional_MK` | `R-PERDA-PROV-DKI-JAKARTA-2024-1-2227d61ab1`, `0117748e9b` (`MK-2024-19-PUU-XXII`) |
| **TK-D1** | Administrasi NIK-NPWP & SPT | OP Penduduk → `Kewajiban_NPWP_NIK_OP` + tenggat 3 bln; Badan → tenggat 4 bln | `R-PMK-2022-112-a91070d05f`, `R-UU-1983-6-ec282e98db`, `31abe376bc` |
| **TK-D2** | Risiko Sanksi & SEMA TUN | Telat SPT → `Sanksi_Denda_KUP_TerlambatSPT`; Keberatan ditolak → `30%`; Banding ditolak → `60%` | `R-UU-1983-6-a86dd99b6a`, `c367eea7f6`, `ad287a542a` (`SEMA-2024-2-TUN-4`) |
| **TK-E1** | Justifikasi & SPARQL | Rantai lengkap `Tarif/Fasilitas/Sanksi -> AturanHukum -> Pasal -> Regulasi + PutusanMK/SEMA_TUN + source_quote` via `reason_wajib_pajak()` & `query_rule_provenance_sparql()` | Teruji pada `kbr_pajak_reasoning.owl` & `kbr-data.ttl` (`12.907` aturan) |

---

## 4. Artefak Dihasilkan

- `ontology/kbr-core.ttl` (`20 KB`) & `ontology/kbr_pajak_tbox.owl` (`41 KB`) — TBox `SROIQ(D)`
- `ontology/kbr_pajak_reasoning.owl` (`329 KB`) — TBox + `28` SWRL + `322` individu + `8` skenario uji
- `ontology/rule_map.json` (`21 KB`) — peta `31` konsep katalog → `rule_id` & pasal
- `ontology/ontology_build_report.json` — ringkasan build & hasil inferensi 8 skenario
- `data/export/kbr-data.ttl` (`9,9 MB`) — ekspor RDF penuh `12.907` aturan
- `src/ontology.py`, `scripts/fase5_ontology.py`, `tests/test_ontology.py`
