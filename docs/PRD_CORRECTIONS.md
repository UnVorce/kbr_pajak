# Daftar Koreksi PRD v2.0 (untuk diedit di docx)

Disusun dari perbandingan PRD v2.0 dengan artefak riil `kbr_pajak/` dan kontrak API v2.0.0.
**Kontrak API (`docs/API_CONTRACT_v2.md`) adalah sumber kebenaran untuk frontend; PRD adalah narasi produk.**

| # | Lokasi PRD | Tertulis di PRD | Fakta riil | Tindakan |
|---|---|---|---|---|
| 1 | §1, §4 (tabel metrik) | 120 kelas, 17 object props, 62 data props, 368 individu, 79 SWRL | **157 kelas, 18 object props, 70 data props, 446 individu, 97 SWRL** | Perbarui tabel; rujuk `ontology_build_report.json` |
| 2 | §4.1 judul | "156 Kelas (120 TBox & 36 inferensi)" | 157 kelas; tidak ada pemisahan TBox/inferensi seperti itu | Tulis "157 kelas" |
| 3 | §4.5 narasi | "28 aturan SWRL" (di §4.6 juga) | **97 aturan SWRL** (klaster awal 28) | Ganti menjadi 97; sebut 28 sebagai klaster inti |
| 4 | §9 tabel | "SWRLTab / Pellet / Owlready2" | **HermiT** (Pellet gagal di OpenJDK 21: `UnsupportedClassVersionError`) | Ganti Pellet → HermiT |
| 5 | §9 tabel | "Apache Jena Fuseki (TDB2)" | **rdflib in-memory** (TTL 9,9 MB) | Ganti/tandai "rdflib; Fuseki opsional" |
| 6 | §9.2 | Vite + React + Tailwind | konsisten | tidak perlu diubah |
| 7 | §12 | "frontend Next.js/HTML" | **Vite + React** | Perbaiki |
| 8 | §3 tabel | "524 Pemda" | **524 dokumen Perda**, **390 Pemda unik** | Ganti menjadi "390 Pemda (dari 524 Perda)" |
| 9 | §5 TASK-1 | "basis data 524 Pemda" | 390 Pemda; 2.107 item tarif; 360/390 punya tarif | Perbaiki angka |
| 10 | §9.3.6 | "katalog 1.790 KBLI" | **1.453 KBLI** | Perbaiki |
| 11 | §10 / §11 | "149 skenario pengujian" | **164 tes** (setelah API v2) | Perbaiki |
| 12 | §9.3.5 contoh | Bandung `IBU_KOTA_PROVINSI_LAINNYA` | Bandung = **`10_IbuKota_Provinsi`** (10 ibu kota provinsi, PER-17/PJ/2015) | Perbaiki enum contoh |
| 13 | §9.3.5 contoh | TER K/1 = **Kategori A, 1,5%**, potongan 127.500 | K/1 = **Kategori B, 1,0%**, potongan **85.000** (PP 58/2023) | Perbaiki contoh |
| 14 | §9.3.5 contoh | PBB Bandung **0,15%**, NJOPTKP **25 jt** | Tarif umum tidak terekstrak (hanya tarif khusus 0,05% lahan pangan); NJOPTKP null | Hapus angka; gunakan `null` + catatan |
| 15 | §9.3.5 contoh | KBLI 62019 punya NPPN 50% | Lampiran NPPN hanya memuat **62010**; 62019 dipetakan eksplisit ke kelompok 62010 | Tambahkan catatan pemetaan; angka 50% tetap sah |
| 16 | §9.2 | HermiT "0,8–1,5 detik" | **rata-rata 5,5 detik, maks 6,1 detik** (cache-hit < 50 ms) | Perbaiki angka; atau nyatakan target p95 terpisah |
| 17 | §10 quality gate | "p95 latency < 3,0 detik" | belum tercapai tanpa cache; usulan gate: **cache-miss < 7 s, cache-hit < 1 s** | Sesuaikan gate |
| 18 | §9.3.4 response | `elapsed_ms` contoh 138,4 | riil ±5.500 | Perbaiki contoh |
| 19 | §9.3.3/§9.3.4 | hanya 1770/1771 | 1770 S/1770 SS **belum ada dasar hukum di korpus** | Nyatakan "menyusul"; API mengembalikan `PERLU_VERIFIKASI` |
| 20 | §9.3.2 | `/api/options` = jenis badan, status kawin, PTKP, pekerjaan | sudah diperluas sesuai itu | tidak perlu diubah |
| 21 | §8 CBR | field `jenis_koreksi`, `fakta_kunci`, `rasio_decidendi`, `argumen_menang`, `bukti_penentu` | **0 dari 284** putusan memiliki field tersebut; yang ada: `klaster`, `pokok_sengketa` (284), `pertimbangan_majelis` (278), `cited_regulations`, `amar_kategori` | Nyatakan CBR tahap 1 memakai field tersedia; anotasi 60 kasus = prasyarat formula penuh |
| 22 | §8 amar | `KABUL_SELURUHNYA / KABUL_SEBAGIAN / TOLAK / TIDAK_DAPAT_DITERIMA` | distribusi riil: KABUL_SELURUHNYA 158, TOLAK 75, KABUL_SEBAGIAN 41, LAINNYA 9, **BATAL 1** | Tambahkan `LAINNYA` & `BATAL` ke enum |
| 23 | §11 roadmap | "Fase 3 CBR SELESAI 100%" | CBR **tahap 1** sudah ada (`/api/cbr/search`, 284 kasus, BM25+klaster+regulasi); formula penuh belum | Koreksi status → "tahap 1 selesai; formula penuh butuh anotasi 60 kasus" |
| 24 | §7 RP-04 | PP 20/2026 sebagai dasar | **14 aturan** sudah terekstrak & diaudit (X-1) | Selesai — gunakan `rule_id` PP-2026-20 |
| 25 | §1 | "0% logika pajak di-hardcode" vs §6 "Kalkulator Python Decimal" | implementasi: tarif dari ontologi + aritmetika `SPARQL BIND`/helper | Satukan istilah: "tarif tidak hardcode; aritmetika deterministik" |
| 26 | §4.1 pohon kelas | `pjk:Firma` | tidak ada kelas `Firma` di ontologi | Hapus atau tambahkan kelas (butuh rebuild) |
| 27 | §4.1 pohon kelas | `FasilitasPerpajakan` & `KewajibanPajak` di bawah `AturanHukum` | keduanya `owl:Thing` (katalog), bukan subclass `AturanHukum` | Perbaiki pohon |
| 28 | §9.3.2 | base `http://127.0.0.1:8000/api` | sesuai; ditambah alias `/api/v1` | tambahkan alias |
| 29 | §9.3.3 | field `kelompok_wilayah_nppn` wajib | opsional (diturunkan dari `pemda_id`) | Longgarkan |
| 30 | §9.3.4 | `klaster_subjek` string | objek `{kode, label}` | Perbaiki tipe |
| 31 | §9.3.4 `playbook_coretax` | KAP/KJS lengkap untuk semua jenis pajak | Buku Manual Coretax 2024 hanya memuat **54 KAP/KJS**; PPh 21/23 tidak tercantum | Nyatakan cakupan; API menandai `null` + catatan |

## Angka acuan (satu sumber: `ontology/ontology_build_report.json`)

- Kelas **157** · Object props **18** · Data props **70** · Individu **446** · SWRL **97** · Katalog **103** · Aturan **12.921**
- TER **127** bracket · KBLI **1.453** · Pemda **390** · Perda **524** · Item tarif **2.107** · Putusan **284** · MK **15** · SEMA **78** (14 pajak)
- Tes: **165** (`12` ontologi + `13` API + `4` TER/KBLI + `2` Perda + `132` pipeline/korpus + sisa)
