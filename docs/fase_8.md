# Laporan Akhir Fase 8 — Dokumentasi Menyeluruh Sistem KBR Perpajakan Indonesia (Fase 0–8)

> **Status:** **SELESAI — Gerbang G8 (Serah Terima Final)**
> **Seluruh Fase (0–8) selesai:** Akuisisi korpus resmi, konsolidasi-lite 32 rantai amandemen, ekstraksi 12.907 aturan atomik, ontologi OWL 2 `SROIQ(D)` + 28 SWRL (HermiT), ekspor RDF/SPARQL penuh, dan service API FastAPI (`backend/`), dengan **`146/146` tes otomatis lulus**.

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
  59 Kelas OWL 2 SROIQ(D) · 28 Aturan SWRL        Ekspor RDF penuh 12.907 aturan
  322 Individu (31 Katalog + MK + SEMA + Uji)     beserta quote & rujukan MK/SEMA
        │                                              │
        ▼ (HermiT Reasoner, World() terisolasi)        ▼ (rdflib SPARQL engine)
[FASTAPI BACKEND: backend/main.py] ◄───────────────────┘
  POST /reason · GET /sparql/provenance · GET /sparql/stats · GET /catalog · GET /health
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
1. **Lapisan Reasoning (`ontology/kbr_pajak_reasoning.owl`, `329 KB`):**
   - Berisi TBox lengkap **`59` kelas `SROIQ(D)`**, **`14` Object Properties** (3 pasang *inverse*), **`30` Data Properties**, **`28` aturan SWRL DL-safe**, dan **`322` individu** (`31` item katalog tarif/fasilitas/kewajiban/sanksi yang masing-masing tertaut ke `AturanHukum -> Pasal -> Regulasi` + `15` `PutusanMK` + `14` `SEMA_TUN` + `120` aturan terkurasi + `8` skenario).
   - **Seluruh ambang numerik** (`> Rp4,8M`, `≤ Rp4,8M`, `≥ 40%`, 6 interval Tax Holiday, jumlah kendaraan `1..5+`) dimodelkan dengan **`OWL 2 ConstrainedDatatype`** (bagian `(D)` dari `SROIQ(D)`), bukan di Python dan bukan lewat `swrlb:*`.
   - **HermiT** mengeksekusi klasifikasi `SROIQ(D)` + 28 aturan SWRL secara utuh dalam **`~2,3 detik` per *request*** di `owlready2.World()` terisolasi.
2. **Lapisan Graf Penuh (`kbr-data.ttl`, `9,9 MB`):**
   - Menyimpan seluruh **`12.907` aturan atomik** dalam format Turtle RDF untuk query **SPARQL lokal (`rdflib`)** dalam hitungan milidetik setelah dimuat ke memori.

### 3.3 Alur Eksekusi `POST /reason` (0% Hardcode Pajak di Python)
1. **Validasi input (Pydantic):** `ReasonRequest` memastikan `wp_id` valid, `wp_kind` anggota enum kelas (`PT`, `CV`, `Koperasi`, `Yayasan`, `BadanUsahaTetap`, `Badan`, `OrangPribadi`), nilai rupiah `≥ 0`, dan persentase saham `0..100`.
2. **Instansiasi di `World()` terisolasi:** `KBRReasoningEngine.reason()` memuat `kbr_pajak_reasoning.owl` ke `World()` baru sehingga profil wajib pajak satu pengguna **tidak pernah bocor** ke pengguna lain.
3. **Klasifikasi & Inferensi HermiT:**
   - Misal input: `CV`, `hasOmzetTahunan = 4_800_000_001`, `isUMKM_PP55 = True`.
   - HermiT mengevaluasi `hasOmzetTahunan > 4.8e9` (`min_exclusive=4800000000.0`) → mengklasifikasikan individu ke `PengusahaKenaPajak` (dan otomatis `WajibPajakNonUMKM`, bukan `WajibPajakUMKM`).
   - Aturan SWRL `SWRL_TK_A2_2_UMKM_Lewat_4_8M` & `SWRL_TK_B1_PKP_PPN` & `SWRL_TK_A2_2_Badan_Umum` menembak relasi `memilikiKewajiban` & `dikenaiTarif`.
4. **Penelusuran Provenance (`TK-E1`):** API mengikuti relasi `didasarkanPadaAturan -> diaturDalam / diaturDalamPasal / terdampakPutusanMK / merujukSEMA` untuk mengembalikan teks pasal, kutipan sumber persis, dan peringatan yurisprudensi terkait.

---

## 4. Ringkasan Capaian Kuantitatif (Fase 1–8)

| Dimensi | Metrik Terverifikasi | Sumber Bukti |
|---|---|---|
| **Korpus Regulasi & Yurisprudensi** | `165` pusat (`97` aktif), `32` konsolidasi, `524` Perda, `284` SetPP, `15` MK, `78` SEMA (`14` pajak) | `knowledge_json/`, `manifest.json` |
| **Penutupan Gap (`G3`)** | `389` regulasi dikutip selesai (`0` `UNRESOLVED`) | `metadata/gaps.json`, `unresolved_citations.json` |
| **Aturan Atomik (`G4`)** | **`12.907` aturan** (`100` dokumen, `9` domain), `621` baris audit `P1`–`P6` ter-apply | `legal_rules.jsonl`, `review_apply_report.json` |
| **Ontologi `SROIQ(D)` (`G5–G6`)** | **`59` kelas**, `14` object props, `30` data props, **`28` SWRL**, `322` individu reasoning, `12.907` aturan RDF | `ontology/ontology_build_report.json`, `kbr-data.ttl` |
| **Evaluasi Skenario (`G7`)** | **`12 / 12` PASS** (termasuk boundary `Rp4,8M` vs `+1 Rp`, Tbk `30%` vs `45%`, Tax Holiday, MK Spa, SEMA Banding), rata-rata **`2.347,7 ms`** | `docs/fase7_eval_results.json` |
| **Test Suite Otomatis** | **`146 / 146` `pytest` PASS** (pipeline, konsolidasi, validator, ontologi HermiT, SPARQL, dan FastAPI `TestClient`) | `fatih/tests/` |

---

## 5. Panduan Penggunaan untuk Tim & Penguji

### 5.1 Menjalankan Backend API (`kbr_pajak/` atau `fatih/`)
```bash
# Prasyarat: Python 3.10+, Java JRE/JDK (untuk HermiT), paket di backend/requirements.txt
cd /media/fatih/Data1/KULIAH/KULIAH/sains-data/smt5/kbr/projek_kbr/kbr_pajak
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
- Swagger UI interaktif: `http://localhost:8000/docs`
- Konsumsi untuk **`yoeke-front`**: panggil `POST /reason` untuk evaluasi profil wajib pajak, gunakan `GET /catalog` untuk daftar label/tarif, dan `GET /sparql/provenance` untuk membuka detail ayat/kutipan.
- Konsumsi untuk **`daRAG`**: gunakan `knowledge_json/rules/legal_rules.jsonl` (atau `GET /sparql/provenance?q=...`) sebagai sumber grounded dengan `rule_id` & `source_quote` resmi.

### 5.2 Membangun Ulang Ontologi & Menguji Sistem (`fatih/`)
```bash
cd /media/fatih/Data1/KULIAH/KULIAH/sains-data/smt5/kbr/projek_kbr/fatih
python3 scripts/fase5_ontology.py build       # rebuild TBox, Reasoning OWL, rule_map.json, & kbr-data.ttl
python3 scripts/fase7_eval.py                 # uji 12 skenario & boundary case via HermiT
pytest -q                                     # jalankan seluruh 146 automated tests
python3 scripts/sync_kbr_pajak.py             # sinkronkan artefak bersih ke repo tim kbr_pajak/
```

### 5.3 Inspeksi Visual di Protégé
- Buka `ontology/kbr_pajak_reasoning.owl` (atau `ontology/kbr_pajak_tbox.owl`) di **Protégé**.
- Pilih menu **Reasoner → HermiT** → **Start reasoner** untuk melihat hasil klasifikasi kelas `WajibPajak`, `PengusahaKenaPajak`, `BadanTerbukaTbk`, `LayakTaxHoliday_*`, dan 8 individu skenario bawaan secara visual.

---

## 6. Batasan & Catatan Penting

1. **Java JRE/JDK wajib terpasang** di mesin yang menjalankan `backend/` karena `owlready2` memanggil HermiT via JVM.
2. **`PER-DJP-2015-17` dikarantina (`ISSUES.md #A7`):** file PDF sumber BPK tidak valid (berisi Perda Kab. Pangandaran) dan sudah diblokir di `src/validate.py`.
3. **`PMK-2008-253` (PPh 22 barang sangat mewah):** naskah awal tidak tersedia di BPK; perubahan berlakunya (`PMK-2015-90` & `PMK-2019-92`) sudah masuk korpus.
4. **Status Putusan MK & SEMA TUN:** disimpan sebagai lapisan anotasi/interpretasi (`terdampakPutusanMK`, `merujukSEMA`) yang ditampilkan dalam justifikasi, bukan menimpa teks undang-undang hasil konsolidasi.
5. **Keamanan Git `kbr_pajak/`:** folder `sources/` berisi PDF mentah lokal (~24,6 MB) dan **tidak pernah** disinkronkan atau di-commit ke GitHub.

---

## 7. Daftar Dokumen & Laporan Terkait

- `docs/DATA_DICTIONARY.md` — kamus data lengkap skema korpus, `legal_rules.jsonl`, 59 kelas & properti ontologi, serta kontrak API.
- `docs/fase_1.md`, `docs/fase_2.md`, `docs/fase_3.md`, `docs/fase_3b.md`, `docs/fase_4.md`, `docs/fase_5_6.md`, `docs/fase_7.md` — catatan progres & gerbang tiap fase.
- `docs/ISSUES.md` — catatan anomali sumber dan keputusan teknis.
- `backend/README.md` — panduan cepat menjalankan API.
