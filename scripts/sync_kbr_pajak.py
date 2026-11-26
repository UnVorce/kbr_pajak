# -*- coding: utf-8 -*-
"""Sinkronkan hasil pipeline fatih/ ke repo korpus kbr_pajak/ (tanpa PDF mentah).

Yang disalin:
- knowledge_json/{documents,consolidated,perda,jurisprudence,putusan_mk,sema_tun}/
- knowledge_json/rules/legal_rules.jsonl
- knowledge_json/review/{priority_review_audited.csv,llm_audit_log.jsonl,gold_standard_template.jsonl,gold_standard_review.csv,review_queue.jsonl}
- knowledge_json/metadata/*.json|*.jsonl|*.yaml
- docs/{fase_4.md,ISSUES.md}
- notebooks/colab_extract_t2.ipynb

Yang TIDAK pernah disalin: sources/, download-pdf/, data/text/, data/llm_results/, data/chunks/pending/.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KBR = ROOT.parent / "kbr_pajak"

DATA_DIRS = ["documents", "consolidated", "perda", "jurisprudence", "putusan_mk", "sema_tun"]
METADATA_FILES = [
    ("data/manifest.json", "manifest.json"),
    ("data/perda_manifest.json", "perda_manifest.json"),
    ("data/jurisprudence_manifest.json", "jurisprudence_manifest.json"),
    ("data/mk_manifest.json", "mk_manifest.json"),
    ("data/sema_tun_manifest.json", "sema_tun_manifest.json"),
    ("data/consolidation.yaml", "consolidation.yaml"),
    ("data/gaps.json", "gaps.json"),
    ("data/gaps_attempts.json", "gaps_attempts.json"),
    ("data/citations.jsonl", "citations.jsonl"),
    ("data/unresolved_citations.json", "unresolved_citations.json"),
    ("data/metadata_repair_log.json", "metadata_repair_log.json"),
    ("data/scope_manifest.jsonl", "scope_manifest.jsonl"),
    ("data/validation/validation_report.json", "validation_report.json"),
    ("data/chunks/chunk_manifest.json", "chunk_manifest.json"),
    ("data/review/review_apply_report.json", "review_apply_report.json"),
]
EXTRA_FILES = [
    ("conftest.py", "conftest.py"),
    ("data/legal_rules.jsonl", "knowledge_json/rules/legal_rules.jsonl"),
    ("data/export/kbr-data.ttl", "knowledge_json/rules/kbr-data.ttl"),
    ("ontology/kbr-core.ttl", "ontology/kbr-core.ttl"),
    ("ontology/kbr_pajak_tbox.owl", "ontology/kbr_pajak_tbox.owl"),
    ("ontology/kbr_pajak_tbox.ttl", "ontology/kbr_pajak_tbox.ttl"),
    ("ontology/kbr_pajak_reasoning.owl", "ontology/kbr_pajak_reasoning.owl"),
    ("ontology/rule_map.json", "ontology/rule_map.json"),
    ("ontology/ontology_build_report.json", "ontology/ontology_build_report.json"),
    ("ontology/kbr_ter_pph21.ttl", "ontology/kbr_ter_pph21.ttl"),
    ("ontology/kbr_kbli.ttl", "ontology/kbr_kbli.ttl"),
    ("ontology/step_b_build_report.json", "ontology/step_b_build_report.json"),
    ("ontology/kbr-perda-rates.ttl", "ontology/kbr-perda-rates.ttl"),
    ("ontology/step_c_build_report.json", "ontology/step_c_build_report.json"),
    ("data/text/PP-2023-58.txt", "knowledge_json/text_lampiran/PP-2023-58.txt"),
    ("data/text/PP-2019-78.txt", "knowledge_json/text_lampiran/PP-2019-78.txt"),
    ("data/text/PERBKPM-2020-7-LAMP.txt", "knowledge_json/text_lampiran/PERBKPM-2020-7-LAMP.txt"),
    ("data/text/PMK-2020-16.txt", "knowledge_json/text_lampiran/PMK-2020-16.txt"),
    ("data/text/PMK-2020-16-LAMP-OCR.txt", "knowledge_json/text_lampiran/PMK-2020-16-LAMP-OCR.txt"),
    ("data/review/priority_review_llm_draft.csv", "knowledge_json/review/priority_review_audited.csv"),
    ("data/review/llm_audit_log.jsonl", "knowledge_json/review/llm_audit_log.jsonl"),
    ("data/review/pph_final_audit_log.jsonl", "knowledge_json/review/pph_final_audit_log.jsonl"),
    ("data/review/pp2026_20_audit_log.jsonl", "knowledge_json/review/pp2026_20_audit_log.jsonl"),
    ("data/review/pp2026_20_audit_report.json", "knowledge_json/review/pp2026_20_audit_report.json"),
    ("data/review/pph_final_audit_report.json", "knowledge_json/review/pph_final_audit_report.json"),
    ("data/gold_standard_template.jsonl", "knowledge_json/review/gold_standard_template.jsonl"),
    ("data/gold_standard_review.csv", "knowledge_json/review/gold_standard_review.csv"),
    ("data/review/review_queue.jsonl", "knowledge_json/review/review_queue.jsonl"),
    ("reports/phase_0.md", "docs/phase_0.md"),
    ("reports/phase_1.md", "docs/phase_1.md"),
    ("reports/source_coverage.md", "docs/source_coverage.md"),
    ("reports/fase_4.md", "docs/fase_4.md"),
    ("reports/fase_5_6.md", "docs/fase_5_6.md"),
    ("reports/fase_7.md", "docs/fase_7.md"),
    ("reports/fase_8.md", "docs/fase_8.md"),
    ("reports/DATA_DICTIONARY.md", "docs/DATA_DICTIONARY.md"),
    ("reports/fase7_eval_results.json", "docs/fase7_eval_results.json"),
    ("docs/API_CONTRACT_v1.md", "docs/API_CONTRACT_v1.md"),
    ("docs/API_CONTRACT_v2.md", "docs/API_CONTRACT_v2.md"),
    ("docs/PRD_CORRECTIONS.md", "docs/PRD_CORRECTIONS.md"),
    ("docs/DEPLOYMENT.md", "docs/DEPLOYMENT.md"),
    ("docker-compose.yml", "docker-compose.yml"),
    ("Makefile", "Makefile"),
    (".dockerignore", ".dockerignore"),
    (".env.example", ".env.example"),
    ("deploy/nginx.conf", "deploy/nginx.conf"),
    ("AGENTS.md", "docs/AGENTS.md"),
    ("KBR_Extraction_Spec_v2.md", "docs/KBR_Extraction_Spec_v2.md"),
    ("kbr_knowledge_acquisition_plan.md", "docs/kbr_knowledge_acquisition_plan.md"),
    ("ISSUES.md", "docs/ISSUES.md"),
    ("notebooks/colab_extract_t2.ipynb", "notebooks/colab_extract_t2.ipynb"),
    ("notebooks/README.md", "notebooks/README.md"),
]

CODE_DIRS = ["src", "scripts", "tests", "config"]

PER17_LAMPIRAN_FILES = [
    "Lampiran 1_PER - 17.PJ_.2015.txt",
    "Lampiran 2_PER - 17.PJ_.2015.txt",
    "Lampiran 3_PER - 17.PJ_.2015.txt",
]

BACKEND_FILES = [
    "__init__.py",
    "engine.py",
    "main.py",
    "contract_v2.py",
    "advisory.py",
    "coretax.py",
    "coretax_playbook.json",
    "risk_patterns.json",
    "cbr_index.json",
    "nppn_kelompok.json",
    "pp55_rules.json",
    "requirements.txt",
    "requirements-dev.txt",
    "Dockerfile",
    "README.md",
]


def _sync_dir(src: Path, dst: Path, prune: bool) -> tuple[int, int, int]:
    copied = unchanged = pruned = 0
    dst.mkdir(parents=True, exist_ok=True)
    src_names = set()
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        if "__pycache__" in f.parts or f.suffix in (".pyc", ".pyo"):
            continue
        rel = f.relative_to(src)
        src_names.add(rel.as_posix())
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and filecmp.cmp(f, target, shallow=False):
            unchanged += 1
            continue
        shutil.copy2(f, target)
        copied += 1
    if prune:
        for f in sorted(dst.rglob("*"), reverse=True):
            if f.is_file() and f.relative_to(dst).as_posix() not in src_names:
                f.unlink()
                pruned += 1
    return copied, unchanged, pruned


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true",
                    help="hapus file di tujuan yang tidak ada di sumber (hati-hati)")
    args = ap.parse_args()

    if not KBR.exists():
        print(f"[ERR] repo tujuan tidak ditemukan: {KBR}")
        return 1

    total_copied = total_unchanged = total_pruned = 0
    for name in DATA_DIRS:
        src = ROOT / "data" / name
        if not src.exists():
            print(f"  [SKIP] data/{name} belum ada")
            continue
        c, u, p = _sync_dir(src, KBR / "knowledge_json" / name, args.prune)
        total_copied += c
        total_unchanged += u
        total_pruned += p
        print(f"  [{name:14}] copied={c:4} unchanged={u:5} pruned={p:3}")

    meta_dst = KBR / "knowledge_json" / "metadata"
    meta_dst.mkdir(parents=True, exist_ok=True)
    for src_rel, dst_name in METADATA_FILES:
        src = ROOT / src_rel
        if not src.exists():
            print(f"  [SKIP] {src_rel} belum ada")
            continue
        target = meta_dst / dst_name
        if target.exists() and filecmp.cmp(src, target, shallow=False):
            total_unchanged += 1
            continue
        shutil.copy2(src, target)
        total_copied += 1
        print(f"  [meta] {dst_name} disalin")

    for src_rel, dst_rel in EXTRA_FILES:
        src = ROOT / src_rel
        if not src.exists():
            print(f"  [SKIP] {src_rel} belum ada")
            continue
        target = KBR / dst_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and filecmp.cmp(src, target, shallow=False):
            total_unchanged += 1
            continue
        shutil.copy2(src, target)
        total_copied += 1
        print(f"  [extra] {dst_rel} disalin")

    for name in CODE_DIRS:
        src = ROOT / name
        if not src.exists():
            continue
        c, u, p = _sync_dir(src, KBR / name, args.prune)
        total_copied += c
        total_unchanged += u
        total_pruned += p
        print(f"  [code:{name:8}] copied={c:4} unchanged={u:5} pruned={p:3}")

    per17_src_dir = ROOT.parent / "forNow" / "knowledge_txt" / "4_PER_DGTRegulations"
    lamp_dst = KBR / "knowledge_json" / "text_lampiran"
    lamp_dst.mkdir(parents=True, exist_ok=True)
    for fname in PER17_LAMPIRAN_FILES:
        src = per17_src_dir / fname
        if not src.exists():
            continue
        target = lamp_dst / fname
        if target.exists() and filecmp.cmp(src, target, shallow=False):
            total_unchanged += 1
            continue
        shutil.copy2(src, target)
        total_copied += 1
        print(f"  [lampiran] {fname} disalin")

    backend_dst = KBR / "backend"
    backend_dst.mkdir(parents=True, exist_ok=True)
    for fname in BACKEND_FILES:
        src = ROOT / "backend" / fname
        if not src.exists():
            continue
        target = backend_dst / fname
        if target.exists() and filecmp.cmp(src, target, shallow=False):
            total_unchanged += 1
            continue
        shutil.copy2(src, target)
        total_copied += 1
        print(f"  [backend] backend/{fname} disalin")

    print(f"Sinkron selesai: copied={total_copied} unchanged={total_unchanged} pruned={total_pruned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
