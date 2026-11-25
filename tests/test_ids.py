# -*- coding: utf-8 -*-
"""Tes normalisasi document_id dan locator (src/ids.py) — spec 5.1.

Kasus uji diambil dari contoh nyata yang tertulis di spec (Bagian 5.1 dan Fase 0).
Bisa dijalankan lewat pytest ATAU langsung:  python3 tests/test_ids.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ids import (
    CODE_TO_PART,
    JENIS_KNOWN,
    PART_TO_CODE,
    build_locator,
    is_canonical_document_id,
    normalize_document_id,
    parse_document_ref,
    parse_locator,
    part_from_code,
    part_to_code,
)


# ---------------------------------------------------------------------------
# document_id — kasus dari spec 5.1
# ---------------------------------------------------------------------------

def test_uu_no7_tahun_1983():
    d = parse_document_ref("UU No. 7 Tahun 1983")
    assert d == {
        "jenis": "UU",
        "tahun": 1983,
        "nomor_raw": "7",
        "nomor_norm": "7",
        "document_id": "UU-1983-7",
    }


def test_undang_undang_nomor_7_tahun_1983():
    d = parse_document_ref("Undang-Undang Nomor 7 Tahun 1983")
    assert d["document_id"] == "UU-1983-7"
    assert d["jenis"] == "UU"


def test_uu_dengan_judul_panjang():
    d = parse_document_ref(
        "Undang-Undang Nomor 6 Tahun 1983 tentang Ketentuan Umum dan Tata Cara Perpajakan"
    )
    assert d["document_id"] == "UU-1983-6"


def test_pp_no_55_2022():
    d = parse_document_ref("PP No. 55/2022")
    assert d == {
        "jenis": "PP",
        "tahun": 2022,
        "nomor_raw": "55/2022",
        "nomor_norm": "55",
        "document_id": "PP-2022-55",
    }


def test_peraturan_pemerintah_nomor_55_tahun_2022():
    d = parse_document_ref("Peraturan Pemerintah Nomor 55 Tahun 2022")
    assert d["document_id"] == "PP-2022-55"


def test_pmk_81_pmk03_2024():
    d = parse_document_ref("PMK-81/PMK.03/2024")
    assert d["document_id"] == "PMK-2024-81"
    assert d["nomor_norm"] == "81"
    assert d["nomor_raw"] == "PMK-81/PMK.03/2024"


def test_peraturan_menteri_keuangan_nomor_81():
    d = parse_document_ref("Peraturan Menteri Keuangan Nomor 81/PMK.03/2024")
    assert d["document_id"] == "PMK-2024-81"


def test_per_djp():
    d = parse_document_ref("PER-14/PJ/2013")
    assert d["document_id"] == "PER-DJP-2013-14"
    assert d["nomor_raw"] == "PER-14/PJ/2013"


def test_peraturan_dirjen_pajak_nomor_per():
    d = parse_document_ref("Peraturan Direktur Jenderal Pajak Nomor PER-14/PJ/2013")
    assert d["document_id"] == "PER-DJP-2013-14"


def test_putusan_mk():
    d = parse_document_ref("14/PUU-XX/2022")
    assert d["document_id"] == "PUTUSAN-MK-2022-14"
    assert d["nomor_raw"] == "14/PUU-XX/2022"


def test_putusan_mk_bentuk_panjang():
    d = parse_document_ref("Putusan Mahkamah Konstitusi Nomor 14/PUU-XX/2022")
    assert d["document_id"] == "PUTUSAN-MK-2022-14"


def test_perpu():
    d = parse_document_ref("Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022")
    assert d["document_id"] == "PERPU-2022-2"


def test_perpres():
    d = parse_document_ref("Peraturan Presiden Nomor 33 Tahun 2012")
    assert d["document_id"] == "PERPRES-2012-33"


def test_idempoten_canonical():
    for cid in ("UU-1983-7", "PP-2022-55", "PMK-2024-81", "PER-DJP-2013-14", "PUTUSAN-MK-2022-14"):
        assert normalize_document_id(cid) == cid


def test_idempoten_roundtrip():
    for raw in ("UU No. 7 Tahun 1983", "PP No. 55/2022", "PMK-81/PMK.03/2024", "PER-14/PJ/2013"):
        first = normalize_document_id(raw)
        assert first is not None
        assert normalize_document_id(first) == first


def test_is_canonical_document_id():
    assert is_canonical_document_id("UU-1983-7") is True
    assert is_canonical_document_id("UU No. 7 Tahun 1983") is False
    assert is_canonical_document_id("bukan-id") is False


# ---------------------------------------------------------------------------
# Kasus negatif (tidak boleh menebak)
# ---------------------------------------------------------------------------

def test_uu_penetapan_perpu():
    """Judul yang MENYEBUT Perpu lain harus tetap dikenali sebagai UU (posisi terawal)."""
    d = parse_document_ref(
        "UU No. 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti "
        "Undang-Undang Nomor 2 Tahun 2022"
    )
    assert d["document_id"] == "UU-2023-6"
    assert d["jenis"] == "UU"


def test_perpu_menyebut_uu_lain():
    d = parse_document_ref(
        "Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 "
        "tentang Cipta Kerja"
    )
    assert d["document_id"] == "PERPU-2022-2"


def test_uud_1945_ditolak():
    assert parse_document_ref("Undang-Undang Dasar Negara Republik Indonesia Tahun 1945") is None


def test_bukan_rujukan_peraturan():
    assert parse_document_ref("Pasal 17 ayat (1) huruf a") is None


def test_jenis_tidak_dikenal():
    # KEP bukan bagian JENIS_KNOWN -> None (pemanggil menandai NEEDS_REVIEW).
    assert parse_document_ref("KEP-DJP-2015-7") is None


def test_teks_kosong():
    assert parse_document_ref("") is None
    assert normalize_document_id("   ") is None


# ---------------------------------------------------------------------------
# locator — spec 5.1
# ---------------------------------------------------------------------------

def test_build_locator_lengkap():
    loc = build_locator("UU-1983-7", "BT", "17", "1", "a")
    assert loc == "UU-1983-7#BT/17/1/a"


def test_build_locator_pasal_saja():
    assert build_locator("UU-1983-7", "BT", "17") == "UU-1983-7#BT/17"


def test_build_locator_pasal_sisipan_4a():
    assert build_locator("UU-1983-6", "BT", "4A") == "UU-1983-6#BT/4A"


def test_build_locator_penjelasan():
    assert build_locator("UU-1983-7", "PENJELASAN", "17", "1") == "UU-1983-7#PJ/17/1"


def test_build_locator_pasal_wajib():
    try:
        build_locator("UU-1983-7", "BT")
        assert False, "harusnya ValueError"
    except ValueError:
        pass


def test_part_mapping():
    assert part_to_code("BATANG_TUBUH") == "BT"
    assert part_to_code("PENJELASAN") == "PJ"
    assert part_to_code("BT") == "BT"
    assert part_from_code("PJ") == "PENJELASAN"
    assert part_from_code("XX") is None
    assert PART_TO_CODE == {"BATANG_TUBUH": "BT", "PENJELASAN": "PJ"}
    assert CODE_TO_PART == {"BT": "BATANG_TUBUH", "PJ": "PENJELASAN"}


def test_parse_locator_roundtrip():
    loc = build_locator("UU-1983-7", "BT", "17", "1", "a")
    d = parse_locator(loc)
    assert d == {
        "document_id": "UU-1983-7",
        "part_code": "BT",
        "part": "BATANG_TUBUH",
        "pasal": "17",
        "ayat": "1",
        "huruf": "a",
        "angka": None,
    }


def test_parse_locator_minimal():
    d = parse_locator("UU-1983-7#BT/17")
    assert d["pasal"] == "17"
    assert d["ayat"] is None and d["huruf"] is None and d["angka"] is None


def test_parse_locator_pasal_4a():
    assert parse_locator("UU-1983-6#BT/4A")["pasal"] == "4A"


def test_parse_locator_invalid():
    assert parse_locator("bukan locator") is None
    assert parse_locator("UU-1983-7#BT") is None  # tanpa pasal
    assert parse_locator("UU-1983-7#XX/17") is None  # part tidak dikenal


def test_jenis_known_sesuai_spec():
    assert JENIS_KNOWN == (
        "UU", "PERPU", "PP", "PERPRES", "PMK", "PER-DJP", "SE-DJP", "KMK", "PUTUSAN-MK",
    )


def _main():
    import traceback

    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
        except Exception:
            failed += 1
            print(f"ERROR {name}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} lulus")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _main()
