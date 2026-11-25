# -*- coding: utf-8 -*-
"""S2 — gerbang relevansi dan kepemilikan (KBR spec 6.2 dan 6.4).

Skor deterministik untuk Fase 1 (tanpa LLM/T3):
- subjek/bidang sumber cocok dengan subject_hints kartu   -> +0.7
- kata kunci judul cocok dengan keyword_hints             -> +0.2
- relasi langsung ke dokumen IN_SCOPE (tetangga penjelajahan) -> +0.3
Skor maksimum 1.0. Thresholds (auto_in=0.80, review_min=0.40) dari kartu lingkup;
WAJIB dikalibrasi di Fase 2 (G2). T3 (LLM) ditambahkan bila diperlukan kemudian.

Keputusan:
- skor >= auto_in            -> IN_SCOPE
- review_min <= skor < auto_in -> UNDECIDED (review_queue, TIDAK dijelajahi dulu)
- skor < review_min          -> BOUNDARY (dicatat, tidak dijelajahi)
- seed (manual manusia)      -> IN_SCOPE langsung
- OUT_OF_SCOPE hanya lewat review manusia (agent tidak menebak).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml


def load_card(path) -> dict:
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        card = yaml.safe_load(f)
    required = ("domain_id", "subject_hints", "keyword_hints", "thresholds")
    missing = [k for k in required if k not in card]
    if missing:
        raise ValueError(f"kartu lingkup {p} tidak lengkap: {missing}")
    return card


def score_document(
    meta: dict,
    card: dict,
    neighbor_in_scope: bool = False,
) -> Tuple[float, dict]:
    """Hitung skor relevansi dokumen terhadap kartu lingkup. Return (skor, sinyal)."""
    signals: Dict[str, object] = {}
    score = 0.0

    judul = (meta.get("Judul") or "").casefold()
    # Topik KELUAR bersifat deterministik dan diprioritaskan: dokumen yang
    # jelas di luar lingkup domain (mis. PPN untuk domain PPh/UMKM) langsung
    # BOUNDARY (record_and_stop), tidak dijelajahi, bisa diklaim domain lain.
    if any(kw.casefold() in judul for kw in card.get("exclude_keywords", [])):
        return 0.0, {"exclude_match": True}

    subjek = ((meta.get("Subjek") or "") + " " + (meta.get("Bidang") or "")).casefold()
    if any(hint.casefold() in subjek for hint in card.get("subject_hints", [])):
        score += 0.7
        signals["subject_match"] = True

    if any(kw.casefold() in judul for kw in card.get("keyword_hints", [])):
        score += 0.2
        signals["keyword_match"] = True

    if neighbor_in_scope:
        score += 0.3
        signals["relation_to_in_scope"] = True

    return round(min(score, 1.0), 2), signals


def decide_scope(score: float, card: dict, is_seed: bool = False) -> str:
    """Tentukan scope_status dari skor (spec 6.2)."""
    if is_seed:
        return "IN_SCOPE"
    thresholds = card["thresholds"]
    if score >= thresholds["auto_in"]:
        return "IN_SCOPE"
    if score >= thresholds["review_min"]:
        return "UNDECIDED"
    return "BOUNDARY"


def hierarchy_level(jenis: Optional[str]) -> Optional[int]:
    """Hierarki dokumen (spec 5.2): UU=1, Perpu=1, PP=2, Perpres=3, PMK=4,
    PER-DJP=5, SE=6. KMK disetarakan PMK; PUTUSAN-MK disejajarkan UU."""
    return {
        "UU": 1, "PERPU": 1, "PUTUSAN-MK": 1,
        "PP": 2,
        "PERPRES": 3,
        "PMK": 4, "KMK": 4,
        "PER-DJP": 5,
        "SE-DJP": 6,
    }.get(jenis)
