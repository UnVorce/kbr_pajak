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
| `GET` | `/health` | Status ontologi `.owl`, `.ttl`, dan statistik build |
| `POST` | `/reason` | Evaluasi profil `WajibPajak` via HermiT (`World()` terisolasi) + justifikasi pasal/MK/SEMA |
| `GET` | `/catalog` | Peta 31 konsep tarif/fasilitas/kewajiban/sanksi (`rule_map.json`) |
| `GET` | `/scenarios` | Hasil inferensi 8 skenario demonstrasi |
| `GET` | `/sparql/provenance` | Query SPARQL provenance (`rule_id`, `document_id`, `domain`, `rule_type`, `q`) atas 12.907 aturan |
| `GET` | `/sparql/stats` | Agregasi jumlah aturan per domain & kelas dari RDF `kbr-data.ttl` |

## Contoh Request `POST /reason`

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
      "isUMKM_PP55": false,
      "hasNPWP": true
    }
  }'
```
