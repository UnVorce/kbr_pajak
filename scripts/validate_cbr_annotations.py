# -*- coding: utf-8 -*-
"""B4.1 — Validator anotasi CBR (taksonomi, kelengkapan, kutipan verbatim, kappa).

Contoh:
    python3 scripts/validate_cbr_annotations.py                     # laporan progres + error
    python3 scripts/validate_cbr_annotations.py --strict            # wajib 60/60 lengkap
    python3 scripts/validate_cbr_annotations.py --second file2.csv  # hitung Cohen's kappa
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

def _pick(*rels: str) -> Path:
    for r in rels:
        p = ROOT / r
        if p.exists():
            return p
    return ROOT / rels[0]


TAXONOMY = ROOT / "config" / "cbr_taxonomy.json"
DEFAULT_CSV = _pick("data/jurisprudence", "knowledge_json/jurisprudence") / "annotations" / "worksheet_60.csv"

REQUIRED = ("jenis_koreksi", "fakta_kunci", "rasio_decidendi", "rezim_hukum", "annotator")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def load_taxonomy(path: Path = TAXONOMY) -> dict:
    tax = json.loads(path.read_text(encoding="utf-8"))
    codes: Dict[str, set] = {}
    for key in ("jenis_koreksi", "fakta_kunci", "bukti_penentu"):
        items = tax.get(key) or []
        codes[key] = {i["kode"] for i in items}
        parents = {i["induk"] for i in items if i.get("induk")}
        children = {i["kode"] for i in items if i.get("induk")}
        codes[f"{key}__leaf"] = {i["kode"] for i in items if i["kode"] not in parents}
    return {
        "raw": tax,
        "codes": codes,
        "rezim": set(tax.get("rezim_hukum") or []),
        "amar": set(tax.get("amar") or []),
    }


def _split(val: str) -> List[str]:
    return [x.strip() for x in re.split(r"[;,]", val or "") if x.strip()]


def _row_blank(row: dict) -> bool:
    return not any((row.get(k) or "").strip() for k in REQUIRED + ("argumen_menang", "bukti_penentu", "quotes_json"))


def validate_rows(rows: List[dict], tax: dict) -> Tuple[List[dict], dict]:
    errors: List[dict] = []
    seen = set()
    by_klaster: Counter = Counter()
    by_amar: Counter = Counter()
    label_use: Dict[str, Counter] = defaultdict(Counter)
    annotated = pending = 0

    for i, row in enumerate(rows, 2):  # baris 1 = header
        cid = (row.get("case_id") or "").strip()
        if not cid:
            errors.append({"baris": i, "case_id": None, "error": "case_id kosong"})
            continue
        if cid in seen:
            errors.append({"baris": i, "case_id": cid, "error": "case_id duplikat"})
        seen.add(cid)
        by_klaster[row.get("klaster") or "lain"] += 1
        by_amar[row.get("amar_kategori_asal") or "LAINNYA"] += 1

        if _row_blank(row):
            pending += 1
            continue
        annotated += 1

        def err(msg: str) -> None:
            errors.append({"baris": i, "case_id": cid, "error": msg})

        for field in REQUIRED:
            if not (row.get(field) or "").strip():
                err(f"field wajib kosong: {field}")

        amar = (row.get("amar_kategori_asal") or "").strip()
        if amar and amar not in tax["amar"]:
            err(f"amar tidak dikenal: {amar}")
        if amar.startswith("KABUL") and not (row.get("argumen_menang") or "").strip():
            err("argumen_menang wajib untuk amar KABUL")

        for field in ("jenis_koreksi", "fakta_kunci", "bukti_penentu"):
            labels = _split(row.get(field) or "")
            for lab in labels:
                if lab not in tax["codes"][field]:
                    err(f"{field}: kode tidak dikenal '{lab}'")
                else:
                    label_use[field][lab] += 1
            if field in ("jenis_koreksi", "fakta_kunci") and labels and (row.get(field) or "").strip():
                if not any(lab in tax["codes"][f"{field}__leaf"] for lab in labels):
                    err(f"{field}: wajib memuat minimal satu kode daun (bukan hanya induk)")

        rezim = (row.get("rezim_hukum") or "").strip()
        if rezim and rezim not in tax["rezim"]:
            err(f"rezim_hukum tidak dikenal: {rezim}")

        pert = _norm(row.get("pertimbangan_majelis"))
        rasio = _norm(row.get("rasio_decidendi"))
        if rasio and pert and rasio not in pert:
            err("rasio_decidendi bukan substring persis pertimbangan_majelis")
        arg = _norm(row.get("argumen_menang"))
        if arg and pert and arg not in pert:
            err("argumen_menang bukan substring persis pertimbangan_majelis")

        raw_quotes = (row.get("quotes_json") or "").strip()
        if raw_quotes:
            try:
                quotes = json.loads(raw_quotes)
                if not isinstance(quotes, list):
                    raise ValueError("quotes_json harus list")
                for q in quotes:
                    if not isinstance(q, dict) or not q.get("quote"):
                        err("quotes_json: setiap entri wajib punya 'quote'")
                        continue
                    if _norm(q["quote"]) not in pert:
                        err("quotes_json: kutipan tidak ditemukan di pertimbangan_majelis")
                    if q.get("field") not in ("rasio_decidendi", "argumen_menang"):
                        err("quotes_json: 'field' harus rasio_decidendi/argumen_menang")
            except Exception as exc:  # noqa: BLE001
                err(f"quotes_json tidak valid: {exc}")

    summary = {
        "total": len(rows),
        "annotated": annotated,
        "pending": pending,
        "errors": len(errors),
        "by_klaster": dict(sorted(by_klaster.items())),
        "by_amar": dict(sorted(by_amar.items())),
        "label_usage": {k: dict(v.most_common()) for k, v in label_use.items()},
    }
    return errors, summary


def cohen_kappa(a: List[str], b: List[str]) -> Optional[float]:
    if not a or len(a) != len(b):
        return None
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa1 = sum(1 for x in a if x) / n
    pb1 = sum(1 for y in b if y) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe >= 1.0:
        return None
    return round((po - pe) / (1 - pe), 4)


def _read(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def kappa_between(csv_a: Path, csv_b: Path) -> dict:
    a = {r["case_id"]: r for r in _read(csv_a) if (r.get("case_id") or "").strip()}
    b = {r["case_id"]: r for r in _read(csv_b) if (r.get("case_id") or "").strip()}
    common = sorted(set(a) & set(b))
    out = {"kesepakatan_kasus": len(common)}
    for field in ("jenis_koreksi", "fakta_kunci"):
        vals_a, vals_b = [], []
        for cid in common:
            la = set(_split(a[cid].get(field) or ""))
            lb = set(_split(b[cid].get(field) or ""))
            for lab in sorted(la | lb):
                vals_a.append("1" if lab in la else "")
                vals_b.append("1" if lab in lb else "")
        out[field] = cohen_kappa(vals_a, vals_b)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Validator anotasi CBR")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--second", default=None, help="CSV annotator kedua untuk Cohen's kappa")
    ap.add_argument("--strict", action="store_true", help="gagal bila masih ada baris pending")
    ap.add_argument("--json", default=None, help="simpan laporan ke path JSON")
    args = ap.parse_args()

    tax = load_taxonomy()
    rows = _read(Path(args.csv))
    errors, summary = validate_rows(rows, tax)
    if args.second:
        summary["kappa"] = kappa_between(Path(args.csv), Path(args.second))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for e in errors[:30]:
        print(f"  [ERROR] baris {e['baris']} {e['case_id']}: {e['error']}")
    if len(errors) > 30:
        print(f"  ... {len(errors) - 30} error lain")

    if args.json:
        Path(args.json).write_text(json.dumps({"summary": summary, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = bool(errors) or (args.strict and summary["pending"] > 0)
    print("\nHASIL:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
