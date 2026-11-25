# Backend KBR Pajak (FastAPI + HermiT + SPARQL)

Service API reasoning berbasis ontologi OWL 2 `SROIQ(D)` + SWRL (`HermiT`) dan query SPARQL (`rdflib`) atas `12.907` aturan hukum perpajakan.

## Prasyarat
- Python 3.10+
- Java JRE/JDK (diperlukan oleh `owlready2` untuk menjalankan reasoner **HermiT**)
- Dependensi Python: `pip install -r backend/requirements.txt`

## Menjalankan Server

Dari root repo (`kbr_pajak/` atau `fatih/`):

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Dokumentasi interaktif Swagger UI tersedia di: `http://localhost:8000/docs`

## Endpoint Utama

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/health` | Status ontologi `.owl`, `.ttl` (termasuk `kbr_ter_pph21.ttl`, `kbr_kbli.ttl`, & `kbr-perda-rates.ttl`), dan statistik build |
| `GET` | `/options` | Daftar `30` pilihan `JenisPekerjaan` & `6` `WilayahDaerah` langsung dari OWL |
| `GET` | `/kbli` | Cari kode/uraian KBLI di graf SKOS `kbr_kbli.ttl` (`?q=...&limit=20`, `1.453` KBLI) |
| `GET` | `/kbli/{kode}` | Detail 1 kode KBLI (NPPN 3 wilayah, Tax Allowance PP 78/2019, Industri Pionir PerBKPM 7/2020, Padat Karya PMK 16/2020) |
| `GET` | `/perda` | Cari/daftar `390` Pemda dari `524` Perda PDRD (`?q=...&tingkat=PROV|KOTA|KAB`) |
| `GET` | `/perda/{pemda_id}` | Detail tarif pajak daerah (`2.029` item) & kutipan pasal resmi untuk 1 Pemda |
| `POST` | `/reason` | Evaluasi profil `WajibPajak` via HermiT + auto-mapping `kodeKBLI` & `pemdaId` + **`estimasi_pajak` (`SPARQL BIND`, TER PPh 21, NPPN, PBB lokal)** + justifikasi pasal/MK/SEMA |
| `GET` | `/catalog` | Peta `83` konsep tarif/fasilitas/kewajiban/sanksi (`rule_map.json`) |
| `GET` | `/scenarios` | Hasil inferensi `15` skenario demonstrasi bawaan |
| `GET` | `/sparql/provenance` | Query SPARQL provenance (`rule_id`, `document_id`, `domain`, `rule_type`, `q`) atas 12.907 aturan |
| `GET` | `/sparql/stats` | Agregasi jumlah aturan per domain & kelas dari RDF `kbr-data.ttl` |

## Contoh Request `POST /reason`

### 1. Badan Usaha (`PT` Tbk Go Public + BKP Mewah)
```bash
curl -X POST http://localhost:8000/reason \
  -H "Content-Type: application/json" \
  -d '{
    "wp_id": "PT_Contoh_Tbk",
    "wp_kind": "PT",
    "properties": {
      "hasOmzetTahunan": 120000000000,
      "isPerseroanTerbuka": true,
      "hasPersentaseSahamPublik": 45.0,
      "hasJumlahPemegangSahamPublik": 350,
      "hasHariTerpenuhiTbk": 200,
      "isPenyerahanBKP_Mewah": true,
      "isUMKM_PP55": false,
      "hasNPWP": true
    }
  }'
```

### 2. Orang Pribadi Multi-Peran (`Dokter` + `PegawaiTetap` + `Pedagang_ECommerce`)
```bash
curl -X POST http://localhost:8000/reason \
  -H "Content-Type: application/json" \
  -d '{
    "wp_id": "OP_Dr_Siti",
    "wp_kind": "OrangPribadi",
    "properties": {
      "memilikiPekerjaan": ["Dokter", "PegawaiTetap_Swasta", "Pedagang_ECommerce"],
      "berdomisiliDi": ["Wilayah_Kota_Surabaya"],
      "isSubjekLuarNegeri": false,
      "isPendudukIndonesia": true,
      "isKawin": false,
      "hasJumlahTanggungan": 0,
      "isUMKM_PP55": true,
      "hasOmzetTahunan": 350000000,
      "hasPenghasilanKenaPajakTahunan": 300000000,
      "hasNPWP": true
    }
  }'
```
