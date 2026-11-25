# Laporan Fase 5 & 6 — TBox Ontologi `SROIQ(D)`, ABox, SWRL, Reasoning HermiT & SPARQL

> **Status:** **SELESAI — Gerbang G5 & G6 Tercapai** (TBox `SROIQ(D)` penuh: `113` kelas, `17` object properties, `51` data properties, `73` aturan SWRL DL-safe, `450` individu inti + ekspor penuh `12.907` aturan RDF Turtle + **seluruh tes ontologi & SPARQL lulus (`0` error HermiT)**).

---

## 1. Desain TBox `SROIQ(D)` & Integrasi Starter Tim (`ontology/kbr-core.ttl`, `ontology/kbr_pajak_tbox.owl`)

Dibangun melalui `src/ontology.py` (`build_tbox()`) dan dijalankan lewat `scripts/fase5_ontology.py build`:

- **Integrasi Starter UC1 & UC2 + Ekspansi Lintas Domain:**
  - Mewarisi kelas `WajibPajak`, `OrangPribadi`, `UMKM`, `TarifPajak`, `TarifProgresif`, `TarifFinal`, `FasilitasPerpajakan`, `PP55UMKM` (`ontology_pajak.owl`) serta `Badan`, `PT`, `CV`, `Koperasi`, `Yayasan`, `BadanUsahaTetap` (`ontology_PPh_BadanUsaha.owl`).
  - Memisahkan `BadanDalamNegeri` (`BadanHukumIndonesia` -> `PT`, `Koperasi`; serta `CV`, `Yayasan`) dari `BadanUsahaTetap` (`BUT`) untuk menangani **Pasal 31E**, **syarat `PP 55/2022`**, **syarat badan hukum Tax Holiday `PMK-2020-130`**, dan **Branch Profit Tax `20%` (`Pasal 26(4)`)**.
  - Memodelkan **`OrangPribadi` dunia nyata** lewat relasi `memilikiPekerjaan -> JenisPekerjaan` (`30` individu profesi di bawah `PekerjaanPegawai`, `PekerjaanBebas`, `UsahaDagangJasa`) sehingga mendukung kasus **multi-peran**, **TER A/B/C (`PP 58/2023`)**, **bebas PPh `≤ Rp500jt`**, **larangan PP 55 & opsi NPPN bagi Pekerja Bebas**, serta **5 lapis tarif Pasal 17 (`5%`–`35%`)**.
  - Memodelkan **5 Perda PDRD pilot** (`WilayahDaerah`: DKI Jakarta, Jawa Barat, Kota Surabaya, Kota Semarang, Provinsi Bali) + **PPh Pasal 23** (`2%`, `15%`, pengecualian Bank, penalti `+100%` non-NPWP) + **sanksi KUP terdiferensiasi** (`OP Rp100rb`, `Badan Rp1jt`, `Masa PPN Rp500rb`, `SKPKB bunga & 75%`).

- **Pembuktian Konstruk `SROIQ(D)` Penuh:**
  - **$\mathcal{S}$ (*Transitive*):** `merujukDokumen` (`DokumenHukum >> DokumenHukum, TransitiveProperty`) diuji HermiT (`PMK-2023-164 → PP-2022-55 → UU-2021-7 → UU-1983-7`).
  - **$\mathcal{R}$ (*Role Axioms & Property Chain*):** *property chain* `diaturDalamPasal ○ bagianDariRegulasi ⊑ diaturDalam` (`propertyChainAxiom`), serta `AsymmetricProperty` & `IrreflexiveProperty` pada `diaturDalamPasal` dan `bagianDariRegulasi`.
  - **$\mathcal{O}$ (*Nominals*):** `DomainPajak` (`9` domain) dan `WilayahDaerah` (`5` wilayah Perda pilot) via `OneOf`.
  - **$\mathcal{I}$ (*Inverse*):** `mengatur <-> diaturDalam`, `memuatAturan <-> diaturDalamPasal`, `memilikiPasal <-> bagianDariRegulasi`.
  - **$\mathcal{Q}$ (*Qualified Cardinality*):** `Pasal ⊑ = 1 bagianDariRegulasi.Regulasi`, `AturanHukum ⊑ ≥ 1 diaturDalamPasal.Pasal`, dan `TarifPajak ⊑ ≥ 1 didasarkanPadaAturan.AturanHukum`.
  - **$\mathcal{ALC}$ & Disjointness:** `AllDisjoint([OrangPribadi, Badan])`, `AllDisjoint([PT, CV, Koperasi, Yayasan, BadanUsahaTetap])`, `AllDisjoint([PekerjaanPegawai, PekerjaanBebas, UsahaDagangJasa])`, `SubjekPajakAktif ≡ OrangPribadi ⊔ Badan`, `BadanNonTbk ≡ Badan ⊓ ¬BadanTerbukaTbk`, `WajibPajakNonUMKM ≡ WajibPajak ⊓ ¬WajibPajakUMKM` (uji negatif memicu `OwlReadyInconsistentOntologyError`).
  - **$(D)$ (*Datatype Restrictions*):** `ConstrainedDatatype` untuk ambang PKP (`> 4.8e9`), UMKM OP (`≤ 500jt` & `500jt–4.8M`), Pasal 31E (`≤ 50M`), Tbk (`≥ 40%` publik, `≥ 300` pihak, `≥ 183` hari), 6 tier Tax Holiday, 5 lapis Pasal 17 (`> 0` s.d. `> 5M`), PBB Surabaya 6 lapis NJOP, dan PKB Progresif/CC.

---

## 2. Arsitektur Dua Lapisan ABox & Reasoner (HermiT + `rdflib`)

1. **Reasoning Layer (`ontology/kbr_pajak_reasoning.owl`, RDF/XML):** `113` kelas, `73` aturan SWRL DL-safe, `450` individu (`79` item katalog ber-provenance `AturanHukum -> Pasal -> Regulasi` + `30` `JenisPekerjaan` + `5` `WilayahDaerah` + `15` `PutusanMK` + `14` `SEMA_TUN` pajak + `50` aturan terkurasi + `15` skenario uji). Pada inferensi tunggal (`reason_wajib_pajak`), individu demo & aturan non-katalog dibersihkan di memori sehingga HermiT tetap steril & cepat (`~4,8 dtk`).
2. **Full Knowledge Graph (`data/export/kbr-data.ttl`, `9,9 MB`, Turtle):** mengekspor seluruh **`12.907` aturan atomik** `legal_rules.jsonl` lengkap dengan *provenance* untuk query **SPARQL lokal (`rdflib`)**.

---

## 3. Artefak Dihasilkan

- `ontology/kbr-core.ttl` & `ontology/kbr_pajak_tbox.owl` — TBox `SROIQ(D)`
- `ontology/kbr_pajak_reasoning.owl` — TBox + `73` SWRL + `450` individu + `15` skenario uji
- `ontology/rule_map.json` — peta `79` konsep katalog → `rule_id`, `source_locator`, `source_quote`, MK/SEMA
- `ontology/ontology_build_report.json` — ringkasan build & hasil inferensi `15` skenario
- `data/export/kbr-data.ttl` (`9,9 MB`) — ekspor RDF penuh `12.907` aturan
- `src/ontology.py`, `scripts/fase5_ontology.py`, `tests/test_ontology.py`
