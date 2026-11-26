# -*- coding: utf-8 -*-
"""Unit test pembagian tugas anotasi CBR (B4.2)."""
from __future__ import annotations

from scripts.build_cbr_assignment import build_assignment


def _rows() -> list[dict]:
    klas = ["pph_badan", "pph_potput", "kup_gugatan", "ppn", "kepabeanan_cukai", "pbb"]
    out = []
    for k in klas:
        for i in range(10):
            out.append({
                "case_id": f"C-{k}-{i:02d}",
                "klaster": k,
                "amar_kategori_asal": ["TOLAK", "KABUL_SEBAGIAN", "KABUL_SELURUHNYA"][i % 3],
                "putusan_nomor": f"PUT/{k}/{i}",
            })
    return out


def test_assignment_counts_and_overlap():
    res = build_assignment(_rows())
    assert res["summary"]["total_kasus"] == 60
    assert len(res["A"]) == 38
    assert len(res["B"]) == 37
    assert len(res["overlap_ids"]) == 15

    ids_a = {r["case_id"] for r in res["A"]}
    ids_b = {r["case_id"] for r in res["B"]}
    assert len(ids_a | ids_b) == 60
    assert len(ids_a & ids_b) == 15
    assert set(res["overlap_ids"]) == ids_a & ids_b


def test_assignment_deterministic_and_roles():
    res1 = build_assignment(_rows())
    res2 = build_assignment(_rows())
    assert [r["case_id"] for r in res1["A"]] == [r["case_id"] for r in res2["A"]]

    for row in res1["A"] + res1["B"]:
        if row["case_id"] in res1["overlap_ids"]:
            assert row["is_overlap"] == "YA"
            assert row["peran"] in ("UTAMA", "OVERLAP")
        else:
            assert row["is_overlap"] == "TIDAK"
            assert row["peran"] == "UTAMA"
