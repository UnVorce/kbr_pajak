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
    # Relasi individu (lihat GET /options & GET /kbli)
    memilikiPekerjaan: Optional[List[str]] = Field(default=None, description="Daftar ID JenisPekerjaan (khusus OrangPribadi), mis. ['Dokter', 'PegawaiTetap_Swasta']")
    berdomisiliDi: Optional[List[str]] = Field(default=None, description="Daftar ID WilayahDaerah, mis. ['Wilayah_Kota_Surabaya']")
    kodeKBLI: Optional[str] = Field(default=None, description="Kode KBLI/KLU 5 digit (mis. '69100', '86201', '03222') untuk lookup SKOS NPPN & Tax Allowance")
    lokasiProvinsiTaxAllowance: Optional[str] = Field(default=None, description="Nama provinsi/kota lokasi proyek untuk syarat wilayah Lampiran II PP 78/2019")
    pemdaId: Optional[str] = Field(default=None, description="ID Pemda dari 524 Perda (mis. 'KOTA_BANDUNG', 'KAB_BOGOR', 'PROV_DKI_JAKARTA') — lihat GET /perda")

    # Kuantitatif umum & Badan
    hasOmzetTahunan: Optional[float] = Field(default=None, ge=0, description="Peredaran bruto tahunan (Rp)")
    hasNilaiInvestasi: Optional[float] = Field(default=None, ge=0, description="Nilai rencana penanaman modal baru (Rp)")
    hasPersentaseSahamPublik: Optional[float] = Field(default=None, ge=0, le=100, description="Persentase saham publik (%)")
    hasJumlahPemegangSahamPublik: Optional[int] = Field(default=None, ge=0, description="Jumlah pihak pemegang saham publik (syarat Tbk >= 300)")
    hasHariTerpenuhiTbk: Optional[int] = Field(default=None, ge=0, le=366, description="Jumlah hari pemenuhan syarat Tbk dalam 1 tahun pajak (>= 183)")
    hasJumlahKendaraan: Optional[int] = Field(default=None, ge=0, description="Urutan kepemilikan kendaraan bermotor")
    hasKapasitasMesinCC: Optional[int] = Field(default=None, ge=0, description="Kapasitas mesin kendaraan (cc, untuk PKB Bali)")
    hasNilaiNJOP: Optional[float] = Field(default=None, ge=0, description="Nilai Jual Objek Pajak PBB-P2 (Rp)")
    hasPersentaseNJOP_PBB: Optional[float] = Field(default=None, ge=0, le=100, description="Persentase NJOP pengenaan PBB-P2 (20-100%, opsional untuk kalkulator)")
    hasNJOPTKP_PBB: Optional[float] = Field(default=None, ge=0, description="NJOPTKP daerah PBB-P2 (Rp, opsional untuk kalkulator)")
    hasDPP_PPN: Optional[float] = Field(default=None, ge=0, description="Dasar Pengenaan Pajak PPN tahunan/transaksi (Rp, opsional untuk kalkulator)")

    # Status Badan & Fasilitas
    isPerseroanTerbuka: Optional[bool] = None
    isPerseroanPerorangan: Optional[bool] = None
    isIndustriPionir: Optional[bool] = None
    isPenanamanModalBaru: Optional[bool] = None
    isBidangUsahaTaxAllowance: Optional[bool] = None
    isLokasiProvinsiMemenuhiTaxAllowance: Optional[bool] = None
    isIndustriPadatKarya: Optional[bool] = None
    hasSuratKeteranganFiskal: Optional[bool] = None
    isBelumPernahPutusTaxHoliday: Optional[bool] = None
    isUMKM_PP55: Optional[bool] = None
    hasNPWP: Optional[bool] = None

    # Status Orang Pribadi (PPh 21 / TER / Pasal 17 / SPLN / NPPN)
    isPendudukIndonesia: Optional[bool] = None
    isSubjekLuarNegeri: Optional[bool] = None
    isKawin: Optional[bool] = None
    hasJumlahTanggungan: Optional[int] = Field(default=None, ge=0, le=10, description="Jumlah tanggungan keluarga (maks diakui PTKP = 3)")
    isPenghasilanIstriDigabung: Optional[bool] = None
    hasPenghasilanKenaPajakTahunan: Optional[float] = Field(default=None, ge=0, description="Penghasilan Kena Pajak (PKP) tahunan OP atau Badan (Rp)")
    hasPenghasilanBrutoBulanan: Optional[float] = Field(default=None, ge=0, description="Penghasilan bruto bulanan OP (Rp, untuk PPh 21 TER)")
    hasJumlahPemberiKerja: Optional[int] = Field(default=None, ge=0, description="Jumlah pemberi kerja dalam 1 tahun pajak")
    isPemberitahuanNPPNTepatWaktu: Optional[bool] = None
    isTidakMenyelenggarakanPembukuanPencatatan: Optional[bool] = None
    kelompokWilayahNPPN: Optional[Literal["10_IbuKota_Provinsi", "IbuKota_Provinsi_Lain", "Daerah_Lain"]] = None

    # PPN & Pemotongan PPh 23
    isPenyerahanNonMewahPPN: Optional[bool] = None
    isPenyerahanBKP_Mewah: Optional[bool] = None
    isPenyerahanBKPStrategis: Optional[bool] = None
    isPenerimaPenghasilanPPh23_JasaSewa: Optional[bool] = None
    isPenerimaPenghasilanPPh23_Modal: Optional[bool] = None
    isBankPenerimaPenghasilan: Optional[bool] = None

    # Pajak Daerah & Kepatuhan/Sanksi
    isDomisiliDKI: Optional[bool] = None
    isMilikPribadi: Optional[bool] = None
    isMemilikiObjekPBB: Optional[bool] = None
    isUsahaSpaKesehatanTradisional: Optional[bool] = None
    isUsahaHiburanSpaUmum: Optional[bool] = None
    isTerlambatLaporSPT: Optional[bool] = None
    isTerlambatLaporSPTMasaPPN: Optional[bool] = None
    isDikecualikanDendaSPT: Optional[bool] = None
    isKurangBayarSKPKB: Optional[bool] = None
    isTidakSetorPajakDipungut: Optional[bool] = None
    isKeberatanDitolak: Optional[bool] = None
    isBandingDitolak: Optional[bool] = None


class ReasonRequest(BaseModel):
    wp_id: str = Field(default="WP_Simulasi_001", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    wp_kind: Literal["PT", "CV", "Koperasi", "Yayasan", "BadanUsahaTetap", "BUT", "Badan", "OrangPribadi"] = "PT"
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
    kbli_info: Optional[Dict[str, Any]] = None
    perda_info: Optional[Dict[str, Any]] = None
    estimasi_pajak: Dict[str, Any] = Field(default_factory=dict)
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


@app.get("/catalog", summary="Daftar konsep katalog Tarif/Fasilitas/Kewajiban/Sanksi dan pemetaan rule_id")
def get_catalog() -> dict:
    try:
        items = engine.get_catalog()
        return {"count": len(items), "items": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/options", summary="Daftar pilihan JenisPekerjaan (30 profesi) & WilayahDaerah (5 Perda) dari ontologi")
def get_options() -> dict:
    try:
        return engine.get_options()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/kbli", summary="Cari kode & uraian KBLI/KLU di graf SKOS (PER-17/PJ/2015 & PP 78/2019)")
def get_kbli_search(
    q: str = Query(default="", description="Kata kunci uraian atau prefiks kode KBLI, mis. 'dokter' atau '6910'"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        items = engine.search_kbli(query=q, limit=limit)
        return {"count": len(items), "results": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/kbli/{kode}", summary="Detail 1 kode KBLI/KLU (persentase NPPN 3 wilayah & Tax Allowance PP 78/2019)")
def get_kbli_detail(kode: str) -> dict:
    item = engine.lookup_kbli(kode)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Kode KBLI '{kode}' tidak ditemukan di kbr_kbli.ttl")
    return item


@app.get("/perda", summary="Cari/daftar Pemda dari 524 Perda PDRD se-Indonesia (390 Pemda unik)")
def get_perda_list(
    q: str = Query(default="", description="Kata kunci nama/ID Pemda, mis. 'bandung', 'bogor', 'yogyakarta'"),
    tingkat: Optional[Literal["PROV", "KOTA", "KAB"]] = Query(default=None, description="Filter tingkat Pemda"),
    limit: int = Query(default=30, ge=1, le=400),
) -> dict:
    try:
        items = engine.search_pemda(query=q, tingkat=tingkat, limit=limit)
        return {"count": len(items), "results": items}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/perda/{pemda_id}", summary="Detail tarif pajak daerah & kutipan Perda resmi untuk 1 Pemda")
def get_perda_detail(pemda_id: str) -> dict:
    item = engine.lookup_pemda(pemda_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Pemda '{pemda_id}' tidak ditemukan di kbr-perda-rates.ttl")
    return item


@app.get("/scenarios", summary="Ringkasan hasil inferensi skenario bawaan di kbr_pajak_reasoning.owl")
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
