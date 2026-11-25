# -*- coding: utf-8 -*-
"""Tes chunker T2_RULE (src/chunking.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.chunking import (  # noqa: E402
    chunk_pasal,
    is_table_like,
    make_chunk_id,
    normalize_ocr_text,
)


def test_short_pasal_stays_single_chunk():
    pr = {"locator": "UU-1983-8#BT/7", "nomor": "7", "role": "SUBSTANTIVE",
          "text": "(1) Tarif PPN 11%.\n(2) Ekspor 0%."}
    out = chunk_pasal(document_id="UU-1983-8", domain="B_PPN", judul="UU PPN",
                      source_kind="consolidated", pasal_row=pr, children_by_parent={})
    assert len(out) == 1
    assert out[0]["source_locator"] == "UU-1983-8#BT/7"
    assert out[0]["chunk_id"] == make_chunk_id(
        "UU-1983-8", "UU-1983-8#BT/7", normalize_ocr_text(pr["text"])
    )


def test_normalize_ocr_text():
    t = (
        "3Oo/o dan O,5% (l) (21 Rp60.000.000,0O "
        "Rpl00.000.000.000,00 lO% RpS.000.OO0.000,00 (21untuk "
        "www.jdih.kemenkeu.go.id MENTERI KEUANGAN REPUBLIK INDONESIA -3- "
        "SK No 096280 A PRESIDEN REPUBLIK INDONESIA -3-"
    )
    n = normalize_ocr_text(t)
    assert "30%" in n
    assert "0,5%" in n
    assert "(1)" in n
    assert "(2)" in n
    assert "(2) untuk" in n
    assert "Rp60.000.000,00" in n
    assert "Rp100.000.000.000,00" in n
    assert "10%" in n
    assert "Rp5.000.000.000,00" in n
    assert "jdih.kemenkeu.go.id" not in n
    assert "SK No" not in n
    assert "PRESIDEN REPUBLIK INDONESIA -3-" not in n


def test_is_table_like():
    table = "\n".join([
        "5% sampai dengan Rp60.000.000,00",
        "15% di atas Rp60.000.000,00",
        "25% di atas Rp250.000.000,00",
        "30% di atas Rp500.000.000,00",
        "35% di atas Rp5.000.000.000,00",
        "Tarif Pajak",
    ])
    assert is_table_like(table)
    wrapped_prose = "\n".join([
        "(1) Jenis Pajak provinsi sebagaimana",
        "dimaksud dalam Pasal 2 huruf a",
        "terdiri atas:",
        "a. PKB sesuai Pasal 3;",
        "b. BBNKB sesuai Pasal 4;",
        "c. PAB sesuai Pasal 5;",
        "(2) Pajak ditetapkan oleh Gubernur.",
    ])
    assert not is_table_like(wrapped_prose)
    assert not is_table_like("Kalimat biasa yang panjang. " * 10)


def test_chunk_membawa_rujukan_mk_dan_sema():
    pr = {"locator": "UU-2002-14#BT/5", "nomor": "5", "role": "SUBSTANTIVE",
          "text": "Pembinaan Pengadilan Pajak dilakukan oleh Departemen Keuangan."}
    out = chunk_pasal(
        document_id="UU-2002-14", domain="D_ADMIN_SANKSI", judul="UU Pengadilan Pajak",
        source_kind="consolidated", pasal_row=pr, children_by_parent={},
        review_refs={"mk": ["MK-2023-26-PUU-XXI"],
                     "sema": ["SEMA-2024-2-TUN-3"]},
    )
    assert out[0]["context"]["mk_review_refs"] == ["MK-2023-26-PUU-XXI"]
    assert out[0]["context"]["sema_tun_refs"] == ["SEMA-2024-2-TUN-3"]


def test_long_pasal_splits_by_ayat_never_mid_ayat():
    ay1 = "Ayat satu cukup panjang. " * 70
    ay2 = "Ayat dua juga panjang. " * 70
    pr = {"locator": "UU-1983-7#BT/17", "nomor": "17", "role": "SUBSTANTIVE",
          "text": f"Ketentuan tarif:\n(1) {ay1}\n(2) {ay2}"}
    children = {
        "UU-1983-7#BT/17": [
            {"level": "AYAT", "nomor": "1", "locator": "UU-1983-7#BT/17/1", "text": ay1},
            {"level": "AYAT", "nomor": "2", "locator": "UU-1983-7#BT/17/2", "text": ay2},
        ]
    }
    out = chunk_pasal(document_id="UU-1983-7", domain="A2_PPH_BADAN", judul="UU PPh",
                      source_kind="consolidated", pasal_row=pr, children_by_parent=children)
    assert len(out) == 2
    assert out[0]["source_locator"] == "UU-1983-7#BT/17/1"
    assert out[1]["source_locator"] == "UU-1983-7#BT/17/2"
    assert out[0]["text"].startswith("Ketentuan tarif:")
    assert "(1)" in out[0]["text"]
    assert "(2)" in out[1]["text"]


def test_trim_lampiran_and_split_long_leaf():
    pr = {"locator": "PMK-2024-118#BT/63", "nomor": "63", "role": "SUBSTANTIVE",
          "text": ("Ketentuan penutup berlaku sejak 1 Januari 2025.\n"
                   "Agar setiap orang mengetahuinya, memerintahkan pengundangan.\n"
                   "LAMPIRAN I\n(1) Contoh formulir panjang\n" + ("isi form " * 500))}
    out = chunk_pasal(document_id="PMK-2024-118", domain="D_ADMIN_SANKSI",
                      judul="PMK 118/2024", source_kind="consolidated",
                      pasal_row=pr, children_by_parent={})
    assert len(out) == 1
    assert "Contoh formulir panjang" not in out[0]["text"]
    assert out[0]["char_len"] < 200
