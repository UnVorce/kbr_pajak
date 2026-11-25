# -*- coding: utf-8 -*-
"""Utilitas ekspor & apply review manusia prioritas tinggi (Fase 4D -> G4)."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CORE_DOC_IDS = {
    "UU-1983-6", "UU-1983-7", "UU-1983-8", "UU-1985-12", "UU-1997-19",
    "UU-2002-14", "UU-2020-10", "UU-2021-7", "UU-2022-1",
    "PP-2008-51", "PP-2023-58", "PP-2022-55",
    "PMK-2016-101", "PMK-2023-164", "PMK-2020-130",
    "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-JAWA-BARAT-2023-9",
    "PERDA-KOTA-SEMARANG-2023-10", "PERDA-KOTA-SURABAYA-2023-7",
    "PERDA-PROV-BALI-2024-1",
}

CSV_COLUMNS = [
    "priority",
    "status_asal",
    "rule_id",
    "chunk_id",
    "domain",
    "document_id",
    "source_locator",
    "alasan_review",
    "rujukan_mk_sema",
    "rule_type",
    "subject",
    "rate_or_value_json",
    "condition_json",
    "obligation_right_prohibition_json",
    "exception_json",
    "deadline",
    "consequence",
    "source_quote",
    "teks_chunk",
    "human_decision",
    "human_notes",
]

PRIORITY_ORDER = {
    "P1_TABLE": 1,
    "P2_MK": 2,
    "P3_SEMA": 3,
    "P4_PARSE_ERROR": 4,
    "P5_RATE_CORE": 5,
    "P6_REJECTED_CORE": 6,
}


def classify_priority(item: dict, chunk: Optional[dict] = None) -> Optional[str]:
    """Klasifikasikan item review_queue ke bucket prioritas, atau None jika non-prioritas."""
    rs = item.get("reason") or []
    did = item.get("document_id") or (chunk or {}).get("document_id")
    ctx = (chunk or {}).get("context") or {}
    mk = item.get("mk_review_refs") or ctx.get("mk_review_refs") or []
    sema = item.get("sema_tun_refs") or ctx.get("sema_tun_refs") or []

    if "table_layout_review" in rs:
        return "P1_TABLE"
    if mk:
        return "P2_MK"
    if sema:
        return "P3_SEMA"
    if "llm_parse_error" in rs:
        return "P4_PARSE_ERROR"
    if "validator_rejected" in rs and did in CORE_DOC_IDS:
        return "P6_REJECTED_CORE"
    if "rule_type:rate" in rs and did in CORE_DOC_IDS:
        return "P5_RATE_CORE"
    return None


def _jdump(val) -> str:
    if val is None or val == [] or val == {}:
        return ""
    return json.dumps(val, ensure_ascii=False)


def _jload(s: str, default):
    s = (s or "").strip()
    if not s:
        return default
    return json.loads(s)


def export_priority_review_csv(
    review_items: List[dict],
    chunks_by_id: Dict[str, dict],
    out_csv: Path,
) -> dict:
    """Ekspor item prioritas tinggi dari review_queue ke CSV dengan kolom label."""
    rows: List[dict] = []
    counts: Counter = Counter()

    for item in review_items:
        cid = item.get("chunk_id")
        chunk = chunks_by_id.get(cid, {})
        prio = classify_priority(item, chunk)
        if not prio:
            continue

        rs = item.get("reason") or []
        if "llm_parse_error" in rs:
            status_asal = "PARSE_ERROR"
        elif "validator_rejected" in rs:
            status_asal = "REJECTED"
        else:
            status_asal = "REVIEW_REQUIRED"

        ctx = chunk.get("context") or {}
        mk = item.get("mk_review_refs") or ctx.get("mk_review_refs") or []
        sema = item.get("sema_tun_refs") or ctx.get("sema_tun_refs") or []
        ref_parts = []
        if mk:
            ref_parts.append("MK: " + ", ".join(mk))
        if sema:
            ref_parts.append("SEMA: " + ", ".join(sema))

        cr = item.get("candidate_rule") or {}
        orp = {}
        for k in ("obligation", "right", "prohibition"):
            if cr.get(k):
                orp[k] = cr[k]

        if status_asal == "PARSE_ERROR":
            sq_or_err = f"[PARSE_ERROR] {item.get('error', '')} | raw: {(item.get('raw_output') or '')[:300]}"
        else:
            sq_or_err = item.get("source_quote") or cr.get("source_quote") or ""

        row = {
            "priority": prio,
            "status_asal": status_asal,
            "rule_id": item.get("rule_id") or "",
            "chunk_id": cid or "",
            "domain": item.get("domain") or chunk.get("domain") or "",
            "document_id": item.get("document_id") or chunk.get("document_id") or "",
            "source_locator": item.get("source_locator") or chunk.get("source_locator") or "",
            "alasan_review": "; ".join(str(r) for r in rs),
            "rujukan_mk_sema": " | ".join(ref_parts),
            "rule_type": cr.get("rule_type") or "",
            "subject": cr.get("subject") or "",
            "rate_or_value_json": _jdump(cr.get("rate_or_value")),
            "condition_json": _jdump(cr.get("condition")),
            "obligation_right_prohibition_json": _jdump(orp),
            "exception_json": _jdump(cr.get("exception")),
            "deadline": cr.get("deadline") or "",
            "consequence": cr.get("consequence") or "",
            "source_quote": sq_or_err,
            "teks_chunk": chunk.get("text") or item.get("chunk_text") or "",
            "human_decision": "PENDING",
            "human_notes": "",
        }
        rows.append(row)
        counts[prio] += 1

    rows.sort(key=lambda r: (
        PRIORITY_ORDER.get(r["priority"], 99),
        r["document_id"],
        r["source_locator"],
        r["rule_id"],
    ))

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)

    return {
        "total_exported": len(rows),
        "by_priority": dict(sorted(counts.items())),
        "output_csv": str(out_csv),
    }


def apply_review_csv(
    csv_path: Path,
    legal_rules: List[dict],
    chunks_by_id: Dict[str, dict],
) -> Tuple[List[dict], dict]:
    """Terapkan keputusan manusia (APPROVED / FIXED / REJECTED) dari CSV ke legal_rules."""
    by_id: Dict[str, dict] = {r["rule_id"]: dict(r) for r in legal_rules}
    ordered_ids: List[str] = [r["rule_id"] for r in legal_rules]
    removed_ids: set[str] = set()
    stats: Counter = Counter()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, 1):
            dec = (row.get("human_decision") or "").strip().upper()
            if not dec or dec in ("PENDING", "SKIP"):
                stats["SKIPPED_PENDING"] += 1
                continue

            rid = (row.get("rule_id") or "").strip()
            notes = (row.get("human_notes") or "").strip()
            status_asal = (row.get("status_asal") or "").strip()

            if dec == "REJECTED":
                if rid and rid in by_id:
                    removed_ids.add(rid)
                    stats["REMOVED_FROM_LEGAL_RULES"] += 1
                else:
                    stats["CONFIRMED_REJECTED"] += 1
                continue

            if dec not in ("APPROVED", "FIXED"):
                stats["UNKNOWN_DECISION"] += 1
                continue

            if rid and rid in by_id:
                rec = by_id[rid]
                if dec == "FIXED":
                    _apply_edits_to_rule(rec, row)
                    rec["validation_status"] = "HUMAN_FIXED"
                    stats["FIXED_EXISTING"] += 1
                else:
                    rec["validation_status"] = "HUMAN_APPROVED"
                    stats["APPROVED_EXISTING"] += 1
                if notes:
                    rec["human_notes"] = notes
            else:
                # Promosikan rule dari REJECTED / PARSE_ERROR yang disetujui/diperbaiki manusia
                cid = (row.get("chunk_id") or "").strip()
                chunk = chunks_by_id.get(cid, {})
                ctx = chunk.get("context") or {}
                did = (row.get("document_id") or chunk.get("document_id") or "").strip()
                loc = (row.get("source_locator") or chunk.get("source_locator") or "").strip()
                sq = (row.get("source_quote") or "").strip()
                new_rid = rid or f"R-{did}-{hashlib.sha1(f'{cid}|human|{row_num}|{sq}'.encode()).hexdigest()[:10]}"
                rec = {
                    "rule_id": new_rid,
                    "domain": (row.get("domain") or chunk.get("domain") or "").strip(),
                    "document_id": did,
                    "source_locator": loc,
                    "chunk_id": cid,
                    "rule_type": (row.get("rule_type") or "other").strip(),
                    "subject": (row.get("subject") or "").strip() or None,
                    "condition": [],
                    "obligation": [],
                    "right": [],
                    "prohibition": [],
                    "exception": [],
                    "consequence": None,
                    "deadline": None,
                    "rate_or_value": [],
                    "cross_references": [],
                    "source_quote": sq,
                    "effective_period_hint": None,
                    "confidence": 1.0,
                    "mk_review_refs": ctx.get("mk_review_refs") or [],
                    "sema_tun_refs": ctx.get("sema_tun_refs") or [],
                    "validation_status": "HUMAN_FIXED" if dec == "FIXED" else "HUMAN_APPROVED",
                    "review_reasons": [f"human_promoted_from_{status_asal.lower()}"],
                    "extraction_method": {"model_id": "human_review", "prompt_version": "G4"},
                }
                _apply_edits_to_rule(rec, row)
                if notes:
                    rec["human_notes"] = notes
                by_id[new_rid] = rec
                ordered_ids.append(new_rid)
                stats["PROMOTED_NEW"] += 1

    out_rules = [by_id[i] for i in ordered_ids if i not in removed_ids]
    return out_rules, {
        "total_rules_out": len(out_rules),
        "stats": dict(sorted(stats.items())),
    }


def _apply_edits_to_rule(rec: dict, row: dict) -> None:
    if (row.get("rule_type") or "").strip():
        rec["rule_type"] = row["rule_type"].strip()
    rec["subject"] = (row.get("subject") or "").strip() or None
    rec["rate_or_value"] = _jload(row.get("rate_or_value_json", ""), [])
    rec["condition"] = _jload(row.get("condition_json", ""), [])
    orp = _jload(row.get("obligation_right_prohibition_json", ""), {})
    if isinstance(orp, dict):
        rec["obligation"] = orp.get("obligation") or []
        rec["right"] = orp.get("right") or []
        rec["prohibition"] = orp.get("prohibition") or []
    rec["exception"] = _jload(row.get("exception_json", ""), [])
    rec["deadline"] = (row.get("deadline") or "").strip() or None
    rec["consequence"] = (row.get("consequence") or "").strip() or None
    if (row.get("source_quote") or "").strip():
        rec["source_quote"] = row["source_quote"].strip()
