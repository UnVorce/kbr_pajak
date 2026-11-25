# -*- coding: utf-8 -*-
"""CLI Fase 5 & 6 — Bangun TBox SROIQ(D), Reasoning OWL (HermiT + SWRL), Rule Map, dan ekspor RDF penuh.

Contoh:
    python3 scripts/fase5_ontology.py build
    python3 scripts/fase5_ontology.py sparql --rule-id R-UU-1983-6-ad287a542a
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ontology import build_all_ontologies, query_rule_provenance_sparql


def _pick_path(primary: str, fallback: str) -> Path:
    p1 = ROOT / primary
    return p1 if p1.exists() else (ROOT / fallback)


def cmd_build(args: argparse.Namespace) -> int:
    rules_path = ROOT / args.rules if args.rules else _pick_path("data/legal_rules.jsonl", "knowledge_json/rules/legal_rules.jsonl")
    mk_dir = ROOT / args.mk_dir if args.mk_dir else _pick_path("data/putusan_mk", "knowledge_json/putusan_mk")
    sema_dir = ROOT / args.sema_dir if args.sema_dir else _pick_path("data/sema_tun", "knowledge_json/sema_tun")
    full_ttl = ROOT / args.full_ttl if args.full_ttl else _pick_path("data/export/kbr-data.ttl", "knowledge_json/rules/kbr-data.ttl")
    summary = build_all_ontologies(
        rules_jsonl=rules_path,
        mk_dir=mk_dir,
        sema_dir=sema_dir,
        out_dir=ROOT / args.out_dir,
        full_ttl_path=full_ttl,
    )
    report_json = ROOT / args.out_dir / "ontology_build_report.json"
    report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_sparql(args: argparse.Namespace) -> int:
    rdf_path = ROOT / args.rdf if args.rdf else _pick_path("data/export/kbr-data.ttl", "knowledge_json/rules/kbr-data.ttl")
    rows = query_rule_provenance_sparql(
        rdf_path,
        rule_id=args.rule_id,
        document_id=args.document_id,
        limit=args.limit,
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Builder Ontologi & Reasoning KBR Pajak (Fase 5-6)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build", help="Bangun TBox, Reasoning OWL, Rule Map, dan full TTL + verifikasi HermiT")
    p_b.add_argument("--rules", default=None)
    p_b.add_argument("--mk-dir", default=None)
    p_b.add_argument("--sema-dir", default=None)
    p_b.add_argument("--out-dir", default="ontology")
    p_b.add_argument("--full-ttl", default=None)
    p_b.set_defaults(func=cmd_build)

    p_s = sub.add_parser("sparql", help="Uji query SPARQL provenance pada ekspor RDF")
    p_s.add_argument("--rdf", default=None)
    p_s.add_argument("--rule-id", default=None)
    p_s.add_argument("--document-id", default=None)
    p_s.add_argument("--limit", type=int, default=10)
    p_s.set_defaults(func=cmd_sparql)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
