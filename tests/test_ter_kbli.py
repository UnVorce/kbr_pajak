# -*- coding: utf-8 -*-
"""Unit tests untuk Step B — Parser TER PPh 21 (PP 58/2023) & SKOS KBLI (PER-17/PJ/2015 + PP 78/2019)."""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from src.ter_kbli import (
    lookup_kbli_sparql,
    lookup_ter_rate_sparql,
    parse_pp58_ter,
    resolve_nppn_wilayah_kelompok,
    search_kbli_sparql,
)

ROOT = Path(__file__).resolve().parents[1]
TER_TTL = ROOT / "ontology" / "kbr_ter_pph21.ttl"
KBLI_TTL = ROOT / "ontology" / "kbr_kbli.ttl"


def test_pp58_ter_brackets_continuous_and_complete():
    pp58_txt = ROOT / "data" / "text" / "PP-2023-58.txt"
    if not pp58_txt.exists():
        pp58_txt = ROOT / "knowledge_json" / "text_lampiran" / "PP-2023-58.txt"
    brackets = parse_pp58_ter(pp58_txt)
    by_cat = {}
    for b in brackets:
        by_cat.setdefault(b.kategori, []).append(b)
    assert len(by_cat["TER_A"]) == 44
    assert len(by_cat["TER_B"]) == 40
    assert len(by_cat["TER_C"]) == 41
    assert len(by_cat["TER_Harian"]) == 2
    assert by_cat["TER_A"][0].rate_percent == 0.0
    assert by_cat["TER_A"][-1].rate_percent == 34.0
    assert by_cat["TER_C"][6].rate_percent == 1.5  # OCR catch: '1,5' terbaca '5' di digit, 'satu koma lima' di terbilang


def test_ter_ttl_sparql_lookup():
    assert TER_TTL.exists()
    g = Graph()
    g.parse(str(TER_TTL), format="turtle")
    hit_a = lookup_ter_rate_sparql(g, "TER_A", 10_000_000.0)
    assert hit_a and hit_a["tarif_persen"] == 2.0
    hit_b = lookup_ter_rate_sparql(g, "TER_B", 15_000_000.0)
    assert hit_b and hit_b["tarif_persen"] == 6.0
    hit_c = lookup_ter_rate_sparql(g, "TER_C", 25_000_000.0)
    assert hit_c and hit_c["tarif_persen"] == 9.0


def test_kbli_skos_ttl_nppn_dan_tax_allowance():
    assert KBLI_TTL.exists()
    g = Graph()
    g.parse(str(KBLI_TTL), format="turtle")

    # Cek kode yang sempat terpotong/menempel saat inspeksi awal
    for code in ("01119", "03118", "47729", "47914", "64131"):
        assert lookup_kbli_sparql(g, code) is not None, f"KBLI {code} hilang dari kbr_kbli.ttl"

    k69100 = lookup_kbli_sparql(g, "69100")
    assert k69100["nppn_op"]["10_IbuKota_Provinsi"] == 51.0
    assert k69100["nppn_op"]["Daerah_Lain"] == 50.0
    assert k69100["terkait_jenis_pekerjaan"] == "Pengacara"

    k03222 = lookup_kbli_sparql(g, "03222")
    assert k03222["tax_allowance"]["eligible_kbli"] is True
    assert k03222["tax_allowance"]["kecuali_dki"] is True

    k05101 = lookup_kbli_sparql(g, "05101")
    assert k05101["tax_allowance"]["eligible_kbli"] is True
    assert "Kalimantan Timur" in k05101["tax_allowance"]["provinsi_syarat"]

    # Step D: Industri Pionir (PerBKPM 7/2020) & Padat Karya (PMK 16/2020 / PMK 81/2024)
    k24101 = lookup_kbli_sparql(g, "24101")
    assert k24101["industri_pionir"]["eligible_kbli"] is True
    assert "24101A" in k24101["industri_pionir"]["subkode"]

    k17011 = lookup_kbli_sparql(g, "17011")
    assert k17011["industri_pionir"]["eligible_kbli"] is True
    # 17011 hanya syarat integrasi di PMK 16/2020, bukan KBLI penerima Padat Karya
    assert k17011["industri_padat_karya"]["eligible_kbli"] is False

    k15202 = lookup_kbli_sparql(g, "15202")
    assert k15202["industri_padat_karya"]["eligible_kbli"] is True

    k10761 = lookup_kbli_sparql(g, "10761")
    assert k10761["industri_padat_karya"]["eligible_kbli"] is True
    assert k10761["industri_padat_karya"]["kecuali_dki"] is True

    res_search = search_kbli_sparql(g, "dokter", limit=5)
    assert any(x["kode_kbli"] == "86201" for x in res_search)


def test_nppn_wilayah_mapping_memisahkan_provinsi_dan_ibukota():
    assert resolve_nppn_wilayah_kelompok("Wilayah_DKI_Jakarta") == "10_IbuKota_Provinsi"
    assert resolve_nppn_wilayah_kelompok("Wilayah_Kota_Surabaya") == "10_IbuKota_Provinsi"
    assert resolve_nppn_wilayah_kelompok("Wilayah_Kota_Semarang") == "10_IbuKota_Provinsi"
    assert resolve_nppn_wilayah_kelompok("Kota Bandung") == "10_IbuKota_Provinsi"
    # Provinsi Jabar & Bali bukan otomatis 10 Ibu Kota Provinsi (hanya Bandung & Denpasar)
    assert resolve_nppn_wilayah_kelompok("Wilayah_Jawa_Barat") == "Daerah_Lain"
    assert resolve_nppn_wilayah_kelompok("Wilayah_Prov_Bali") == "Daerah_Lain"
    assert resolve_nppn_wilayah_kelompok("Kota Yogyakarta") == "IbuKota_Provinsi_Lain"
