# Laporan Fase 4 — Konsolidasi Cipta Kerja, Ekstraksi Aturan (`T2_RULE`), Validasi S8 & Pre-Audit (`P1`–`P6`)

> **Status:** Fase 4A–4D selesai; pre-audit prioritas tinggi (`P1`–`P6`) selesai dan menunggu *sign-off* manusia + `apply` untuk Gerbang **G4**.

---

## 1. Persiapan & Chunking (`4A`–`4B`)

- **Korpus aktif:** `165` dokumen pusat (`97` `active_for_rules`), `32` konsolidasi terbaru (termasuk klaster pajak `UU-2023-6` Cipta Kerja setelah `UU-2021-7` HPP, `PMK-2024-118`, `PMK-2020-130`, `PERDA-KOTA-SEMARANG-2023-10`), `5` Perda PDRD pilot, `15` Putusan MK pajak, dan `78` butir SEMA Kamar TUN (`14` pajak).
- **Scope manifest (`scope_manifest.jsonl`):** `4.603` pasal dievaluasi → **`4.463` `extract_t2`**, lengkap dengan penanda `mk_review_refs` dan `sema_tun_refs`.
- **Chunking `T2_RULE` (`src/chunking.py`):**
  - Total **`5.509` chunk** (`5.465` `chunk_id` unik; estimasi **`1.982.924` token input**, rata-rata `1.079,8` karakter).
  - Normalisasi artefak OCR (`3Oo/o` → `30%`, `O,5%` → `0,5%`, `Rpl00` → `Rp100`, `lO%` → `10%`, `(l)` → `(1)`) dan pembersihan *watermark* PDF (`www.jdih.kemenkeu.go.id`, `www.djpp.depkumham.go.id`, `SK No ...`, `PRESIDEN REPUBLIK INDONESIA -N-`).
  - Deteksi tabel nyata: **`17` chunk tabel** (`context.is_table = true`).
  - *Gold standard template:* **`36` chunk** representatif lintas domain.

---

## 2. Ekstraksi Massal Google Colab Pro (`4C`)

- **Model & lingkungan:** `Qwen/Qwen2.5-32B-Instruct-AWQ` via `vLLM` (A100 80 GB, `max_model_len=8192`, `max_tokens=4096`, `VLLM_ENABLE_V1_MULTIPROCESSING=0`).
- **Sanity check iteratif (`36` gold chunk):**
  - `sanity_36_v3` → `75` lolos (`42 VALIDATED`, `33 REVIEW_REQUIRED`), `30 REJECTED`, `1 PARSE_ERROR`
  - `sanity_36_v4` → `80` lolos (`45 VALIDATED`, `35 REVIEW_REQUIRED`), `6 REJECTED`, `3 PARSE_ERROR`
  - `sanity_36_v5` → **`88` lolos (`50 VALIDATED`, `38 REVIEW_REQUIRED`, `92,6%`)**, `7 REJECTED`, `2 PARSE_ERROR`
- **Ekstraksi penuh (`t2_results_v2.jsonl`):** **`5.509 / 5.509` baris selesai (`0` chunk terlewat)**.

---

## 3. Validasi Deterministik S8 & Karantina Sumber (`4D`)

Validasi dijalankan lewat `scripts/fase4_validate.py` (`src/validate.py`, **132 unit test lulus** via `pytest -q`):

| Metrik | Jumlah | Keterangan |
|---|---:|---|
| Baris diproses | **5.509** | `100%` chunk tercakup |
| **`VALIDATED`** | **8.717** | Langsung lolos seluruh cek S8 |
| **`REVIEW_REQUIRED`** | **3.935** | Aturan tarif, sanksi, tenggat, pengecualian, tabel, MK/SEMA, OCR spasi, sampel ≥10% |
| **Total lolos (`legal_rules.jsonl`)** | **12.652** | **95,1%** dari `13.302` kandidat (`100` dokumen unik, `9` domain) |
| **`REJECTED`** | **650** | **4,9%** (mayoritas `source_quote` melompati cabang/typo; masuk `review_queue.jsonl`) |
| **`PARSE_ERROR`** | **27** | **0,49%** dari 5.509 chunk |
| **`QUARANTINED_SOURCE`** | **153 chunk** | `PER-DJP-2015-17` dikeluarkan bersih (lihat di bawah) |
| **`NOT_FOUND_IN_CHUNK`** | **944** | Pasal definisi umum / asas / delegasi ke Lampiran |
| **`DUPLICATE_SKIPPED`** | **43** | Aturan duplikat dalam chunk |

**Sebaran `12.652` aturan di `legal_rules.jsonl`:**
- **Per domain:** `D_ADMIN_SANKSI` (`3.344`), `B_PPN` (`2.092`), `PERDA_PDRD` (`1.663`), `A2_PPH_BADAN` (`1.553`), `C_PBB_HKPD` (`1.177`), `FASILITAS_SEKTOR` (`1.114`), `KEPABEANAN_CUKAI` (`969`), `PPH_OP_POTPUT` (`592`), `PPH_FINAL_SEKTOR` (`148`).
- **Per jenis (`rule_type`):** `definition` (`4.124`), `obligation` (`3.078`), `procedure` (`2.678`), `prohibition` (`802`), `rate` (`676`), `deadline` (`417`), `exception` (`296`), `sanction` (`282`), `right` (`246`), `eligibility` (`30`), `other` (`23`).

### Temuan Anomali Sumber (`ISSUES.md #A7`)
- **`PER-DJP-2015-17`** (*seharusnya PER-17/PJ/2015 tentang NPPN*) memiliki PDF sumber salah unduh dari BPK yang berisi **Perda Kabupaten Pangandaran tentang Perlindungan dan Pengelolaan Lingkungan Hidup**.
- Dokumen tersebut dikarantina di `src/validate.py` (`QUARANTINED_DOC_IDS`) sehingga **`79` aturan lingkungan hidup** yang sempat muncul berhasil dibuang bersih dari `legal_rules.jsonl`.

---

## 4. Pre-Audit Prioritas Tinggi (`P1`–`P6`, `priority_review_audited.csv`)

Sebanyak **`498` baris** prioritas tinggi diekspor dari `review_queue.jsonl` (berkembang menjadi **`532` baris** setelah pemulihan seluruh aturan dari `27` chunk `PARSE_ERROR`) dan diaudit per batch dengan **`gemini-4-hydrogen-high`** + verifikasi deterministik `validate_rule()`:

| Priority | Total | `APPROVED` | `FIXED` | `REJECTED` | Catatan Utama |
|---|---:|---:|---:|---:|---|
| **`P1_TABLE`** | 7 | 7 | 0 | 0 | Lapisan tarif PPh Pasal 17 (`UU-1983-7`, `UU-2021-7`) tepat |
| **`P2_MK`** | 44 | 24 | 20 | 0 | Penyesuaian amar `8` Putusan MK (mandi uap/spa, pembinaan Pengadilan Pajak ke MA, bukti permulaan tanpa upaya paksa, DBHCT) |
| **`P3_SEMA`** | 33 | 9 | 24 | 0 | Pemilahan gugatan vs banding (`SEMA 2/2024`), bukti susulan (`Pasal 26A`), kuasa hukum & larangan PK II (`SEMA 2/2019`) |
| **`P4_PARSE_ERROR`** | 61 | 0 | 61 | 0 | **27 / 27** chunk `PARSE_ERROR` pulih menjadi **61 aturan** (`0` error `validate_rule`) |
| **`P5_RATE_CORE`** | 257 | 77 | 156 | 24 | Perbaikan sisa OCR (`60%`→`6%`, `1,270`→`1,2%`, `2070`→`20%`), syarat NPOPTKP, penyelamatan 6 tier Tax Holiday `PMK-2020-130`, buang artefak hal. `23` |
| **`P6_REJECTED_CORE`** | 130 | 0 | 122 | 8 | `122` aturan penting dipulihkan (`0` error `validate_rule`); `8` fragmen/delegasi kosong dikonfirmasi ditolak |
| **Total** | **532** | **117** | **383** | **32** | Tersimpan di `review/priority_review_audited.csv` & `review/llm_audit_log.jsonl` |

---

## 5. Status Menuju Gerbang G4 & Fase 5

- **Status sekarang:** Draf hasil audit `P1`–`P6` (`priority_review_audited.csv`) sudah siap ditinjau akhir oleh manusia (*sign-off*) sebelum menjalankan `scripts/fase4_review.py apply` ke `legal_rules.jsonl`.
- **Siap lanjut setelah *apply*:** Fase 5 (**TBox Ontologi OWL `SROIQ(D)`** di Protégé) & Fase 6 (**ABox + SWRL + Pellet**).
