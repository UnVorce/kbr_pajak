# -*- coding: utf-8 -*-
"""Tes parser SEMA Kamar TUN dan Putusan MK."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.crawl_putusan_mk import is_tax_relevant, make_mk_id  # noqa: E402
from scripts.ingest_putusan_mk import (  # noqa: E402
    _impacted_corpus_docs,
    classify_mk_amar,
    extract_pasal_diuji,
    parse_mk_text,
)
from scripts.ingest_sema_tun import _classify_klaster  # noqa: E402


def test_mk_pasal_diuji_abaikan_batu_uji_uud():
    """Pasal dari UUD 1945 (batu uji) tidak boleh tercatat sebagai pasal diuji."""
    amar = (
        "Menyatakan frasa \"pelaksanaan hak dan kewajiban kuasa\" dalam Pasal 32 ayat (3a) "
        "Undang-Undang Nomor 28 Tahun 2007 tentang KUP bertentangan dengan Undang-Undang Dasar "
        "Negara Republik Indonesia Tahun 1945 dan tidak mempunyai kekuatan hukum mengikat "
        "sepanjang tidak dimaknai hanya dapat dilakukan oleh kuasa yang memenuhi syarat."
    )
    hasil = extract_pasal_diuji("", amar)
    assert hasil == ["Pasal 32 ayat (3a)"], hasil


def test_mk_impacted_docs_petakan_uu_amandemen_ke_induk():
    assert "UU-1983-6" in _impacted_corpus_docs(["UU-2007-28"], "", "")
    assert "UU-1983-8" in _impacted_corpus_docs(["UU-2009-42"], "", "")
    docs_hpp = _impacted_corpus_docs(
        ["UU-2021-7"],
        "Pengujian Materiil Undang-Undang Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan",
        "Pasal 2 angka 13 Undang-Undang Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan",
        ["Pasal 43A ayat (1)"],
    )
    assert "UU-1983-6" in docs_hpp
    # PDRD tidak dipetakan ke HKPD pada level pasal (nomor pasal berbeda)
    from scripts.ingest_putusan_mk import _successor_corpus_docs
    assert _successor_corpus_docs(["UU-2009-28"]) == ["UU-2022-1"]
    assert "UU-2022-1" not in _impacted_corpus_docs(["UU-2009-28"], "", "")


def test_sema_klaster_and_2020_extracted():
    assert _classify_klaster("Pengenaan Pasal 26 ayat (4) UU PPh bagi BUT Branch Profit Tax") == "PPH_BADAN_BUT"
    assert _classify_klaster("Permohonan Peninjauan Kembali II dalam perkara pajak") == "PENGADILAN_PAJAK_PK"
    p = ROOT / "data" / "sema_tun" / "SEMA-2020-10-TUN-4.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        assert "UU-2002-14" in d["cited_regulations"]


def test_mk_filter_and_id():
    assert make_mk_id("26/PUU-XXI/2023") == "MK-2023-26-PUU-XXI"
    tax_card = {
        "nomor_perkara": "39/PUU-XIV/2016",
        "pokok_perkara": "Pengujian Undang-Undang Nomor 42 Tahun 2009 tentang Pajak Pertambahan Nilai",
        "amar_putusan": "Mengabulkan permohonan para Pemohon untuk sebagian",
        "jenis_amar": "Dikabulkan",
    }
    non_tax_card = {
        "nomor_perkara": "100/PUU-XX/2022",
        "pokok_perkara": "Pengujian Undang-Undang Nomor 7 Tahun 2017 tentang Pemilihan Umum",
        "amar_putusan": "Mengabulkan sebagian tentang verifikasi partai politik",
        "jenis_amar": "Dikabulkan",
    }
    assert is_tax_relevant(tax_card) is True
    assert is_tax_relevant(non_tax_card) is False


def test_mk_parse_sections_and_amar():
    rec = {
        "case_id": "MK-2023-26-PUU-XXI",
        "nomor_perkara": "26/PUU-XXI/2023",
        "tanggal_putusan": "25 Mei 2023",
        "pemohon": "Nurhidayat",
        "pokok_perkara": "Pengujian Materiil Undang-Undang Nomor 14 Tahun 2002 tentang Pengadilan Pajak",
        "amar_putusan": (
            "Mengabulkan permohonan untuk sebagian. Menyatakan frasa Departemen Keuangan dalam "
            "Pasal 5 ayat (2) UU 14/2002 bertentangan dengan UUD 1945 sepanjang tidak dimaknai "
            "Mahkamah Agung."
        ),
        "pdf_url": "https://s.mkri.id/sample.pdf",
        "pdf_file": "MK-2023-26-PUU-XXI.pdf",
    }
    txt = (
        "[3.1] Pertimbangan Mahkamah mengenai Pasal 5 ayat (2) UU Nomor 14 Tahun 2002.\n"
        "MENGADILI\n"
        "1. Mengabulkan permohonan untuk sebagian;\n"
        "2. Menyatakan frasa Departemen Keuangan dalam Pasal 5 ayat (2) UU 14/2002 bertentangan dengan UUD 1945 sepanjang tidak dimaknai Mahkamah Agung.\n"
        "Demikian diputus dalam Rapat Permusyawaratan Hakim."
    )
    out = parse_mk_text(rec, txt, 75, 2000.0)
    assert out["amar_kategori"] == "KONSTITUSIONAL_BERSYARAT"
    assert "UU-2002-14" in out["uu_diuji"]
    assert "Pasal 5 ayat (2)" in out["pasal_diuji"]
    assert out["amar_lengkap"].startswith("Mengabulkan permohonan")


def test_mk_amar_fallback_ke_pdf_bila_kartu_kosong():
    rec = {
        "case_id": "MK-2023-26-PUU-XXI",
        "nomor_perkara": "26/PUU-XXI/2023",
        "tanggal_putusan": "25 Mei 2023",
        "pemohon": "Nurhidayat",
        "pokok_perkara": "Pengujian Materiil Undang-Undang Nomor 14 Tahun 2002 tentang Pengadilan Pajak",
        "amar_putusan": "",
        "pdf_url": "https://s.mkri.id/sample.pdf",
        "pdf_file": "MK-2023-26-PUU-XXI.pdf",
    }
    txt = "MENGADILI\n1. Mengabulkan permohonan untuk sebagian.\nDemikian diputus."
    out = parse_mk_text(rec, txt, 5, 2000.0)
    assert out["amar_lengkap"].startswith("MENGADILI")
    assert "Demikian" not in out["amar_lengkap"]
    assert classify_mk_amar("Mengabulkan permohonan untuk seluruhnya.") == "KABUL_SELURUHNYA"
    assert extract_pasal_diuji("Pasal 32 ayat (3a) UU KUP", "") == ["Pasal 32 ayat (3a)"]
