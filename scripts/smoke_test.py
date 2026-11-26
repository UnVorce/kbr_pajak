# -*- coding: utf-8 -*-
"""Smoke test kontrak API v2.0.0 (dijalankan sebelum/sesudah deploy, tanpa butuh server).

    python3 scripts/smoke_test.py --in-process            # CI, tanpa uvicorn
    python3 scripts/smoke_test.py --base-url http://host:8000

Exit code 0 bila semua cek lulus.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOLERANCE = 0.5


class Checker:
    def __init__(self) -> None:
        self.rows: List[Tuple[str, bool, str]] = []

    def check(self, name: str, actual: Any, expected: Any) -> None:
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            ok = abs(float(actual) - float(expected)) <= TOLERANCE
        else:
            ok = actual == expected
        self.rows.append((name, ok, f"actual={actual!r} expected={expected!r}"))

    def has(self, name: str, actual, expected_subset) -> None:
        missing = sorted(set(expected_subset) - set(actual))
        self.rows.append((name, not missing, f"missing={missing}" if missing else "semua ada"))

    def summary(self) -> int:
        failed = [r for r in self.rows if not r[1]]
        width = max((len(r[0]) for r in self.rows), default=10)
        for name, ok, detail in self.rows:
            print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}}  {'' if ok else detail}")
        print(f"\n{len(self.rows) - len(failed)}/{len(self.rows)} cek lulus")
        return 0 if not failed else 1


def _client(base_url: str, in_process: bool):
    if in_process:
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)
    import httpx

    return httpx.Client(base_url=base_url, timeout=90.0)


def _post(client, path: str, payload: dict) -> dict:
    r = client.post(path, json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:500]}")
    return r.json()


PRD_GURU = {
    "wp_id": "SMOKE_PRD_GURU",
    "wp_kind": "OrangPribadi",
    "tahun_pajak": 2026,
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
}


def run(base_url: str, in_process: bool) -> int:
    client = _client(base_url, in_process)
    c = Checker()

    # 1. Artefak & statistik
    h = client.get("/api/health").json()
    c.check("health.status", h.get("status"), "ok")
    c.check("health.api_version", h.get("api_version"), "2.0.0")
    c.check("health.swrl_rules", h.get("swrl_rules"), 97)
    c.check("health.reasoning_classes", h.get("reasoning_classes"), 157)
    c.check("health.reasoning_individuals", h.get("reasoning_individuals"), 446)
    c.check("health.ptkp_tiers", h.get("ptkp_tiers"), 8)
    c.check("health.regions", h.get("regions"), 390)
    c.check("health.full_rules_exported", h.get("full_rules_exported"), 12921)

    # 2. Kontrak: root dihapus, alias v1 hidup, strictness
    c.check("contract.root_removed", client.get("/health").status_code, 404)
    c.check("contract.alias_v1", client.get("/api/v1/health").status_code, 200)
    c.check("contract.extra_field_422", client.post("/api/reason", json={"wp_id": "X", "wp_kind": "PT", "x": 1}).status_code, 422)
    c.check(
        "contract.bad_json_400",
        client.post("/api/reason", content="{bad", headers={"content-type": "application/json"}).status_code,
        400,
    )
    c.check("contract.unknown_kbli_422", client.post("/api/reason", json={"wp_id": "X", "wp_kind": "PT", "kode_kbli": "99999"}).status_code, 422)

    # 3. Opsi & wilayah
    opt = client.get("/api/options").json()
    c.check("options.jobs", len(opt["jobs"]), 32)
    c.check("options.ptkp", len(opt["ptkp"]), 8)
    c.check("options.final_objects", len(opt["final_income_objects"]), 13)
    reg = client.get("/api/regions").json()
    c.check("regions.count", reg["count"], 390)
    c.check("regions.total_perda", reg["total_perda"], 524)
    bandung = next(x for x in reg["results"] if x["pemda_id"] == "KOTA_BANDUNG")
    c.check("regions.bandung.zona", bandung["zona_nppn"], "10_IbuKota_Provinsi")
    c.check("regions.bandung.pbb_null", bandung["tarif_pbb_persen"], None)
    bogor = next(x for x in reg["results"] if x["pemda_id"] == "KAB_BOGOR")
    c.check("regions.bogor.pbb", bogor["tarif_pbb_persen"], 0.25)

    # 4. Graf pendukung & provenance
    c.check("kbli.69100.nppn", client.get("/api/kbli/69100").json()["nppn_op"]["10_IbuKota_Provinsi"], 51.0)
    c.check("kbli.41011.konstruksi", client.get("/api/kbli/41011").json()["is_jasa_konstruksi"], True)
    c.check("perda.bogor.pbb", client.get("/api/perda/KAB_BOGOR").json()["tarif_daerah"]["PBB_P2"]["tarif_persen"], 0.25)
    prov = client.get("/api/sparql/provenance", params={"rule_id": "R-UU-1983-6-ad287a542a"}).json()
    c.check("sparql.provenance", prov["count"], 1)
    c.check("sparql.document", prov["results"][0]["document_id"], "UU-1983-6")
    c.check("sparql.stats.total", client.get("/api/sparql/stats").json()["total_rules"], 12921)

    # 4b. X-1: aturan PP 20/2026 & kelayakan PPh Final
    pp26 = client.get("/api/sparql/provenance", params={"document_id": "PP-2026-20", "limit": 20}).json()
    c.check("pp2026.rules", pp26["count"], 14)
    larangan = client.get("/api/sparql/provenance", params={"document_id": "PP-2026-20", "rule_type": "Larangan"}).json()
    c.check("pp2026.pasal_20a", larangan["count"], 1)

    kop = _post(client, "/api/reason", {
        "wp_id": "SMOKE_PP2026_KOPERASI", "wp_kind": "Koperasi", "tahun_pajak": 2026,
        "tahun_terdaftar": 2021,
        "pekerjaan_sekunder": {"nama": "Unit Usaha", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
    })["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    c.check("pp2026.koperasi_4th", kop["status"], "DISKUALIFIKASI")
    c.check("pp2026.koperasi_dasar", bool(kop["dasar_hukum"]), True)

    per = _post(client, "/api/reason", {
        "wp_id": "SMOKE_PP2026_PERALIHAN", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
        "tahun_mulai_pp55": 2018,
        "pekerjaan_sekunder": {"nama": "Toko", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
    })["estimasi_pajak"]["komparasi_skema"]["skema_pp55_final"]
    c.check("pp2026.peralihan_op", per["status"], "LAYAK")

    # 4c. B3/B4: katalog risiko & CBR tahap 1
    cat = client.get("/api/risk-patterns").json()
    c.check("risk.catalog", cat["total"], 10)
    cbr = client.get("/api/cbr/search", params={"q": "koreksi biaya promosi", "limit": 3}).json()
    c.check("cbr.count", cbr["count"], 3)
    c.check("cbr.max_score", max(m["similarity_score"] for m in cbr["results"]) <= 1.0, True)
    kode = client.get("/api/coretax/kode", params={"q": "sewa"}).json()
    c.check("coretax.kode", kode["count"] >= 1 and kode["results"][0]["kap_kjs"], "411128-403")
    c.check("coretax.total_kode", kode["total_kode"], 54)

    # 5. Kasus PRD §9.3.5 — Guru + Freelance Bandung
    g = _post(client, "/api/reason", PRD_GURU)
    c.check("PRD.klaster", g["klaster_subjek"]["kode"], "WPOP_MULTI_STREAM")
    c.check("PRD.ter_kategori", g["estimasi_pajak"]["ter_bulanan"]["kategori"], "B")
    c.check("PRD.ter_persen", g["estimasi_pajak"]["ter_bulanan"]["tarif_ter_persen"], 1.0)
    c.check("PRD.ter_bulanan", g["estimasi_pajak"]["ter_bulanan"]["potongan_per_bulan"], 85_000.0)
    nppn = g["estimasi_pajak"]["komparasi_skema"]["skema_norma_nppn"]
    c.check("PRD.nppn_pct", nppn["persentase_norma"], 50.0)
    c.check("PRD.nppn_neto", nppn["penghasilan_neto"], 90_000_000.0)
    c.check("PRD.rekomendasi", g["estimasi_pajak"]["komparasi_skema"]["rekomendasi_skema"]["skema_terpilih"], "skema_norma_nppn")
    c.check("PRD.penghematan_dasar", g["estimasi_pajak"]["komparasi_skema"]["rekomendasi_skema"]["penghematan_dasar_kena_pajak"], 50_000_000.0)
    prd = g["estimasi_pajak"]["rekonsiliasi_mode_prd"]
    c.check("PRD.neto_gabungan", prd["total_penghasilan_neto_gabungan"], 192_000_000.0)
    c.check("PRD.pkp", prd["penghasilan_kena_pajak_pkp"], 129_000_000.0)
    c.check("PRD.pph17", prd["pph_terutang_pasal_17_idr"], 13_350_000.0)
    c.check("PRD.pph29", prd["pph_pasal_29_kurang_bayar_idr"], 11_820_000.0)
    benar = g["estimasi_pajak"]["rekonsiliasi_spt_tahunan"]
    c.check("PRD.neto_benar", benar["total_penghasilan_neto_gabungan"], 186_900_000.0)
    c.check("PRD.pkp_benar", benar["penghasilan_kena_pajak_pkp"], 123_900_000.0)
    c.check("PRD.pph17_benar", benar["pph_terutang_pasal_17_idr"], 12_585_000.0)
    c.check("PRD.formulir", next(k for k in g["kewajiban"] if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan"))["formulir_spt"], "1770")
    c.check("PRD.tenggat", next(k for k in g["kewajiban"] if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan"))["tenggat_waktu"], "31 Maret 2027")
    c.check("PRD.pbb_status", g["estimasi_pajak"]["pbb_status"], "TARIF_UMUM_TIDAK_TEREKSTRAK")
    c.check("PRD.risiko_list", isinstance(g.get("risiko_fiskal"), list), True)


    # 6. Kasus emas A — OP UMKM kuliner
    a = _post(client, "/api/reason", {
        "wp_id": "SMOKE_A_UMKM", "wp_kind": "OrangPribadi",
        "pekerjaan_utama": {"nama": "Warung", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_200_000_000.0},
        "is_umkm_pp55": True, "has_penghasilan_kena_pajak_tahunan": 300_000_000.0,
    })["estimasi_pajak"]["rincian"]
    c.check("A.porsi_bebas", a["porsi_omzet_bebas_500jt_idr"], 500_000_000.0)
    c.check("A.pph_umkm", a["pph_final_umkm_op_idr"], 3_500_000.0)
    c.check("A.pph17", a["pph_op_pasal17_idr"], 44_000_000.0)

    # 7. Kasus emas C — CV Pasal 31E + PPN + denda
    cv = _post(client, "/api/reason", {
        "wp_id": "SMOKE_C_31E", "wp_kind": "CV",
        "has_omzet_tahunan": 10_000_000_000.0, "has_penghasilan_kena_pajak_tahunan": 1_000_000_000.0,
        "has_dpp_ppn": 2_000_000_000.0, "is_penyerahan_non_mewah_ppn": True, "is_terlambat_lapor_spt": True,
    })["estimasi_pajak"]["rincian"]
    c.check("C.pph_badan", cv["pph_badan_idr"], 167_200_000.0)
    c.check("C.penghematan_31e", cv["penghematan_pasal_31e_idr"], 52_800_000.0)
    c.check("C.ppn", cv["ppn_terutang_idr"], 220_000_000.0)
    c.check("C.denda", cv["denda_administratif_tetap_idr"], 1_000_000.0)

    # 8. Kasus emas D — PT Tbk 19%
    tbk = _post(client, "/api/reason", {
        "wp_id": "SMOKE_D_TBK", "wp_kind": "PT",
        "has_omzet_tahunan": 200_000_000_000.0, "has_penghasilan_kena_pajak_tahunan": 100_000_000_000.0,
        "is_perseroan_terbuka": True, "has_persentase_saham_publik": 45.0,
        "has_jumlah_pemegang_saham_publik": 350, "has_hari_terpenuhi_tbk": 200,
    })
    c.check("D.pph_badan_19", tbk["estimasi_pajak"]["rincian"]["pph_badan_idr"], 19_000_000_000.0)
    c.has("D.tarif", {t["id"] for t in tbk["tarif"]}, {"Tarif_PPhBadan_Tbk_19Pct"})

    # 9. Kasus emas E — konstruksi + pengalihan rumah sederhana
    e = _post(client, "/api/reason", {
        "wp_id": "SMOKE_E_KONSTRUKSI", "wp_kind": "PT", "kode_kbli": "41011",
        "penghasilan_final": {
            "jasa_konstruksi": {"jenis": "NON_KECIL_SBU", "nilai_bruto": 1_000_000_000.0},
            "pengalihan_tanah_bangunan": {"jenis": "RUMAH_SEDERHANA", "nilai": 500_000_000.0},
        },
    })
    pf = e["estimasi_pajak"]["pph_final_pasal4_2"]
    c.check("E.konstruksi", pf["pph_final_jasa_konstruksi_idr"], 26_500_000.0)
    c.check("E.pengalihan", pf["pph_final_pengalihan_tanah_bangunan_idr"], 5_000_000.0)
    c.check("E.total_final", pf["total_pph_final_pasal4_2_idr"], 31_500_000.0)

    # 10. Kasus emas F — pengecualian PPh Final
    f_res = _post(client, "/api/reason", {
        "wp_id": "SMOKE_F_PENGECUALIAN", "wp_kind": "OrangPribadi",
        "penghasilan_final": {
            "sewa_tanah_bangunan": 20_000_000.0, "is_jasa_akomodasi_penginapan": True,
            "bunga_deposito": 300_000.0, "pokok_deposito": 5_000_000.0,
            "pengalihan_tanah_bangunan": {"jenis": "UMUM", "nilai": 45_000_000.0},
            "is_penghasilan_dibawah_ptkp": True,
        },
    })
    f = f_res["estimasi_pajak"]["pph_final_pasal4_2"]
    pb = {p.get("kap_kjs") for p in f_res.get("playbook_coretax") or []}
    c.check("F.playbook_sewa", "411128-403" in pb, True)
    c.check("F.sewa_nihil", f["pph_final_sewa_tanah_bangunan_idr"], 0.0)
    c.check("F.deposito_nihil", f["pph_final_bunga_deposito_idr"], 0.0)
    c.check("F.pengalihan_nihil", f["pph_final_pengalihan_tanah_bangunan_idr"], 0.0)
    c.check("F.total_nihil", f["total_pph_final_pasal4_2_idr"], 0.0)

    # 11. Karyawan murni — formulir 1770 S/SS ditandai perlu verifikasi
    peg = _post(client, "/api/reason", {
        "wp_id": "SMOKE_G_PEGAWAI", "wp_kind": "OrangPribadi",
        "pekerjaan_utama": {"nama": "Staf", "jenis": "PEGAWAI_TETAP", "gaji_bulanan": 10_000_000.0},
    })
    spt = next(k for k in peg["kewajiban"] if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan"))
    c.check("G.ter_A", peg["estimasi_pajak"]["ter_bulanan"]["kategori"], "A")
    c.check("G.formulir_null", spt["formulir_spt"], None)
    c.check("G.status_formulir", spt["status_formulir"], "PERLU_VERIFIKASI")

    return c.summary()


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke test kontrak KBR Pajak API v2.0.0")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--in-process", action="store_true", help="uji langsung FastAPI tanpa server")
    args = ap.parse_args()
    print(f"Smoke test -> {'in-process (TestClient)' if args.in_process else args.base_url}\n")
    try:
        return run(args.base_url, args.in_process)
    except Exception as exc:  # noqa: BLE001
        print(f"SMOKE TEST GAGAL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
