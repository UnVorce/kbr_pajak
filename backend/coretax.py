# -*- coding: utf-8 -*-
"""Playbook Coretax (B5) — langkah & KAP/KJS untuk kewajiban yang terinferensi.

Sumber: `coretax_playbook.json` (dari Buku Manual Coretax 2024 — Seri Pembayaran).
Panduan ini **bukan** peraturan; setiap entri membawa `jenis_sumber: panduan_djp`
dan tidak boleh dipakai sebagai dasar hukum.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

_PATH = Path(__file__).with_name("coretax_playbook.json")
_data: Optional[dict] = None


def _load() -> dict:
    global _data
    if _data is None:
        _data = json.loads(_PATH.read_text(encoding="utf-8")) if _PATH.exists() else {
            "menu": [], "kode": [], "peta_kewajiban": {}, "langkah_umum": [], "sumber": {},
        }
    return _data


def catalog() -> dict:
    d = _load()
    return {
        "sumber": d.get("sumber"),
        "menu": d.get("menu") or [],
        "total_kode": len(d.get("kode") or []),
        "total_kewajiban_terpetakan": len(d.get("peta_kewajiban") or {}),
    }


def search_kode(query: str = "", limit: int = 20) -> List[dict]:
    q = (query or "").strip().lower()
    items = _load().get("kode") or []
    if q:
        items = [c for c in items if q in c["kap_kjs"].lower() or q in c["keterangan"].lower()]
    return items[: max(1, min(int(limit), 100))]


def playbook_for(kewajiban_ids: List[str]) -> List[dict]:
    d = _load()
    mapping: Dict[str, dict] = d.get("peta_kewajiban") or {}
    out: List[dict] = []
    seen = set()
    for kid in kewajiban_ids:
        entry = mapping.get(kid)
        if not entry or kid in seen:
            continue
        seen.add(kid)
        out.append({**entry, "kewajiban_id": kid, "sumber": d.get("sumber")})
    if not out:
        generic = mapping.get("PLAYBOOK_KODE_BILLING")
        if generic:
            out.append({**generic, "kewajiban_id": None, "sumber": d.get("sumber")})
    return out


def playbook_all() -> List[dict]:
    d = _load()
    mapping: Dict[str, dict] = d.get("peta_kewajiban") or {}
    return [
        {**entry, "kewajiban_id": k, "sumber": d.get("sumber")}
        for k, entry in mapping.items()
    ]
