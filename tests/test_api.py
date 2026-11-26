# -*- coding: utf-8 -*-
"""Integration tests FastAPI — kontrak API v2.0.0 (`/api`, payload PRD §9.3)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _reason(payload: dict) -> dict:
    r = client.post("/api/reason", json=payload)
    assert r.status_code == 200, r.text[:800]
    return r.json()


def test_api_health_catalog_options_regions_scenarios():
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["api_version"] == "2.0.0"
    assert h["swrl_rules"] == 97
    assert h["ptkp_tiers"] == 8
    assert h["regions"] == 390

    cat = client.get("/api/catalog").json()
    assert cat["count"] == 103
    assert "Tarif_PPhBadan_22Pct" in cat["items"]

    opt = client.get("/api/options").json()
    assert len(opt["jobs"]) == 32
    assert len(opt["final_income_objects"]) == 13
    assert len(opt["ptkp"]) == 8
    assert {p["status"] for p in opt["ptkp"]} == {"TK/0", "TK/1", "TK/2", "TK/3", "K/0", "K/1", "K/2", "K/3"}

    reg = client.get("/api/regions").json()
    assert reg["count"] == 390
    assert reg["total_perda"] == 524
    bandung = next(x for x in reg["results"] if x["pemda_id"] == "KOTA_BANDUNG")
    assert bandung["zona_nppn"] == "10_IbuKota_Provinsi"
    assert bandung["tarif_pbb_persen"] is None
    assert bandung["catatan_pbb"]

    sc = client.get("/api/scenarios").json()
    assert sc["count"] >= 15


def test_api_contract_v2_root_removed_alias_strictness():
    assert client.get("/health").status_code == 404
    assert client.get("/api/v1/health").status_code == 200

    # Field asing -> 422 (bukan diabaikan diam-diam)
    bad = client.post("/api/reason", json={"wp_id": "X", "wp_kind": "PT", "field_asing": 1})
    assert bad.status_code == 422

    # JSON rusak -> 400
    broken = client.post("/api/reason", content="{bukan json", headers={"content-type": "application/json"})
    assert broken.status_code == 400

    # KBLI / Pemda tak dikenal -> 422
    assert client.post("/api/reason", json={"wp_id": "X", "wp_kind": "PT", "kode_kbli": "99999"}).status_code == 422
    assert client.post("/api/reason", json={"wp_id": "X", "wp_kind": "PT", "pemda_id": "KOTA_TIDAK_ADA"}).status_code == 422

    # Validasi domain
    assert client.post("/api/reason", json={"wp_id": "bad id", "wp_kind": "PT"}).status_code == 422
    assert client.post(
        "/api/reason",
        json={"wp_id": "X", "wp_kind": "PT", "has_persentase_saham_publik": 150},
    ).status_code == 422


def test_api_reason_umkm_boundary_exact_vs_over():
    exact = _reason({"wp_id": "API_UMKM_Exact", "wp_kind": "CV", "has_omzet_tahunan": 4_800_000_000.0, "is_umkm_pp55": True})
    assert "WajibPajakUMKM" in exact["inferred_classes"]
    assert "PengusahaKenaPajak" not in exact["inferred_classes"]
    assert [f["id"] for f in exact["fasilitas"]] == ["Fasilitas_PP55_Final_0_5Pct"]

    over = _reason({"wp_id": "API_UMKM_Over", "wp_kind": "CV", "has_omzet_tahunan": 4_800_000_001.0, "is_umkm_pp55": True})
    assert "PengusahaKenaPajak" in over["inferred_classes"]
    assert "WajibPajakUMKM" not in over["inferred_classes"]
    kew = {k["id"] for k in over["kewajiban"]}
    assert {"Kewajiban_DaftarPKP_PungutPPN", "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum"}.issubset(kew)


def test_api_reason_tbk_threshold_and_mk_provenance():
    low = _reason({
        "wp_id": "API_Tbk_30", "wp_kind": "PT", "has_omzet_tahunan": 80_000_000_000.0,
        "is_perseroan_terbuka": True, "has_persentase_saham_publik": 30.0,
    })
    tarif_low = {t["id"] for t in low["tarif"]}
    assert "Tarif_PPhBadan_22Pct" in tarif_low and "Tarif_PPhBadan_Tbk_19Pct" not in tarif_low

    spa = _reason({
        "wp_id": "API_Spa_MK", "wp_kind": "PT", "has_omzet_tahunan": 2_000_000_000.0,
        "is_usaha_spa_kesehatan_tradisional": True,
    })
    fas = {f["id"]: f for f in spa["fasilitas"]}
    assert "Fasilitas_Pengecualian_SpaKesehatanTradisional_MK" in fas
    assert "MK-2024-19-PUU-XXII" in fas["Fasilitas_Pengecualian_SpaKesehatanTradisional_MK"]["justifikasi"][0]["mk_refs"]


def test_api_reason_op_multistream_prd_golden():
    """Kasus PRD §9.3.5: Guru + Freelance Bandung — mode benar vs mode PRD."""
    d = _reason({
        "wp_id": "WP-OP-BDG-2025-001", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
        "pemda_id": "KOTA_BANDUNG",
        "pekerjaan_utama": {
            "nama": "Guru Swasta SMA", "jenis": "PEGAWAI_TETAP", "kbli": "85121",
            "gaji_bulanan": 8_500_000.0, "omzet_tahunan": 102_000_000.0,
        },
        "pekerjaan_sekunder": {
            "nama": "Freelance Web Developer", "jenis": "PEKERJA_BEBAS", "kbli": "62019",
            "omzet_tahunan": 180_000_000.0, "hpp_tahunan": 25_000_000.0,
            "biaya_operasional_tahunan": 15_000_000.0,
        },
        "is_kawin": True, "has_jumlah_tanggungan": 1, "status_ptkp": "K/1",
        "is_pemberitahuan_nppn_tepat_waktu": True,
        "is_memiliki_objek_pbb": True, "has_nilai_njop": 450_000_000.0,
        "kredit_pajak_1721a1": 1_530_000.0, "jumlah_bukti_potong": 1,
    })
    assert d["klaster_subjek"]["kode"] == "WPOP_MULTI_STREAM"
    assert {"OP_TER_Kategori_B", "OP_PekerjaBebas", "OP_PekerjaBebas_LayakNPPN"}.issubset(set(d["inferred_classes"]))

    ter = d["estimasi_pajak"]["ter_bulanan"]
    assert ter["kategori"] == "B" and ter["tarif_ter_persen"] == 1.0
    assert ter["potongan_per_bulan"] == 85_000.0 and ter["total_potongan_setahun"] == 1_020_000.0

    nppn = d["estimasi_pajak"]["komparasi_skema"]["skema_norma_nppn"]
    assert nppn["status"] == "TERSEDIA"
    assert nppn["persentase_norma"] == 50.0
    assert nppn["penghasilan_neto"] == 90_000_000.0
    assert "62010" in nppn["sumber_norma"]

    rekom = d["estimasi_pajak"]["komparasi_skema"]["rekomendasi_skema"]
    assert rekom["skema_terpilih"] == "skema_norma_nppn"
    assert rekom["penghematan_dasar_kena_pajak"] == 50_000_000.0

    # Mode PRD (gaji bruto tanpa biaya jabatan) harus mereproduksi angka PRD §9.3.5
    prd = d["estimasi_pajak"]["rekonsiliasi_mode_prd"]
    assert prd["total_penghasilan_neto_gabungan"] == 192_000_000.0
    assert prd["penghasilan_kena_pajak_pkp"] == 129_000_000.0
    assert prd["pph_terutang_pasal_17_idr"] == 13_350_000.0
    assert prd["pph_pasal_29_kurang_bayar_idr"] == 11_820_000.0

    benar = d["estimasi_pajak"]["rekonsiliasi_spt_tahunan"]
    assert benar["total_penghasilan_neto_gabungan"] == 186_900_000.0
    assert benar["penghasilan_kena_pajak_pkp"] == 123_900_000.0
    assert benar["pph_terutang_pasal_17_idr"] == 12_585_000.0

    assert any(k["formulir_spt"] == "1770" for k in d["kewajiban"])
    tenggat = [k for k in d["kewajiban"] if k["id"] == "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln"][0]
    assert tenggat["tenggat_waktu"] == "31 Maret 2027"

    assert d["perda_info"]["pemda_id"] == "KOTA_BANDUNG"
    assert d["perda_info"]["zona_nppn"] == "10_IbuKota_Provinsi"
    assert d["estimasi_pajak"]["pbb_p2_terutang_idr"] is None
    assert d["estimasi_pajak"]["pbb_status"] == "TARIF_UMUM_TIDAK_TEREKSTRAK"


def test_api_reason_pure_employee_formulir_needs_verification():
    d = _reason({
        "wp_id": "API_Pegawai_TK0", "wp_kind": "OrangPribadi",
        "pekerjaan_utama": {"nama": "Staf", "jenis": "PEGAWAI_TETAP", "gaji_bulanan": 10_000_000.0},
        "is_kawin": False, "has_jumlah_tanggungan": 0,
        "has_penghasilan_bruto_bulanan": 10_000_000.0,
    })
    assert d["estimasi_pajak"]["ter_bulanan"]["kategori"] == "A"
    assert d["estimasi_pajak"]["ter_bulanan"]["potongan_per_bulan"] == 200_000.0
    spt = [k for k in d["kewajiban"] if k["id"] == "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln"][0]
    assert spt["formulir_spt"] is None
    assert spt["status_formulir"] == "PERLU_VERIFIKASI"
    assert spt["catatan_formulir"]


def test_api_reason_estimator_31e_ppn_denda_dan_pbb_surabaya():
    cv = _reason({
        "wp_id": "API_Est_31E", "wp_kind": "CV",
        "has_omzet_tahunan": 10_000_000_000.0, "has_penghasilan_kena_pajak_tahunan": 1_000_000_000.0,
        "has_dpp_ppn": 2_000_000_000.0, "is_penyerahan_non_mewah_ppn": True, "is_terlambat_lapor_spt": True,
    })
    r = cv["estimasi_pajak"]["rincian"]
    assert r["pph_badan_idr"] == 167_200_000.0
    assert r["penghematan_pasal_31e_idr"] == 52_800_000.0
    assert r["ppn_terutang_idr"] == 220_000_000.0
    assert r["denda_administratif_tetap_idr"] == 1_000_000.0

    op = _reason({
        "wp_id": "API_Est_OP", "wp_kind": "OrangPribadi", "pemda_id": "KOTA_SURABAYA",
        "pekerjaan_utama": {"nama": "Warung", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_200_000_000.0},
        "is_umkm_pp55": True, "has_penghasilan_kena_pajak_tahunan": 300_000_000.0,
        "is_memiliki_objek_pbb": True, "has_nilai_njop": 1_500_000_000.0,
    })
    r2 = op["estimasi_pajak"]["rincian"]
    assert r2["porsi_omzet_bebas_500jt_idr"] == 500_000_000.0
    assert r2["pph_final_umkm_op_idr"] == 3_500_000.0
    assert r2["pph_op_pasal17_idr"] == 44_000_000.0
    assert r2["pbb_terutang_idr"] == 2_227_500.0


def test_api_step_b_kbli_nppn_ter_dan_tax_allowance_wilayah():
    adv = _reason({
        "wp_id": "API_Advokat_Sby", "wp_kind": "OrangPribadi", "pemda_id": "KOTA_SURABAYA",
        "pekerjaan_utama": {"nama": "Advokat", "jenis": "PEKERJA_BEBAS", "kbli": "69100", "omzet_tahunan": 1_000_000_000.0},
    })
    r = adv["estimasi_pajak"]["rincian"]
    assert r["nppn_wilayah_kelompok"] == "10_IbuKota_Provinsi"
    assert r["nppn_persen"] == 51.0
    assert r["penghasilan_neto_nppn_idr"] == 510_000_000.0

    dki = _reason({
        "wp_id": "API_TA_03222_DKI", "wp_kind": "PT", "kode_kbli": "03222",
        "lokasi_provinsi_tax_allowance": "DKI Jakarta", "is_penanaman_modal_baru": True,
        "has_omzet_tahunan": 20_000_000_000.0,
    })
    assert not any(f["id"] == "Fasilitas_TaxAllowance_PP78_30Pct" for f in dki["fasilitas"])

    jatim = _reason({
        "wp_id": "API_TA_03222_Jatim", "wp_kind": "PT", "kode_kbli": "03222",
        "lokasi_provinsi_tax_allowance": "Jawa Timur", "is_penanaman_modal_baru": True,
        "has_omzet_tahunan": 20_000_000_000.0,
    })
    assert any(f["id"] == "Fasilitas_TaxAllowance_PP78_30Pct" for f in jatim["fasilitas"])


def test_api_step_c_hybrid_perda_bogor():
    bogor = _reason({
        "wp_id": "API_Bogor_Hybrid", "wp_kind": "OrangPribadi", "pemda_id": "KAB_BOGOR",
        "pekerjaan_utama": {"nama": "Advokat", "jenis": "PEKERJA_BEBAS", "kbli": "69100", "omzet_tahunan": 1_000_000_000.0},
        "is_memiliki_objek_pbb": True, "has_nilai_njop": 510_000_000.0, "has_jumlah_kendaraan": 1,
    })
    kew = {k["id"] for k in bogor["kewajiban"]}
    assert {"Kewajiban_LaporPBB", "Kewajiban_Opsen_PKB_66Pct"}.issubset(kew)
    r = bogor["estimasi_pajak"]["rincian"]
    assert r["nppn_wilayah_kelompok"] == "Daerah_Lain"
    assert r["nppn_persen"] == 50.0
    assert r["pbb_terutang_idr"] == 1_250_000.0
    assert bogor["perda_info"]["tarif_pbb_persen"] == 0.25


def test_api_step_d_pionir_dan_padat_karya():
    pionir = _reason({
        "wp_id": "API_Pionir_24101", "wp_kind": "PT", "kode_kbli": "24101",
        "is_penanaman_modal_baru": True, "has_surat_keterangan_fiskal": True,
        "is_belum_pernah_putus_tax_holiday": True, "has_nilai_investasi": 1_500_000_000_000.0,
        "has_omzet_tahunan": 80_000_000_000.0,
    })
    assert "LayakTaxHoliday_100Pct_7Thn" in pionir["inferred_classes"]
    assert pionir["inferred_classes"] and any(
        f["id"] == "Fasilitas_TaxHoliday_100Pct_7Thn" for f in pionir["fasilitas"]
    )

    padat = _reason({
        "wp_id": "API_PadatKarya_15202", "wp_kind": "PT", "kode_kbli": "15202",
        "is_penanaman_modal_baru": True, "has_omzet_tahunan": 60_000_000_000.0,
    })
    assert "BadanLayakPadatKarya" in padat["inferred_classes"]
    assert "Fasilitas_PadatKarya_PMK81_60Pct" in {f["id"] for f in padat["fasilitas"]}

    padat_dki = _reason({
        "wp_id": "API_PadatKarya_10761_DKI", "wp_kind": "PT", "kode_kbli": "10761",
        "pemda_id": "PROV_DKI_JAKARTA", "is_penanaman_modal_baru": True,
        "has_omzet_tahunan": 60_000_000_000.0,
    })
    assert "Fasilitas_PadatKarya_PMK81_60Pct" not in {f["id"] for f in padat_dki["fasilitas"]}


def test_api_pph_final_pasal4_2_sewa_deposito_konstruksi_pengalihan():
    op = _reason({
        "wp_id": "API_OP_Final_Split", "wp_kind": "OrangPribadi",
        "pekerjaan_utama": {"nama": "Pegawai", "jenis": "PEGAWAI_TETAP", "gaji_bulanan": 5_000_000.0},
        "is_kawin": False, "has_jumlah_tanggungan": 0,
        "has_penghasilan_kena_pajak_tahunan": 60_000_000.0,
        "penghasilan_final": {"sewa_tanah_bangunan": 120_000_000.0, "bunga_deposito": 50_000_000.0, "pokok_deposito": 1_000_000_000.0},
    })
    pf = op["estimasi_pajak"]["pph_final_pasal4_2"]
    assert pf["pph_final_sewa_tanah_bangunan_idr"] == 12_000_000.0
    assert pf["pph_final_bunga_deposito_idr"] == 10_000_000.0
    assert pf["total_pph_final_pasal4_2_idr"] == 22_000_000.0
    # rincian memakai PKP yang diberikan; rekonsiliasi selalu menghitung ulang dari stream
    assert op["estimasi_pajak"]["rincian"]["pph_op_pasal17_idr"] == 3_000_000.0
    assert op["estimasi_pajak"]["rekonsiliasi_spt_tahunan"]["pph_terutang_pasal_17_idr"] == 150_000.0

    pt = _reason({
        "wp_id": "API_PT_Konst_RS", "wp_kind": "PT", "kode_kbli": "41011",
        "penghasilan_final": {
            "jasa_konstruksi": {"jenis": "NON_KECIL_SBU", "nilai_bruto": 1_000_000_000.0},
            "pengalihan_tanah_bangunan": {"jenis": "RUMAH_SEDERHANA", "nilai": 500_000_000.0},
        },
    })
    pf2 = pt["estimasi_pajak"]["pph_final_pasal4_2"]
    assert pf2["pph_final_jasa_konstruksi_idr"] == 26_500_000.0
    assert pf2["pph_final_pengalihan_tanah_bangunan_idr"] == 5_000_000.0
    assert pf2["total_pph_final_pasal4_2_idr"] == 31_500_000.0


def test_api_but_branch_profit():
    but = _reason({
        "wp_id": "API_BUT_01", "wp_kind": "BadanUsahaTetap",
        "has_omzet_tahunan": 3_000_000_000.0, "has_penghasilan_kena_pajak_tahunan": 500_000_000.0,
        "is_umkm_pp55": True,
    })
    assert {"Tarif_PPhBadan_22Pct", "Tarif_PPh26_4_BUT_BranchProfit_20Pct"}.issubset({t["id"] for t in but["tarif"]})
    assert but["fasilitas"] == []
    assert but["klaster_subjek"]["kode"] == "BUT"


def test_api_sparql_provenance_and_stats():
    prov = client.get("/api/sparql/provenance", params={"rule_id": "R-UU-1983-6-ad287a542a"}).json()
    assert prov["count"] == 1
    assert prov["results"][0]["document_id"] == "UU-1983-6"
    assert prov["results"][0]["sema_ref"] == "SEMA_2024_2_TUN_4"

    stats = client.get("/api/sparql/stats").json()
    assert stats["total_rules"] == 12921
    assert stats["by_domain"]["Domain_D_ADMIN_SANKSI"] == 3417

def test_api_pp2026_20_kelayakan_pp55_dan_provenance():
    """X-1: PP 20/2026 — koperasi 4 tahun, PT Perorangan keahlian khusus, omzet gabungan, peralihan OP."""
    koperasi = _reason({
        "wp_id": "API_PP2026_Koperasi", "wp_kind": "Koperasi", "tahun_pajak": 2026,
        "tahun_terdaftar": 2021,
        "pekerjaan_sekunder": {"nama": "Unit Usaha", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
    })
    pk = koperasi["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    assert pk["status"] == "DISKUALIFIKASI"
    assert "Pasal 57(2)f" in pk["alasan"]
    assert pk["dasar_hukum"], "harus mengutip rule_id PP-2026-20"

    ptp = _reason({
        "wp_id": "API_PP2026_PTP", "wp_kind": "PT", "tahun_pajak": 2026,
        "is_perseroan_perorangan": True, "memiliki_keahlian_khusus": True,
        "pekerjaan_sekunder": {"nama": "Konsultan", "jenis": "USAHA_UMKM", "omzet_tahunan": 500_000_000.0},
    })
    ptp_pp = ptp["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    assert ptp_pp["status"] == "DISKUALIFIKASI"
    assert "Pasal 57(2)b" in ptp_pp["alasan"]

    gabungan = _reason({
        "wp_id": "API_PP2026_Gabungan", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
        "pekerjaan_sekunder": {"nama": "Toko", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
        "omzet_gabungan_grup": 5_000_000_000.0,
    })
    gb = gabungan["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    assert gb["status"] == "DISKUALIFIKASI"
    assert "Pasal 57(2)e" in gb["alasan"]

    peralihan = _reason({
        "wp_id": "API_PP2026_Peralihan", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
        "tahun_mulai_pp55": 2018,
        "pekerjaan_sekunder": {"nama": "Toko", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
    })
    pr = peralihan["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    assert pr["status"] == "LAYAK"
    assert "Pasal II" in pr["alasan"]

    prov = client.get("/api/sparql/provenance", params={"document_id": "PP-2026-20", "limit": 20}).json()
    assert prov["count"] == 14
    larangan = client.get(
        "/api/sparql/provenance", params={"document_id": "PP-2026-20", "rule_type": "Larangan", "limit": 5}
    ).json()
    assert larangan["count"] == 1
    assert "suap" in larangan["results"][0]["source_quote"].lower()

def test_api_risk_patterns_dan_cbr_tahap1():
    cat = client.get("/api/risk-patterns").json()
    assert cat["total"] == 10
    ids = {i["pola_id"] for i in cat["items"]}
    assert ids == {f"RP-{n:02d}" for n in range(1, 11)}
    assert all(i["dasar_hukum"] for i in cat["items"])
    assert all(i["grounding_status"] == "LENGKAP" for i in cat["items"])

    cbr = client.get("/api/cbr/search", params={"q": "koreksi biaya promosi", "klaster": "pph_badan"}).json()
    assert cbr["count"] == 3
    assert all(0.0 <= m["similarity_score"] <= 1.0 for m in cbr["results"])
    assert cbr["results"][0]["case_id"]

    pt = _reason({
        "wp_id": "API_RISK_PT", "wp_kind": "PT", "tahun_pajak": 2026,
        "has_omzet_tahunan": 5_000_000_000.0, "is_umkm_pp55": True, "tahun_mulai_pp55": 2019,
        "is_terdaftar_pkp": False,
        "pekerjaan_sekunder": {"nama": "Unit", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
        "cbr_kueri": "koreksi biaya promosi",
    })
    pola = {r["pola_id"] for r in pt["risiko_fiskal"]}
    assert {"RP-01", "RP-04"}.issubset(pola)
    assert len(pt["cbr_matches"]) == 3

    op = _reason({
        "wp_id": "API_RISK_OP", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
        "has_omzet_tahunan": 2_500_000_000.0, "is_umkm_pp55": True,
        "is_pisah_harta": True, "omzet_pasangan": 3_000_000_000.0,
        "pekerjaan_sekunder": {"nama": "Freelance", "jenis": "PEKERJA_BEBAS", "omzet_tahunan": 500_000_000.0},
    })
    pola_op = {r["pola_id"] for r in op["risiko_fiskal"]}
    assert {"RP-02", "RP-06"}.issubset(pola_op)

    suap = _reason({
        "wp_id": "API_RISK_SUAP", "wp_kind": "PT",
        "is_membebankan_suap_gratifikasi": True,
    })
    rp7 = [r for r in suap["risiko_fiskal"] if r["pola_id"] == "RP-07"]
    assert rp7 and rp7[0]["tingkat_risiko"] == "TINGGI"
    assert any(j["document_id"] == "PP-2026-20" for j in rp7[0]["dasar_hukum"])


def test_api_coretax_playbook_kap_kjs():
    kode = client.get("/api/coretax/kode", params={"q": "sewa"}).json()
    assert kode["count"] >= 1
    assert kode["results"][0]["kap_kjs"] == "411128-403"

    pb = client.get(
        "/api/coretax/playbook", params={"kewajiban": "Kewajiban_PotongSetor_SewaTanahBangunan"}
    ).json()
    assert pb["count"] == 1
    item = pb["items"][0]
    assert item["kap_kjs"] == "411128-403"
    assert item["langkah"] and item["langkah"][0]["halaman"] == 23
    assert pb["sumber"]["jenis_sumber"] == "panduan_djp"

    semua = client.get("/api/coretax/playbook").json()
    assert semua["count"] == 13

    d = _reason({
        "wp_id": "API_CORETAX_SEWA", "wp_kind": "OrangPribadi",
        "penghasilan_final": {"sewa_tanah_bangunan": 120_000_000.0},
    })
    ids = {p["kewajiban_id"] for p in d["playbook_coretax"]}
    assert "Kewajiban_PotongSetor_SewaTanahBangunan" in ids


def test_api_metrics_dan_cache_hit():
    m = client.get("/api/metrics").json()
    assert "cache" in m and "latency_ms" in m
    assert m["target"]["cache_hit_p95_ms"] == 1000
    assert m["target"]["cache_miss_p95_ms"] == 10000

    payload = {"wp_id": "API_METRIK_CACHE", "wp_kind": "CV", "has_omzet_tahunan": 5_000_000_000.0}
    first = _reason(payload)
    assert first["cache_hit"] is False
    second = _reason(payload)
    assert second["cache_hit"] is True
    assert second["elapsed_ms"] < 1000

    m2 = client.get("/api/metrics").json()
    assert m2["cache"]["hits"] >= 1
    assert m2["cache"]["hit_rate"] > 0
