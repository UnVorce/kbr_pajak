# -*- coding: utf-8 -*-
"""Tes validator S8 (src/validate.py) dengan keluaran palsu/dummy."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.validate import validate_rule, validate_staging_results  # noqa: E402

CHUNK = {
    "chunk_id": "abc123",
    "domain": "B_PPN",
    "document_id": "UU-1983-8",
    "source_locator": "UU-1983-8#BT/7",
    "text": ("(1) Tarif Pajak Pertambahan Nilai yaitu:\n"
             "a. sebesar 11% (sebelas persen) yang mulai berlaku pada tanggal 1 April 2022;\n"
             "b. sebesar 12% (dua belas persen) yang mulai berlaku paling lambat pada tanggal 1 Januari 2025."),
}


def test_validate_rule_rejects_bad_quote_and_hallucinated_number():
    bad_q = {"rule_type": "rate", "source_quote": "Tarif PPN 25%", "rate_or_value": [{"value": 25, "unit": "%"}], "confidence": 0.9}
    st, errs, _ = validate_rule(bad_q, CHUNK)
    assert st == "REJECTED"
    assert any("source_quote" in e for e in errs)
    assert any("angka" in e for e in errs)


def test_validate_rule_accepts_exact_quote_and_routes_rate_to_review():
    ok_rate = {
        "rule_type": "rate",
        "subject": "Pengusaha Kena Pajak",
        "condition": [],
        "obligation": ["Mengenakan tarif PPN 11%"],
        "right": [],
        "prohibition": [],
        "exception": [],
        "consequence": None,
        "deadline": None,
        "rate_or_value": [{"value": 11, "unit": "%", "raw": "11%"}],
        "cross_references": [],
        "source_quote": "sebesar 11% (sebelas persen) yang mulai berlaku pada tanggal 1 April 2022",
        "confidence": 0.95,
    }
    st, errs, reasons = validate_rule(ok_rate, CHUNK)
    assert errs == []
    assert st == "REVIEW_REQUIRED"
    assert "rule_type:rate" in reasons


def test_rule_with_mk_review_refs_routed_to_review():
    chunk = {
        **CHUNK,
        "chunk_id": "mkref1",
        "context": {"mk_review_refs": ["MK-2023-26-PUU-XXI"], "sema_tun_refs": []},
    }
    rule = {
        "rule_type": "procedure",
        "condition": [], "obligation": ["Pembinaan oleh Mahkamah Agung"],
        "right": [], "prohibition": [], "exception": [],
        "rate_or_value": [], "cross_references": [],
        "source_quote": "sebesar 11% (sebelas persen) yang mulai berlaku pada tanggal 1 April 2022",
        "confidence": 0.95,
    }
    rules, rev, rep = validate_staging_results(
        [{"chunk_id": "mkref1", "parsed_output": {"found": True, "rules": [rule]}}],
        {"mkref1": chunk},
    )
    assert rep["counts"]["REVIEW_REQUIRED"] == 1
    assert "mk_constitutional_review" in rev[0]["reason"]
    assert rules[0]["mk_review_refs"] == ["MK-2023-26-PUU-XXI"]


def test_validate_staging_results_dedup_and_parse_error():
    proc_chunk = {
        "chunk_id": "proc1",
        "domain": "D_ADMIN_SANKSI",
        "document_id": "PMK-2024-118",
        "source_locator": "PMK-2024-118#BT/5",
        "text": "Permohonan pembetulan diajukan secara tertulis kepada Direktur Jenderal Pajak.",
    }
    good_proc = {
        "rule_type": "procedure",
        "condition": [],
        "obligation": ["Mengajukan permohonan secara tertulis"],
        "right": [], "prohibition": [], "exception": [],
        "rate_or_value": [], "cross_references": [],
        "source_quote": "Permohonan pembetulan diajukan secara tertulis kepada Direktur Jenderal Pajak.",
        "confidence": 0.95,
    }
    results = [
        {"chunk_id": "proc1", "model_id": "Qwen32B", "prompt_version": "T2_v1",
         "parsed_output": {"found": True, "rules": [good_proc, good_proc]}},
        {"chunk_id": "abc123", "model_id": "Qwen32B", "prompt_version": "T2_v1",
         "parse_error": "JSONDecodeError", "raw_output": "{bad"},
    ]
    rules, rev, rep = validate_staging_results(results, {"proc1": proc_chunk, "abc123": CHUNK})
    assert len(rules) == 1  # duplikat disaring
    assert rep["counts"]["DUPLICATE_SKIPPED"] == 1
    assert rep["counts"]["PARSE_ERROR"] == 1
    assert len(rev) >= 1


def test_validate_rule_table_fuzzy_goes_to_review():
    chunk = {
        "chunk_id": "tbl1",
        "domain": "A2_PPH_BADAN",
        "document_id": "UU-1983-7",
        "source_locator": "UU-1983-7#BT/17",
        "context": {"is_table": True},
        "text": (
            "5% (lima persen) sampai dengan Rp60.000.000,00 (enam puluh juta rupiah) "
            "15% (lima belas persen) di atas Rp60.000.000,00 (enam puluh juta rupiah) "
            "sampai dengan Rp250.000.000,00 (dua ratus lima puluh juta rupiah)"
        ),
    }
    rule = {
        "rule_type": "definition",
        "condition": [], "obligation": [], "right": [], "prohibition": [],
        "exception": [], "rate_or_value": [], "cross_references": [],
        "source_quote": (
            "15% di atas Rp60.000.000,00 (enam puluh juta rupiah) "
            "sampai dengan Rp250.000.000,00"
        ),
        "confidence": 0.9,
    }
    status, errs, reasons = validate_rule(rule, chunk)
    assert status == "REVIEW_REQUIRED"
    assert "table_layout_review" in reasons
    assert errs == []


def test_validate_rule_normalizes_ocr_quote():
    chunk = {
        "chunk_id": "ocr1",
        "domain": "A2_PPH_BADAN",
        "document_id": "UU-1983-7",
        "source_locator": "UU-1983-7#BT/17",
        "text": (
            "Tarif lO% dan Rpl00.000.000.000,00 serta "
            "www.jdih.kemenkeu.go.id MENTERI KEUANGAN REPUBLIK INDONESIA -3- "
            "Rp60.000.000,0O"
        ),
    }
    rule = {
        "rule_type": "rate",
        "condition": [{"attribute": "nilai", "operator": ">=", "value": "Rp100.000.000.000,00", "raw": "Rp100.000.000.000,00"}],
        "obligation": [], "right": [], "prohibition": [],
        "exception": [],
        "rate_or_value": [{"value": 10, "unit": "%", "raw": "10%"}],
        "cross_references": [],
        "source_quote": "Tarif 10% dan Rp100.000.000.000,00 serta Rp60.000.000,00",
        "confidence": 0.9,
    }
    status, errs, _ = validate_rule(rule, chunk)
    assert errs == []
    assert status in ("VALIDATED", "REVIEW_REQUIRED")


def test_validate_rule_handles_ligatures_page_markers_rupiah_cents_and_iso_date():
    chunk = {
        "chunk_id": "v2fix1",
        "domain": "A2_PPH_BADAN",
        "document_id": "PMK-2023-164",
        "source_locator": "PMK-2023-164#BT/1",
        "text": (
            "Bukti Pemotongan Uniﬁkasi untuk Undang- Undang ini berlaku sebelum tanggal 1 Januari 2024 "
            "- 34 - sebesar Rp54.000.000,00 dan Rp4.800.000.000,00 atau l,75oh serta 1.500,00, 600/o, RpS00.000.000,00."
        ),
    }
    rule = {
        "rule_type": "rate",
        "condition": [
            {"attribute": "tgl", "operator": "<", "value": "2024-01-01", "raw": "sebelum tanggal 1 Januari 2024"},
            {"attribute": "omzet", "operator": "<=", "value": "Rp4.800.000.000,00", "raw": "Rp4.800.000.000,00,00"},
            {"attribute": "batas", "operator": "<=", "value": "Rp500.000.000,00", "raw": "RpS00.000.000,00"},
        ],
        "obligation": [], "right": [], "prohibition": [], "exception": [],
        "rate_or_value": [
            {"value": "54000000", "unit": "rupiah", "raw": "Rp54.000.000,00"},
            {"value": "1,75", "unit": "%", "raw": "1,75%"},
            {"value": "1,500.00", "unit": "USD", "raw": "1,500.00"},
            {"value": "600/o", "unit": "%", "raw": "600/o"},
        ],
        "cross_references": [],
        "source_quote": (
            "Bukti Pemotongan Unifikasi untuk Undang-Undang ini berlaku sebelum tanggal 1 Januari 2024 "
            "sebesar Rp54.000.000,00 dan Rp4.800.000.000,00 atau 1,75% serta 1.500,00, 60%, Rp500.000.000,00."
        ),
        "confidence": 0.95,
    }
    status, errs, _ = validate_rule(rule, chunk)
    assert errs == []
    assert status == "REVIEW_REQUIRED"


def test_validate_rule_routes_ocr_space_split_to_review():
    chunk = {
        "chunk_id": "sp1",
        "domain": "FASILITAS_SEKTOR",
        "document_id": "PMK-2020-237",
        "source_locator": "PMK-2020-237#BT/3",
        "text": "Badan U saha atau Pelaku U saha wajib melalui SINSW.",
    }
    rule = {
        "rule_type": "obligation",
        "condition": [], "obligation": ["Melalui SINSW"], "right": [],
        "prohibition": [], "exception": [], "rate_or_value": [], "cross_references": [],
        "source_quote": "Badan Usaha atau Pelaku Usaha wajib melalui SINSW.",
        "confidence": 0.95,
    }
    status, errs, reasons = validate_rule(rule, chunk)
    assert errs == []
    assert status == "REVIEW_REQUIRED"
    assert "quote_whitespace_ocr_diff" in reasons


def test_validate_staging_quarantines_corrupt_per_djp_2015_17():
    bad_chunk = {
        "chunk_id": "badsrc1",
        "domain": "PPH_OP_POTPUT",
        "document_id": "PER-DJP-2015-17",
        "source_locator": "PER-DJP-2015-17#BT/66",
        "text": "Dalam Peraturan Daerah ini tentang Kabupaten Pangandaran.",
    }
    res = [{
        "chunk_id": "badsrc1",
        "parsed_output": {
            "found": True,
            "rules": [{
                "rule_type": "obligation",
                "condition": [], "obligation": ["Uji"], "right": [],
                "prohibition": [], "exception": [], "rate_or_value": [], "cross_references": [],
                "source_quote": "Dalam Peraturan Daerah ini tentang Kabupaten Pangandaran.",
                "confidence": 0.9,
            }],
        },
    }]
    rules, rev, rep = validate_staging_results(res, {"badsrc1": bad_chunk})
    assert rules == []
    assert rev == []
    assert rep["counts"]["QUARANTINED_SOURCE"] == 1
    assert rep["quarantined_docs"] == ["PER-DJP-2015-17"]
