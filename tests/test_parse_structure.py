# -*- coding: utf-8 -*-
"""Tes parser struktur S4 (src/parse_structure.py) — teks sintetis."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.parse_structure import parse_document  # noqa: E402


def _pasal(r):
    return [p for p in r["provisions"] if p["level"] == "PASAL"]


def test_numeric_dasar():
    t = ("JUDUL\n\nBAB I\nKETENTUAN UMUM\nPasal 1\nYang dimaksud dengan:\n"
         "Pasal 2\n(1) Isi ayat satu.\n(2) Isi ayat dua.\nPasal 3\nIsi.\n")
    r = parse_document("UU-2000-1", t)
    assert r["structure"] == "NUMERIC"
    pasal = _pasal(r)
    assert [p["nomor"] for p in pasal] == ["1", "2", "3"]
    assert pasal[0]["role"] == "DEFINITION"
    ayat = [p for p in r["provisions"] if p["level"] == "AYAT"]
    assert [a["locator"] for a in ayat] == ["UU-2000-1#BT/2/1", "UU-2000-1#BT/2/2"]
    assert pasal[1]["section"] is not None  # BAB I menempel


def test_huruf_dan_angka():
    t = ("Pasal 1\n(1) Ketentuan:\na. huruf a;\n  1. angka satu;\n  2. angka dua;\n"
         "b. huruf b.\n(2) Ayat dua.\n")
    r = parse_document("UU-2000-1", t)
    huruf = [p for p in r["provisions"] if p["level"] == "HURUF"]
    angka = [p for p in r["provisions"] if p["level"] == "ANGKA"]
    assert [h["nomor"] for h in huruf] == ["a", "b"]
    assert [a["locator"] for a in angka] == ["UU-2000-1#BT/1/1/a/1", "UU-2000-1#BT/1/1/a/2"]


def test_amending_roman_inline():
    t = ("PERATURAN ... TENTANG PERUBAHAN ...\n"
         "Pasal I\n1. Ketentuan Pasal 1 diubah sehingga berbunyi sebagai berikut:\n"
         '"Pasal 1\nBaru.\n"\n'
         "dikembalikan. Pasal II Undang-undang ini mulai berlaku pada tanggal diundangkan.\n")
    r = parse_document("UU-2000-2", t)
    assert r["structure"] == "AMENDING_ROMAN"
    pasal = _pasal(r)
    assert [p["nomor"] for p in pasal] == ["I", "II"]
    assert pasal[0]["role"] == "AMENDING_INSTRUCTION"
    assert pasal[1]["role"] == "EFFECTIVITY"


def test_rujukan_mengingat_tidak_jadi_pasal():
    t = ("Mengingat:\n1. Pasal 5 ayat (1), Pasal 20 ayat (1) UUD 1945;\n"
         "Pasal 20\nayat (1)\nPasal 1\nIsi pasal 1.\nPasal 2\nIsi pasal 2.\n")
    r = parse_document("UU-2000-1", t)
    pasal = _pasal(r)
    assert [p["nomor"] for p in pasal] == ["1", "2"]


def test_penjelasan_dipisah():
    t = ("Pasal 1\nIsi.\n\nPENJELASAN ATAS UNDANG-UNDANG NOMOR 1 TAHUN 2000\n"
         "PASAL DEMI PASAL\nPasal 1\nCukup jelas.\n")
    r = parse_document("UU-2000-1", t)
    assert len(_pasal(r)) == 1
    assert any(a["locator"] == "UU-2000-1#PJ/1" for a in r["penjelasan_articles"])


def test_sisipan_4a():
    t = ("Pasal 1\nA.\nPasal 2\nB.\nPasal 3\nC.\n"
         "Pasal 4\nIsi 4.\nPasal 4A\nIsi 4A.\nPasal 5\nIsi 5.\n")
    r = parse_document("UU-2000-1", t)
    assert [p["nomor"] for p in _pasal(r)] == ["1", "2", "3", "4", "4A", "5"]


def test_teks_tanpa_struktur():
    r = parse_document("XX-2000-1", "Teks bebas tanpa Pasal.\n")
    assert r["structure"] == "UNKNOWN"
    assert r["provisions"] == []


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
