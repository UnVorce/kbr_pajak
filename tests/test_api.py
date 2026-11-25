# -*- coding: utf-8 -*-
"""Integration tests untuk FastAPI backend (Fase 7) memakai TestClient."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_api_health_and_catalog():
    r_health = client.get("/health")
    assert r_health.status_code == 200
    h = r_health.json()
    assert h["status"] == "ok"
    assert h["reasoning_owl_exists"] is True
    assert h["full_ttl_exists"] is True
    assert h["swrl_rules"] >= 73

    r_cat = client.get("/catalog")
    assert r_cat.status_code == 200
    cat = r_cat.json()
    assert cat["count"] >= 79
    assert "Tarif_PPhBadan_22Pct" in cat["items"]

    r_opt = client.get("/options")
    assert r_opt.status_code == 200
    opt = r_opt.json()
    assert len(opt["jobs"]) == 30
    assert len(opt["regions"]) == 6

    r_sc = client.get("/scenarios")
    assert r_sc.status_code == 200
    assert r_sc.json()["count"] >= 15


def test_api_reason_boundary_umkm_exact_vs_over():
    """Batas tepat Rp4,8M tetap UMKM PP 55; Rp4.800.000.001 berpindah ke PKP & ketentuan umum."""
    r_exact = client.post(
        "/reason",
        json={
            "wp_id": "API_UMKM_Exact",
            "wp_kind": "CV",
            "properties": {
                "hasOmzetTahunan": 4_800_000_000.0,
                "isUMKM_PP55": True,
                "isPerseroanTerbuka": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_exact.status_code == 200
    d_exact = r_exact.json()
    assert "WajibPajakUMKM" in d_exact["inferred_classes"]
    assert "PengusahaKenaPajak" not in d_exact["inferred_classes"]
    assert [f["id"] for f in d_exact["fasilitas"]] == ["Fasilitas_PP55_Final_0_5Pct"]

    r_over = client.post(
        "/reason",
        json={
            "wp_id": "API_UMKM_Over",
            "wp_kind": "CV",
            "properties": {
                "hasOmzetTahunan": 4_800_000_001.0,
                "isUMKM_PP55": True,
                "isPerseroanTerbuka": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_over.status_code == 200
    d_over = r_over.json()
    assert "PengusahaKenaPajak" in d_over["inferred_classes"]
    assert "WajibPajakUMKM" not in d_over["inferred_classes"]
    kew_ids = {k["id"] for k in d_over["kewajiban"]}
    assert "Kewajiban_DaftarPKP_PungutPPN" in kew_ids
    assert "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum" in kew_ids


def test_api_reason_tbk_threshold_and_mk_provenance():
    """Uji batas 40% Tbk vs non-Tbk dan pengecualian Spa MK-2024-19-PUU-XXII."""
    r_tbk_low = client.post(
        "/reason",
        json={
            "wp_id": "API_Tbk_30Pct",
            "wp_kind": "PT",
            "properties": {
                "hasOmzetTahunan": 80_000_000_000.0,
                "isPerseroanTerbuka": True,
                "hasPersentaseSahamPublik": 30.0,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_tbk_low.status_code == 200
    tarif_low = {t["id"] for t in r_tbk_low.json()["tarif"]}
    assert "Tarif_PPhBadan_22Pct" in tarif_low
    assert "Tarif_PPhBadan_Tbk_19Pct" not in tarif_low

    r_spa_mk = client.post(
        "/reason",
        json={
            "wp_id": "API_Spa_MK",
            "wp_kind": "PT",
            "properties": {
                "hasOmzetTahunan": 2_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "isUsahaSpaKesehatanTradisional": True,
                "hasNPWP": True,
            },
        },
    )
    assert r_spa_mk.status_code == 200
    d_spa = r_spa_mk.json()
    fas = {f["id"]: f for f in d_spa["fasilitas"]}
    assert "Fasilitas_Pengecualian_SpaKesehatanTradisional_MK" in fas
    assert "MK-2024-19-PUU-XXII" in fas["Fasilitas_Pengecualian_SpaKesehatanTradisional_MK"]["justifikasi"][0]["mk_refs"]


def test_api_reason_validation_rejects_bad_input():
    r_bad = client.post(
        "/reason",
        json={
            "wp_id": "bad id with spaces",
            "wp_kind": "PT",
            "properties": {"hasPersentaseSahamPublik": 150.0},
        },
    )
    assert r_bad.status_code == 422


def test_api_sparql_provenance_and_stats():
    r_prov = client.get("/sparql/provenance", params={"rule_id": "R-UU-1983-6-ad287a542a"})
    assert r_prov.status_code == 200
    p = r_prov.json()
    assert p["count"] == 1
    assert p["results"][0]["document_id"] == "UU-1983-6"
    assert p["results"][0]["sema_ref"] == "SEMA_2024_2_TUN_4"

    r_stats = client.get("/sparql/stats")
    assert r_stats.status_code == 200
    s = r_stats.json()
    assert s["total_rules"] == 12907
    assert s["by_domain"]["Domain_D_ADMIN_SANKSI"] == 3417


def test_api_reason_op_multirole_but_and_wilayah_surabaya():
    """Uji POST /reason untuk OP multi-pekerjaan, BUT Branch Profit Tax, dan Wilayah Surabaya."""
    r_op = client.post(
        "/reason",
        json={
            "wp_id": "API_Dr_Multi",
            "wp_kind": "OrangPribadi",
            "properties": {
                "memilikiPekerjaan": ["Dokter", "PegawaiTetap_Swasta", "Pedagang_ECommerce"],
                "berdomisiliDi": ["Wilayah_Kota_Surabaya"],
                "isSubjekLuarNegeri": False,
                "isPendudukIndonesia": True,
                "isKawin": True,
                "hasJumlahTanggungan": 2,
                "isUMKM_PP55": True,
                "hasOmzetTahunan": 350_000_000.0,
                "hasPenghasilanKenaPajakTahunan": 300_000_000.0,
                "isMemilikiObjekPBB": True,
                "hasNilaiNJOP": 1_500_000_000.0,
                "hasNPWP": True,
            },
        },
    )
    assert r_op.status_code == 200
    d_op = r_op.json()
    assert {"OP_PekerjaBebas", "OP_TER_Kategori_B", "OP_UMKM_Bebas_500Jt", "WP_PBB_Surabaya_L3"}.issubset(
        set(d_op["inferred_classes"])
    )
    assert {"Tarif_PPh21_TER_Bulanan_Kategori_B", "Tarif_PPh21_BukanPegawai_DPP50Pct", "Tarif_PBB_Surabaya_L3_0_15Pct"}.issubset(
        {t["id"] for t in d_op["tarif"]}
    )
    assert "Fasilitas_OP_UMKM_BebasPPh_500Jt" in {f["id"] for f in d_op["fasilitas"]}

    r_but = client.post(
        "/reason",
        json={
            "wp_id": "API_BUT_01",
            "wp_kind": "BUT",
            "properties": {"hasOmzetTahunan": 3_000_000_000.0, "isUMKM_PP55": True, "hasNPWP": True},
        },
    )
    assert r_but.status_code == 200
    d_but = r_but.json()
    assert {"Tarif_PPhBadan_22Pct", "Tarif_PPh26_4_BUT_BranchProfit_20Pct"}.issubset({t["id"] for t in d_but["tarif"]})
    assert d_but["fasilitas"] == []


def test_api_sparql_bind_estimator_pasal31e_op_ppn_pbb_dan_denda():
    """Uji kalkulator SPARQL BIND (Opsi A): Pasal 31E, PPN 11%, denda 1jt, OP Pasal 17 5 lapis & PBB."""
    r_cv = client.post(
        "/reason",
        json={
            "wp_id": "API_Est_31E",
            "wp_kind": "CV",
            "properties": {
                "hasOmzetTahunan": 10_000_000_000.0,
                "hasPenghasilanKenaPajakTahunan": 1_000_000_000.0,
                "hasDPP_PPN": 2_000_000_000.0,
                "isUMKM_PP55": False,
                "isPerseroanTerbuka": False,
                "isPenyerahanNonMewahPPN": True,
                "isTerlambatLaporSPT": True,
                "hasNPWP": True,
            },
        },
    )
    assert r_cv.status_code == 200
    est_cv = r_cv.json()["estimasi_pajak"]["rincian"]
    assert est_cv["pph_badan_idr"] == 167_200_000.0
    assert est_cv["penghematan_pasal_31e_idr"] == 52_800_000.0
    assert est_cv["ppn_terutang_idr"] == 220_000_000.0
    assert est_cv["denda_administratif_tetap_idr"] == 1_000_000.0

    r_op = client.post(
        "/reason",
        json={
            "wp_id": "API_Est_OP",
            "wp_kind": "OrangPribadi",
            "properties": {
                "memilikiPekerjaan": ["Usaha_Kuliner_Warung"],
                "berdomisiliDi": ["Wilayah_Kota_Surabaya"],
                "isSubjekLuarNegeri": False,
                "isUMKM_PP55": True,
                "hasOmzetTahunan": 1_200_000_000.0,
                "hasPenghasilanKenaPajakTahunan": 300_000_000.0,
                "isMemilikiObjekPBB": True,
                "hasNilaiNJOP": 1_500_000_000.0,
                "hasNPWP": True,
            },
        },
    )
    assert r_op.status_code == 200
    est_op = r_op.json()["estimasi_pajak"]["rincian"]
    # (1.2M - 500jt) * 0.5% = 3.5jt
    assert est_op["porsi_omzet_bebas_500jt_idr"] == 500_000_000.0
    assert est_op["pph_final_umkm_op_idr"] == 3_500_000.0
    # Pasal 17: 60jt*5% (3jt) + 190jt*15% (28.5jt) + 50jt*25% (12.5jt) = 44jt
    assert est_op["pph_op_pasal17_idr"] == 44_000_000.0
    # PBB Surabaya NJOP 1.5M - NJOPTKP 15jt = 1.485M * 0.15% = 2.227.500
    assert est_op["pbb_terutang_idr"] == 2_227_500.0


def test_api_step_b_kbli_skos_ter_pph21_dan_tax_allowance_wilayah():
    """Uji Step B API: /kbli, auto-mapping kodeKBLI + NPPN, TER bulanan PP 58/2023, dan syarat wilayah PP 78/2019."""
    r_search = client.get("/kbli", params={"q": "dokter", "limit": 5})
    assert r_search.status_code == 200
    assert any(x["kode_kbli"] == "86201" for x in r_search.json()["results"])

    r_detail = client.get("/kbli/69100")
    assert r_detail.status_code == 200
    assert r_detail.json()["nppn_op"]["10_IbuKota_Provinsi"] == 51.0

    # 1. Pengacara pakai kodeKBLI 69100 di Surabaya (10 Ibu Kota Provinsi) -> NPPN 51% + netto 510jt
    r_adv = client.post(
        "/reason",
        json={
            "wp_id": "API_Advokat_Sby",
            "wp_kind": "OrangPribadi",
            "properties": {
                "kodeKBLI": "69100",
                "berdomisiliDi": ["Wilayah_Kota_Surabaya"],
                "hasOmzetTahunan": 1_000_000_000.0,
                "hasNPWP": True,
            },
        },
    )
    assert r_adv.status_code == 200
    d_adv = r_adv.json()
    assert "OP_PekerjaBebas" in d_adv["inferred_classes"]
    assert d_adv["kbli_info"]["kode_kbli"] == "69100"
    assert d_adv["estimasi_pajak"]["rincian"]["nppn_persen"] == 51.0
    assert d_adv["estimasi_pajak"]["rincian"]["penghasilan_neto_nppn_idr"] == 510_000_000.0

    # 2. Pegawai Tetap TK/0 gaji bruto 10jt/bulan -> TER_A 2% -> Rp200.000/bulan
    r_peg = client.post(
        "/reason",
        json={
            "wp_id": "API_Peg_TER_A",
            "wp_kind": "OrangPribadi",
            "properties": {
                "memilikiPekerjaan": ["PegawaiTetap_Swasta"],
                "isKawin": False,
                "hasJumlahTanggungan": 0,
                "hasPenghasilanBrutoBulanan": 10_000_000.0,
                "hasNPWP": True,
            },
        },
    )
    assert r_peg.status_code == 200
    est_peg = r_peg.json()["estimasi_pajak"]["rincian"]
    assert est_peg["pph21_ter_kategori"] == "TER_A"
    assert est_peg["pph21_ter_persen"] == 2.0
    assert est_peg["pph21_ter_bulanan_idr"] == 200_000.0

    # 3. PT KBLI 03222 (PP 78/2019 Lampiran II kecuali DKI Jakarta)
    r_ta_dki = client.post(
        "/reason",
        json={
            "wp_id": "API_TA_03222_DKI",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "03222",
                "lokasiProvinsiTaxAllowance": "DKI Jakarta",
                "isPenanamanModalBaru": True,
                "hasOmzetTahunan": 20_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_ta_dki.status_code == 200
    assert not any(f["id"] == "Fasilitas_TaxAllowance_PP78_30Pct" for f in r_ta_dki.json()["fasilitas"])

    r_ta_jatim = client.post(
        "/reason",
        json={
            "wp_id": "API_TA_03222_Jatim",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "03222",
                "lokasiProvinsiTaxAllowance": "Jawa Timur",
                "isPenanamanModalBaru": True,
                "hasOmzetTahunan": 20_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_ta_jatim.status_code == 200
    assert any(f["id"] == "Fasilitas_TaxAllowance_PP78_30Pct" for f in r_ta_jatim.json()["fasilitas"])


def test_api_step_c_hybrid_524_perda_endpoints_dan_reasoning():
    """Uji Step C API: /perda, /perda/{id}, dan reasoning hybrid HermiT + SPARQL lokal untuk Kab. Bogor & Kota Bandung."""
    r_list = client.get("/perda", params={"q": "bogor"})
    assert r_list.status_code == 200
    assert any(x["pemda_id"] == "KAB_BOGOR" for x in r_list.json()["results"])

    r_bogor = client.get("/perda/KAB_BOGOR")
    assert r_bogor.status_code == 200
    assert r_bogor.json()["tarif_daerah"]["PBB_P2"]["tarif_persen"] == 0.25

    # Kab. Bogor (bukan 10 Ibu Kota Provinsi -> NPPN Pengacara 50%, PBB 0.25% NJOPTKP 10jt, plus Opsen PKB HKPD)
    r_res_bogor = client.post(
        "/reason",
        json={
            "wp_id": "API_Bogor_Hybrid",
            "wp_kind": "OrangPribadi",
            "properties": {
                "pemdaId": "KAB_BOGOR",
                "kodeKBLI": "69100",
                "hasOmzetTahunan": 1_000_000_000.0,
                "isMemilikiObjekPBB": True,
                "hasNilaiNJOP": 510_000_000.0,
                "hasJumlahKendaraan": 1,
                "hasNPWP": True,
            },
        },
    )
    assert r_res_bogor.status_code == 200
    d_b = r_res_bogor.json()
    kew_b = {k["id"] for k in d_b["kewajiban"]}
    assert {"Kewajiban_LaporPBB", "Kewajiban_Opsen_PKB_66Pct"}.issubset(kew_b)
    assert d_b["perda_info"]["pemda_id"] == "KAB_BOGOR"
    est_b = d_b["estimasi_pajak"]["rincian"]
    assert est_b["nppn_wilayah_kelompok"] == "Daerah_Lain"
    assert est_b["nppn_persen"] == 50.0
    # PBB Bogor: (510jt - 10jt) * 0.25% = 1.250.000
    assert est_b["pbb_terutang_idr"] == 1_250_000.0


def test_api_step_d_kbli_auto_pionir_dan_padat_karya():
    """Uji Step D: kodeKBLI '24101' otomatis memicu Tax Holiday (PerBKPM 7/2020) & '15202' memicu Padat Karya (PMK 16/2020)."""
    r_pionir = client.post(
        "/reason",
        json={
            "wp_id": "API_Pionir_24101",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "24101",
                "isPenanamanModalBaru": True,
                "hasSuratKeteranganFiskal": True,
                "isBelumPernahPutusTaxHoliday": True,
                "hasNilaiInvestasi": 1_500_000_000_000.0,
                "hasOmzetTahunan": 80_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_pionir.status_code == 200
    d_p = r_pionir.json()
    assert "LayakTaxHoliday_100Pct_7Thn" in d_p["inferred_classes"]
    assert d_p["kbli_info"]["industri_pionir"]["eligible_kbli"] is True
    assert "Fasilitas_TaxHoliday_100Pct_7Thn" in {f["id"] for f in d_p["fasilitas"]}

    r_pk = client.post(
        "/reason",
        json={
            "wp_id": "API_PadatKarya_15202",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "15202",
                "isPenanamanModalBaru": True,
                "hasOmzetTahunan": 60_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_pk.status_code == 200
    d_pk = r_pk.json()
    assert "BadanLayakPadatKarya" in d_pk["inferred_classes"]
    assert "Fasilitas_PadatKarya_PMK81_60Pct" in {f["id"] for f in d_pk["fasilitas"]}

    # KBLI 10761 Padat Karya (kecuali DKI Jakarta) -> ditolak jika lokasi DKI Jakarta
    r_pk_dki = client.post(
        "/reason",
        json={
            "wp_id": "API_PadatKarya_10761_DKI",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "10761",
                "pemdaId": "PROV_DKI_JAKARTA",
                "isPenanamanModalBaru": True,
                "hasOmzetTahunan": 60_000_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_pk_dki.status_code == 200
    assert "Fasilitas_PadatKarya_PMK81_60Pct" not in {f["id"] for f in r_pk_dki.json()["fasilitas"]}


def test_api_pph_final_pasal4_2_sewa_deposito_konstruksi_pengalihan():
    """Uji PPh Final Pasal 4(2) end-to-end: /options, pemisahan PKP Pasal 17, konstruksi KBLI 41011, pengalihan, dan pengecualian SPARQL BIND."""
    opt = client.get("/options").json()
    final_ids = {x["id"] for x in opt["final_income_objects"]}
    assert {
        "Jenis_SewaTanahBangunan",
        "Jenis_BungaDepositoTabungan",
        "Jenis_JasaKonstruksi_Kecil_SBU",
        "Jenis_PengalihanTanahBangunan_Umum",
    }.issubset(final_ids)

    # 1. OP Pegawai + Sewa Ruko 120jt + Deposito 50jt + PKP 60jt -> Pasal 17 terpisah dari PPh Final
    r_op = client.post(
        "/reason",
        json={
            "wp_id": "API_OP_Final_Split",
            "wp_kind": "OrangPribadi",
            "properties": {
                "memilikiPekerjaan": ["PegawaiTetap_Swasta"],
                "isSubjekLuarNegeri": False,
                "isPendudukIndonesia": True,
                "isKawin": False,
                "hasJumlahTanggungan": 0,
                "hasPenghasilanKenaPajakTahunan": 60_000_000.0,
                "hasNilaiSewaTanahBangunanTahunan": 120_000_000.0,
                "hasBungaDepositoTabunganTahunan": 50_000_000.0,
                "hasPokokDepositoTabungan": 1_000_000_000.0,
                "hasNPWP": True,
            },
        },
    )
    assert r_op.status_code == 200
    est_op = r_op.json()["estimasi_pajak"]["rincian"]
    assert est_op["pph_op_pasal17_idr"] == 3_000_000.0
    assert est_op["pph_final_sewa_tanah_bangunan_idr"] == 12_000_000.0
    assert est_op["pph_final_bunga_deposito_idr"] == 10_000_000.0
    assert est_op["total_pph_final_pasal4_2_idr"] == 22_000_000.0

    # 2. PT Konstruksi (KBLI 41011) Non-Kecil SBU (2,65%) + Pengalihan Rumah Sederhana (1%)
    r_pt = client.post(
        "/reason",
        json={
            "wp_id": "API_PT_Konst_RS",
            "wp_kind": "PT",
            "properties": {
                "kodeKBLI": "41011",
                "memilikiPenghasilanFinal": ["Jenis_JasaKonstruksi_NonKecil_SBU", "Jenis_PengalihanRumahSederhana"],
                "hasNilaiBrutoJasaKonstruksi": 1_000_000_000.0,
                "hasNilaiPengalihanTanahBangunan": 500_000_000.0,
                "isPerseroanTerbuka": False,
                "isUMKM_PP55": False,
                "hasNPWP": True,
            },
        },
    )
    assert r_pt.status_code == 200
    d_pt = r_pt.json()
    assert d_pt["kbli_info"]["is_jasa_konstruksi"] is True
    est_pt = d_pt["estimasi_pajak"]["rincian"]
    assert est_pt["pph_final_jasa_konstruksi_idr"] == 26_500_000.0
    assert est_pt["pph_final_pengalihan_tanah_bangunan_idr"] == 5_000_000.0
    assert est_pt["total_pph_final_pasal4_2_idr"] == 31_500_000.0

    # 3. Pengecualian: akomodasi penginapan + pokok deposito <= 7,5jt + OP < PTKP pengalihan < 60jt -> semua estimasi final 0.0
    r_exc = client.post(
        "/reason",
        json={
            "wp_id": "API_OP_Final_ZeroExc",
            "wp_kind": "OrangPribadi",
            "properties": {
                "memilikiPenghasilanFinal": ["Jenis_PengalihanTanahBangunan_Umum"],
                "hasNilaiSewaTanahBangunanTahunan": 20_000_000.0,
                "isJasaAkomodasiPenginapan": True,
                "hasBungaDepositoTabunganTahunan": 300_000.0,
                "hasPokokDepositoTabungan": 5_000_000.0,
                "hasNilaiPengalihanTanahBangunan": 45_000_000.0,
                "isPenghasilanDibawahPTKP": True,
                "hasNPWP": True,
            },
        },
    )
    assert r_exc.status_code == 200
    est_exc = r_exc.json()["estimasi_pajak"]["rincian"]
    assert est_exc["pph_final_sewa_tanah_bangunan_idr"] == 0.0
    assert est_exc["pph_final_bunga_deposito_idr"] == 0.0
    assert est_exc["pph_final_pengalihan_tanah_bangunan_idr"] == 0.0
    assert est_exc["total_pph_final_pasal4_2_idr"] == 0.0
