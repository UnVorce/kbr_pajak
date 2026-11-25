# -*- coding: utf-8 -*-
"""Tes logika deterministik Fase 1 (scripts/fase1_korpus.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import (  # noqa: E402
    canon_doc,
    doc_id_from_filename,
)
from src.textutil import (  # noqa: E402
    cut_penjelasan,
    normalize_headings,
    roman_to_int,
    split_pasal,
)


# ---------------------------------------------------------------------------
# normalisasi nama file -> document_id
# ---------------------------------------------------------------------------

def test_nama_file_lama():
    assert doc_id_from_filename("6TAHUN1983UU.json") == "UU-1983-6"
    assert doc_id_from_filename("55TAHUN2022PP.json") == "PP-2022-55"
    assert doc_id_from_filename("101~PMK.010~2016Per.json") == "PMK-2016-101"
    assert doc_id_from_filename("56~PMK.03~2019Per.json") == "PMK-2019-56"
    assert doc_id_from_filename("2024pmkeuangan081.json") == "PMK-2024-81"
    assert doc_id_from_filename("2026pmkeuangan06.json") == "PMK-2026-6"
    assert doc_id_from_filename("PER - 17.PJ_.2015.json") == "PER-DJP-2015-17"
    assert doc_id_from_filename("UU Nomor 42 Tahun 2009.json") == "UU-2009-42"
    assert doc_id_from_filename("Salinan UU Nomor 7 Tahun 2021.json") == "UU-2021-7"
    assert doc_id_from_filename("Buku Manual Coretax 2024 - Seri Pembayaran.json") is None
    assert doc_id_from_filename("Lampiran 1_PER - 17.PJ_.2015.json") is None


# ---------------------------------------------------------------------------
# potong penjelasan & normalisasi heading
# ---------------------------------------------------------------------------

def test_cut_penjelasan_heading_besar():
    t = "JUDUL\nBAB I\nPasal 1\nIsi.\nPENJELASAN ATAS UNDANG-UNDANG REPUBLIK INDONESIA\n...\n"
    batang, penj = cut_penjelasan(t)
    assert "PENJELASAN" in penj
    assert "PENJELASAN" not in batang


def test_cut_penjelasan_kecil_tidak_dipotong():
    t = "Pasal 1\nIsi penjelasan ayat (1) huruf d).\n"
    batang, penj = cut_penjelasan(t)
    assert penj == ""


def test_join_pasal_dan_nomor():
    t = "Awal\nPasal\n1\nIsi pasal 1.\n"
    assert "Pasal 1" in normalize_headings(t)


def test_ocr_fix_pasa1():
    t = "Awal\nPasa1 1\nIsi.\n"
    n = normalize_headings(t)
    assert "Pasal 1" in n


def test_roman_to_int():
    assert roman_to_int("I") == 1
    assert roman_to_int("II") == 2
    assert roman_to_int("IV") == 4
    assert roman_to_int("VI") == 6


# ---------------------------------------------------------------------------
# split_pasal
# ---------------------------------------------------------------------------

def test_split_numeric_lewati_rujukan():
    t = (
        "JUDUL\n\nMengingat:\n1. Pasal 5 ayat (1) UUD;\n"
        "Pasal 20\nayat (1) UUD;\n\n"
        "Pasal 1\nIsi pasal 1.\n"
        "Pasal 2\nIsi pasal 2.\n"
        "Pasal 7\nini rujukan ke pasal 7 di tengah teks.\n"
        "Pasal 3\nIsi pasal 3.\n"
    )
    pre, arts, struct = split_pasal(t)
    assert struct == "NUMERIC"
    assert [a["pasal"] for a in arts] == ["1", "2", "3"]
    assert "Isi pasal 2." in arts[1]["full_text"]


def test_split_numeric_dengan_sisipan_sufiks():
    t = ("Pasal 1\nA.\nPasal 2\nB.\nPasal 3\nC.\n"
         "Pasal 4\nD.\nPasal 4A\nE.\nPasal 5\nF.\n")
    _pre, arts, struct = split_pasal(t)
    assert struct == "NUMERIC"
    assert [a["pasal"] for a in arts] == ["1", "2", "3", "4", "4A", "5"]


def test_split_roman_amending():
    t = (
        "PERATURAN ... TENTANG PERUBAHAN ...\n"
        "Pasal I\nKetentuan Pasal 1 diubah sehingga berbunyi:\n"
        "Pasal II Undang-undang ini mulai berlaku pada tanggal diundangkan.\n"
    )
    _pre, arts, struct = split_pasal(t)
    assert struct == "AMENDING_ROMAN"
    assert [a["pasal"] for a in arts] == ["I", "II"]


def test_split_unknown():
    t = "Teks tanpa pasal sama sekali.\n"
    _pre, arts, struct = split_pasal(t)
    assert struct == "UNKNOWN"
    assert arts == []


def test_split_quoted_heading_diabaikan_pada_dokumen_amending():
    """Heading numerik dalam kutipan teks pengganti tidak boleh jadi artikel."""
    t = (
        "Pasal I\nKetentuan Pasal 2 diubah sehingga berbunyi sebagai berikut:\n"
        '"Pasal 2\nisi baru pasal 2\n"\n'
        "Pasal II Undang-undang ini mulai berlaku.\n"
    )
    _pre, arts, struct = split_pasal(t)
    assert struct == "AMENDING_ROMAN"
    assert [a["pasal"] for a in arts] == ["I", "II"]


# ---------------------------------------------------------------------------
# canon_doc
# ---------------------------------------------------------------------------

def test_canon_doc_minimal():
    rec = canon_doc("UU-1983-6", "UU", 1983, "Judul UU",
                    [{"pasal": "1", "full_text": "Isi."}],
                    {"origin": "corpus"})
    assert rec["document_id"] == "UU-1983-6"
    assert rec["articles"][0]["locator"] == "UU-1983-6#BT/1"
    assert rec["content_hash"]
    assert rec["quality"]["zero_pasal"] is False


def test_canon_doc_manual_tahun_none():
    rec = canon_doc("CORETAX-x", "MANUAL", None, "Manual", [], {"origin": "corpus"})
    assert rec["tahun"] is None
    assert rec["quality"]["zero_pasal"] is True


def test_normalize_headings_ocr_bullet_dot_nospace():
    t = "Pasal1\nA\n· Pasal 2\nB\nPasa13\nC\nPasal 4 . \nD"
    _pre, arts, struct = split_pasal(t)
    assert struct == "NUMERIC"
    assert [a["pasal"] for a in arts] == ["1", "2", "3", "4"]


def test_normalize_headings_pasall_roman():
    t = "Pasall\nBeberapa ketentuan diubah.\nPasal II\nBerlaku."
    _pre, arts, struct = split_pasal(t)
    assert struct == "AMENDING_ROMAN"
    assert [a["pasal"] for a in arts] == ["I", "II"]


def test_normalize_headings_ocr_digits_and_column_jump():
    t = (
        "Pasal 1\nA\nPasal 2\nB\nPasal 3\nC\n"
        "Pasal 5\nE\n"  # Pasal 4 hilang/tertukar, lanjut ke 5
        "Pasal 6\nF\nPasal 7\nG\nPasal 8\nH\nPasal 9\nI\n"
        "Pasal 1O\nJ\nPasal 1 1\nK\nPasal L2\nL\n"
    )
    _pre, arts, struct = split_pasal(t)
    assert struct == "NUMERIC"
    assert [a["pasal"] for a in arts] == ["1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12"]
    assert "Pasal 72" in normalize_headings("Pasal T2\n")
    assert "Pasal 21" in normalize_headings("Pasal 2 I\n")
    assert "Pasal 101" in normalize_headings("Pasal 1O1\n")


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
