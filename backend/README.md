# Backend KBR Pajak — API v2.0.0 (`/api`)

Service API reasoning OWL 2 `SROIQ(D)` + SWRL (**HermiT**) dan SPARQL (`rdflib`) atas
`12.907` aturan hukum perpajakan, dengan kontrak sesuai **PRD §9.3**.

> **Kontrak resmi:** [`docs/API_CONTRACT_v2.md`](../docs/API_CONTRACT_v2.md) · **Swagger:** `/api/docs` · **OpenAPI:** `/api/openapi.json`

## Prasyarat
- Python 3.10+ (teruji 3.13)
- **Java JRE/JDK** (HermiT) — teruji OpenJDK 21
- `pip install -r backend/requirements.txt`

## Menjalankan

```bash
# dari root repo (yang memuat backend/, ontology/, knowledge_json/)
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Docker
cp .env.example .env && docker compose up -d --build
```

Base path **`/api`** (alias `/api/v1`). Route root lama **dihapus**.

## Endpoint

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/health` | status artefak, `ptkp_tiers`, `regions`, cache |
| `GET` | `/api/options` | `wp_kinds`, `ptkp`, `zona_nppn`, `pekerjaan_jenis`, `jobs` (32), `final_income_objects` (13) |
| `GET` | `/api/regions` | **390 Pemda** (dari 524 Perda): zona NPPN, PBB-P2, NJOPTKP, `jumlah_perda` |
| `GET` | `/api/kbli` & `/api/kbli/{kode}` | 1.453 KBLI SKOS (NPPN/Tax Allowance/Pionir/Padat Karya) |
| `GET` | `/api/perda` & `/api/perda/{id}` | tarif pajak daerah + kutipan pasal |
| `POST` | `/api/reason` | inferensi + TER + komparasi 3 skema + rekonsiliasi PPh 29 + PPh Final 4(2) + provenance |
| `GET` | `/api/catalog` | 103 katalog → `rule_id` |
| `GET` | `/api/scenarios` | 15 skenario bawaan |
| `GET` | `/api/sparql/provenance` & `/api/sparql/stats` | 12.907 aturan |

## Contoh `POST /api/reason` (PRD §9.3.5)

```bash
curl -X POST http://localhost:8000/api/reason \
  -H "Content-Type: application/json" \
  -d '{
    "wp_id": "WP-OP-BDG-2025-001",
    "wp_kind": "OrangPribadi",
    "tahun_pajak": 2026,
    "pemda_id": "KOTA_BANDUNG",
    "pekerjaan_utama": {
      "nama": "Guru Swasta SMA", "jenis": "PEGAWAI_TETAP", "kbli": "85121",
      "gaji_bulanan": 8500000
    },
    "pekerjaan_sekunder": {
      "nama": "Freelance Web Developer", "jenis": "PEKERJA_BEBAS", "kbli": "62019",
      "omzet_tahunan": 180000000, "hpp_tahunan": 25000000, "biaya_operasional_tahunan": 15000000
    },
    "is_kawin": true, "has_jumlah_tanggungan": 1,
    "kredit_pajak_1721a1": 1530000
  }'
```

Hasil penting:
- TER **Kategori B** 1,0% → Rp85.000/bulan
- NPPN 50% → neto Rp90 jt; rekomendasi **NPPN**; penghematan dasar Rp50 jt
- `rekonsiliasi_mode_prd` → PKP 129 jt, PPh 17 Rp13,35 jt, PPh 29 Rp11,82 jt
- `rekonsiliasi_spt_tahunan` (benar) → PKP 123,9 jt, PPh 17 Rp12,585 jt

## Prinsip
- **0% tarif di-hardcode**: tarif dibaca dari ontologi (`hasTarifPersen`).
- **Field asing → 422** (tidak diabaikan diam-diam).
- **Cache** per hash profil: request identik < 50 ms (`cache_hit: true`).
- **Provenance** setiap item: `rule_id`, `source_locator`, `source_quote`, `mk_refs`, `sema_refs`.

## Verifikasi

```bash
python3 scripts/smoke_test.py --in-process   # 64 cek kontrak
pytest tests/test_api.py -q                  # 13 tes integrasi
```
