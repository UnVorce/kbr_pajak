# -*- coding: utf-8 -*-
"""Unit test toolkit anotasi CBR (B4.1) — tanpa HermiT, cepat."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.build_risk_cbr as index_builder
from scripts.build_cbr_worksheet import select_cases
from scripts.validate_cbr_annotations import cohen_kappa, load_taxonomy, validate_rows

ROOT = Path(__file__).resolve().parents[1]


def _case(i: int, klaster: str, amar: str) -> dict:
    return {
        "case_id": f"C-{klaster}-{i:02d}",
        "klaster": klaster,
        "amar_kategori": amar,
        "putusan_nomor": f"PUT/{i}",
        "jenis_pajak": "PPh",
        "tahun_pajak": 2020,
        "pokok_sengketa": "Koreksi peredaran bruto",
        "pertimbangan_majelis": "bahwa koreksi peredaran bruto tidak dapat dibuktikan oleh Terbanding.",
        "cited_regulations": ["UU-1983-7"],
        "source": {"url": "https://example"},
    }


def test_select_cases_60_stratified():
    klas = ["pph_badan", "pph_potput", "kup_gugatan", "ppn", "kepabeanan_cukai", "pbb"]
    cases = []
    for k in klas:
        for i in range(12):
            amar = ["TOLAK", "KABUL_SEBAGIAN", "KABUL_SELURUHNYA"][i % 3]
            cases.append(_case(i, k, amar))
    sel = select_cases(cases, per_klaster=10)
    assert len(sel) == 60
    from collections import Counter
    per = Counter(c["klaster"] for c in sel)
    assert all(per[k] == 10 for k in klas)
    # deterministik
    assert [c["case_id"] for c in select_cases(cases, 10)] == [c["case_id"] for c in sel]


def _valid_row() -> dict:
    return {
        "case_id": "C-1",
        "klaster": "pph_badan",
        "amar_kategori_asal": "KABUL_SELURUHNYA",
        "pertimbangan_majelis": "bahwa koreksi peredaran bruto tidak dapat dibuktikan oleh Terbanding.",
        "jenis_koreksi": "KOR_OMZET;KOR_OMZET_EKUALISASI",
        "fakta_kunci": "FK_ADA_PEMBUKUAN;FK_REKONSILIASI_BANK",
        "rasio_decidendi": "koreksi peredaran bruto tidak dapat dibuktikan oleh Terbanding",
        "argumen_menang": "koreksi peredaran bruto tidak dapat dibuktikan",
        "bukti_penentu": "BUKTI_REKONSILIASI_BANK",
        "rezim_hukum": "AKTIF",
        "quotes_json": json.dumps([{"field": "rasio_decidendi", "halaman": 4, "quote": "koreksi peredaran bruto tidak dapat dibuktikan"}]),
        "catatan": "",
        "annotator": "PR",
        "reviewer": "D",
    }


def test_validate_rows_accepts_valid_and_rejects_errors():
    tax = load_taxonomy()
    good = _valid_row()
    pending = dict(good, case_id="C-2", jenis_koreksi="", fakta_kunci="", rasio_decidendi="",
                   argumen_menang="", bukti_penentu="", rezim_hukum="", quotes_json="",
                   catatan="", annotator="", reviewer="")

    errors, summary = validate_rows([good, pending], tax)
    assert errors == []
    assert summary == {**summary, "total": 2, "annotated": 1, "pending": 1, "errors": 0}

    bad_label = _valid_row() | {"case_id": "C-3", "jenis_koreksi": "KOR_TIDAK_ADA"}
    bad_quote = _valid_row() | {"case_id": "C-4", "rasio_decidendi": "kalimat yang tidak ada di pertimbangan"}
    bad_kabul = _valid_row() | {"case_id": "C-5", "argumen_menang": ""}
    only_parent = _valid_row() | {"case_id": "C-6", "jenis_koreksi": "KOR_OMZET"}
    errors, _ = validate_rows([bad_label, bad_quote, bad_kabul, only_parent], tax)
    msgs = [e["error"] for e in errors]
    assert any("tidak dikenal" in m for m in msgs)
    assert any("bukan substring" in m for m in msgs)
    assert any("argumen_menang wajib" in m for m in msgs)
    assert any("kode daun" in m for m in msgs)


def test_cohen_kappa():
    assert cohen_kappa(["1", "", "1"], ["1", "", "1"]) == 1.0
    assert cohen_kappa([], []) is None
    k = cohen_kappa(["1", "", "1", ""], ["", "1", "", "1"])
    assert k is not None and k < 0.1


def test_build_cbr_index_merges_annotations(tmp_path, monkeypatch):
    jdir = tmp_path / "juris"
    jdir.mkdir()
    (jdir / "c1.json").write_text(json.dumps(_case(1, "pph_badan", "TOLAK")), encoding="utf-8")

    ann = {
        "version": "1.0",
        "annotations": {
            "C-pph_badan-01": {
                "jenis_koreksi": ["KOR_OMZET_EKUALISASI"],
                "fakta_kunci": ["FK_ADA_PEMBUKUAN"],
                "rasio_decidendi": "koreksi peredaran bruto tidak dapat dibuktikan",
                "argumen_menang": "",
                "bukti_penentu": ["BUKTI_PEMBUKUAN"],
            }
        },
    }
    apath = tmp_path / "annotations_v1.json"
    apath.write_text(json.dumps(ann), encoding="utf-8")

    monkeypatch.setattr(index_builder, "JURIS", jdir)
    monkeypatch.setattr(index_builder, "ANNOTATIONS", apath)
    idx = index_builder.build_cbr_index()
    assert idx["total"] == 1
    assert idx["annotated_cases"] == 1
    assert idx["cases"][0]["jenis_koreksi"] == ["KOR_OMZET_EKUALISASI"]
    assert idx["cases"][0]["annotated"] is True
