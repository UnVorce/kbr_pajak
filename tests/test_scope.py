# -*- coding: utf-8 -*-
"""Tes S2 gerbang relevansi (src/scope.py) — spec 6.2."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.scope import decide_scope, hierarchy_level, score_document

CARD = {
    "domain_id": "DOMAIN_A",
    "subject_hints": ["perpajakan"],
    "keyword_hints": ["pajak", "perpajakan", "PPh", "NPWP", "SPT"],
    "thresholds": {"auto_in": 0.80, "review_min": 0.40},
}


def test_pajak_lengkap_in_scope():
    meta = {"Judul": "Undang-undang (UU) Nomor 7 Tahun 1983 tentang Pajak Penghasilan",
            "Subjek": "PERPAJAKAN"}
    score, signals = score_document(meta, CARD, neighbor_in_scope=False)
    assert score == 0.9
    assert signals == {"subject_match": True, "keyword_match": True}
    assert decide_scope(score, CARD) == "IN_SCOPE"


def test_subjek_saja_undecided():
    meta = {"Judul": "Peraturan tentang Ketenagakerjaan", "Subjek": "PERPAJAKAN"}
    score, _ = score_document(meta, CARD)
    assert score == 0.7
    assert decide_scope(score, CARD) == "UNDECIDED"


def test_tanpa_sinyal_boundary():
    meta = {"Judul": "Peraturan Daerah tentang Jalan", "Subjek": "PEKERJAAN UMUM"}
    score, _ = score_document(meta, CARD)
    assert score == 0.0
    assert decide_scope(score, CARD) == "BOUNDARY"


def test_topik_keluar_diprioritaskan():
    """Dokumen PPN di luar lingkup DOMAIN_A -> BOUNDARY walau subjeknya pajak."""
    card = {**CARD, "exclude_keywords": ["pertambahan nilai", "PPN"]}
    meta = {"Judul": "Undang-undang (UU) Nomor 42 Tahun 2009 tentang Perubahan Ketiga "
                     "atas Undang-Undang Nomor 8 Tahun 1983 tentang Pajak Pertambahan "
                     "Nilai Barang dan Jasa dan Pajak Penjualan atas Barang Mewah",
            "Subjek": "PERPAJAKAN"}
    score, signals = score_document(meta, card, neighbor_in_scope=True)
    assert score == 0.0
    assert signals == {"exclude_match": True}
    assert decide_scope(score, card) == "BOUNDARY"


def test_relasi_ke_in_scope():
    meta = {"Judul": "Putusan ...", "Subjek": "KETENAGAKERJAAN"}
    score, signals = score_document(meta, CARD, neighbor_in_scope=True)
    assert score == 0.3
    assert signals == {"relation_to_in_scope": True}
    assert decide_scope(score, CARD) == "BOUNDARY"  # < review_min: dicatat, tak dijelajahi


def test_seed_selalu_in_scope():
    score = 0.0
    assert decide_scope(score, CARD, is_seed=True) == "IN_SCOPE"


def test_skor_dibatasi_1():
    meta = {"Judul": "Pajak Pajak Pajak", "Subjek": "PERPAJAKAN"}
    score, _ = score_document(meta, CARD, neighbor_in_scope=True)
    assert score == 1.0


def test_hierarchy_level():
    assert hierarchy_level("UU") == 1
    assert hierarchy_level("PERPU") == 1
    assert hierarchy_level("PUTUSAN-MK") == 1
    assert hierarchy_level("PP") == 2
    assert hierarchy_level("PERPRES") == 3
    assert hierarchy_level("PMK") == 4
    assert hierarchy_level("KMK") == 4
    assert hierarchy_level("PER-DJP") == 5
    assert hierarchy_level("SE-DJP") == 6
    assert hierarchy_level("TIDAK-DIKENAL") is None


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
