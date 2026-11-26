# -*- coding: utf-8 -*-
"""FastAPI Service KBR Pajak — API v2.0.0 (kontrak PRD §9.3).

Semua route berada di bawah `/api` (alias `/api/v1`). Root lama (`/reason`, `/health`)
dihapus sesuai keputusan B0-1.

- `POST /api/reason` : payload PRD (snake_case, `pekerjaan_utama`/`pekerjaan_sekunder`)
- `GET  /api/regions`: 390 Pemda kanonik (dari 524 Perda PDRD)
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .contract_v2 import ReasonRequest, build_response, to_internal
from .engine import KBRReasoningEngine

engine = KBRReasoningEngine()


def _cors_origins() -> List[str]:
    """Origin FE yang diizinkan: `*` (dev) atau daftar dipisah koma (produksi)."""
    raw = (os.environ.get("KBR_CORS_ORIGINS") or "*").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(
    title="KBR Pajak Reasoning & Provenance API",
    description=(
        "API Reasoning Ontologi Pajak Indonesia (OWL 2 SROIQ(D) + SWRL via HermiT) "
        "dan Query Provenance SPARQL atas 12.921 aturan hukum tervalidasi. "
        "Kontrak mengikuti PRD §9.3: multi-stream income, PPh 21 TER, komparasi 3 skema, "
        "rekonsiliasi PPh 29, PPh Final Pasal 4(2), dan provenance."
    ),
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """JSON rusak -> 400 (PRD §9.3.6); pelanggaran domain -> 422."""
    errors = exc.errors()
    if any(e.get("type") == "json_invalid" for e in errors):
        return JSONResponse(status_code=400, content={"detail": "Format JSON tidak valid.", "errors": errors})
    return JSONResponse(status_code=422, content={"detail": errors})


api = APIRouter()


@api.get("/health", summary="Status artefak ontologi, RDF, PTKP, dan cache")
def get_health() -> dict:
    health = engine.health()
    health["api_version"] = app.version
    health["ptkp_tiers"] = len(engine.get_ptkp_table())
    health["regions"] = len(engine.list_regions())
    return health


@api.get("/options", summary="Katalog opsi dropdown: badan, PTKP, pekerjaan, PPh Final, zona NPPN")
def get_options() -> dict:
    try:
        base = engine.get_options()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    ptkp = [
        {"status": k, "nominal": v["nominal"]}
        for k, v in sorted(engine.get_ptkp_table().items(), key=lambda kv: (kv[0].startswith("K"), kv[0]))
    ]
    return {
        "wp_kinds": ["OrangPribadi", "PT", "CV", "Koperasi", "Yayasan", "BadanUsahaTetap", "Badan"],
        "status_perkawinan": [{"kode": "TK", "label": "Tidak Kawin"}, {"kode": "K", "label": "Kawin"}],
        "ptkp": ptkp,
        "zona_nppn": [
            {"kode": "10_IBU_KOTA_PROVINSI", "label": "10 Ibu Kota Provinsi"},
            {"kode": "IBU_KOTA_PROVINSI_LAINNYA", "label": "Ibu Kota Provinsi Lainnya"},
            {"kode": "DAERAH_LAINNYA", "label": "Daerah Lainnya"},
        ],
        "pekerjaan_jenis": [
            {"kode": "PEGAWAI_TETAP", "label": "Pegawai Tetap"},
            {"kode": "PEGAWAI_TIDAK_TETAP", "label": "Pegawai Tidak Tetap / Harian"},
            {"kode": "PESERTA_KEGIATAN", "label": "Peserta Kegiatan"},
            {"kode": "PEKERJA_BEBAS", "label": "Pekerjaan Bebas / Tenaga Ahli"},
            {"kode": "USAHA_UMKM", "label": "Pelaku Usaha / UMKM"},
        ],
        **base,
    }


@api.get("/regions", summary="390 Pemda (dari 524 Perda PDRD): zona NPPN, tarif PBB-P2, NJOPTKP")
def get_regions(
    q: str = Query(default="", description="Kata kunci nama/ID Pemda"),
    tingkat: Optional[Literal["PROV", "KOTA", "KAB"]] = Query(default=None),
) -> dict:
    try:
        items = engine.list_regions()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    key = (q or "").strip().lower()
    if key:
        items = [r for r in items if key in r["nama_daerah"].lower() or key in r["pemda_id"].lower()]
    if tingkat:
        items = [r for r in items if r["tingkat"] == tingkat]
    return {
        "count": len(items),
        "total_pemda": len(engine.list_regions()),
        "total_perda": sum(r["jumlah_perda"] for r in engine.list_regions()),
        "results": items,
    }


@api.post("/reason", summary="Inferensi profil WP (payload PRD §9.3.3) + estimasi & provenance")
def post_reason(req: ReasonRequest) -> dict:
    try:
        _validate_lookups(req)
        wp_kind, props, ctx = to_internal(engine, req)
        v1 = engine.reason(req.wp_id, wp_kind, props)
        return build_response(engine, req, v1, ctx)
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - reasoner dapat melempar bermacam error
        msg = str(exc)
        if "Inconsistent" in msg or "inconsistent" in msg:
            raise HTTPException(
                status_code=500,
                detail=f"Kontradiksi logika ontologi: {msg}",
            ) from exc
        raise HTTPException(status_code=500, detail=f"Reasoning gagal: {msg}") from exc


def _validate_lookups(req: ReasonRequest) -> None:
    """PRD §9.3.6: KBLI / Pemda yang tidak ada -> 422 (bukan diabaikan diam-diam)."""
    for label, pekerjaan in (("pekerjaan_utama", req.pekerjaan_utama), ("pekerjaan_sekunder", req.pekerjaan_sekunder)):
        if pekerjaan and pekerjaan.kbli:
            if engine.lookup_kbli(pekerjaan.kbli) is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"KBLI '{pekerjaan.kbli}' pada {label} tidak ditemukan dalam katalog 1.453 KBLI.",
                )
    if req.kode_kbli and engine.lookup_kbli(req.kode_kbli) is None:
        raise HTTPException(
            status_code=422,
            detail=f"KBLI '{req.kode_kbli}' tidak ditemukan dalam katalog 1.453 KBLI.",
        )
    if req.pemda_id and engine.lookup_pemda(req.pemda_id) is None:
        raise HTTPException(
            status_code=422,
            detail=f"Pemda '{req.pemda_id}' tidak ditemukan dalam katalog 390 Pemda.",
        )


@api.get("/kbli", summary="Cari kode & uraian KBLI/KLU (SKOS PER-17/PJ/2015 & PP 78/2019)")
def get_kbli_search(
    q: str = Query(default="", description="Kata kunci uraian atau prefiks kode KBLI"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        items = engine.search_kbli(query=q, limit=limit)
        return {"count": len(items), "results": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.get("/kbli/{kode}", summary="Detail 1 KBLI: NPPN 3 zona, Tax Allowance, Pionir, Padat Karya")
def get_kbli_detail(kode: str) -> dict:
    item = engine.lookup_kbli(kode)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Kode KBLI '{kode}' tidak ditemukan di kbr_kbli.ttl")
    return item


@api.get("/perda", summary="Cari/daftar dokumen Perda PDRD (524) beserta tarif terekstrak")
def get_perda_list(
    q: str = Query(default="", description="Kata kunci nama/ID Pemda"),
    tingkat: Optional[Literal["PROV", "KOTA", "KAB"]] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=400),
) -> dict:
    try:
        items = engine.search_pemda(query=q, tingkat=tingkat, limit=limit)
        return {"count": len(items), "results": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.get("/perda/{pemda_id}", summary="Detail tarif pajak daerah & kutipan pasal untuk 1 Pemda")
def get_perda_detail(pemda_id: str) -> dict:
    item = engine.lookup_pemda(pemda_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Pemda '{pemda_id}' tidak ditemukan di kbr-perda-rates.ttl")
    return item


@api.get("/catalog", summary="Peta 103 konsep katalog -> rule_id & source_quote")
def get_catalog() -> dict:
    try:
        items = engine.get_catalog()
        return {"count": len(items), "items": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.get("/scenarios", summary="Hasil inferensi 15 skenario bawaan ontologi")
def get_scenarios() -> dict:
    scenarios = engine.get_preset_scenarios()
    return {"count": len(scenarios), "scenarios": scenarios}


@api.get("/sparql/provenance", summary="Provenance 12.921 aturan (rule_id/document_id/domain/tipe/teks)")
def get_sparql_provenance(
    rule_id: Optional[str] = Query(default=None),
    document_id: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    rule_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    try:
        rows = engine.query_provenance(
            rule_id=rule_id,
            document_id=document_id,
            domain=domain,
            rule_type=rule_type,
            quote_contains=q,
            limit=limit,
        )
        return {"count": len(rows), "results": rows}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@api.get("/sparql/stats", summary="Agregasi 12.921 aturan per domain & kelas RDF")
def get_sparql_stats() -> dict:
    try:
        return engine.sparql_stats()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app.include_router(api, prefix="/api")
app.include_router(api, prefix="/api/v1", include_in_schema=False)
