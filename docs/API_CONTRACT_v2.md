# Kontrak API v2.0.0 — PRD §9.3 (menggantikan v1)

**Status:** DIBEKUKAN untuk integrasi `yoeke-front`.
**Base path:** `/api` (alias `/api/v1`) · **OpenAPI:** `/api/openapi.json` · **Swagger:** `/api/docs`

> Root lama (`/health`, `/reason`, …) **dihapus**. Semua route wajib memakai prefix `/api`.
> Aturan perubahan: dalam `v2.x` hanya penambahan. Rename/hapus field → `v3`.

---

## 1. Endpoint

| Method | Path | Latensi | Keterangan |
|---|---|---|---|
| `GET` | `/api/health` | < 20 ms | status artefak, `ptkp_tiers`, `regions`, cache |
| `GET` | `/api/options` | **< 500 ms** (ter-cache) | `wp_kinds`, `status_perkawinan`, `ptkp`, `zona_nppn`, `pekerjaan_jenis`, `jobs`, `final_income_objects` |
| `GET` | `/api/regions` | < 100 ms (ter-cache) | **390 Pemda** + zona NPPN + PBB-P2 + NJOPTKP + `jumlah_perda` |
| `GET` | `/api/kbli?q=&limit=` | < 50 ms | autocomplete 1.453 KBLI |
| `GET` | `/api/kbli/{kode}` | < 50 ms | detail NPPN 3 zona, Tax Allowance, Pionir, Padat Karya, `is_jasa_konstruksi` |
| `GET` | `/api/perda?q=&tingkat=&limit=` | < 30 ms | cari Pemda (390) |
| `GET` | `/api/perda/{pemda_id}` | < 30 ms | 2.107 item tarif + kutipan pasal |
| `POST` | `/api/reason` | **± 5,5 s (maks 6,1 s)**, cache-hit < 50 ms | inferensi + estimasi + provenance |
| `GET` | `/api/catalog` | < 20 ms | 103 katalog → `rule_id` |
| `GET` | `/api/scenarios` | < 20 ms | 15 skenario bawaan |
| `GET` | `/api/sparql/provenance` | 100–400 ms | 12.907 aturan |
| `GET` | `/api/sparql/stats` | 100–400 ms | agregasi per domain/kelas |

**Catatan wilayah:** `524` = jumlah **dokumen Perda**; `390` = jumlah **Pemda unik**. `/api/regions` mengembalikan 390 baris, masing-masing dengan `jumlah_perda`.

---

## 2. Request `POST /api/reason`

Field berada **di root** (bukan di dalam `properties`). **Field asing → `422`** (`extra="forbid"`).

```jsonc
{
  "wp_id": "WP-OP-BDG-2025-001",
  "wp_kind": "OrangPribadi",                 // OrangPribadi|PT|CV|Koperasi|Yayasan|BadanUsahaTetap|Badan
  "tahun_pajak": 2026,                      // default 2026; dipakai menghitung tenggat
  "pemda_id": "KOTA_BANDUNG",
  "kelompok_wilayah_nppn": "IBU_KOTA_PROVINSI_LAINNYA", // opsional; jika kosong diambil dari pemda_id
  "kode_kbli": "62019",                     // KBLI utama (wajib untuk Badan)

  "pekerjaan_utama": {
    "nama": "Guru Swasta SMA",
    "jenis": "PEGAWAI_TETAP",               // PEGAWAI_TETAP|PEGAWAI_TIDAK_TETAP|PESERTA_KEGIATAN|PEKERJA_BEBAS|USAHA_UMKM
    "kbli": "85121",
    "gaji_bulanan": 8500000,
    "omzet_tahunan": 102000000,
    "hpp_tahunan": 0,
    "biaya_operasional_tahunan": 0
  },
  "pekerjaan_sekunder": {
    "nama": "Freelance Web Developer",
    "jenis": "PEKERJA_BEBAS",
    "kbli": "62019",
    "omzet_tahunan": 180000000,
    "hpp_tahunan": 25000000,
    "biaya_operasional_tahunan": 15000000
  },

  "is_kawin": true,
  "has_jumlah_tanggungan": 1,
  "status_ptkp": "K/1",                     // opsional; dihitung dari kawin+tanggungan bila kosong
  "is_pemberitahuan_nppn_tepat_waktu": true,
  "is_penduduk_indonesia": true,
  "is_subjek_luar_negeri": false,

  "is_memiliki_objek_pbb": true,
  "has_nilai_njop": 450000000,
  "has_njoptkp_pbb": null,
  "has_persentase_njop_pbb": null,

  "is_perseroan_terbuka": false,
  "has_persentase_saham_publik": 0,
  "has_jumlah_pemegang_saham_publik": null,
  "has_hari_terpenuhi_tbk": null,
  "is_industri_pionir": false,
  "is_penanaman_modal_baru": false,
  "has_surat_keterangan_fiskal": false,
  "is_belum_pernah_putus_tax_holiday": false,
  "has_nilai_investasi": 0,
  "is_bidang_usaha_tax_allowance": false,
  "is_lokasi_provinsi_memenuhi_tax_allowance": false,
  "is_industri_padat_karya": false,

  "has_omzet_tahunan": null,
  "has_penghasilan_kena_pajak_tahunan": null,
  "has_penghasilan_bruto_bulanan": null,
  "is_umkm_pp55": false,
  "tahun_mulai_pp55": null,                 // untuk uji masa berlaku 7/4/3 Tahun Pajak
  "is_milik_pribadi": false,
  "has_jumlah_kendaraan": 0,
  "has_kapasitas_mesin_cc": null,
  "is_domisili_dki": false,
  "is_usaha_spa_kesehatan_tradisional": false,
  "is_usaha_hiburan_spa_umum": false,
  "is_penerima_penghasilan_pph23_jasa_sewa": false,
  "is_penerima_penghasilan_pph23_modal": false,
  "is_bank_penerima_penghasilan": false,

  "has_dpp_ppn": null,
  "is_penyerahan_bkp_mewah": false,
  "is_penyerahan_non_mewah_ppn": false,
  "is_penyerahan_bkp_strategis": false,

  "kredit_pajak_1721a1": 1530000,
  "jumlah_bukti_potong": 1,

  "is_terlambat_lapor_spt": false,
  "is_terlambat_lapor_spt_masa_ppn": false,
  "is_kurang_bayar_skpkb": false,
  "is_tidak_setor_pajak_dipungut": false,
  "is_keberatan_ditolak": false,
  "is_banding_ditolak": false,
  "is_dikecualikan_denda_spt": false,

  "penghasilan_final": {                    // ekstensi v2 (PPh Final Pasal 4(2))
    "sewa_tanah_bangunan": 0,
    "bunga_deposito": 0,
    "pokok_deposito": 0,
    "jasa_konstruksi": { "jenis": "NON_KECIL_SBU", "nilai_bruto": 0 },
    "pengalihan_tanah_bangunan": { "jenis": "UMUM", "nilai": 0 },
    "is_jasa_akomodasi_penginapan": false,
    "is_penghasilan_dibawah_ptkp": false
  },

  "persentase_nppn": null                   // override manual bila KBLI tidak punya baris NPPN
}
```

**Enum penting**
- `jenis` konstruksi: `KECIL_SBU`, `NON_KECIL_SBU`, `TERINTEGRASI_SBU`, `TANPA_SBU`, `TERINTEGRASI_TANPA_SBU`, `KONSULTANSI_SBU`, `KONSULTANSI_TANPA_SBU`
- `jenis` pengalihan: `UMUM`, `RUMAH_SEDERHANA`, `PEMERINTAH`
- `kelompok_wilayah_nppn`: `10_IBU_KOTA_PROVINSI`, `IBU_KOTA_PROVINSI_LAINNYA`, `DAERAH_LAINNYA`
- `status_ptkp`: `TK/0`…`TK/3`, `K/0`…`K/3`

---

## 3. Response

```jsonc
{
  "wp_id": "...", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
  "klaster_subjek": { "kode": "WPOP_MULTI_STREAM", "label": "WPOP Multi-Stream Income (...)" },
  "inferred_classes": ["OP_TER_Kategori_B", "OP_PekerjaBebas", "..."],
  "direct_classes": ["OrangPribadi"],
  "tarif": [{ "id": "...", "label_resmi": "...", "tarif_persen": 10.0, "tipe": "FINAL|PROGRESIF|UMUM",
              "dasar_hukum": { /* justifikasi[0] */ }, "justifikasi": [ ... ] }],
  "fasilitas": [ ... ],
  "kewajiban": [{ "id": "...", "nama_kewajiban": "...", "tenggat_waktu": "31 Maret 2027|null",
                  "dasar_tenggat": "3 bulan setelah akhir Tahun Pajak|null",
                  "formulir_spt": "1770|1771|null", "status_formulir": "TERVERIFIKASI|PERLU_VERIFIKASI|null",
                  "catatan_formulir": "...|null", "dasar_hukum": {...}, "justifikasi": [ ... ] }],
  "sanksi": [{ "id": "...", "nama_sanksi": "...", "tingkat_risiko": "TINGGI|SEDANG|RENDAH",
               "nominal_estimasi_idr": 1000000, "langkah_mitigasi": "...", "dasar_hukum": {...} }],
  "perda_info": { "pemda_id": "KOTA_BANDUNG", "nama_daerah": "Kota Bandung",
                  "zona_nppn": "10_IbuKota_Provinsi", "tarif_pbb_persen": null,
                  "njoptkp": null, "jumlah_perda": 5,
                  "catatan_pbb": "Tarif umum PBB-P2 tidak terekstrak; hanya tarif khusus ..." },
  "pekerjaan_info": { "multi_stream": true, "utama": {...}, "sekunder": {...},
                      "neto_utama_idr": 96900000, "neto_utama_mode_prd_idr": 102000000, "catatan": "..." },
  "estimasi_pajak": {
    "ter_bulanan": { "kategori": "B", "gaji_bruto": 8500000, "tarif_ter_persen": 1.0,
                     "potongan_per_bulan": 85000, "total_potongan_setahun": 1020000, "bracket_order": 5 },
    "komparasi_skema": {
      "objek_komparasi": "penghasilan_sekunder", "omzet_sekunder": 180000000,
      "skema_pp55_final": { "status": "DISKUALIFIKASI", "alasan": "...", "pph_idr": null },
      "skema_pembukuan": { "penghasilan_neto": 140000000, "estimasi_pph_idr": 15000000 },
      "skema_norma_nppn": { "persentase_norma": 50.0, "sumber_norma": "kelompok 62010 (dipetakan dari KBLI 62019)",
                            "penghasilan_neto": 90000000, "estimasi_pph_idr": 7500000 },
      "rekomendasi_skema": { "skema_terpilih": "skema_norma_nppn",
                             "penghematan_pph_idr": 7500000,
                             "penghematan_dasar_kena_pajak": 50000000, "alasan": "..." }
    },
    "rekonsiliasi_spt_tahunan": { "mode": "perhitungan_benar", "penghasilan_neto_utama": 96900000,
      "penghasilan_neto_sekunder": 90000000, "total_penghasilan_neto_gabungan": 186900000,
      "ptkp_status": "K/1", "ptkp_idr": 63000000, "penghasilan_kena_pajak_pkp": 123900000,
      "pph_terutang_pasal_17_idr": 12585000, "lapisan_pasal_17": [...],
      "kredit_pajak_1721a1_idr": 1530000, "pph_pasal_29_kurang_bayar_idr": 11055000, "pph_lebih_bayar_idr": 0 },
    "rekonsiliasi_mode_prd": { "mode": "mode_prd", "...": "gaji bruto tanpa biaya jabatan; mereproduksi PRD §9.3.5" },
    "pbb_p2_terutang_idr": null, "pbb_status": "TARIF_UMUM_TIDAK_TEREKSTRAK|null",
    "pph_final_pasal4_2": { "pph_final_sewa_tanah_bangunan_idr": 0, "total_pph_final_pasal4_2_idr": 0 },
    "rincian": { /* seluruh kunci SPARQL BIND, kompatibilitas internal */ },
    "catatan": "Estimasi indikatif, bukan pengganti perhitungan SPT resmi."
  },
  "cbr_matches": [], "playbook_coretax": [],
  "provenance": [{ "kategori": "tarif", "katalog_id": "...", "rule_id": "...", "source_locator": "...",
                   "source_quote": "...", "validation_status": "...", "regulasi": [...], "mk_refs": [], "sema_refs": [] }],
  "reasoner": "HermiT (...) + SPARQL BIND/SKOS/TER/PERDA",
  "elapsed_ms": 5496.69, "cache_hit": false
}
```

### 3.1 Dua mode rekonsiliasi (keputusan B1-1)
- `rekonsiliasi_spt_tahunan` = **perhitungan benar**: gaji bruto − biaya jabatan 5% (maks Rp6 jt/tahun).
- `rekonsiliasi_mode_prd` = **reproduksi contoh PRD §9.3.5**: gaji bruto dianggap neto (tanpa biaya jabatan). Angka PRD (192 jt / PKP 129 jt / PPh 13,35 jt / PPh 29 11,82 jt) cocok di mode ini.
- UI wajib memberi label mode yang ditampilkan; jangan mencampur keduanya.

### 3.2 Catatan formulir SPT (keputusan B2-2 = opsi b)
- `1770` (OP dengan usaha/pekerjaan bebas/penghasilan final) dan `1771` (Badan) → `status_formulir: "TERVERIFIKASI"`.
- OP **karyawan murni** → `formulir_spt: null`, `status_formulir: "PERLU_VERIFIKASI"`, dengan `catatan_formulir`. Kriteria 1770 S / 1770 SS **belum ada di korpus**, jadi tidak dikarang. Menyusul setelah akuisisi dokumen bentuk SPT Tahunan.

### 3.3 PBB-P2: perubahan penting (B2-4)
- Ekstraktor sekarang memisahkan `PBB_P2` (tarif umum) dari `PBB_P2_Khusus` (lahan produksi pangan/ternak).
- Bila tarif umum tidak terekstrak (contoh: **Kota Bandung** hanya punya 0,05% khusus) → `tarif_pbb_persen: null` + `catatan_pbb`, **tidak** memakai angka khusus sebagai tarif umum.
- NJOPTKP yang tidak terekstrak → `null`. Bila engine masih menghitung PBB dengan default Rp10 jt, hasilnya diberi `pbb_njoptkp_sumber: "default_10jt"` dan `pbb_status: "INDIKATIF"`.
- **Konsekuensi:** contoh PRD "Bandung PBB 0,15%" tidak dapat direproduksi — angka itu tidak ditemukan di Perda Kota Bandung 2024-1. Gunakan `null` sampai ekstraksi diperbaiki.

---

## 4. Kasus emas (kontrak, diuji `scripts/smoke_test.py`)

### A. OP UMKM kuliner
`pekerjaan_utama {jenis: USAHA_UMKM, omzet_tahunan: 1.200.000.000}`, `is_umkm_pp55: true`, `has_penghasilan_kena_pajak_tahunan: 300.000.000`
→ `porsi_omzet_bebas_500jt_idr = 500.000.000` · `pph_final_umkm_op_idr = 3.500.000` · `pph_op_pasal17_idr = 44.000.000`

### B. PRD §9.3.5 — Guru + Freelance Bandung
Payload persis pada §2 di atas (KBLI 85121 & 62019, K/1, kredit 1.530.000).
→ `klaster_subjek.kode = WPOP_MULTI_STREAM` · TER **B** 1,0% = **85.000/bulan**
→ NPPN 50% → neto **90.000.000**; rekomendasi NPPN; penghematan dasar **50.000.000**
→ mode PRD: neto 192.000.000 · PKP 129.000.000 · PPh 17 **13.350.000** · PPh 29 **11.820.000**
→ mode benar: neto 186.900.000 · PKP 123.900.000 · PPh 17 **12.585.000**
→ formulir **1770** · tenggat **31 Maret 2027** · `pbb_status: TARIF_UMUM_TIDAK_TEREKSTRAK`

### C. CV Pasal 31E + PPN + denda
`has_omzet_tahunan 10 M`, `has_penghasilan_kena_pajak_tahunan 1 M`, `has_dpp_ppn 2 M`, `is_penyerahan_non_mewah_ppn true`, `is_terlambat_lapor_spt true`
→ `pph_badan_idr 167.200.000` · `penghematan_pasal_31e_idr 52.800.000` · `ppn_terutang_idr 220.000.000` · `denda_administratif_tetap_idr 1.000.000`

### D. PT Tbk 19%
`is_perseroan_terbuka true`, publik 45%, 350 pihak, 183+ hari, PKP 100 M
→ `pph_badan_idr 19.000.000.000` · tarif memuat `Tarif_PPhBadan_Tbk_19Pct`

### E. PT konstruksi + pengalihan rumah sederhana
`kode_kbli 41011`, `penghasilan_final.jasa_konstruksi {NON_KECIL_SBU, 1 M}`, `pengalihan_tanah_bangunan {RUMAH_SEDERHANA, 500 jt}`
→ `26.500.000` + `5.000.000` = **31.500.000**

### F. Pengecualian PPh Final
akomodasi penginapan, pokok deposito ≤ Rp7,5 jt, OP di bawah PTKP, pengalihan < Rp60 jt
→ seluruh `pph_final_*` dan `total_pph_final_pasal4_2_idr` = **0**

### G. Karyawan murni
`pekerjaan_utama {PEGAWAI_TETAP, gaji 10 jt}`
→ TER **A** 2% = **200.000/bulan** · `formulir_spt: null` · `status_formulir: PERLU_VERIFIKASI`

---

## 5. Error

| HTTP | Kapan |
|---|---|
| `400` | Body bukan JSON valid |
| `422` | Field asing, tipe/enum salah, `wp_id` ilegal, angka di luar batas, **KBLI/Pemda tidak ditemukan** |
| `404` | `GET /api/kbli/{kode}` atau `/api/perda/{id}` tidak ada |
| `503` | Artefak `.owl`/`.ttl` tidak ada di server |
| `500` | Kontradiksi ontologi / kegagalan reasoner |

---

## 6. Deviasi PRD yang disengaja (agar FE tidak salah asumsi)

| PRD | Kontrak v2 | Alasan |
|---|---|---|
| `/api/...` saja | `/api` + alias `/api/v1` | versioning |
| `524 Pemda` | **390 Pemda**, `jumlah_perda` 1–n | 524 = dokumen Perda, bukan Pemda |
| Bandung `IBU_KOTA_PROVINSI_LAINNYA` | **`10_IbuKota_Provinsi`** | Bandung termasuk 10 ibu kota provinsi (PER-17/PJ/2015) |
| TER K/1 = Kategori A, 1,5% | **Kategori B, 1,0%** | PP 58/2023: K/1 masuk Kategori B |
| Bandung PBB 0,15%, NJOPTKP 25 jt | **null** + catatan | tidak ditemukan di Perda Kota Bandung 2024-1 |
| `elapsed_ms ≈ 138` | **± 5.500 (maks 6.100)**; cache-hit < 50 | HermiT nyata; PRD optimistis |
| 1770 S / 1770 SS | `null` + `PERLU_VERIFIKASI` | belum ada dasar hukum bentuk SPT di korpus |
| Statistik 120 kelas / 79 SWRL / 149 tes | **157 / 97 / 446 individu / 164 tes** | angka riil `ontology_build_report.json` |

---

## 7. Serah terima ke FE

- [ ] Generate klien TS dari `/api/openapi.json`
- [ ] Cache `/api/options`, `/api/regions`, daftar `/api/kbli`: TTL 1 jam
- [ ] `POST /api/reason` hanya saat submit; loading 6–8 s; tanpa auto-retry
- [ ] Tampilkan `rekonsiliasi_spt_tahunan` **atau** `rekonsiliasi_mode_prd` dengan label jelas
- [ ] Jangan hardcode tarif; semua dari `rincian`/`komparasi_skema`
- [ ] Tampilkan `pbb_status`/`catatan_pbb` bila `pbb_p2_terutang_idr` null
- [ ] Formulir `null` → tampilkan "perlu verifikasi", bukan menebak 1770 S/SS
- [ ] Tampilkan badge sumber pada `provenance[]` (`rule_id`, `source_locator`, `mk_refs`, `sema_refs`)
