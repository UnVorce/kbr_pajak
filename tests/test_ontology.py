# -*- coding: utf-8 -*-
"""Unit & integration tests untuk Fase 5-6 Ontologi SROIQ(D), Reasoning HermiT, dan SPARQL Provenance (TK-A2-1..TK-E1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from owlready2 import OwlReadyInconsistentOntologyError, World, sync_reasoner_hermit
from rdflib import Graph

from src.ontology import (
    CORE_RULE_SPECS,
    build_tbox,
    query_rule_provenance_sparql,
    reason_wajib_pajak,
)

ROOT = Path(__file__).resolve().parents[1]
REASONING_OWL = ROOT / "ontology" / "kbr_pajak_reasoning.owl"
CORE_TTL = ROOT / "ontology" / "kbr-core.ttl"
FULL_TTL = (ROOT / "data" / "export" / "kbr-data.ttl") if (ROOT / "data" / "export" / "kbr-data.ttl").exists() else (ROOT / "knowledge_json" / "rules" / "kbr-data.ttl")
RULE_MAP_JSON = ROOT / "ontology" / "rule_map.json"
LEGAL_RULES_JSONL = (ROOT / "data" / "legal_rules.jsonl") if (ROOT / "data" / "legal_rules.jsonl").exists() else (ROOT / "knowledge_json" / "rules" / "legal_rules.jsonl")


def test_core_rule_specs_grounded_in_legal_rules():
    """P3 & P4: seluruh rule_id di CORE_RULE_SPECS wajib ada di legal_rules.jsonl beserta source_quote."""
    rules = {
        json.loads(line)["rule_id"]: json.loads(line)
        for line in LEGAL_RULES_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for _, cat_id, _, _, rid, _, _ in CORE_RULE_SPECS:
        assert rid in rules, f"{cat_id} merujuk rule_id yang tidak ada: {rid}"
        assert rules[rid].get("source_quote"), f"{rid} tidak memiliki source_quote"
        assert rules[rid].get("source_locator"), f"{rid} tidak memiliki source_locator"


def test_tbox_sroiq_constructs_and_disjointness():
    """Verifikasi TBox memuat seluruh konstruk SROIQ(D) (S, R, O, I, Q, D) dan ditegakkan HermiT."""
    owl_txt = (ROOT / "ontology" / "kbr_pajak_tbox.owl").read_text(encoding="utf-8")
    # S (Transitive), R (PropertyChain, Asymmetric, Irreflexive), O (OneOf), I (Inverse), Q (QualifiedCardinality), D (Datatype)
    for token in (
        "TransitiveProperty",
        "AsymmetricProperty",
        "IrreflexiveProperty",
        "propertyChainAxiom",
        "oneOf",
        "inverseOf",
        "qualifiedCardinality",
        "minQualifiedCardinality",
        "onDatatype",
        "AllDisjointClasses",
        "complementOf",
        "unionOf",
    ):
        assert token in owl_txt, f"Konstruk SROIQ(D) hilang dari TBox: {token}"

    w, onto = build_tbox()
    with onto:
        # Cek nominals DomainPajak (9 domain)
        assert len(list(onto.DomainPajak.instances())) == 9
        # Cek inverse properties terhubung
        assert onto.mengatur.inverse_property is onto.diaturDalam
        assert onto.memuatAturan.inverse_property is onto.diaturDalamPasal
        assert onto.memilikiPasal.inverse_property is onto.bagianDariRegulasi

        # Uji TransitiveProperty (S) & PropertyChain (R) dijalankan HermiT
        r1 = onto.UndangUndang("Test_UU_Induk")
        r2 = onto.PeraturanPemerintah("Test_PP_Pelaksana")
        r3 = onto.PeraturanMenteriKeuangan("Test_PMK_Teknis")
        r3.merujukDokumen.append(r2)
        r2.merujukDokumen.append(r1)

        p1 = onto.Pasal("Test_Pasal_Chain")
        p1.bagianDariRegulasi.append(r1)
        a1 = onto.AturanTarif("Test_Aturan_Chain")
        a1.diaturDalamPasal.append(p1)
        sync_reasoner_hermit(w, infer_property_values=True, debug=0)
        assert r1 in r3.merujukDokumen
        assert r1 in a1.diaturDalam

        # Cek disjointness OrangPribadi vs Badan & bentuk badan usaha memicu inkonsistensi saat digabung
        bad_ind = onto.OrangPribadi("Test_Inconsistent_WP")
        bad_ind.is_a.append(onto.Badan)
        with pytest.raises(OwlReadyInconsistentOntologyError):
            sync_reasoner_hermit(w, debug=0)

    w2, onto2 = build_tbox()
    with onto2:
        bad_corp = onto2.PT("Test_Inconsistent_Corp")
        bad_corp.is_a.append(onto2.BUT)
        with pytest.raises(OwlReadyInconsistentOntologyError):
            sync_reasoner_hermit(w2, debug=0)


def test_artifacts_exist_and_valid_rdf():
    assert REASONING_OWL.exists()
    assert CORE_TTL.exists()
    assert FULL_TTL.exists()
    assert RULE_MAP_JSON.exists()

    g_core = Graph()
    g_core.parse(str(CORE_TTL), format="turtle")
    assert len(g_core) > 200

    rule_map = json.loads(RULE_MAP_JSON.read_text(encoding="utf-8"))
    assert len(rule_map) == len(CORE_RULE_SPECS)


@pytest.fixture(scope="module")
def full_rdf_graph() -> Graph:
    g = Graph()
    g.parse(str(FULL_TTL), format="turtle")
    return g


def test_tk_a2_1_tax_holiday_tiers():
    """TK-A2-1: Kelayakan Tax Holiday PMK 130/2020 (PT/Koperasi + SKF + belum pernah putus + transisi 2 thn)."""
    res_50 = reason_wajib_pajak(
        REASONING_OWL,
        "Test_TH_250M",
        "PT",
        {
            "hasOmzetTahunan": 50_000_000_000.0,
            "isIndustriPionir": True,
            "isPenanamanModalBaru": True,
            "hasSuratKeteranganFiskal": True,
            "isBelumPernahPutusTaxHoliday": True,
            "hasNilaiInvestasi": 250_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert "LayakTaxHoliday_50Pct_5Thn" in res_50["inferred_classes"]
    fas_50 = {f["id"] for f in res_50["fasilitas"]}
    assert {"Fasilitas_TaxHoliday_50Pct_5Thn", "Fasilitas_TaxHoliday_Transisi_25Pct_2Thn", "Fasilitas_Pasal31E_Diskon50Pct_11Pct"}.issubset(fas_50)

    res_20 = reason_wajib_pajak(
        REASONING_OWL,
        "Test_TH_35T",
        "PT",
        {
            "hasOmzetTahunan": 100_000_000_000.0,
            "isIndustriPionir": True,
            "isPenanamanModalBaru": True,
            "hasSuratKeteranganFiskal": True,
            "isBelumPernahPutusTaxHoliday": True,
            "hasNilaiInvestasi": 35_000_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert "LayakTaxHoliday_100Pct_20Thn" in res_20["inferred_classes"]
    fas_20 = {f["id"] for f in res_20["fasilitas"]}
    assert {"Fasilitas_TaxHoliday_100Pct_20Thn", "Fasilitas_TaxHoliday_Transisi_50Pct_2Thn"}.issubset(fas_20)

    # CV tidak berbadan hukum Indonesia -> tidak layak Tax Holiday PMK 130/2020 Pasal 3(1)b
    res_cv = reason_wajib_pajak(
        REASONING_OWL,
        "Test_TH_CV_Denied",
        "CV",
        {
            "hasOmzetTahunan": 100_000_000_000.0,
            "isIndustriPionir": True,
            "isPenanamanModalBaru": True,
            "hasSuratKeteranganFiskal": True,
            "isBelumPernahPutusTaxHoliday": True,
            "hasNilaiInvestasi": 250_000_000_000.0,
            "hasNPWP": True,
        },
    )
    assert not any(f["id"].startswith("Fasilitas_TaxHoliday") for f in res_cv["fasilitas"])


def test_tk_a2_2_pph_badan_and_umkm_transition():
    """TK-A2-2: Tarif 19% Tbk (>=40% publik, >=300 pihak, >=183 hari), Pasal 31E, BUT, dan transisi UMKM."""
    res_tbk = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PT_Tbk",
        "PT",
        {
            "hasOmzetTahunan": 120_000_000_000.0,
            "isPerseroanTerbuka": True,
            "hasPersentaseSahamPublik": 42.5,
            "hasJumlahPemegangSahamPublik": 320,
            "hasHariTerpenuhiTbk": 190,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert "BadanTerbukaTbk" in res_tbk["inferred_classes"]
    assert any(t["id"] == "Tarif_PPhBadan_Tbk_19Pct" and t["tarif_persen"] == 19.0 for t in res_tbk["tarif"])

    # Tbk saham 45% tapi pemegang saham < 300 -> tetap 22%
    res_tbk_fail = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PT_Tbk_FewShareholders",
        "PT",
        {
            "hasOmzetTahunan": 120_000_000_000.0,
            "isPerseroanTerbuka": True,
            "hasPersentaseSahamPublik": 45.0,
            "hasJumlahPemegangSahamPublik": 150,
            "hasHariTerpenuhiTbk": 200,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert "BadanNonTbk" in res_tbk_fail["inferred_classes"]
    assert any(t["id"] == "Tarif_PPhBadan_22Pct" for t in res_tbk_fail["tarif"])

    res_umkm_over = reason_wajib_pajak(
        REASONING_OWL,
        "Test_CV_Over_4_8M",
        "CV",
        {
            "hasOmzetTahunan": 5_100_000_000.0,
            "isUMKM_PP55": True,
            "isPerseroanTerbuka": False,
            "hasNPWP": True,
        },
    )
    assert "PengusahaKenaPajak" in res_umkm_over["inferred_classes"]
    assert "WajibPajakNonUMKM" in res_umkm_over["inferred_classes"]
    assert "BadanLayakPasal31E" in res_umkm_over["inferred_classes"]
    assert any(k["id"] == "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum" for k in res_umkm_over["kewajiban"])
    assert any(f["id"] == "Fasilitas_Pasal31E_Diskon50Pct_11Pct" for f in res_umkm_over["fasilitas"])

    # BUT dilarang PP 55 & Pasal 31E, dikenai PPh 22% + Branch Profit Tax 20%
    res_but = reason_wajib_pajak(
        REASONING_OWL,
        "Test_BUT_RealWorld",
        "BUT",
        {
            "hasOmzetTahunan": 3_000_000_000.0,
            "isUMKM_PP55": True,
            "hasNPWP": True,
        },
    )
    tarif_but = {t["id"] for t in res_but["tarif"]}
    assert {"Tarif_PPhBadan_22Pct", "Tarif_PPh26_4_BUT_BranchProfit_20Pct"}.issubset(tarif_but)
    assert res_but["fasilitas"] == []


def test_tk_b1_b2_ppn_pkp_dan_fasilitas():
    """TK-B1 & TK-B2: Ambang PKP, PPN 12% khusus BKP Mewah vs PPN Efektif 11% non-mewah, dan BKP Strategis."""
    res_non = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PKP_PPN_NonMewah",
        "PT",
        {
            "hasOmzetTahunan": 6_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isPenyerahanNonMewahPPN": True,
            "isPenyerahanBKPStrategis": True,
            "hasNPWP": True,
        },
    )
    assert "PengusahaKenaPajak" in res_non["inferred_classes"]
    assert any(k["id"] == "Kewajiban_DaftarPKP_PungutPPN" for k in res_non["kewajiban"])
    tarif_non = {t["id"] for t in res_non["tarif"]}
    assert "Tarif_PPN_Efektif_11Pct" in tarif_non
    assert "Tarif_PPN_12Pct" not in tarif_non
    assert any(f["id"] == "Fasilitas_PPN_Dibebaskan_Strategis" for f in res_non["fasilitas"])

    res_mewah = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PKP_PPN_Mewah",
        "PT",
        {
            "hasOmzetTahunan": 60_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isPenyerahanBKP_Mewah": True,
            "hasNPWP": True,
        },
    )
    tarif_mewah = {t["id"] for t in res_mewah["tarif"]}
    assert "Tarif_PPN_12Pct" in tarif_mewah
    assert "Tarif_PPN_Efektif_11Pct" not in tarif_mewah


def test_tk_c1_c2_pbb_pkb_dan_mk_spa():
    """TK-C1 & TK-C2: PBB-P2 DKI, PKB Progresif ke-4 (5%), dan Pengecualian Spa MK-2024-19-PUU-XXII."""
    res_op = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_PKB_4",
        "OrangPribadi",
        {
            "isDomisiliDKI": True,
            "isMilikPribadi": True,
            "hasJumlahKendaraan": 4,
            "isMemilikiObjekPBB": True,
            "isPendudukIndonesia": True,
            "hasNPWP": True,
        },
    )
    assert "OP_KendaraanKe4_DKI" in res_op["inferred_classes"]
    assert any(t["id"] == "Tarif_PKB_DKI_Ke4_5Pct" and t["tarif_persen"] == 5.0 for t in res_op["tarif"])
    assert any(t["id"] == "Tarif_PBB_DKI_0_5Pct" for t in res_op["tarif"])
    assert any(k["id"] == "Kewajiban_LaporPBB" for k in res_op["kewajiban"])

    res_spa = reason_wajib_pajak(
        REASONING_OWL,
        "Test_Spa_MK",
        "PT",
        {
            "hasOmzetTahunan": 2_000_000_000.0,
            "isUsahaSpaKesehatanTradisional": True,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    spa_fac = [f for f in res_spa["fasilitas"] if f["id"] == "Fasilitas_Pengecualian_SpaKesehatanTradisional_MK"]
    assert spa_fac
    assert "MK-2024-19-PUU-XXII" in spa_fac[0]["justifikasi"][0]["mk_refs"]


def test_tk_d1_d2_admin_nik_spt_dan_sanksi_sema():
    """TK-D1 & TK-D2: NIK-NPWP, tenggat SPT OP vs Badan, sanksi KUP (OP 100rb / Badan 1jt / PPN 500rb / SKPKB) + SEMA."""
    res_op = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_Admin",
        "OrangPribadi",
        {"isPendudukIndonesia": True, "hasNPWP": True, "isTerlambatLaporSPT": True},
    )
    kew_op = {k["id"] for k in res_op["kewajiban"]}
    assert {"Kewajiban_NPWP_NIK_OP", "Kewajiban_LaporSPT", "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln"}.issubset(kew_op)
    assert any(s["id"] == "Sanksi_Denda_KUP_SPT_OP_100Rb" for s in res_op["sanksi"])

    res_badan = reason_wajib_pajak(
        REASONING_OWL,
        "Test_Badan_Sanksi",
        "PT",
        {
            "hasOmzetTahunan": 10_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
            "isTerlambatLaporSPT": True,
            "isTerlambatLaporSPTMasaPPN": True,
            "isKurangBayarSKPKB": True,
            "isTidakSetorPajakDipungut": True,
            "isKeberatanDitolak": True,
            "isBandingDitolak": True,
        },
    )
    assert any(k["id"] == "Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln" for k in res_badan["kewajiban"])
    sanksi_map = {s["id"]: s for s in res_badan["sanksi"]}
    assert {
        "Sanksi_Denda_KUP_SPT_Badan_1Jt",
        "Sanksi_Denda_KUP_SPT_MasaPPN_500Rb",
        "Sanksi_Bunga_SKPKB_Pasal13_2",
        "Sanksi_Kenaikan_75Pct_TidakSetor_Pasal13_3",
        "Sanksi_Keberatan_30Pct",
        "Sanksi_Banding_60Pct",
    }.issubset(set(sanksi_map))
    assert "SEMA-2024-2-TUN-4" in sanksi_map["Sanksi_Banding_60Pct"]["justifikasi"][0]["sema_refs"]


def test_multidaerah_perda_dan_pph23_penalti_non_npwp():
    """Uji 5 Perda pilot (DKI Badan 2%, Jabar, Surabaya, Semarang, Bali) dan PPh 23 + non-NPWP +100%."""
    res_sby = reason_wajib_pajak(
        REASONING_OWL,
        "Test_Sby_PBB_PBJT",
        "PT",
        {
            "berdomisiliDi": ["Wilayah_Kota_Surabaya"],
            "isMemilikiObjekPBB": True,
            "hasNilaiNJOP": 1_500_000_000.0,
            "isUsahaHiburanSpaUmum": True,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasOmzetTahunan": 3_000_000_000.0,
            "hasNPWP": True,
        },
    )
    assert {"Tarif_PBB_Surabaya_L3_0_15Pct", "Tarif_PBJT_Hiburan_Surabaya_50Pct"}.issubset(
        {t["id"] for t in res_sby["tarif"]}
    )

    res_bali = reason_wajib_pajak(
        REASONING_OWL,
        "Test_Bali_PKB_250cc",
        "OrangPribadi",
        {
            "berdomisiliDi": ["Wilayah_Prov_Bali"],
            "hasJumlahKendaraan": 1,
            "hasKapasitasMesinCC": 250,
            "hasNPWP": True,
        },
    )
    assert any(t["id"] == "Tarif_PKB_Bali_Over200cc_1_2Pct" for t in res_bali["tarif"])
    assert any(k["id"] == "Kewajiban_Opsen_PKB_66Pct" for k in res_bali["kewajiban"])

    res_pph23 = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PPh23_NonNPWP",
        "CV",
        {
            "isPenerimaPenghasilanPPh23_JasaSewa": True,
            "isBankPenerimaPenghasilan": False,
            "hasNPWP": False,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasOmzetTahunan": 1_000_000_000.0,
        },
    )
    assert any(t["id"] == "Tarif_PPh23_JasaSewa_2Pct" for t in res_pph23["tarif"])
    assert any(s["id"] == "Sanksi_PPh23_Kenaikan100Pct_NonNPWP" for s in res_pph23["sanksi"])

    res_bank = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PPh23_Bank",
        "PT",
        {"isBankPenerimaPenghasilan": True, "hasNPWP": True, "isPerseroanTerbuka": False, "isUMKM_PP55": False, "hasOmzetTahunan": 100_000_000_000.0},
    )
    assert any(f["id"] == "Fasilitas_Pengecualian_PPh23_Bank" for f in res_bank["fasilitas"])


def test_tk_e1_sparql_provenance_on_full_export(full_rdf_graph: Graph):
    """TK-E1: SPARQL pada full TTL (12.907 aturan) mengembalikan regulasi, pasal, quote, MK/SEMA."""
    # Uji rule dengan SEMA_TUN
    rows_sema = query_rule_provenance_sparql(
        FULL_TTL,
        rule_id="R-UU-1983-6-ad287a542a",
        graph=full_rdf_graph,
    )
    assert rows_sema
    assert rows_sema[0]["document_id"] == "UU-1983-6"
    assert rows_sema[0]["source_locator"] == "UU-1983-6#BT/27/1..5d"
    assert "60%" in rows_sema[0]["source_quote"]
    assert rows_sema[0]["sema_ref"] == "SEMA_2024_2_TUN_4"

    # Uji rule dengan PutusanMK
    rows_mk = query_rule_provenance_sparql(
        FULL_TTL,
        rule_id="R-PERDA-PROV-DKI-JAKARTA-2024-1-0117748e9b",
        graph=full_rdf_graph,
    )
    assert rows_mk
    assert rows_mk[0]["document_id"] == "PERDA-PROV-DKI-JAKARTA-2024-1"
    assert rows_mk[0]["mk_ref"] == "MK_2024_19_PUU_XXII"


def test_op_pekerjaan_ter_bebas500jt_pekerja_bebas_dan_pph17():
    """Uji model OrangPribadi real-world: JenisPekerjaan, TER A/B/C, bebas 500jt, Pekerja Bebas, multi-peran, 5 layer Pasal 17, SPLN."""
    # 1. Pegawai Tetap K/3 -> TER Kategori C + PTKP + Multi pemberi kerja
    res_k3 = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_TER_C",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["PNS_TNI_Polri_Pejabat"],
            "isSubjekLuarNegeri": False,
            "isPendudukIndonesia": True,
            "isKawin": True,
            "hasJumlahTanggungan": 3,
            "hasJumlahPemberiKerja": 2,
            "hasPenghasilanKenaPajakTahunan": 6_000_000_000.0,
            "hasNPWP": True,
        },
    )
    assert "OP_TER_Kategori_C" in res_k3["inferred_classes"]
    assert "OP_MultiPemberiKerja" in res_k3["inferred_classes"]
    tarif_k3 = {t["id"] for t in res_k3["tarif"]}
    assert {
        "Tarif_PPh21_TER_Bulanan_Kategori_C",
        "Tarif_PPhOP_Layer1_5Pct",
        "Tarif_PPhOP_Layer2_15Pct",
        "Tarif_PPhOP_Layer3_25Pct",
        "Tarif_PPhOP_Layer4_30Pct",
        "Tarif_PPhOP_Layer5_35Pct",
    }.issubset(tarif_k3)
    assert any(k["id"] == "Kewajiban_Rekonsiliasi_MultiPemberiKerja" for k in res_k3["kewajiban"])

    # 2. Pekerja Bebas (Dokter) meski isUMKM_PP55=True -> TIDAK dapat PP 55 0,5%, diarahkan ke tarif umum & NPPN
    res_doc = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_Dokter_NoPP55",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["Dokter"],
            "isSubjekLuarNegeri": False,
            "isUMKM_PP55": True,
            "hasOmzetTahunan": 1_500_000_000.0,
            "hasPenghasilanKenaPajakTahunan": 300_000_000.0,
            "hasNPWP": True,
        },
    )
    assert "OP_PekerjaBebas" in res_doc["inferred_classes"]
    assert "OP_PekerjaBebas_LayakNPPN" in res_doc["inferred_classes"]
    fas_doc = {f["id"] for f in res_doc["fasilitas"]}
    assert "Fasilitas_PP55_Final_0_5Pct" not in fas_doc
    assert "Fasilitas_NPPN_OP_Dibawah_4_8M" in fas_doc
    assert any(k["id"] == "Kewajiban_PekerjaBebas_TarifUmum_NonPP55" for k in res_doc["kewajiban"])

    # 3. OP UMKM Dagang omzet <= Rp500jt -> hanya bebas 0%, bukan 0,5%
    res_umkm_400 = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_UMKM_400Jt",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["Pedagang_ECommerce"],
            "isSubjekLuarNegeri": False,
            "isUMKM_PP55": True,
            "hasOmzetTahunan": 400_000_000.0,
            "hasNPWP": True,
        },
    )
    assert "OP_UMKM_Bebas_500Jt" in res_umkm_400["inferred_classes"]
    fas_400 = {f["id"] for f in res_umkm_400["fasilitas"]}
    assert "Fasilitas_OP_UMKM_BebasPPh_500Jt" in fas_400
    assert "Fasilitas_PP55_Final_0_5Pct" not in fas_400

    # 4. OP UMKM Dagang omzet > Rp500jt s.d. Rp4,8M -> bebas Rp500jt pertama + PP 55 0,5%
    res_umkm_1_2m = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_UMKM_1_2M",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["Usaha_Kuliner_Warung"],
            "isSubjekLuarNegeri": False,
            "isUMKM_PP55": True,
            "hasOmzetTahunan": 1_200_000_000.0,
            "hasNPWP": True,
        },
    )
    fas_1_2m = {f["id"] for f in res_umkm_1_2m["fasilitas"]}
    assert {"Fasilitas_OP_UMKM_BebasPPh_500Jt", "Fasilitas_PP55_Final_0_5Pct"}.issubset(fas_1_2m)

    # 5. Multi-peran (Dokter + Karyawan + Toko Online) tidak inkonsisten di HermiT & SPJN/SPLN PPh 26
    res_multi = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_MultiRole",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["Dokter", "PegawaiTetap_Swasta", "Pedagang_ECommerce"],
            "isSubjekLuarNegeri": False,
            "isKawin": False,
            "hasJumlahTanggungan": 1,
            "isUMKM_PP55": True,
            "hasOmzetTahunan": 350_000_000.0,
            "hasNPWP": True,
        },
    )
    assert {"OP_PekerjaBebas", "OP_PenerimaPPh21_PegawaiTetap", "OP_TER_Kategori_A", "OP_UMKM_Bebas_500Jt"}.issubset(
        set(res_multi["inferred_classes"])
    )

    res_spln = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_SPLN",
        "OrangPribadi",
        {"isSubjekLuarNegeri": True, "memilikiPekerjaan": ["Konsultan"]},
    )
    assert "OP_SubjekLuarNegeri" in res_spln["inferred_classes"]
    assert any(t["id"] == "Tarif_PPh26_OP_LuarNegeri_20Pct" for t in res_spln["tarif"])


def test_step_a_tax_allowance_padat_karya_nppn_terlambat_dan_hkpd_opsen():
    """Uji Step A: Tax Allowance PP 78/2019, Padat Karya PMK 81/2024, NPPN terlambat/non-pembukuan, HKPD non-DKI."""
    res_ta = reason_wajib_pajak(
        REASONING_OWL,
        "Test_TaxAllowance_PadatKarya",
        "PT",
        {
            "isBidangUsahaTaxAllowance": True,
            "isLokasiProvinsiMemenuhiTaxAllowance": True,
            "isIndustriPadatKarya": True,
            "isPenanamanModalBaru": True,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasOmzetTahunan": 80_000_000_000.0,
            "hasNPWP": True,
        },
    )
    fas_ta = {f["id"] for f in res_ta["fasilitas"]}
    assert {"Fasilitas_TaxAllowance_PP78_30Pct", "Fasilitas_PadatKarya_PMK81_60Pct"}.issubset(fas_ta)

    res_nppn_late = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_NPPN_Late",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["Akuntan"],
            "hasOmzetTahunan": 1_000_000_000.0,
            "isPemberitahuanNPPNTepatWaktu": False,
            "isTidakMenyelenggarakanPembukuanPencatatan": True,
            "hasNPWP": True,
        },
    )
    assert any(k["id"] == "Kewajiban_Pembukuan_OP_NPPN_Terlambat" for k in res_nppn_late["kewajiban"])
    assert any(s["id"] == "Sanksi_NPPN_Norma_Pemeriksaan_Pasal14_5" for s in res_nppn_late["sanksi"])

    res_sby_kend = reason_wajib_pajak(
        REASONING_OWL,
        "Test_Sby_Kendaraan_HKPD",
        "OrangPribadi",
        {"berdomisiliDi": ["Wilayah_Kota_Surabaya"], "hasJumlahKendaraan": 1, "hasNPWP": True},
    )
    assert "WP_Wilayah_NonDKI_Kendaraan" in res_sby_kend["inferred_classes"]
    assert any(k["id"] == "Kewajiban_Opsen_PKB_66Pct" for k in res_sby_kend["kewajiban"])


def test_pph_final_pasal4_2_sewa_deposito_konstruksi_pengalihan():
    """Uji PPh Final Pasal 4(2): Sewa Tanah/Bangunan, Bunga Deposito, Jasa Konstruksi (PP 9/2022), Pengalihan Tanah/Bangunan & pengecualiannya."""
    # 1. OP multi-penghasilan: Pegawai Tetap + Sewa Ruko + Bunga Deposito + Pengalihan Tanah/Bangunan Umum
    res_op = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_PPhFinal_Multi",
        "OrangPribadi",
        {
            "memilikiPekerjaan": ["PegawaiTetap_Swasta"],
            "memilikiPenghasilanFinal": [
                "Jenis_SewaTanahBangunan",
                "Jenis_BungaDepositoTabungan",
                "Jenis_PengalihanTanahBangunan_Umum",
            ],
            "isSubjekLuarNegeri": False,
            "isPendudukIndonesia": True,
            "isKawin": False,
            "hasJumlahTanggungan": 0,
            "hasPenghasilanKenaPajakTahunan": 100_000_000.0,
            "hasNPWP": True,
        },
    )
    tarifs_op = {t["id"] for t in res_op["tarif"]}
    kews_op = {k["id"] for k in res_op["kewajiban"]}
    assert {
        "Tarif_PPhFinal_SewaTanahBangunan_10Pct",
        "Tarif_PPhFinal_BungaDepositoTabungan_20Pct",
        "Tarif_PPhFinal_PengalihanTanahBangunan_2_5Pct",
        "Tarif_PPh21_TER_Bulanan_Kategori_A",
        "Tarif_PPhOP_Layer1_5Pct",
    }.issubset(tarifs_op)
    assert {
        "Kewajiban_PotongSetor_SewaTanahBangunan",
        "Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta",
    }.issubset(kews_op)

    # 2. PT Jasa Konstruksi (PP 51/2008 jo. PP 9/2022): Kecil SBU 1,75% vs Konsultansi Tanpa SBU 6%
    res_kecil = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PT_Konst_Kecil",
        "PT",
        {
            "memilikiPenghasilanFinal": ["Jenis_JasaKonstruksi_Kecil_SBU"],
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert any(t["id"] == "Tarif_PPhFinal_Konstruksi_KecilSBU_1_75Pct" for t in res_kecil["tarif"])
    assert any(k["id"] == "Kewajiban_PencatatanTerpisah_JasaKonstruksi" for k in res_kecil["kewajiban"])

    res_kons_non = reason_wajib_pajak(
        REASONING_OWL,
        "Test_PT_Konst_Kons_NonSBU",
        "PT",
        {
            "memilikiPenghasilanFinal": ["Jenis_JasaKonstruksi_Konsultansi_TanpaSBU"],
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
    )
    assert any(t["id"] == "Tarif_PPhFinal_Konstruksi_KonsultansiTanpaSBU_6Pct" for t in res_kons_non["tarif"])

    # 3. Pengecualian (ConstrainedDatatype & boolean): penginapan PP 34, pokok deposito <= 7,5jt, & pengalihan OP < PTKP dan < 60jt
    res_exc = reason_wajib_pajak(
        REASONING_OWL,
        "Test_OP_PPhFinal_Exceptions",
        "OrangPribadi",
        {
            "memilikiPenghasilanFinal": [
                "Jenis_SewaTanahBangunan",
                "Jenis_BungaDepositoTabungan",
                "Jenis_PengalihanTanahBangunan_Umum",
            ],
            "isJasaAkomodasiPenginapan": True,
            "hasPokokDepositoTabungan": 5_000_000.0,
            "isPenghasilanDibawahPTKP": True,
            "hasNilaiPengalihanTanahBangunan": 45_000_000.0,
            "hasNPWP": True,
        },
    )
    fas_exc = {f["id"] for f in res_exc["fasilitas"]}
    assert {
        "Fasilitas_Pengecualian_SewaPenginapan_PP34",
        "Fasilitas_Pengecualian_Deposito_Dibawah_7_5Jt",
        "Fasilitas_Restitusi_BungaDeposito_DibawahPTKP",
        "Fasilitas_Pengecualian_Pengalihan_OP_Dibawah60Jt_PTKP",
    }.issubset(fas_exc)
