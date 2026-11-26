# -*- coding: utf-8 -*-
"""Katalog risiko RP-01..RP-10 & Case-Based Reasoning tahap 1 (B3/B4).

Sumber data (dihasilkan `scripts/build_risk_cbr.py`):
- `risk_patterns.json` : 10 pola + dasar hukum terverifikasi (rule_id PP-2026-20 dll.)
- `cbr_index.json`     : 284 putusan Pengadilan Pajak (field yang tersedia)

Formula CBR tahap 1 (deterministik):
    0.70 * BM25(pokok_sengketa) + 0.20 * klaster + 0.10 * Jaccard(regulasi)
Formulir penuh PRD (WuPalmer + fakta_kunci + penalti rezim) menunggu anotasi 60 kasus.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

_RISK_PATH = Path(__file__).with_name("risk_patterns.json")
_CBR_PATH = Path(__file__).with_name("cbr_index.json")

_STOP = {
    "dan", "atau", "yang", "untuk", "dengan", "dari", "pada", "dalam", "tidak", "telah",
    "adalah", "oleh", "sebagai", "juga", "atas", "kepada", "karena", "agar", "dapat", "ini",
    "itu", "para", "suatu", "sebuah", "sesuai", "berdasarkan", "terhadap", "mengenai",
}

_catalog: Optional[dict] = None
_cbr: Optional[dict] = None
_bm25: Optional[dict] = None
_cbr_cache: Dict[tuple, List[dict]] = {}


def _load_catalog() -> dict:
    global _catalog
    if _catalog is None:
        _catalog = json.loads(_RISK_PATH.read_text(encoding="utf-8")) if _RISK_PATH.exists() else {"total": 0, "items": []}
    return _catalog


def _load_cbr() -> dict:
    global _cbr
    if _cbr is None:
        _cbr = json.loads(_CBR_PATH.read_text(encoding="utf-8")) if _CBR_PATH.exists() else {"total": 0, "cases": []}
    return _cbr


def risk_catalog() -> dict:
    return _load_catalog()


def _by_id(catalog: dict) -> Dict[str, dict]:
    return {i["pola_id"]: i for i in catalog.get("items", [])}


def _job_names(req) -> List[str]:
    names: List[str] = []
    for p in (req.pekerjaan_utama, req.pekerjaan_sekunder):
        if p is not None:
            names.append(p.jenis)
    return names


def evaluate_risks(req, v1: dict, ctx: dict, pp55: dict) -> List[dict]:
    """Kembalikan hanya pola yang terindikasi (deterministik, berbasis fakta request + inferensi)."""
    cat = _by_id(_load_catalog())
    rincian = ((v1.get("estimasi_pajak") or {}).get("rincian")) or {}
    omzet = float(ctx.get("omzet_bisnis") or 0.0)
    if req.has_omzet_tahunan is not None:
        omzet = max(omzet, float(req.has_omzet_tahunan))
    omzet_pasangan = float(req.omzet_pasangan or 0.0)
    jenis = _job_names(req)

    def add(pola_id: str, indikator: str, dampak: Optional[float] = None) -> None:
        src = cat.get(pola_id)
        if not src:
            return
        out.append({
            "pola_id": pola_id,
            "nama": src["nama"],
            "status": "TERINDIKASI",
            "tingkat_risiko": src["tingkat_risiko"],
            "indikator_terdeteksi": indikator,
            "estimasi_dampak_idr": round(dampak, 2) if dampak else None,
            "rekomendasi": src["rekomendasi"],
            "grounding_status": src["grounding_status"],
            "dasar_hukum": src["dasar_hukum"],
        })

    out: List[dict] = []

    if omzet > 4_800_000_000 and not req.is_terdaftar_pkp:
        add("RP-01", f"Omzet Rp{omzet:,.0f} > Rp4,8 M dan status belum PKP.", rincian.get("ppn_terutang_idr"))

    if req.is_umkm_pp55 and ("PEKERJA_BEBAS" in jenis or "OP_PekerjaBebas" in (v1.get("inferred_classes") or [])):
        add("RP-02", "WP orang pribadi pekerjaan bebas menerapkan PPh Final 0,5%.")

    if "OP_NPPN_Gugur_TelatLapor" in (v1.get("inferred_classes") or []) or (
        "PEKERJA_BEBAS" in jenis and not req.is_pemberitahuan_nppn_tepat_waktu
    ):
        add("RP-03", "NPPN digunakan tanpa pemberitahuan tepat waktu.")

    alasan = (pp55 or {}).get("alasan") or ""
    alasan_l = alasan.lower()
    if (
        req.is_umkm_pp55
        and req.wp_kind in ("PT", "CV", "Koperasi", "Firma", "Badan")
        and (pp55 or {}).get("status") == "DISKUALIFIKASI"
        and (any(k in alasan for k in ("Pasal 57(1)", "Pasal 57(2)f", "Pasal 57(4)")) or "masa peralihan" in alasan_l)
    ):
        add("RP-04", alasan)

    if req.omzet_gabungan_grup is not None and float(req.omzet_gabungan_grup) > 4_800_000_000:
        add("RP-05", f"Omzet gabungan grup Rp{float(req.omzet_gabungan_grup):,.0f} > Rp4,8 M.")

    if req.is_pisah_harta and (omzet + omzet_pasangan) > 4_800_000_000:
        add("RP-06", f"Omzet gabungan suami-istri Rp{omzet + omzet_pasangan:,.0f} > Rp4,8 M.")

    if req.is_membebankan_suap_gratifikasi:
        add("RP-07", "Terdapat pengeluaran suap/gratifikasi yang dibebankan sebagai biaya.")

    if req.is_terlambat_lapor_spt or req.is_terlambat_lapor_spt_masa_ppn:
        add("RP-08", "Terdapat keterlambatan penyetoran/pelaporan SPT.", rincian.get("denda_administratif_tetap_idr"))

    if req.has_selisih_ekualisasi:
        add("RP-09", "Terdapat selisih ekualisasi omzet SPT vs arus uang/SPT PPN.")

    if req.is_tidak_memotong_pph_pihak_ketiga:
        add("RP-10", "Pembayaran jasa pihak ketiga tanpa pemotongan PPh 23/21.")

    return out


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in _STOP]


def _build_bm25() -> dict:
    global _bm25
    if _bm25 is not None:
        return _bm25
    data = _load_cbr()
    docs = []
    df: Counter = Counter()
    for c in data.get("cases", []):
        toks = _tokens(c.get("pokok_sengketa", ""))
        tf = Counter(toks)
        for t in tf:
            df[t] += 1
        docs.append({"case": c, "tf": tf, "len": len(toks), "regs": set(c.get("cited_regulations") or [])})
    avgdl = (sum(d["len"] for d in docs) / len(docs)) if docs else 0.0
    _bm25 = {"docs": docs, "df": df, "avgdl": avgdl, "n": len(docs)}
    return _bm25


def cbr_search(
    query: str,
    klaster: Optional[str] = None,
    regulasi: Optional[List[str]] = None,
    limit: int = 3,
) -> List[dict]:
    if not (query or "").strip():
        return []
    cache_key = ((query or "").strip().lower(), klaster, tuple(sorted(regulasi or [])), int(limit))
    if cache_key in _cbr_cache:
        return _cbr_cache[cache_key]
    idx = _build_bm25()
    if not idx["docs"]:
        return []
    q = _tokens(query)
    if not q:
        return []
    k1, b = 1.5, 0.75
    regs_q = {r.upper() for r in (regulasi or [])}
    scored: List[dict] = []
    for d in idx["docs"]:
        score = 0.0
        for t in q:
            f = d["tf"].get(t, 0)
            if not f:
                continue
            idf = math.log(1 + (idx["n"] - idx["df"][t] + 0.5) / (idx["df"][t] + 0.5))
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * d["len"] / max(idx["avgdl"], 1)))
        if score <= 0:
            continue
        c = d["case"]
        klaster_sim = 1.0 if klaster and c.get("klaster") == klaster else 0.0
        reg_sim = (len(regs_q & d["regs"]) / len(regs_q | d["regs"])) if (regs_q and d["regs"]) else 0.0
        scored.append({
            "case": c,
            "bm25": score,
            "klaster_sim": klaster_sim,
            "reg_sim": reg_sim,
        })
    if not scored:
        return []
    max_bm25 = max(s["bm25"] for s in scored)
    for s in scored:
        s["similarity"] = (
            0.70 * (s["bm25"] / max_bm25) + 0.20 * s["klaster_sim"] + 0.10 * s["reg_sim"]
        )
    scored.sort(key=lambda s: (-s["similarity"], s["case"].get("case_id") or ""))
    out = []
    for s in scored[: max(1, min(int(limit), 10))]:
        c = s["case"]
        out.append({
            "case_id": c.get("case_id"),
            "putusan_nomor": c.get("putusan_nomor"),
            "klaster": c.get("klaster"),
            "jenis_pajak": c.get("jenis_pajak"),
            "tahun_pajak": c.get("tahun_pajak"),
            "amar_kategori": c.get("amar_kategori"),
            "similarity_score": round(s["similarity"], 4),
            "komponen": {
                "bm25": round(s["bm25"] / max_bm25, 4),
                "klaster": s["klaster_sim"],
                "regulasi": round(s["reg_sim"], 4),
            },
            "pokok_sengketa": (c.get("pokok_sengketa") or "")[:600],
            "pertimbangan_majelis": (c.get("pertimbangan_majelis") or "")[:600],
            "cited_regulations": c.get("cited_regulations") or [],
            "source_url": c.get("source_url"),
        })
    if len(_cbr_cache) > 128:
        _cbr_cache.clear()
    _cbr_cache[cache_key] = out
    return out
