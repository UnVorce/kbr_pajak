# -*- coding: utf-8 -*-
"""Tes konsolidasi-lite (src/consolidate.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.consolidate import (  # noqa: E402
    consolidate,
    extract_instructions,
    fix_ocr_rates,
    natural_key,
    parse_item,
    scope_target,
    split_top_level_pasals,
)


def test_natural_key():
    ks = sorted(["10", "2", "4A", "1"], key=natural_key)
    assert ks == ["1", "2", "4A", "10"]


def test_parse_item_ubah_pasal():
    item = ('Ketentuan Pasal 2 diubah, sehingga keseluruhan Pasal 2 berbunyi '
            'sebagai berikut:\n"Pasal 2\n(1) Isi baru pasal 2.\n"')
    ins = parse_item(item, "UU-2000-1", "UU-1983-6")
    assert ins["action"] == "UBAH"
    assert ins["target"] == "2"
    assert "Isi baru pasal 2" in ins["new_text"]
    assert "Pasal 2" not in ins["new_text"]  # heading dibuang
    assert ins["ayat_level"] is False
    assert ins["target_doc"] == "UU-1983-6"


def test_parse_item_hapus():
    ins = parse_item("Pasal 5 dihapus.", "X", "Y")
    assert ins["action"] == "HAPUS"
    assert ins["target"] == "5"


def test_parse_item_sisip():
    item = ('Di antara Pasal 2 dan Pasal 3 disisipkan 1 (satu) pasal, yakni '
            'Pasal 2A yang berbunyi sebagai berikut:\n"Pasal 2A\nIsi sisipan.\n"')
    ins = parse_item(item, "X", "Y")
    assert ins["action"] == "SISIP"
    assert ins["target"] == "2A"
    assert ins["insert_after"] == "2"
    assert ins["insert_before"] == "3"
    assert "Isi sisipan" in ins["new_text"]


def test_parse_item_ayat_level_ditandai():
    item = ('Ketentuan ayat (2) dan ayat (3) Pasal 9 diubah sehingga berbunyi '
            'sebagai berikut:\n(2) A.\n(3) B.\n')
    ins = parse_item(item, "X", "Y")
    assert ins["ayat_level"] is True


def test_parse_item_scope_omnibus():
    item = ('Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 1983 tentang '
            'Ketentuan Umum dan Tata Cara Perpajakan diubah sebagai berikut:\n'
            '1. Ketentuan Pasal 1 diubah sehingga keseluruhan Pasal 1 berbunyi '
            'sebagai berikut:\n"Pasal 1\nBaru.\n"')
    ins = parse_item(item, "UU-2021-7", None)
    assert ins["target_doc"] == "UU-1983-6"


def test_extract_instructions_roman():
    provs = [
        {"level": "PASAL", "nomor": "I", "text":
         "Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 1983 diubah sebagai berikut:\n"
         "1. Ketentuan Pasal 1 diubah sehingga keseluruhan Pasal 1 berbunyi sebagai berikut:\n"
         '"Pasal 1\nIsi baru.\n"\n'
         "2. Pasal 2 dihapus.\n"},
        {"level": "PASAL", "nomor": "II", "text": "Undang-undang ini mulai berlaku."},
    ]
    out = extract_instructions("UU-1994-9", provs)
    assert len(out) == 2
    assert out[0]["target_doc"] == "UU-1983-6"
    assert out[1]["action"] == "HAPUS"


def test_consolidate_chain(tmp_path):
    docs = tmp_path / "docs"
    outd = tmp_path / "out"
    docs.mkdir()
    target = {"document_id": "UU-1983-6",
              "provisions": [
                  {"level": "PASAL", "nomor": "1", "text": "Asli 1."},
                  {"level": "PASAL", "nomor": "2", "text": "Asli 2."},
                  {"level": "PASAL", "nomor": "3", "text": "Asli 3."},
              ]}
    amending = {"document_id": "UU-1994-9",
                "provisions": [
                    {"level": "PASAL", "nomor": "I", "text":
                     "Beberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 1983 diubah sebagai berikut:\n"
                     "1. Ketentuan Pasal 2 diubah sehingga keseluruhan Pasal 2 berbunyi sebagai berikut:\n"
                     '"Pasal 2\nIsi baru pasal 2.\n"\n'
                     "2. Di antara Pasal 2 dan Pasal 3 disisipkan 1 (satu) pasal, yakni Pasal 2A "
                     'yang berbunyi sebagai berikut:\n"Pasal 2A\nIsi sisipan 2A.\n"\n'
                     "3. Pasal 1 dihapus.\n"},
                ]}
    (docs / "UU-1983-6.json").write_text(json.dumps(target), encoding="utf-8")
    (docs / "UU-1994-9.json").write_text(json.dumps(amending), encoding="utf-8")
    res = consolidate("UU-1983-6", ["UU-1994-9"], docs, outd)
    nomors = [p["nomor"] for p in res["provisions"]]
    assert nomors == ["2", "2A", "3"]
    texts = {p["nomor"]: p["text"] for p in res["provisions"]}
    assert "Isi baru pasal 2" in texts["2"]
    assert "Isi sisipan 2A" in texts["2A"]
    assert res["applied_count"] == 3
    assert res["unparsed_count"] == 0


def test_scope_target_ocr_fallback():
    t = ("Beberapa ketentuan dalam Undang-Undang Nomor T Tahun 1983 tentang "
         "Pajak Penghasilan diubah sebagai berikut:")
    assert scope_target(t) == "UU-1983-7"


def test_fix_ocr_rates():
    assert fix_ocr_rates("tarif 5o/o dan l5% sampai Rp25O.000.000,0O") == (
        "tarif 5% dan 15% sampai Rp250.000.000,00"
    )


def test_split_top_level_pasals_omnibus():
    raw = (
        "Pasal 1\nAsas.\n"
        "Pasal 2\nBeberapa ketentuan dalam Undang-Undang Nomor 6 Tahun 1983 diubah:\n"
        "1. Ketentuan Pasal 1 diubah:\nPasal 1\nKutipan pasal 1.\n"
        "Pasal 3\nBeberapa ketentuan dalam Undang-Undang Nomor 7 Tahun 1983 diubah:\n"
        "1. Ketentuan Pasal 4 diubah:\nPasal 4\nKutipan pasal 4.\n"
        "Pasal 4\nBeberapa ketentuan dalam Undang-Undang Nomor 8 Tahun 1983 diubah:\n"
        "Isi pasal 4.\n"
        "PENJELASAN\nPasal 1\nCukup jelas.\n"
    )
    blocks = split_top_level_pasals(raw)
    assert [b["nomor"] for b in blocks] == ["1", "2", "3", "4"]
    assert "Kutipan pasal 1" in blocks[1]["text"]
    assert "Kutipan pasal 4" in blocks[2]["text"]


def test_multi_sisip_and_before_sisip(tmp_path):
    docs = tmp_path / "docs"
    outd = tmp_path / "out"
    docs.mkdir()
    target = {"document_id": "UU-1983-8",
              "provisions": [
                  {"level": "PASAL", "nomor": "16", "text": "Asli 16."},
                  {"level": "PASAL", "nomor": "17", "text": "Asli 17."},
              ]}
    amending = {"document_id": "UU-1994-11",
                "provisions": [
                    {"level": "PASAL", "nomor": "I", "text":
                     "Beberapa ketentuan dalam Undang-Undang Nomor 8 Tahun 1983 diubah:\n"
                     "1. Menambah 2 (dua) ketentuan baru di antara Pasal 16 dan Pasal 17 "
                     "yang dijadikan Pasal 16A dan Pasal 16B, yang masing-masing berbunyi berikut:\n"
                     '"Pasal 16A\nIsi 16A.\n"\n"Pasal 16B\nIsi 16B.\n"\n'
                     "2. Sebelum Pasal 17 dalam BAB V disisipkan 1 (satu) pasal, yakni Pasal 16C "
                     'yang berbunyi sebagai berikut:\n"Pasal 16C\nIsi 16C.\n"'},
                ]}
    (docs / "UU-1983-8.json").write_text(json.dumps(target), encoding="utf-8")
    (docs / "UU-1994-11.json").write_text(json.dumps(amending), encoding="utf-8")
    res = consolidate("UU-1983-8", ["UU-1994-11"], docs, outd)
    assert [p["nomor"] for p in res["provisions"]] == ["16", "16A", "16B", "16C", "17"]


def test_nested_amendment_outer_and_inner(tmp_path):
    docs = tmp_path / "docs"
    outd = tmp_path / "out"
    docs.mkdir()
    pmk81 = {"document_id": "PMK-2024-81",
             "provisions": [{"level": "PASAL", "nomor": "343", "text": "Lama 343."}]}
    pmk11 = {"document_id": "PMK-2025-11",
             "provisions": [{"level": "PASAL", "nomor": "20", "text": "Lama 20."}]}
    pmk53 = {"document_id": "PMK-2025-53",
             "judul": "Perubahan atas Peraturan Menteri Keuangan Nomor 11 Tahun 2025",
             "provisions": [{"level": "PASAL", "nomor": "I", "text":
                 "Ketentuan Pasal 20 dalam Peraturan Menteri Keuangan Nomor 11 Tahun 2025 "
                 "diubah sehingga berbunyi sebagai berikut:\n"
                 "Pasal 20\n"
                 "Beberapa ketentuan dalam Peraturan Menteri Keuangan Nomor 81 Tahun 2024 "
                 "diubah sebagai berikut:\n"
                 "1. Pasal 343 dihapus.\n"}]}
    (docs / "PMK-2024-81.json").write_text(json.dumps(pmk81), encoding="utf-8")
    (docs / "PMK-2025-11.json").write_text(json.dumps(pmk11), encoding="utf-8")
    (docs / "PMK-2025-53.json").write_text(json.dumps(pmk53), encoding="utf-8")
    r81 = consolidate("PMK-2024-81", ["PMK-2025-53"], docs, outd)
    assert [p["nomor"] for p in r81["provisions"]] == []
    r11 = consolidate("PMK-2025-11", ["PMK-2025-53"], docs, outd)
    assert r11["applied_count"] == 1
    assert "343 dihapus" in r11["provisions"][0]["text"]


def test_cross_doc_partial_revocation(tmp_path):
    docs = tmp_path / "docs"
    outd = tmp_path / "out"
    docs.mkdir()
    pp94 = {"document_id": "PP-2010-94",
            "provisions": [
                {"level": "PASAL", "nomor": "2", "text": "Tetap 2."},
                {"level": "PASAL", "nomor": "2A", "text": "Dicabut 2A."},
            ]}
    pp55 = {"document_id": "PP-2022-55",
            "provisions": [{"level": "PASAL", "nomor": "72", "text":
                "Pada saat PP ini mulai berlaku: "
                "b. ketentuan Pasal 2A Peraturan Pemerintah Nomor 94 Tahun 2O1O "
                "dicabut dan dinyatakan tidak berlaku;"}]}
    (docs / "PP-2010-94.json").write_text(json.dumps(pp94), encoding="utf-8")
    (docs / "PP-2022-55.json").write_text(json.dumps(pp55), encoding="utf-8")
    res = consolidate("PP-2010-94", ["PP-2022-55"], docs, outd)
    assert [p["nomor"] for p in res["provisions"]] == ["2"]
    assert res["applied_count"] == 1


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
