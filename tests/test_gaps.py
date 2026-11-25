# -*- coding: utf-8 -*-
"""Tes S6 gap detector (src/gaps.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.gaps import (  # noqa: E402
    aggregate,
    collect,
    extract_citations,
    relations_from_titles,
    write_outputs,
)


def _doc(did, judul="", preamble="", text="", penjelasan="", jenis="UU"):
    return {
        "document_id": did,
        "jenis": jenis,
        "judul": judul,
        "preamble": preamble,
        "provisions": [{"level": "PASAL", "nomor": "1", "text": text}] if text else [],
        "penjelasan": penjelasan,
    }


def test_extract_full_short_and_slash_citations():
    d = _doc(
        "PMK-2025-1",
        preamble="Mengingat Undang-Undang Nomor 7 Tahun 1983 dan PMK 81/2024.",
        text=("Sesuai Peraturan Menteri Keuangan Nomor 130/PMK.010/2020 Tahun 2020 "
              "serta PER-17/PJ/2015 dan PP 55/2022."),
    )
    cits = extract_citations(d)
    got = {c["resolved_document_id"] for c in cits}
    assert {"UU-1983-7", "PMK-2024-81", "PMK-2020-130", "PER-DJP-2015-17", "PP-2022-55"} <= got


def test_extract_ocr_nomor_fix():
    d = _doc("UU-2021-7", text=("Pasal 21 berdasarkan Undang-Undang Nomor 2l Tahun 2020, "
                               "PP 4O/2015, PER-03/PJ/2022, dan 253/PMK03/2008."))
    got = {c["resolved_document_id"] for c in extract_citations(d)}
    assert "UU-2020-21" in got
    assert "PP-2015-40" in got
    assert "PER-DJP-2022-3" in got
    assert "PMK-2008-253" in got
    assert "PMK-2008-3" not in got


def test_collect_auto_detects_closing_revocations():
    docs = [
        _doc("PMK-2023-1", text="Mengacu PMK 99/2018."),
        {
            "document_id": "PMK-2024-81",
            "jenis": "PMK",
            "provisions": [
                {"level": "PASAL", "nomor": "483",
                 "text": ("Pada saat Peraturan Menteri ini mulai berlaku, "
                          "Peraturan Menteri Keuangan Nomor 99/PMK.03/2018 "
                          "dicabut dan dinyatakan tidak berlaku.")}
            ],
        },
    ]
    reg = {"PMK-2023-1": {}, "PMK-2024-81": {}}
    _, agg = collect(docs, reg)
    assert agg["PMK-2018-99"]["status"] == "RESOLVED_EQUIVALENT"
    assert agg["PMK-2018-99"]["equivalent_document_id"] == "PMK-2024-81"


def test_collect_ignores_self_citation_and_manual():
    docs = [
        _doc("PP-2015-40", preamble="PERATURAN PEMERINTAH NOMOR 40 TAHUN 2015 tentang Air Bersih",
             text="Mengacu Undang-Undang Nomor 8 Tahun 1983.", jenis="PP"),
        _doc("UU-1983-8", text="", jenis="UU"),
        _doc("MANUAL-1", text="Undang-Undang Nomor 99 Tahun 1999.", jenis="MANUAL"),
    ]
    reg = {"PP-2015-40": {}, "UU-1983-8": {}}
    cits, agg = collect(docs, reg)
    assert "PP-2015-40" not in agg  # kutipan diri sendiri diabaikan
    assert "UU-1999-99" not in agg  # dokumen MANUAL diabaikan
    assert agg["UU-1983-8"]["status"] == "RESOLVED"


def test_aggregate_all_terminal_and_unresolved_statuses():
    cits = [
        {"resolved_document_id": "UU-1983-7", "in_document_id": "PMK-2024-81",
         "parsed_jenis": "UU", "parsed_nomor": "7", "parsed_tahun": 1983,
         "context_type": "MENGINGAT", "citation_role": "REFERENCE"},
        {"resolved_document_id": "UU-2020-11", "in_document_id": "PMK-2024-81",
         "parsed_jenis": "UU", "parsed_nomor": "11", "parsed_tahun": 2020,
         "context_type": "MENGINGAT", "citation_role": "REFERENCE"},
        {"resolved_document_id": "UU-2011-12", "in_document_id": "UU-2021-7",
         "parsed_jenis": "UU", "parsed_nomor": "12", "parsed_tahun": 2011,
         "context_type": "MENGINGAT", "citation_role": "REFERENCE"},
        {"resolved_document_id": "UU-2003-13", "in_document_id": "UU-2023-6",
         "parsed_jenis": "UU", "parsed_nomor": "13", "parsed_tahun": 2003,
         "context_type": "BATANG_TUBUH", "citation_role": "AMENDMENT"},
        {"resolved_document_id": "PMK-2024-69", "in_document_id": "PMK-2024-81",
         "parsed_jenis": "PMK", "parsed_nomor": "69", "parsed_tahun": 2024,
         "context_type": "BATANG_TUBUH", "citation_role": "REFERENCE"},
        {"resolved_document_id": "PP-2099-1", "in_document_id": "PMK-2024-81",
         "parsed_jenis": "PP", "parsed_nomor": "1", "parsed_tahun": 2099,
         "context_type": "BATANG_TUBUH", "citation_role": "REFERENCE"},
    ]
    reg = {"UU-1983-7": {}, "UU-2023-6": {}}
    attempts = {"PMK-2024-69": {"reason": "tidak ditemukan di BPK", "attempts": [{"result": "404"}]}}
    agg = aggregate(cits, reg, attempts)
    assert agg["UU-1983-7"]["status"] == "RESOLVED"
    assert agg["UU-2020-11"]["status"] == "RESOLVED_EQUIVALENT"
    assert agg["UU-2011-12"]["status"] == "IGNORED_OUT_OF_SCOPE"
    assert agg["UU-2003-13"]["status"] == "DEFERRED_CK"
    assert agg["PMK-2024-69"]["status"] == "NOT_FOUND_AT_SOURCE"
    assert agg["PP-2099-1"]["status"] == "UNRESOLVED"


def test_relations_from_titles_and_write_outputs(tmp_path):
    docs = [
        _doc("PMK-2025-54", judul="Peraturan Menteri Keuangan Nomor 54 Tahun 2025 tentang "
             "Perubahan Ketiga atas Peraturan Menteri Keuangan Nomor 81 Tahun 2024", jenis="PMK"),
        _doc("PMK-2024-81", judul="PMK 81 Tahun 2024", jenis="PMK"),
    ]
    reg = {"PMK-2024-81": {}, "PMK-2025-54": {}}
    rels = relations_from_titles(docs, reg)
    assert len(rels) == 1
    assert rels[0]["from"] == "PMK-2025-54"
    assert rels[0]["to"] == "PMK-2024-81"

    cits, agg = collect(docs, reg)
    write_outputs(cits, agg, rels, tmp_path)
    assert (tmp_path / "citations.jsonl").exists()
    gaps = json.loads((tmp_path / "gaps.json").read_text(encoding="utf-8"))
    assert gaps["summary"]["by_status"]["RESOLVED"] == 1
    assert json.loads((tmp_path / "unresolved_citations.json").read_text(encoding="utf-8")) == []
