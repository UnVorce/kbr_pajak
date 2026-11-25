# -*- coding: utf-8 -*-
"""Tes konverter yurisprudensi Putusan Pengadilan Pajak (scripts/ingest_putusan.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest_putusan import detect_amar, parse_putusan_text  # noqa: E402


def test_detect_amar_categories():
    assert detect_amar("... Memutuskan : Mengabulkan seluruhnya banding Pemohon.")[0] == "KABUL_SELURUHNYA"
    assert detect_amar("... Memutuskan : Mengabulkan sebagian permohonan.")[0] == "KABUL_SEBAGIAN"
    assert detect_amar("... Mengingat ... Memutuskan Menolak gugatan Penggugat.")[0] == "TOLAK"
    assert detect_amar("... Memutuskan: Menyatakan banding tidak dapat diterima.")[0] == "TIDAK_DAPAT_DITERIMA"


def test_parse_putusan_text_extracts_sections_and_citations():
    txt = (
        "Putusan Nomor : PUT-100001.16/2018/PP/M.IIA Tahun 2019\n"
        "Jenis Pajak : Pajak Pertambahan Nilai\n"
        "Tahun Pajak : 2018\n"
        "Pokok Sengketa : Koreksi Pajak Masukan Masa Pajak Januari 2018.\n"
        "Menurut Terbanding : faktur pajak cacat.\n"
        "Menurut Majelis : berdasarkan Undang-Undang Nomor 8 Tahun 1983 dan PMK 81/2024, "
        "faktur memenuhi syarat formal.\n"
        "Mengingat Undang-Undang Nomor 14 Tahun 2002.\n"
        "Memutuskan : Mengabulkan seluruhnya banding Pemohon Banding.\n"
    )
    rec = {"id": 99999, "noput": "PUT-100001.16/2018/PP/M.IIA Tahun 2019",
           "klaster": "ppn", "kode_pajak": "16", "tahun_sengketa": "2018",
           "abstraksi": "Koreksi Pajak Masukan", "url": "https://setpp.kemenkeu.go.id/risalah/ambilFileDariDisk/99999",
           "pdf_file": "sample.pdf"}
    out = parse_putusan_text(rec, txt, 10, 1500.0)
    assert out["case_id"] == "PP-PUT-99999"
    assert out["jenis_pajak"] == "Pajak Pertambahan Nilai"
    assert out["tahun_putusan"] == 2019
    assert out["amar_kategori"] == "KABUL_SELURUHNYA"
    assert "faktur memenuhi syarat formal" in out["pertimbangan_majelis"]
    assert {"UU-1983-8", "PMK-2024-81", "UU-2002-14"} <= set(out["cited_regulations"])
    assert out["quality"]["ocr_suspect"] is False
