# -*- coding: utf-8 -*-
"""X-1 — Kurasi aturan atomik PP 20/2026 (perubahan PP 55/2022) + wiring data PP 55.

Menghasilkan:
- 14 aturan atomik `PP-2026-20` di `data/legal_rules.jsonl` (kutipan verbatim)
- `data/review/pp2026_20_audit_log.jsonl` + `pp2026_20_audit_report.json`
- `backend/pp55_rules.json` (rujukan rule_id & parameter yang dipakai backend)

Jalankan:
    python3 scripts/curate_pp2026_20.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOC_ID = "PP-2026-20"
RULES_JSONL = ROOT / "data" / "legal_rules.jsonl"
DOC_JSON = ROOT / "data" / "documents" / "PP-2026-20.json"
AUDIT_LOG = ROOT / "data" / "review" / "pp2026_20_audit_log.jsonl"
AUDIT_REPORT = ROOT / "data" / "review" / "pp2026_20_audit_report.json"
PP55_JSON = ROOT / "backend" / "pp55_rules.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _rid(quote: str) -> str:
    return f"R-{DOC_ID}-{hashlib.sha1(_norm(quote).encode('utf-8')).hexdigest()[:10]}"


def _quote(prov_text: str, start: str, end: str) -> str:
    """Ambil substring dari teks yang sudah dinormalisasi (verbatim setelah normalisasi spasi)."""
    n = _norm(prov_text)
    i = n.find(start)
    if i < 0:
        raise ValueError(f"Penanda awal tidak ditemukan: {start!r}")
    j = n.find(end, i)
    if j < 0:
        raise ValueError(f"Penanda akhir tidak ditemukan: {end!r} (setelah {start!r})")
    return n[i : j + len(end)]


def build_rules(doc: dict) -> List[dict]:
    prov = {p.get("locator"): _norm(p.get("text") or "") for p in doc.get("provisions") or []}
    t1 = prov.get("PP-2026-20#BT/I", "")
    t2 = prov.get("PP-2026-20#BT/II", "")
    if not t1 or not t2:
        raise ValueError("Provisions PP-2026-20#BT/I atau #BT/II tidak ditemukan")

    now = datetime.now(timezone.utc).isoformat()
    specs: List[dict] = [
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "prohibition",
            "subject": "Wajib Pajak",
            "prohibition": ["Pengeluaran berupa suap, gratifikasi, dan/atau pemberian lain bukan biaya yang dapat mengurangi penghasilan bruto."],
            "quote": _quote(t1, "Pengeluaran berupa suap, gratifikasi,", "pengurang penghasilan bruto."),
            "notes": "Pasal 20A baru: suap/gratifikasi bukan biaya (dasar RP-07).",
            "domain": "Domain_A2_PPhBadan",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "eligibility",
            "subject": "Wajib Pajak dalam negeri",
            "condition": [{
                "attribute": "peredaran bruto",
                "operator": "<=",
                "value": "Rp4.800.000.000",
                "raw": "peredaran bruto tidak melebihi Rp4.80O.OOO.OO0,OO (empat miliar delapan ratus juta rupiah) dalam 1 (satu) Tahun Pajak",
            }],
            "quote": _quote(
                t1,
                "yang dikenai Pajak Penghasilan bersifat Iinal sebagaimana dimaksud dalam Pasal 56 ayat (1) merupakan:",
                "dalam 1 (satu) Tahun Pajak.",
            ),
            "notes": "Pasal 57(1): WP PPh final = OP; badan perseroan perorangan & koperasi.",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "Wajib Pajak",
            "exception": ["Wajib Pajak yang memilih dikenai PPh berdasarkan tarif Pasal 17 (OP) atau Pasal 17(1)b dengan mempertimbangkan Pasal 31E (badan)."],
            "quote": _quote(
                t1,
                "a. Wajib Pajak memilih untuk dikenai Pajak Penghasilan berdasarkan:",
                "untuk Wajib Pajak badan;",
            ),
            "notes": "Pasal 57(2)a: memilih tarif umum.",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "perseroan perorangan",
            "exception": ["Perseroan perorangan yang didirikan OP dengan keahlian khusus yang menyerahkan jasa sejenis pekerjaan bebas."],
            "quote": _quote(
                t1,
                "b. Wajib Pajak badan berbentuk perseroan perorangan sebagaimana dimaksud pada ayat (1) huruf b",
                "Pasal 56 ayat (4);",
            ),
            "notes": "Pasal 57(2)b: PT Perorangan jasa keahlian khusus (dasar RP-02/RP-05).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "Wajib Pajak badan",
            "exception": ["Badan yang memperoleh fasilitas PPh berdasarkan Pasal 31A, PP 94/2010, atau Pasal 75 & 78 PP 40/2021 (KEK)."],
            "quote": _quote(
                t1,
                "c. Wajib Pajak badan sebagaimana dimaksud pada ayat (1) huruf b, yang memperoleh fasilitas Pajak Penghasilan berdasarkan:",
                "Khusus beserta perubahan atau penggantinya;",
            ),
            "notes": "Pasal 57(2)c: penerima fasilitas lain.",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "bentuk usaha tetap",
            "exception": ["Bentuk usaha tetap tidak termasuk WP PPh final 0,5%."],
            "quote": _quote(t1, "d. Wajib Pajak bentuk usaha tetap;", "d. Wajib Pajak bentuk usaha tetap;"),
            "notes": "Pasal 57(2)d: BUT dikecualikan.",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "Wajib Pajak orang pribadi dan perseroan perorangan",
            "exception": ["OP beserta seluruh perseroan perorangan miliknya yang omzet gabungannya melebihi Rp4,8 miliar dalam 1 Tahun Pajak."],
            "quote": _quote(
                t1,
                "e. Wajib Pajak orang pribadi beserta seluruh Wajib Pajak badan berbentuk perseroan perorangan",
                "dalam 1 (satu) Tahun Pajak;",
            ),
            "notes": "Pasal 57(2)e: ambang gabungan OP + PT Perorangan (dasar RP-05).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "koperasi",
            "exception": ["Koperasi yang telah melewati jangka waktu 4 (empat) Tahun Pajak sejak Tahun Pajak terdaftar."],
            "condition": [{
                "attribute": "jangka waktu sejak Tahun Pajak terdaftar",
                "operator": ">=",
                "value": "4 Tahun Pajak",
                "raw": "telah melewati jangka waktu 4 (empat) Tahun Pajak sejak Tahun Pajak Wajib Pajak bersangkutan terdaftar",
            }],
            "quote": _quote(
                t1,
                "f. Wajib Pajak badan berbentuk koperasi sebagaimana dimaksud pada ayat (1) huruf b",
                "terdaftar.",
            ),
            "notes": "Pasal 57(2)f: batas 4 Tahun Pajak koperasi (dasar RP-04).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "exception",
            "subject": "Wajib Pajak",
            "exception": ["WP pada Pasal 57(2)e dan (2)f serta ayat (3) tidak dapat dikenai PPh final pada Tahun Pajak berikutnya."],
            "consequence": "Tidak dapat dikenai PPh final berdasarkan PP ini pada Tahun Pajak berikutnya.",
            "quote": _quote(
                t1,
                "(4) Wajib Pajak sebagaimana dimaksud pada ayat (2) huruf e dan huruf f serta ayat (3)",
                "berdasarkan Peraturan Pemerintah ini,",
            ),
            "notes": "Pasal 57(4): konsekuensi tahun berikutnya (dasar RP-04/RP-05).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/II",
            "rule_type": "right",
            "subject": "Wajib Pajak orang pribadi",
            "right": ["OP yang masa finalnya berakhir Tahun Pajak 2024 dapat dikenai PPh final untuk Tahun Pajak 2025 dan 2026."],
            "deadline": "Tahun Pajak 2025 dan 2026",
            "quote": _quote(
                t2,
                "1) Tahun P41ak 2O24 untuk Wajib Pajak orang pribadi",
                "Tahun Pajak 2026; atau",
            ),
            "notes": "Pasal II huruf a butir 1: peralihan OP (2024 -> 2025-2026).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/II",
            "rule_type": "right",
            "subject": "Wajib Pajak orang pribadi dan perseroan perorangan",
            "right": ["OP dan perseroan perorangan yang masa finalnya berakhir Tahun Pajak 2025 dapat dikenai PPh final untuk Tahun Pajak 2026."],
            "deadline": "Tahun Pajak 2026",
            "quote": _quote(
                t2,
                "2l Tahun Pajak 2025 untuk Wajib Pajak orang pribadi",
                "untuk Tahun Pajak2026,",
            ),
            "notes": "Pasal II huruf a butir 2: peralihan OP & PT Perorangan (2025 -> 2026).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/II",
            "rule_type": "right",
            "subject": "koperasi",
            "right": ["Koperasi terdaftar sebelum PP ini berlaku dengan masa final berakhir 2024-2029 dapat dikenai PPh final untuk Tahun Pajak 2025-2029."],
            "deadline": "Tahun Pajak 2025 s.d. 2029",
            "quote": _quote(
                t2,
                "b. Wajib Pajak badan berbentuk koperasi yang terdaftar sebelum Peraturan Pemerintah ini berlaku",
                "Tahun Pajak 2029 sepanjang",
            ),
            "notes": "Pasal II huruf b: peralihan koperasi (2025-2029).",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/II",
            "rule_type": "right",
            "subject": "Wajib Pajak orang pribadi dan perseroan perorangan",
            "right": ["OP dan perseroan perorangan pada Pasal 57(2)b dan (2)e dapat dikenai PPh final sampai akhir Tahun Pajak 2026."],
            "deadline": "akhir Tahun Pajak 2026",
            "quote": _quote(
                t2,
                "f. Wajib Pajak orang pribadi dan Wajib Pajak badan berbentuk perseroan p€rorangan",
                "sampai dengan akhir Tahun Pajak2026;",
            ),
            "notes": "Pasal II huruf f: batas akhir peralihan 2026.",
            "domain": "Domain_PPh_Final_Sektor",
        },
        {
            "locator": "PP-2026-20#BT/I",
            "rule_type": "definition",
            "subject": "Wajib Pajak orang pribadi suami-istri",
            "condition": [{
                "attribute": "peredaran bruto",
                "operator": "==",
                "value": "penggabungan peredaran bruto suami dan istri",
                "raw": "ditentukan berdasarkan penggabungan peredaran bruto dari suami dan istri",
            }],
            "quote": _quote(
                t1,
                "Dalam hal Wajib Pajak orang pribadi merupakan suami-istri yang:",
                "didirikan oleh suami dan istri.",
            ),
            "notes": "Pasal 58(2)-(3): penggabungan omzet suami-istri & PT Perorangan (dasar RP-06).",
            "domain": "Domain_PPh_Final_Sektor",
        },
    ]

    rules: List[dict] = []
    for spec in specs:
        quote = spec["quote"]
        if _norm(quote) not in t1 and _norm(quote) not in t2:
            raise ValueError(f"Kutipan bukan substring: {quote[:80]!r}")
        rules.append({
            "rule_id": _rid(quote),
            "domain": spec["domain"],
            "document_id": DOC_ID,
            "source_locator": spec["locator"],
            "chunk_id": None,
            "rule_type": spec["rule_type"],
            "subject": spec.get("subject"),
            "condition": spec.get("condition", []),
            "obligation": spec.get("obligation", []),
            "right": spec.get("right", []),
            "prohibition": spec.get("prohibition", []),
            "exception": spec.get("exception", []),
            "consequence": spec.get("consequence"),
            "deadline": spec.get("deadline"),
            "rate_or_value": spec.get("rate_or_value", []),
            "cross_references": spec.get("cross_references", []),
            "source_quote": quote,
            "effective_period_hint": "mulai 2026-04-22",
            "confidence": 1.0,
            "mk_review_refs": [],
            "sema_tun_refs": [],
            "validation_status": "HUMAN_FIXED",
            "review_reasons": ["human_curated_pp2026_20"],
            "extraction_method": {"model_id": "human_curation", "prompt_version": "X1"},
            "human_notes": spec["notes"],
            "audited_at": now,
        })
    return rules


def main() -> int:
    doc = json.loads(DOC_JSON.read_text(encoding="utf-8"))
    new_rules = build_rules(doc)

    existing = [json.loads(l) for l in RULES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept = [r for r in existing if r.get("document_id") != DOC_ID]
    merged = kept + new_rules

    # validasi akhir: rule_id unik & kutipan ada di dokumen
    ids = [r["rule_id"] for r in merged]
    assert len(ids) == len(set(ids)), "rule_id duplikat"
    for r in new_rules:
        assert r["source_quote"] and r["source_locator"]

    RULES_JSONL.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8"
    )

    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_LOG.write_text(
        "".join(json.dumps({
            "rule_id": r["rule_id"], "source_locator": r["source_locator"],
            "rule_type": r["rule_type"], "human_decision": "HUMAN_FIXED",
            "human_notes": r["human_notes"], "audited_at": r["audited_at"],
        }, ensure_ascii=False) + "\n" for r in new_rules),
        encoding="utf-8",
    )

    by_type: Dict[str, int] = {}
    for r in new_rules:
        by_type[r["rule_type"]] = by_type.get(r["rule_type"], 0) + 1
    report = {
        "document_id": DOC_ID,
        "rules_before": len(existing),
        "rules_added": len(new_rules),
        "rules_after": len(merged),
        "by_rule_type": by_type,
        "verbatim_quotes_verified": True,
    }
    AUDIT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Data rujukan untuk backend (rule_id + parameter batas koperasi)
    refs = {}
    for r in new_rules:
        q = r["source_quote"]
        if "memilih untuk dikenai Pajak Penghasilan berdasarkan" in q:
            refs["pasal_57_2a"] = r["rule_id"]
        elif "keahlian khusus" in q:
            refs["pasal_57_2b"] = r["rule_id"]
        elif "memperoleh fasilitas Pajak Penghasilan berdasarkan" in q:
            refs["pasal_57_2c"] = r["rule_id"]
        elif "bentuk usaha tetap" in q:
            refs["pasal_57_2d"] = r["rule_id"]
        elif "seluruh Wajib Pajak badan berbentuk perseroan perorangan" in q:
            refs["pasal_57_2e"] = r["rule_id"]
        elif "koperasi sebagaimana dimaksud pada ayat (1) huruf b" in q:
            refs["pasal_57_2f"] = r["rule_id"]
        elif "P41ak 2O24" in q:
            refs["peralihan_a1"] = r["rule_id"]
        elif "2l Tahun Pajak 2025" in q:
            refs["peralihan_a2"] = r["rule_id"]
        elif "sampai dengan akhir Tahun Pajak2026" in q:
            refs["peralihan_f"] = r["rule_id"]
        elif "tidak dapat dikenai Pajak Penghasilan bersifat linal" in q:
            refs["pasal_57_4"] = r["rule_id"]
        elif "suami-istri" in q:
            refs["pasal_58_2"] = r["rule_id"]
        elif "Pengeluaran berupa suap" in q:
            refs["pasal_20a"] = r["rule_id"]
        elif "merupakan:" in q:
            refs["pasal_57_1"] = r["rule_id"]
    refs["koperasi_batas_tahun"] = 4
    refs["omzet_batas_idr"] = 4_800_000_000
    refs["documents"] = [DOC_ID, "PP-2022-55"]
    PP55_JSON.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("pp55_rules.json:", json.dumps(refs, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
