# -*- coding: utf-8 -*-
"""FastAPI Service untuk KBR Pajak (Fase 7).

Menjalankan reasoning OWL 2 SROIQ(D) + SWRL (HermiT) dan query SPARQL provenance
untuk konsumsi frontend (`yoeke-front`) dan modul RAG (`daRAG`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import KBRReasoningEngine

engine = KBRReasoningEngine()

app = FastAPI(
    title="KBR Pajak Reasoning & Provenance API",
    description=(
        "API Reasoning Ontologi Pajak Indonesia (OWL 2 SROIQ(D) + SWRL via HermiT) "
        "dan Query Provenance SPARQL atas 12.907 aturan hukum tervalidasi."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaxpayerProperties(BaseModel):
    hasOmzetTahunan: Optional[float] = Field(default=None, ge=0, description="Peredaran bruto tahunan (Rp)")
    hasNilaiInvestasi: Optional[float] = Field(default=None, ge=0, description="Nilai rencana penanaman modal baru (Rp)")
    hasPersentaseSahamPublik: Optional[float] = Field(default=None, ge=0, le=100, description="Persentase saham publik (%)")
    hasJumlahKendaraan: Optional[int] = Field(default=None, ge=0, description="Urutan kepemilikan kendaraan bermotor pribadi")
    isPerseroanTerbuka: Optional[bool] = None
    isIndustriPionir: Optional[bool] = None
    isPenanamanModalBaru: Optional[bool] = None
    isUMKM_PP55: Optional[bool] = None
    hasNPWP: Optional[bool] = None
    isDomisiliDKI: Optional[bool] = None
    isMilikPribadi: Optional[bool] = None
    isMemilikiObjekPBB: Optional[bool] = None
    isTerlambatLaporSPT: Optional[bool] = None
    isKeberatanDitolak: Optional[bool] = None
    isBandingDitolak: Optional[bool] = None
    isUsahaSpaKesehatanTradisional: Optional[bool] = None
    isUsahaHiburanSpaUmum: Optional[bool] = None
    isPenyerahanNonMewahPPN: Optional[bool] = None
    isPenyerahanBKPStrategis: Optional[bool] = None
    isPendudukIndonesia: Optional[bool] = None


class ReasonRequest(BaseModel):
    wp_id: str = Field(default="WP_Simulasi_001", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    wp_kind: Literal["PT", "CV", "Koperasi", "Yayasan", "BadanUsahaTetap", "Badan", "OrangPribadi"] = "PT"
    properties: TaxpayerProperties = Field(default_factory=TaxpayerProperties)


class JustificationItem(BaseModel):
    rule_id: Optional[str] = None
    source_locator: Optional[str] = None
    source_quote: Optional[str] = None
    validation_status: Optional[str] = None
    regulasi: List[str] = Field(default_factory=list)
    mk_refs: List[str] = Field(default_factory=list)
    sema_refs: List[str] = Field(default_factory=list)


class InferredConceptItem(BaseModel):
    id: str
    label: str
    tarif_persen: Optional[float] = None
    justifikasi: List[JustificationItem] = Field(default_factory=list)


class ReasonResponse(BaseModel):
    wp_id: str
    wp_kind: str
    applied_properties: Dict[str, Any]
    direct_classes: List[str]
    inferred_classes: List[str]
    tarif: List[InferredConceptItem]
    fasilitas: List[InferredConceptItem]
    kewajiban: List[InferredConceptItem]
    sanksi: List[InferredConceptItem]
    reasoner: str
    elapsed_ms: float


@app.get("/health", summary="Cek kesehatan service, ontologi OWL, dan RDF graph")
def get_health() -> dict:
    return engine.health()


@app.post("/reason", response_model=ReasonResponse, summary="Evaluasi profil Wajib Pajak dengan HermiT + justifikasi pasal")
def post_reason(req: ReasonRequest) -> dict:
    try:
        props = req.properties.model_dump(exclude_none=True)
        return engine.reason(req.wp_id, req.wp_kind, props)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reasoning gagal: {exc}") from exc


@app.get("/catalog", summary="Daftar 31 konsep katalog Tarif/Fasilitas/Kewajiban/Sanksi dan pemetaan rule_id")
def get_catalog() -> dict:
    try:
        items = engine.get_catalog()
        return {"count": len(items), "items": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/scenarios", summary="Ringkasan hasil inferensi 8 skenario bawaan di kbr_pajak_reasoning.owl")
def get_scenarios() -> dict:
    scenarios = engine.get_preset_scenarios()
    return {"count": len(scenarios), "scenarios": scenarios}


@app.get("/sparql/provenance", summary="Query SPARQL provenance aturan hukum pada 12.907 aturan RDF")
def get_sparql_provenance(
    rule_id: Optional[str] = Query(default=None, description="Filter exact rule_id, mis. R-UU-1983-6-ad287a542a"),
    document_id: Optional[str] = Query(default=None, description="Filter exact document_id, mis. UU-1983-7"),
    domain: Optional[str] = Query(default=None, description="Filter substring domain, mis. A2_PPH_BADAN"),
    rule_type: Optional[str] = Query(default=None, description="Kelas aturan OWL, mis. AturanTarif, Sanksi, Pengecualian"),
    q: Optional[str] = Query(default=None, description="Pencarian substring pada source_quote"),
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


@app.get("/sparql/stats", summary="Statistik graf RDF penuh per domain & kelas aturan")
def get_sparql_stats() -> dict:
    try:
        return engine.sparql_stats()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
