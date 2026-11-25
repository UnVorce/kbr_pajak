# Data Dictionary — Sistem KBR Perpajakan Indonesia

> **Cakupan:** Kamus data lengkap untuk seluruh artefak korpus JSON, aturan hukum atomik (`legal_rules.jsonl`), ontologi OWL 2 `SROIQ(D)` (`kbr-core.ttl`, `kbr_pajak_reasoning.owl`, `kbr-data.ttl`), dan kontrak JSON API (`backend/`).

---

## 1. Konvensi Penamaan & ID Kanonik (`src/ids.py`)

| Entitas | Pola ID | Contoh |
|---|---|---|
| Regulasi Pusat | `{JENIS}-{TAHUN}-{NOMOR}` | `UU-1983-7`, `UU-2023-6`, `PP-2022-55`, `PMK-2024-131`, `PMK-2023-168`, `PP-2023-58` |
| Peraturan Daerah | `PERDA-{TINGKAT}-{DAERAH}-{TAHUN}-{NOMOR}` | `PERDA-PROV-DKI-JAKARTA-2024-1`, `PERDA-KOTA-SURABAYA-2023-7`, `PERDA-PROV-JAWA-BARAT-2023-9` |
| Putusan Pengadilan Pajak | `PP-PUT-{NOMOR_PUTUSAN}` | `PP-PUT-000123-16-2023` |
| Putusan Mahkamah Konstitusi | `MK-{TAHUN}-{NOMOR}-PUU-{MASA}` | `MK-2024-19-PUU-XXII` |
| Butir SEMA Kamar TUN | `SEMA-{TAHUN}-{NOMOR}-TUN-{SUB}` | `SEMA-2024-2-TUN-4` |
| Source Locator Pasal | `{DOC_ID}#{BAGIAN}/{PASAL}[/{AYAT}[/{HURUF}]]` | `UU-1983-6#BT/27/1..5d`, `PERDA-KOTA-SURABAYA-2023-7#BT/8` |
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

### 4.1 Hirarki Kelas (`120` Kelas di `kbr_pajak_tbox.owl`)

| Kelompok | Kelas & Subkelas |
|---|---|
| **Wajib Pajak Badan (`Badan`)** | `BadanDalamNegeri`, `BadanHukumIndonesia` (`PT`, `Koperasi`), `CV`, `Yayasan`, `BadanUsahaTetap` (`BUT`), `BadanTerbukaTbk`, `BadanNonTbk`, `BadanUMKM`, `BadanLayakPasal31E`, `BadanLayakTaxAllowance`, `BadanLayakPadatKarya`, `LayakTaxHoliday` (`50Pct_5Thn`, `100Pct_5Thn`, `7Thn`, `10Thn`, `15Thn`, `20Thn`) |
| **Wajib Pajak Orang Pribadi (`OrangPribadi`)** | `OP_SubjekDalamNegeri`, `OP_SubjekLuarNegeri`, `OP_PenerimaPPh21_PegawaiTetap` (`OP_TER_Kategori_A`, `OP_TER_Kategori_B`, `OP_TER_Kategori_C`, `OP_MultiPemberiKerja`), `OP_PenerimaPPh21_TidakTetap`, `OP_PesertaKegiatan`, `OP_PekerjaBebas` (`OP_PekerjaBebas_LayakNPPN`, `OP_NPPN_Gugur_TelatLapor`), `OP_PelakuUsahaNonProfesi` (`OP_UMKM_Bebas_500Jt`, `OP_UMKM_Final_PP55`), `OP_WajibPembukuan`, `OP_PPh17_Layer1_5Pct`..`Layer5_35Pct` |
| **Wajib Pajak Lintas Subjek & Daerah** | `SubjekPajakAktif`, `UMKM`, `PengusahaKenaPajak`, `WajibPajakUMKM`, `WajibPajakNonUMKM`, `WP_TidakSelenggarakanPembukuan`, `WP_Wilayah_DKI`, `WP_Wilayah_Jabar`, `WP_Wilayah_Surabaya`, `WP_Wilayah_Semarang`, `WP_Wilayah_Bali`, `WP_Wilayah_Nasional_NonDKI`, `WP_Wilayah_NonDKI_Kendaraan`, `Badan_PemilikKendaraanDKI`, `OP_PemilikKendaraanDKI` (`Ke1`..`Ke5Plus`), `Badan_PemilikKendaraanJabar`, `OP_KendaraanKe1..5Plus_Jabar`, `WP_PBB_Surabaya_L1..L6`, `OP_Kendaraan_Bali_Max200cc/Over200cc`, `PenerimaPPh23_NonBank_JasaSewa/Modal`, `WP_PPh23_TanpaNPWP` |
| **Pekerjaan & Wilayah** | `JenisPekerjaan` (`PekerjaanPegawai` -> `PekerjaanPegawaiTetap`, `PekerjaanPegawaiTidakTetap`, `PekerjaanPesertaKegiatan`; `PekerjaanBebas`; `UsahaDagangJasa`) berisi `30` individu profesi; `WilayahDaerah` (`6` nominal: `5` daerah pilot + `Wilayah_Nasional_NonDKI`) |
| **Katalog Output (`83` item)** | `TarifPajak` (`TarifProgresif`, `TarifFinal`), `FasilitasPerpajakan` (`PP55UMKM`), `KewajibanPajak`, `SanksiAdministratif`, `DomainPajak` (`9` nominal), `ObjekPajak` |
| **Dokumen & Aturan Reifikasi** | `DokumenHukum` (`Regulasi` -> `UndangUndang`, `PeraturanPemerintah`, `PeraturanMenteriKeuangan`, `PeraturanDirjenPajak`, `PeraturanDaerah`; `Pasal`; `PutusanMK`; `SEMA_TUN`), `AturanHukum` (`Kewajiban`, `Hak`, `Larangan`, `Pengecualian`, `Sanksi`, `BatasWaktu`, `AturanTarif`, `Definisi`, `Prosedur`, `Kelayakan`) |

### 4.2 Object Properties (`17` Properti)

| Properti | Domain | Range | Karakteristik `SROIQ` |
|---|---|---|---|
| `diaturDalam` | `AturanHukum` | `Regulasi` | Inverse `mengatur`; **PropertyChain** `[diaturDalamPasal, bagianDariRegulasi]` ($\mathcal{R},\mathcal{I}$) |
| `diaturDalamPasal` | `AturanHukum` | `Pasal` | Inverse `memuatAturan`; `Asymmetric`, `Irreflexive` ($\mathcal{R},\mathcal{I}$) |
| `bagianDariRegulasi` | `Pasal` | `Regulasi` | Inverse `memilikiPasal`; `Asymmetric`, `Irreflexive` ($\mathcal{R},\mathcal{I}$) |
| `merujukDokumen` | `DokumenHukum` | `DokumenHukum` | `TransitiveProperty` ($\mathcal{S}$) |
| `memilikiPekerjaan` | `OrangPribadi` | `JenisPekerjaan` | Menautkan WP OP ke `30` profesi resmi (multi-peran aman) |
| `berdomisiliDi` | `WajibPajak` | `WilayahDaerah` | Menautkan WP ke salah satu dari `5` Perda pilot |
| `didasarkanPadaAturan` | `Thing` | `AturanHukum` | Penaut katalog ke aturan sumber |
| `terdampakPutusanMK` / `merujukSEMA` | `AturanHukum` | `PutusanMK` / `SEMA_TUN` | Lapisan yurisprudensi |
| `termasukDomain` | `Thing` | `DomainPajak` | Klasifikasi domain |
| `dikenaiTarif`, `memilikiFasilitas`, `memilikiKewajiban`, `berisikoSanksi` | `WajibPajak` | Katalog Output | Hasil inferensi SWRL |

### 4.3 Data Properties (`62` Properti Fungsional)

- **Profil Kuantitatif (`15`):** `hasOmzetTahunan` (`float`), `hasNilaiInvestasi` (`float`), `hasPersentaseSahamPublik` (`float`), `hasJumlahPemegangSahamPublik` (`int`), `hasHariTerpenuhiTbk` (`int`), `hasJumlahKendaraan` (`int`), `hasKapasitasMesinCC` (`int`), `hasNilaiNJOP` (`float`), `hasPersentaseNJOP_PBB` (`float`), `hasNJOPTKP_PBB` (`float`), `hasDPP_PPN` (`float`), `hasJumlahTanggungan` (`int`), `hasPenghasilanKenaPajakTahunan` (`float`, berlaku untuk OP & Badan), `hasPenghasilanBrutoBulanan` (`float`), `hasJumlahPemberiKerja` (`int`).
- **Profil Status & Aktivitas (`36`):** `isPerseroanTerbuka`, `isPerseroanPerorangan`, `isIndustriPionir`, `isPenanamanModalBaru`, `isBidangUsahaTaxAllowance`, `isLokasiProvinsiMemenuhiTaxAllowance`, `isIndustriPadatKarya`, `hasSuratKeteranganFiskal`, `isBelumPernahPutusTaxHoliday`, `isUMKM_PP55`, `hasNPWP`, `isPendudukIndonesia`, `isSubjekLuarNegeri`, `isKawin`, `isPenghasilanIstriDigabung`, `isPemberitahuanNPPNTepatWaktu`, `isTidakMenyelenggarakanPembukuanPencatatan`, `kelompokWilayahNPPN` (`str`), `isPenyerahanNonMewahPPN`, `isPenyerahanBKP_Mewah`, `isPenyerahanBKPStrategis`, `isPenerimaPenghasilanPPh23_JasaSewa`, `isPenerimaPenghasilanPPh23_Modal`, `isBankPenerimaPenghasilan`, `isDomisiliDKI`, `isMilikPribadi`, `isMemilikiObjekPBB`, `isUsahaSpaKesehatanTradisional`, `isUsahaHiburanSpaUmum`, `isTerlambatLaporSPT`, `isTerlambatLaporSPTMasaPPN`, `isDikecualikanDendaSPT`, `isKurangBayarSKPKB`, `isTidakSetorPajakDipungut`, `isKeberatanDitolak`, `isBandingDitolak`.
- **Provenance & Katalog (`11`):** `hasTarifPersen` (`float`), `hasNominalSanksi` (`float`), `hasRuleId`, `hasSourceLocator`, `hasSourceQuote`, `hasStatusValidasi`, `hasCatatanMKSEMA`, `hasDocumentId`, `hasJudul`, `hasAmarKategori`, `hasKaidahStatus` (`str`).

### 4.4 `78` Aturan SWRL DL-Safe (Ringkasan Kelompok)

| Kelompok | Jumlah Rules | Cakupan |
|---|---|---|
| PPh Badan, Tbk, Pasal 31E, BUT, UMKM, Tax Holiday, Tax Allowance & Padat Karya | `17` | `19%`, `22%`, `31E 11%`, `BUT 20%`, `PP55 0,5%`, `OP Bebas 500jt`, transisi `>4,8M`, `6` tier Tax Holiday + masa transisi 2 thn, `Tax Allowance 30%` (`PP 78/2019`), `Padat Karya 60%` (`PMK 81/2024`) |
| PPh OP (`PMK-2023-168`, `PP-2023-58`, `UU HPP`, `PER-17/PJ/2015`) | `15` | `TER A/B/C`, Harian, `PPh 26 20%`, Pekerja Bebas (`DPP 50%`, larangan PP 55, `NPPN`, gugur NPPN bila telat lapor), Pembukuan `≥4,8M`, multi pemberi kerja, `5` layer Pasal 17 (`5%`–`35%`) |
| PPN & Pemotongan PPh 23 | `8` | PKP, PPN `12%` (Mewah) vs Efektif `11%` (Non-Mewah), BKP Strategis, PPh 23 `2%`/`15%`/Bank/Non-NPWP `+100%` |
| Pajak Daerah (`5` Perda Pilot + HKPD) & MK | `25` | PBB DKI/Semarang/Surabaya (6 lapis), PKB DKI (Badan `2%`, OP `2%–6%`), Jabar (`1,12%–3,12%` + Opsen), Bali (`≤200cc`/`>200cc`), Opsen HKPD generik non-DKI (`66%`), PBJT DKI `40%`/Surabaya `50%` vs `MK-2024-19-PUU-XXII` |
| Administrasi KUP & Sanksi + SEMA | `13` | NIK-NPWP, SPT, tenggat 3/4 bln, denda SPT (`OP 100rb`, `Badan 1jt`, `PPN 500rb`, pengecualian `7(2)`), SKPKB (`bunga` & `75%`), norma pemeriksaan `Pasal 14(5)`, Keberatan `30%`, Banding `60%` |

---

## 5. Kontrak API FastAPI (`backend/main.py`) & Modul Step B–C

- **`ontology/kbr_ter_pph21.ttl` (`127` bracket TER PPh 21 dari `PP-2023-58`):** `TER_A` (`44` bracket), `TER_B` (`40` bracket), `TER_C` (`41` bracket), dan `TER_Harian` (`2` bracket), divalidasi kontinuitas penuh batas bawah/atas & keselarasan terbilang Indonesia.
- **`ontology/kbr_kbli.ttl` (`1.449` konsep W3C SKOS `skos:Concept`):** memuat kode KLU/KBLI 5-digit dari `PER-17/PJ/2015` Lampiran I (`1.431` NPPN OP), II (`1.433` Pemeriksaan OP), III (`1.429` Pemeriksaan Badan), dan `PP-2019-78` Lampiran I & II (`168` bidang usaha Tax Allowance beserta syarat provinsi/kecuali DKI Jakarta).
- **`ontology/kbr-perda-rates.ttl` (`390` Pemda dari `524` Perda PDRD, `2.029` item tarif):** menormalisasi `13` ID non-standar, memproses Induk → Perubahan secara kronologis, serta menyimpan tarif PKB, BBNKB, PBB-P2, NJOPTKP, BPHTB, NPOPTKP, PBJT, dan Opsen beserta kutipan pasal (`360/390` Pemda memiliki tarif pajak terekstrak).
- **Endpoint API:**
  - `GET /health` → status `.owl`, `.ttl` (termasuk `ter_ttl_exists`, `kbli_ttl_exists`, `perda_ttl_exists`), jumlah kelas/individu/SWRL.
  - `GET /options` → daftar `30` `JenisPekerjaan` (beserta kategorinya) dan `6` `WilayahDaerah` dari ontologi OWL.
  - `GET /kbli?q=...&limit=20` & `GET /kbli/{kode}` → pencarian dan detail `1.449` kode KBLI SKOS.
  - `GET /perda?q=...&tingkat=...&limit=30` & `GET /perda/{pemda_id}` → pencarian dan detail tarif `390` Pemda (`524` Perda).
  - `GET /catalog` → `83` item katalog `rule_map.json`.
  - `GET /scenarios` → `15` skenario demonstrasi bawaan.
  - `GET /sparql/provenance` & `GET /sparql/stats` → query `kbr-data.ttl` (`12.907` aturan).
  - `POST /reason` → menerima `wp_id`, `wp_kind` (`PT`, `CV`, `Koperasi`, `Yayasan`, `BadanUsahaTetap`, `BUT`, `Badan`, `OrangPribadi`), `kodeKBLI`, `pemdaId`, `lokasiProvinsiTaxAllowance`, `memilikiPekerjaan`, `berdomisiliDi`, dan properti WP, lalu mengembalikan `direct_classes`, `inferred_classes`, `tarif`, `fasilitas`, `kewajiban`, `sanksi`, `kbli_info`, `perda_info`, rantai `justifikasi`, serta **`estimasi_pajak`** (hasil kalkulator deklaratif **`SPARQL 1.1 BIND`** + TER PPh 21 + NPPN KBLI + PBB Pemda lokal).
