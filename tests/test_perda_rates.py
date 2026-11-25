# -*- coding: utf-8 -*-
"""Unit tests untuk Step C — Ekstraksi 524 Perda (390 Pemda) & RDF kbr-perda-rates.ttl."""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from src.perda_rates import canonicalize_pemda

ROOT = Path(__file__).resolve().parents[1]
PERDA_TTL = ROOT / "ontology" / "kbr-perda-rates.ttl"


def test_canonicalize_pemda_handles_non_std_ids_and_dki():
    assert canonicalize_pemda(
        "Peraturan Daerah (Perda) Provinsi Nusa Tenggara Barat Nomor 2 Tahun 2024 tentang PDRD",
        "PERDA-2024-281805",
    )[:2] == ("PROV", "PROV_NUSA_TENGGARA_BARAT")
    assert canonicalize_pemda(
        "Peraturan Daerah (Perda) Provinsi Daerah Istimewa Yogyakarta Nomor 11 Tahun 2023 tentang PDRD",
        "PERDA-DAERAH-274729-2023-11",
    )[:2] == ("PROV", "PROV_DAERAH_ISTIMEWA_YOGYAKARTA")
    assert canonicalize_pemda(
        "Peraturan Daerah (Perda) Provinsi Daerah Khusus Ibukota Jakarta Nomor 1 Tahun 2024 tentang PDRD",
        "PERDA-PROV-DKI-JAKARTA-2024-1",
    )[:2] == ("PROV", "PROV_DKI_JAKARTA")


def test_perda_rates_ttl_coverage_perubahan_and_provenance():
    assert PERDA_TTL.exists()
    g = Graph()
    g.parse(str(PERDA_TTL), format="turtle")

    # Hitung Pemda unik
    pemdas = list(g.query("PREFIX kbr: <http://www.semanticweb.org/ontology/kbr_pajak#> SELECT (COUNT(?p) AS ?c) WHERE { ?p a kbr:PemdaDaerah }"))
    assert int(list(pemdas)[0][0]) == 390

    # Uji Perda Perubahan override (Kab. Bogor PBB 2025 = 0.25% & Kota Bandung PBJT 2025 = 10%/40%)
    q = """
    PREFIX kbr: <http://www.semanticweb.org/ontology/kbr_pajak#>
    SELECT ?pid ?jk ?pct ?nom ?doc ?nppn
    WHERE {
      ?p a kbr:PemdaDaerah ; kbr:hasPemdaId ?pid ; kbr:kelompokWilayahNPPN ?nppn .
      ?r kbr:untukPemda ?p ; kbr:hasJenisPajakDaerah ?jk ; kbr:hasDocumentId ?doc .
      OPTIONAL { ?r kbr:hasTarifPersen ?pct . }
      OPTIONAL { ?r kbr:hasNominalRupiah ?nom . }
      FILTER(STR(?pid) IN ("KAB_BOGOR", "KOTA_BANDUNG", "PROV_DKI_JAKARTA", "PROV_JAWA_BARAT", "PROV_NUSA_TENGGARA_BARAT"))
    }
    """
    rows = {}
    nppn_map = {}
    for r in g.query(q):
        nppn_map[str(r.pid)] = str(r.nppn)
        rows[(str(r.pid), str(r.jk))] = (
            float(r.pct) if r.pct is not None else None,
            float(r.nom) if r.nom is not None else None,
            str(r.doc),
        )

    assert nppn_map["PROV_DKI_JAKARTA"] == "10_IbuKota_Provinsi"
    assert nppn_map["KOTA_BANDUNG"] == "10_IbuKota_Provinsi"
    assert nppn_map["KAB_BOGOR"] == "Daerah_Lain"

    assert rows[("KAB_BOGOR", "PBB_P2")][0] == 0.25
    assert rows[("KAB_BOGOR", "PBB_P2")][2] == "PERDA-KAB-BOGOR-2025-1"
    assert rows[("KOTA_BANDUNG", "PBJT_Hiburan_Khusus")][0] == 40.0
    assert rows[("PROV_JAWA_BARAT", "PKB_Ke2")][0] == 1.62
    assert rows[("PROV_JAWA_BARAT", "PKB_Ke3")][0] == 2.12
    assert rows[("PROV_NUSA_TENGGARA_BARAT", "BBNKB")][0] == 9.0
