# -*- coding: utf-8 -*-
"""Tes parser halaman BPK dan normalisasi relasi (src/crawl.py) — fixture nyata Fase 1."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.crawl import (
    BpkDetailParser,
    normalize_relation_label,
    page_document_id,
    parse_date_id,
    relation_to_active_form,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RELATION_MAP = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "config" / "relation_map.yaml").read_text(encoding="utf-8")
)


def _html(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# tanggal
# ---------------------------------------------------------------------------

def test_parse_date_id():
    assert parse_date_id("29 Oktober 2021") == "2021-10-29"
    assert parse_date_id("01 Januari 1984") == "1984-01-01"
    assert parse_date_id("8 Juni 2018") == "2018-06-08"
    assert parse_date_id("") is None
    assert parse_date_id("bukan tanggal") is None


# ---------------------------------------------------------------------------
# normalisasi label relasi
# ---------------------------------------------------------------------------

def test_label_passive_diubah():
    n = normalize_relation_label("Diubah dengan :", RELATION_MAP)
    assert n["internal"] == "MENGUBAH"
    assert n["direction"] == "passive"


def test_label_active_mengubah():
    n = normalize_relation_label("Mengubah :", RELATION_MAP)
    assert n["internal"] == "MENGUBAH"
    assert n["direction"] == "active"


def test_label_mencabut_sebagian():
    n = normalize_relation_label("Mencabut sebagian", RELATION_MAP)
    assert n["internal"] == "MENCABUT"
    assert n["direction"] == "active"
    assert n["note"] == "sebagian"


def test_label_tidak_dikenal():
    assert normalize_relation_label("Entah apa", RELATION_MAP) is None


# ---------------------------------------------------------------------------
# parser halaman BPK (fixture nyata)
# ---------------------------------------------------------------------------

def test_parse_metadata_hpp():
    page = BpkDetailParser().parse(_html("bpk__UU-2021-7__detail.html"), "http://x")
    meta = page["meta"]
    assert meta["Nomor"] == "7"
    assert meta["Tahun"] == "2021"
    assert meta["Bentuk Singkat"] == "UU"
    assert meta["Status"] == "Berlaku"
    assert meta["Subjek"] == "PERPAJAKAN"
    assert "Harmonisasi Peraturan Perpajakan" in meta["Judul"]
    assert meta["Tanggal Berlaku"] == "29 Oktober 2021"


def test_parse_relations_hpp():
    page = BpkDetailParser().parse(_html("bpk__UU-2021-7__detail.html"), "http://x")
    rels = page["relations"]
    labels = {r["label"] for r in rels}
    assert "Diubah dengan" in labels
    assert "Mengubah" in labels
    diubah = [r for r in rels if r["label"] == "Diubah dengan"]
    assert any("UU No. 6 Tahun 2023" in r["text"] for r in diubah)
    mengubah = [r for r in rels if r["label"] == "Mengubah"]
    teks = " | ".join(r["text"] for r in mengubah)
    assert "UU No. 6 Tahun 1983" in teks
    assert "UU No. 7 Tahun 1983" in teks
    assert "UU No. 8 Tahun 1983" in teks


def test_parse_pdf_links():
    page = BpkDetailParser().parse(_html("bpk__UU-2021-7__detail.html"), "http://x")
    assert any("/Download/" in u for u in page["pdf_links"])


def test_page_document_id_dari_judul():
    hpp = BpkDetailParser().parse(_html("bpk__UU-2021-7__detail.html"), "http://x")
    kup = BpkDetailParser().parse(_html("bpk__UU-1983-6__detail.html"), "http://x")
    pp23 = BpkDetailParser().parse(_html("bpk__PP-2018-23__detail.html"), "http://x")
    assert page_document_id(hpp["meta"])[0] == "UU-2021-7"
    assert page_document_id(kup["meta"])[0] == "UU-1983-6"
    assert page_document_id(pp23["meta"])[0] == "PP-2018-23"


def test_page_uu_2023_6_penetapan_perpu():
    """Regresi: halaman UU penetapan PERPU tidak boleh salah jadi PERPU."""
    page = BpkDetailParser().parse(_html("bpk__UU-2023-6__detail.html"), "http://x")
    doc_id, jenis, _ = page_document_id(page["meta"])
    assert doc_id == "UU-2023-6"
    assert jenis == "UU"


def test_label_menetapkan_perpu():
    n = normalize_relation_label("Menetapkan", RELATION_MAP)
    assert n["internal"] == "MENETAPKAN_PERPU"
    assert n["direction"] == "active"


def test_label_dicabut_sebagian_dengan():
    n = normalize_relation_label("Dicabut sebagian dengan", RELATION_MAP)
    assert n["internal"] == "MENCABUT"
    assert n["direction"] == "passive"
    assert n["note"] == "sebagian"


def test_page_pp_2018_23_relation_cabut():
    """PP-2018-23: blok relasi berisi 'Dicabut dengan' -> PP-2022-55 (pasif)."""
    page = BpkDetailParser().parse(_html("bpk__PP-2018-23__detail.html"), "http://x")
    assert page["meta"]["Status"] == "Tidak Berlaku"
    labels = {r["label"] for r in page["relations"]}
    assert "Dicabut dengan" in labels
    dicabut = [r for r in page["relations"] if r["label"] == "Dicabut dengan"]
    assert any("PP No. 55 Tahun 2022" in r["text"] for r in dicabut)
    mencabut = [r for r in page["relations"] if r["label"] == "Mencabut"]
    assert any("PP No. 46 Tahun 2013" in r["text"] for r in mencabut)


# ---------------------------------------------------------------------------
# bentuk aktif relasi
# ---------------------------------------------------------------------------

def test_bentuk_aktif_passive_dibalik():
    norm = {"label_raw": "Diubah dengan :", "internal": "MENGUBAH",
            "direction": "passive", "note": None}
    rel = relation_to_active_form("UU-2021-7", "UU-2023-6", "UU No. 6 Tahun 2023 ...",
                                  norm, "SOURCE_METADATA", "http://x")
    assert rel["from_document_id"] == "UU-2023-6"   # B mengubah A
    assert rel["to_document_id"] == "UU-2021-7"
    assert rel["relation_type"] == "MENGUBAH"


def test_bentuk_aktif_active_langsung():
    norm = {"label_raw": "Mengubah :", "internal": "MENGUBAH",
            "direction": "active", "note": None}
    rel = relation_to_active_form("UU-2021-7", "UU-1983-7", "UU No. 7 Tahun 1983 ...",
                                  norm, "SOURCE_METADATA", "http://x")
    assert rel["from_document_id"] == "UU-2021-7"
    assert rel["to_document_id"] == "UU-1983-7"
    assert rel["relation_type"] == "MENGUBAH"


def test_bentuk_aktif_mencabut_sebagian_catat_label():
    norm = {"label_raw": "Mencabut sebagian", "internal": "MENCABUT",
            "direction": "active", "note": "sebagian"}
    rel = relation_to_active_form("PP-2022-55", "PP-2018-23", "PP No. 23 Tahun 2018",
                                  norm, "SOURCE_METADATA", "http://x")
    assert rel["relation_type"] == "MENCABUT"
    assert "Mencabut sebagian" in rel["evidence"]


def _main():
    import traceback

    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"ERROR {name}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} lulus")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _main()
