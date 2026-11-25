# -*- coding: utf-8 -*-
"""Tes ekspor & apply CSV review prioritas tinggi (src/review.py)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.review import apply_review_csv, export_priority_review_csv  # noqa: E402


def test_export_and_apply_roundtrip(tmp_path: Path):
    chunks = {
        "c1": {
            "chunk_id": "c1",
            "domain": "A2_PPH_BADAN",
            "document_id": "UU-1983-7",
            "source_locator": "UU-1983-7#BT/17",
            "context": {"mk_review_refs": [], "sema_tun_refs": []},
            "text": "Tarif 5% sampai dengan Rp60.000.000,00.",
        },
        "c2": {
            "chunk_id": "c2",
            "domain": "D_ADMIN_SANKSI",
            "document_id": "UU-2002-14",
            "source_locator": "UU-2002-14#BT/5",
            "context": {"mk_review_refs": ["MK-2023-26-PUU-XXI"], "sema_tun_refs": []},
            "text": "Pembinaan oleh Departemen Keuangan.",
        },
        "c3": {
            "chunk_id": "c3",
            "domain": "D_ADMIN_SANKSI",
            "document_id": "PMK-2010-999",
            "source_locator": "PMK-2010-999#BT/1",
            "context": {"mk_review_refs": [], "sema_tun_refs": []},
            "text": "Contoh non-prioritas.",
        },
    }
    rev = [
        {
            "rule_id": "R-UU-1983-7-1",
            "chunk_id": "c1",
            "domain": "A2_PPH_BADAN",
            "document_id": "UU-1983-7",
            "source_locator": "UU-1983-7#BT/17",
            "reason": ["table_layout_review", "rule_type:rate"],
            "source_quote": "Tarif 5% sampai dengan Rp60.000.000,00.",
            "mk_review_refs": [],
            "sema_tun_refs": [],
            "candidate_rule": {
                "rule_id": "R-UU-1983-7-1",
                "rule_type": "rate",
                "rate_or_value": [{"value": "15%", "unit": "%", "raw": "15%"}],
                "condition": [],
            },
        },
        {
            "rule_id": "R-UU-2002-14-1",
            "chunk_id": "c2",
            "domain": "D_ADMIN_SANKSI",
            "document_id": "UU-2002-14",
            "source_locator": "UU-2002-14#BT/5",
            "reason": ["mk_constitutional_review"],
            "source_quote": "Pembinaan oleh Departemen Keuangan.",
            "mk_review_refs": ["MK-2023-26-PUU-XXI"],
            "sema_tun_refs": [],
            "candidate_rule": {"rule_id": "R-UU-2002-14-1", "rule_type": "obligation"},
        },
        {
            "rule_id": "R-NONPRIO-1",
            "chunk_id": "c3",
            "domain": "D_ADMIN_SANKSI",
            "document_id": "PMK-2010-999",
            "source_locator": "PMK-2010-999#BT/1",
            "reason": ["random_10pct_sample"],
            "source_quote": "Contoh non-prioritas.",
            "mk_review_refs": [],
            "sema_tun_refs": [],
            "candidate_rule": {"rule_id": "R-NONPRIO-1", "rule_type": "procedure"},
        },
    ]

    csv_p = tmp_path / "priority_review.csv"
    rep = export_priority_review_csv(rev, chunks, csv_p)
    assert rep["total_exported"] == 2
    assert rep["by_priority"] == {"P1_TABLE": 1, "P2_MK": 1}

    # Simulasi label manusia: perbaiki c1, approve c2
    with csv_p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows[0]["rate_or_value_json"] = '[{"value": "5%", "unit": "%", "raw": "5%"}]'
    rows[0]["human_decision"] = "FIXED"
    rows[0]["human_notes"] = "Betulkan tarif jadi 5%"
    rows[1]["human_decision"] = "APPROVED"
    rows[1]["human_notes"] = "Catat amar MK"

    with csv_p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    legal_rules = [
        {"rule_id": "R-UU-1983-7-1", "rule_type": "rate", "rate_or_value": [{"value": "15%"}], "validation_status": "REVIEW_REQUIRED"},
        {"rule_id": "R-UU-2002-14-1", "rule_type": "obligation", "validation_status": "REVIEW_REQUIRED"},
        {"rule_id": "R-NONPRIO-1", "rule_type": "procedure", "validation_status": "REVIEW_REQUIRED"},
    ]
    out_rules, apply_rep = apply_review_csv(csv_p, legal_rules, chunks)
    assert apply_rep["total_rules_out"] == 3
    by_id = {r["rule_id"]: r for r in out_rules}
    assert by_id["R-UU-1983-7-1"]["validation_status"] == "HUMAN_FIXED"
    assert by_id["R-UU-1983-7-1"]["rate_or_value"][0]["value"] == "5%"
    assert by_id["R-UU-2002-14-1"]["validation_status"] == "HUMAN_APPROVED"
    assert by_id["R-UU-2002-14-1"]["human_notes"] == "Catat amar MK"
