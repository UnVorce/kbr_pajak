# Laporan Akhir Fase 8 — Dokumentasi Menyeluruh Sistem KBR Perpajakan Indonesia (Fase 0–8)

> **Status:** **SELESAI — Gerbang G8 (Serah Terima Final)**
> **Seluruh Fase (0–8) selesai:** Akuisisi korpus resmi, konsolidasi-lite 32 rantai amandemen, ekstraksi 12.907 aturan atomik, ontologi OWL 2 `SROIQ(D)` penuh (`113` kelas, `73` SWRL, `HermiT`), ekspor RDF/SPARQL penuh, dan service API FastAPI (`backend/`), dengan **`149/149` tes otomatis lulus**.

---

## 1. Tujuan & Masalah yang Diselesaikan

Sistem ini dibangun untuk menjawab masalah nyata pada konsultasi/informasi perpajakan di Indonesia:

1. **Aturan pajak tersebar & sering diamendemen:** Ketentuan PPh, PPN, KUP, dan PDRD berubah berlapis (mis. `UU 6/1983` → `UU 7/2021 HPP` → `UU 6/2023 Cipta Kerja`), sehingga membaca pasal lama secara terpisah sering menyesatkan.
2. **Dampak putusan yudisial sering terlewat:** Amar konstitusional bersyarat dari **Mahkamah Konstitusi (MK)** dan rumusan pleno **SEMA Kamar TUN** mengubah penerapan pasal tanpa selalu mengubah naskah cetak UU.
3. **Kewajiban transparansi KBR (bukan kotak hitam):** Setiap kesimpulan tarif, fasilitas, kewajiban, dan risiko sanksi tidak boleh berasal dari logika *hardcode* Python atau ingatan LLM, melainkan harus keluar dari **inferensi ontologi formal (`SROIQ(D)` + SWRL)** dan **dapat ditelusuri persis** sampai ke `rule_id`, `Pasal`, `Ayat`, kutipan teks asli (`source_quote`), serta rujukan `PutusanMK`/`SEMA_TUN`.

---

## 2. Arsitektur Sistem End-to-End

```text
[SUMBER HUKUM RESMI]
  BPK RI (peraturan.bpk.go.id) · JDIH Kemenkeu · DJP · SetPP · MKRI · MA (SEMA TUN)
        │
        ▼ (Fase 1–3B: Crawl, Scope Gate, PyMuPDF + Tesseract OCR, Gap Closure = 0)
[KORPUS JSON KANONIK & KONSOLIDASI-LITE]
  165 regulasi pusat · 32 consolidated (incl. UU CK & HPP) · 524 Perda PDRD
  284 Putusan SetPP · 15 Putusan MK Pajak · 78 butir SEMA Kamar TUN (14 pajak)
        │
        ▼ (Fase 4: 5.509 Chunk -> Colab Qwen2.5-32B-AWQ -> Validator S8 -> Audit Atomik P1-P6)
[12.907 ATURAN ATOMIK TERVALIDASI: legal_rules.jsonl]
  8.717 VALIDATED · 474 HUMAN_FIXED · 117 HUMAN_APPROVED · 3.599 REVIEW_REQUIRED
  (9 domain pajak, 100 dokumen unik, 0 aturan dari dokumen karantina PER-DJP-2015-17)
        │
        ├──────────────────────────────────────────────┐
        ▼ (Fase 5–6: Lapisan Reasoning Ringkas)         ▼ (Fase 6: Lapisan Graf Penuh)
[kbr_pajak_reasoning.owl + kbr-core.ttl]        [kbr-data.ttl (9,9 MB)]
  113 Kelas OWL 2 SROIQ(D) · 73 Aturan SWRL       Ekspor RDF penuh 12.907 aturan
  450 Individu (79 Katalog + 30 Profesi +         beserta quote & rujukan MK/SEMA
  5 Daerah + MK + SEMA + 15 Skenario)                  │
        │                                              │
        ▼ (HermiT Reasoner, World() terisolasi)        ▼ (rdflib SPARQL engine)
[FASTAPI BACKEND: backend/main.py] ◄───────────────────┘
  GET /options · POST /reason · GET /sparql/provenance · GET /catalog · GET /health
        │
        ▼
[KONSUMEN TIM]
  Frontend Next.js/React (yoeke-front) · Modul RAG (daRAG) · Protégé GUI
```

---

## 3. Penjelasan Mendalam Cara Kerja Komponen Inti

### 3.1 Mengapa Korpus Dibangun dengan Konsolidasi-Lite & Karantina Sumber?
- **Konsolidasi-lite (`src/consolidate.py`):** 32 peraturan induk yang mengalami amandemen (seperti `UU-1983-6` KUP, `UU-1983-7` PPh, `UU-1983-8` PPN, `UU-1985-12` PBB, serta lapisan `UU-2021-7` HPP dan `UU-2023-6` Cipta Kerja) diputar ulang instruksi `UBAH`/`SISIP`/`HAPUS`-nya untuk menghasilkan teks pasal **terbaru** yang bersih tanpa tumpang-tindih versi usang.
- **Integritas sumber (`ISSUES.md #A7`):** Validator S8 mendeteksi bahwa file PDF `PER-DJP-2015-17` dari BPK ternyata berisi Perda Kab. Pangandaran tentang Lingkungan Hidup; `QUARANTINED_DOC_IDS` membuang 153 chunk dokumen tersebut sehingga **0 aturan salah** masuk ke `legal_rules.jsonl`.
- **Audit atomik `P1`–`P6` (`621` baris):** Aturan yang awalnya tergabung dalam satu kalimat/daftar (misalnya 5 tier PKB progresif DKI, 6 tier Tax Holiday `PMK-2020-130`, 6 pengecualian PPh 23 ayat 4, denda keberatan 30% & banding 60%) dipecah menjadi aturan atomik satu-per-satu dan diaudit terhadap teks sumber.

### 3.2 Mengapa Ontologi Memakai Arsitektur Dua Lapisan?
Memasukkan seluruh `12.907` individu + string `source_quote` ke dalam satu file `.owl` untuk reasoner Description Logic (`HermiT`/`Pellet`) akan memperlambat klasifikasi secara drastis, sementara `owlready2 0.51` dengan Pellet bawaan gagal di OpenJDK 21 (`class file version 69.0`) dan `Imp.set_as_rule()` tidak menerima built-in `swrlb:greaterThanOrEqual`.

Solusi arsitektural yang terbukti bersih dan cepat:
1. **Lapisan Reasoning (`ontology/kbr_pajak_reasoning.owl`):**
   - Berisi TBox lengkap **`119` kelas `SROIQ(D)` penuh** (memenuhi $\mathcal{S}$ `TransitiveProperty`, $\mathcal{R}$ `PropertyChain` + `Asymmetric`/`Irreflexive`, $\mathcal{O}$ `OneOf` nominals, $\mathcal{I}$ 3 pasang *inverse*, $\mathcal{Q}$ `= 1` & `≥ 1` *qualified cardinality*, dan $(D)$ `ConstrainedDatatype`), **`17` Object Properties**, **`62` Data Properties**, **`78` aturan SWRL DL-safe**, dan **`367` individu** (`83` item katalog ber-provenance + `30` profesi `JenisPekerjaan` + `5` wilayah `WilayahDaerah` + `15` `PutusanMK` + `14` `SEMA_TUN` + `50` aturan terkurasi + `15` skenario).
   - **Kalkulator Estimasi Nominal (`SPARQL 1.1 BIND`):** `backend/engine.py` mengonversi graf WP hasil HermiT lewat `world.as_rdflib_graph()` lalu menjalankan `SPARQL BIND` untuk mengestimasi rupiah PPh Badan / Pasal 31E, BUT BPT 20%, OP UMKM (`> Rp500jt`), OP Pasal 17 5 lapis, PPN (`12%` Mewah vs `11%` Efektif), PBB-P2, dan denda KUP tetap — tanpa `swrlb:*` yang tidak didukung HermiT dan tanpa hardcode tarif di Python.
2. **Lapisan Graf Penuh (`kbr-data.ttl`, `9,9 MB`):**
   - Menyimpan seluruh **`12.907` aturan atomik** dalam format Turtle RDF untuk query **SPARQL lokal (`rdflib`)** dalam hitungan milidetik setelah dimuat ke memori.

### 3.3 Pemodelan Dunia Nyata (`Badan`, `OrangPribadi`, `BUT`, `PPh 23`, `5` Perda Pilot)
- **`OrangPribadi` Multi-Peran (`memilikiPekerjaan`):** User dapat memilih 1 atau lebih dari `30` profesi resmi (`PegawaiTetap_Swasta`, `Dokter`, `Influencer_KontenKreator`, `Pedagang_ECommerce`, dll.). HermiT dapat mengklasifikasikan seorang dokter yang juga karyawan rumah sakit dan pemilik toko online ke rezimnya masing-masing tanpa konflik `AllDisjoint`.
- **`BadanDalamNegeri` vs `BUT`:** `PT`/`Koperasi`/`CV` mendapat fasilitas Pasal 31E bila omzet `≤ Rp50M`; `BUT` dilarang masuk `BadanUMKM` dan dikenai Branch Profit Tax `20%`.
- **PPN `12%` Mewah vs `11%` Efektif (`PMK-2024-131`):** Dipisahkan tegas agar tidak dobel.
- **Sanksi KUP Terdiferensiasi:** Denda telat SPT `OP Rp100rb`, `Badan Rp1jt`, `Masa PPN Rp500rb`, serta SKPKB bunga & kenaikan `75%`.

---

## 4. Ringkasan Capaian Kuantitatif (Fase 1–8)

| Dimensi | Metrik Terverifikasi | Sumber Bukti |
|---|---|---|
| **Korpus Regulasi & Yurisprudensi** | `165` pusat (`97` aktif), `32` konsolidasi, `524` Perda, `284` SetPP, `15` MK, `78` SEMA (`14` pajak) | `knowledge_json/`, `manifest.json` |
| **Penutupan Gap (`G3`)** | `389` regulasi dikutip selesai (`0` `UNRESOLVED`) | `metadata/gaps.json`, `unresolved_citations.json` |
| **Aturan Atomik (`G4`)** | **`12.907` aturan** (`100` dokumen, `9` domain), `621` baris audit `P1`–`P6` ter-apply | `legal_rules.jsonl`, `review_apply_report.json` |
| **Ontologi `SROIQ(D)` (`G5–G6`)** | **`113` kelas**, `17` object props, `51` data props, **`73` SWRL**, `450` individu (`79` katalog + `30` profesi + `5` wilayah), `12.907` aturan RDF | `ontology/ontology_build_report.json`, `kbr-data.ttl` |
| **Evaluasi Skenario (`G7`)** | **`15 / 15` PASS** (rata-rata **`4.844,55 ms`**, maks `5.401,15 ms`) | `docs/fase7_eval_results.json` |
| **Test Suite Otomatis** | **`149 / 149` `pytest` PASS** (pipeline, konsolidasi, validator, `11` tes ontologi HermiT/SPARQL, `6` tes FastAPI `TestClient`) | `fatih/tests/` |

---

## 5. Panduan Penggunaan untuk Tim & Penguji

### 5.1 Menjalankan Backend API (`kbr_pajak/` atau `fatih/`)
```bash
cd /media/fatih/Data1/KULIAH/KULIAH/sains-data/smt5/kbr/projek_kbr/kbr_pajak
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- Swagger UI interaktif: `http://localhost:8000/docs`
- Konsumsi untuk **`yoeke-front`**: panggil `GET /options` untuk mengisi dropdown `30` pekerjaan & `5` daerah secara dinamis, panggil `POST /reason` untuk evaluasi profil WP, dan gunakan `GET /sparql/provenance` untuk membuka detail ayat/kutipan.
- Konsumsi untuk **`daRAG`**: gunakan `knowledge_json/rules/legal_rules.jsonl` (atau `GET /sparql/provenance?q=...`) sebagai sumber grounded dengan `rule_id` & `source_quote` resmi.

### 5.2 Membangun Ulang Ontologi & Menguji Sistem (`fatih/`)
```bash
cd /media/fatih/Data1/KULIAH/KULIAH/sains-data/smt5/kbr/projek_kbr/fatih
python3 scripts/fase5_ontology.py build       # rebuild TBox, Reasoning OWL, rule_map.json, & kbr-data.ttl
python3 scripts/fase7_eval.py                 # uji 15 skenario & boundary case via HermiT
pytest -q                                     # jalankan seluruh 149 automated tests
python3 scripts/sync_kbr_pajak.py             # sinkronkan artefak bersih ke repo tim kbr_pajak/
```

### 5.3 Inspeksi Visual di Protégé
- Buka `ontology/kbr_pajak_reasoning.owl` (atau `ontology/kbr_pajak_tbox.owl`) di **Protégé**.
- Pilih menu **Reasoner → HermiT** → **Start reasoner** untuk melihat hasil klasifikasi kelas dan `15` individu skenario bawaan secara visual.

---

## 6. Batasan & Catatan Penting

1. **Java JRE/JDK wajib terpasang** di mesin yang menjalankan `backend/` karena `owlready2` memanggil HermiT via JVM.
2. **`PER-DJP-2015-17` dikarantina (`ISSUES.md #A7`):** file PDF sumber BPK tidak valid (berisi Perda Kab. Pangandaran) dan sudah diblokir di `src/validate.py`.
3. **`PMK-2008-253` (PPh 22 barang sangat mewah):** naskah awal tidak tersedia di BPK; perubahan berlakunya (`PMK-2015-90` & `PMK-2019-92`) sudah masuk korpus.
4. **Status Putusan MK & SEMA TUN:** disimpan sebagai lapisan anotasi/interpretasi (`terdampakPutusanMK`, `merujukSEMA`) dalam justifikasi tanpa menimpa teks UU konsolidasi.
5. **Keamanan Git `kbr_pajak/`:** folder `sources/` berisi PDF mentah lokal (~24,6 MB) dan **tidak pernah** disinkronkan atau di-commit ke GitHub.
