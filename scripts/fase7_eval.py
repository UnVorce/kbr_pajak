# -*- coding: utf-8 -*-
"""Evaluasi batch Fase 7 (Gate G7) — Uji 12 skenario normal + boundary + MK/SEMA melalui backend FastAPI/HermiT."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.engine import KBRReasoningEngine

EVAL_SCENARIOS = [
    {
        "code": "TK-A2-1a",
        "desc": "Industri pionir investasi tepat Rp500M -> Tax Holiday 100% 5 tahun",
        "wp_id": "Eval_TH_500M",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 40_000_000_000.0,
            "isIndustriPionir": True,
            "isPenanamanModalBaru": True,
            "hasSuratKeteranganFiskal": True,
            "isBelumPernahPutusTaxHoliday": True,
            "hasNilaiInvestasi": 500_000_000_000.0,
            "isPenyerahanNonMewahPPN": True,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
        "expect_classes": ["LayakTaxHoliday_100Pct_5Thn", "PengusahaKenaPajak", "BadanLayakPasal31E"],
        "expect_fasilitas": ["Fasilitas_TaxHoliday_100Pct_5Thn", "Fasilitas_TaxHoliday_Transisi_50Pct_2Thn"],
        "expect_tarif": ["Tarif_PPhBadan_22Pct", "Tarif_PPN_Efektif_11Pct"],
    },
    {
        "code": "TK-A2-1b",
        "desc": "Industri pionir investasi Rp1,5T -> Tax Holiday 100% 7 tahun",
        "wp_id": "Eval_TH_1_5T",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 60_000_000_000.0,
            "isIndustriPionir": True,
            "isPenanamanModalBaru": True,
            "hasSuratKeteranganFiskal": True,
            "isBelumPernahPutusTaxHoliday": True,
            "hasNilaiInvestasi": 1_500_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
        "expect_classes": ["LayakTaxHoliday_100Pct_7Thn"],
        "expect_fasilitas": ["Fasilitas_TaxHoliday_100Pct_7Thn", "Fasilitas_TaxHoliday_Transisi_50Pct_2Thn"],
    },
    {
        "code": "TK-A2-2a",
        "desc": "PT Tbk saham publik 45%, >=300 pihak, >=183 hari -> Tarif 19% (diskon 3%)",
        "wp_id": "Eval_Tbk_45",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 150_000_000_000.0,
            "isPerseroanTerbuka": True,
            "hasPersentaseSahamPublik": 45.0,
            "hasJumlahPemegangSahamPublik": 350,
            "hasHariTerpenuhiTbk": 200,
            "isPenyerahanBKP_Mewah": True,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
        "expect_classes": ["BadanTerbukaTbk", "PengusahaKenaPajak"],
        "expect_tarif": ["Tarif_PPhBadan_Tbk_19Pct", "Tarif_PPN_12Pct"],
    },
    {
        "code": "TK-A2-2b",
        "desc": "Edge case PT Tbk saham publik hanya 30% (<40%) -> tetap Tarif Umum 22%",
        "wp_id": "Eval_Tbk_30",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 150_000_000_000.0,
            "isPerseroanTerbuka": True,
            "hasPersentaseSahamPublik": 30.0,
            "isUMKM_PP55": False,
            "hasNPWP": True,
        },
        "expect_classes": ["BadanNonTbk", "PengusahaKenaPajak"],
        "expect_tarif": ["Tarif_PPhBadan_22Pct"],
        "forbid_tarif": ["Tarif_PPhBadan_Tbk_19Pct"],
    },
    {
        "code": "TK-A2-2c",
        "desc": "Boundary tepat Rp4,8M UMKM PP 55 -> masih WajibPajakUMKM (belum PKP)",
        "wp_id": "Eval_UMKM_Exact_4_8M",
        "wp_kind": "CV",
        "props": {
            "hasOmzetTahunan": 4_800_000_000.0,
            "isUMKM_PP55": True,
            "isPerseroanTerbuka": False,
            "hasNPWP": True,
        },
        "expect_classes": ["WajibPajakUMKM", "BadanNonTbk"],
        "expect_fasilitas": ["Fasilitas_PP55_Final_0_5Pct"],
        "forbid_classes": ["PengusahaKenaPajak", "WajibPajakNonUMKM"],
        "forbid_kewajiban": ["Kewajiban_DaftarPKP_PungutPPN", "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum"],
    },
    {
        "code": "TK-B1",
        "desc": "Boundary Rp4.800.000.001 UMKM PP 55 -> wajib PKP, transisi ketentuan umum, Pasal 31E & PPN Efektif 11%",
        "wp_id": "Eval_UMKM_Over_1Rp",
        "wp_kind": "CV",
        "props": {
            "hasOmzetTahunan": 4_800_000_001.0,
            "isUMKM_PP55": True,
            "isPenyerahanNonMewahPPN": True,
            "isPerseroanTerbuka": False,
            "hasNPWP": True,
        },
        "expect_classes": ["PengusahaKenaPajak", "WajibPajakNonUMKM", "BadanLayakPasal31E"],
        "expect_kewajiban": ["Kewajiban_DaftarPKP_PungutPPN", "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum"],
        "expect_tarif": ["Tarif_PPhBadan_22Pct", "Tarif_PPN_Efektif_11Pct"],
        "expect_fasilitas": ["Fasilitas_Pasal31E_Diskon50Pct_11Pct"],
        "forbid_classes": ["WajibPajakUMKM"],
        "forbid_fasilitas": ["Fasilitas_PP55_Final_0_5Pct"],
    },
    {
        "code": "TK-B2",
        "desc": "PKP penyerahan barang non-mewah (DPP 11/12) + BKP Strategis dibebaskan (tanpa PPN 12% barang mewah)",
        "wp_id": "Eval_PPN_Mix",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 12_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isPenyerahanNonMewahPPN": True,
            "isPenyerahanBKPStrategis": True,
            "hasNPWP": True,
        },
        "expect_tarif": ["Tarif_PPN_Efektif_11Pct"],
        "forbid_tarif": ["Tarif_PPN_12Pct"],
        "expect_fasilitas": ["Fasilitas_PPN_Dibebaskan_Strategis"],
    },
    {
        "code": "TK-C1",
        "desc": "Pemilik objek PBB-P2 di DKI Jakarta -> Tarif PBB 0,5% + kewajiban PBB",
        "wp_id": "Eval_PBB_DKI",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 3_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isDomisiliDKI": True,
            "isMemilikiObjekPBB": True,
            "hasNPWP": True,
        },
        "expect_tarif": ["Tarif_PBB_DKI_0_5Pct"],
        "expect_kewajiban": ["Kewajiban_LaporPBB"],
    },
    {
        "code": "TK-C2a",
        "desc": "Kontras MK: Spa Kesehatan Tradisional -> Pengecualian PBJT 40% (MK-2024-19-PUU-XXII)",
        "wp_id": "Eval_Spa_MK",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 2_500_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isUsahaSpaKesehatanTradisional": True,
            "hasNPWP": True,
        },
        "expect_fasilitas": ["Fasilitas_Pengecualian_SpaKesehatanTradisional_MK"],
        "forbid_tarif": ["Tarif_PBJT_Hiburan_DKI_40Pct"],
    },
    {
        "code": "TK-C2b",
        "desc": "Kontras MK: Spa Hiburan Umum di DKI -> Tarif PBJT Hiburan Khusus 40%",
        "wp_id": "Eval_Spa_Hiburan",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 2_500_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "isDomisiliDKI": True,
            "isUsahaHiburanSpaUmum": True,
            "hasNPWP": True,
        },
        "expect_tarif": ["Tarif_PBJT_Hiburan_DKI_40Pct"],
        "forbid_fasilitas": ["Fasilitas_Pengecualian_SpaKesehatanTradisional_MK"],
    },
    {
        "code": "TK-D1",
        "desc": "OP Penduduk DKI kendaraan ke-5 -> PKB 6%, NIK-NPWP, tenggat SPT 3 bulan",
        "wp_id": "Eval_OP_5_DKI",
        "wp_kind": "OrangPribadi",
        "props": {
            "isDomisiliDKI": True,
            "isMilikPribadi": True,
            "hasJumlahKendaraan": 5,
            "isPendudukIndonesia": True,
            "hasNPWP": True,
        },
        "expect_classes": ["OP_KendaraanKe5Plus_DKI"],
        "expect_tarif": ["Tarif_PKB_DKI_Ke5Plus_6Pct"],
        "expect_kewajiban": ["Kewajiban_NPWP_NIK_OP", "Kewajiban_LaporSPT", "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln"],
    },
    {
        "code": "TK-D2-E1",
        "desc": "Telat SPT Badan + Keberatan & Banding ditolak -> Denda Rp1jt + 30%/60% + SEMA-2024-2-TUN-4",
        "wp_id": "Eval_Sanksi_Full",
        "wp_kind": "PT",
        "props": {
            "hasOmzetTahunan": 10_000_000_000.0,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasNPWP": True,
            "isTerlambatLaporSPT": True,
            "isKeberatanDitolak": True,
            "isBandingDitolak": True,
        },
        "expect_sanksi": ["Sanksi_Denda_KUP_SPT_Badan_1Jt", "Sanksi_Keberatan_30Pct", "Sanksi_Banding_60Pct"],
    },
    {
        "code": "TK-OP-MULTI",
        "desc": "OP Multi-Peran (Dokter + Pegawai K/2 + E-Commerce 350jt) + PBB Surabaya",
        "wp_id": "Eval_OP_MultiRole",
        "wp_kind": "OrangPribadi",
        "props": {
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
        "expect_classes": ["OP_PekerjaBebas", "OP_TER_Kategori_B", "OP_UMKM_Bebas_500Jt", "WP_PBB_Surabaya_L3"],
        "expect_tarif": ["Tarif_PPh21_TER_Bulanan_Kategori_B", "Tarif_PPh21_BukanPegawai_DPP50Pct", "Tarif_PBB_Surabaya_L3_0_15Pct"],
        "expect_fasilitas": ["Fasilitas_OP_UMKM_BebasPPh_500Jt", "Fasilitas_NPPN_OP_Dibawah_4_8M"],
        "forbid_fasilitas": ["Fasilitas_PP55_Final_0_5Pct"],
    },
    {
        "code": "TK-BUT-23",
        "desc": "BUT kena Branch Profit Tax 20% + PPh 22% (dilarang PP55 & 31E) vs PPh 23 non-NPWP",
        "wp_id": "Eval_BUT_01",
        "wp_kind": "BUT",
        "props": {
            "hasOmzetTahunan": 3_000_000_000.0,
            "isUMKM_PP55": True,
            "hasNPWP": True,
        },
        "expect_tarif": ["Tarif_PPhBadan_22Pct", "Tarif_PPh26_4_BUT_BranchProfit_20Pct"],
        "forbid_fasilitas": ["Fasilitas_PP55_Final_0_5Pct", "Fasilitas_Pasal31E_Diskon50Pct_11Pct"],
    },
    {
        "code": "TK-PPH23",
        "desc": "Penerima jasa PPh 23 tanpa NPWP -> Tarif 2% + Sanksi kenaikan 100%",
        "wp_id": "Eval_PPh23_NonNPWP",
        "wp_kind": "CV",
        "props": {
            "isPenerimaPenghasilanPPh23_JasaSewa": True,
            "isBankPenerimaPenghasilan": False,
            "hasNPWP": False,
            "isPerseroanTerbuka": False,
            "isUMKM_PP55": False,
            "hasOmzetTahunan": 1_000_000_000.0,
        },
        "expect_tarif": ["Tarif_PPh23_JasaSewa_2Pct"],
        "expect_sanksi": ["Sanksi_PPh23_Kenaikan100Pct_NonNPWP"],
    },
]


def run_eval() -> dict:
    engine = KBRReasoningEngine()
    results = []
    passed = 0
    for sc in EVAL_SCENARIOS:
        res = engine.reason(sc["wp_id"], sc["wp_kind"], sc["props"])
        cls_set = set(res["inferred_classes"])
        tarif_set = {x["id"] for x in res["tarif"]}
        fas_set = {x["id"] for x in res["fasilitas"]}
        kew_set = {x["id"] for x in res["kewajiban"]}
        san_set = {x["id"] for x in res["sanksi"]}

        errors = []
        for c in sc.get("expect_classes", []):
            if c not in cls_set:
                errors.append(f"missing class {c}")
        for c in sc.get("forbid_classes", []):
            if c in cls_set:
                errors.append(f"forbidden class {c}")
        for t in sc.get("expect_tarif", []):
            if t not in tarif_set:
                errors.append(f"missing tarif {t}")
        for t in sc.get("forbid_tarif", []):
            if t in tarif_set:
                errors.append(f"forbidden tarif {t}")
        for f in sc.get("expect_fasilitas", []):
            if f not in fas_set:
                errors.append(f"missing fasilitas {f}")
        for f in sc.get("forbid_fasilitas", []):
            if f in fas_set:
                errors.append(f"forbidden fasilitas {f}")
        for k in sc.get("expect_kewajiban", []):
            if k not in kew_set:
                errors.append(f"missing kewajiban {k}")
        for k in sc.get("forbid_kewajiban", []):
            if k in kew_set:
                errors.append(f"forbidden kewajiban {k}")
        for s in sc.get("expect_sanksi", []):
            if s not in san_set:
                errors.append(f"missing sanksi {s}")

        # Cek TK-E1: setiap item hasil reasoning punya minimal 1 justifikasi dengan rule_id & source_quote
        for bucket in (res["tarif"], res["fasilitas"], res["kewajiban"], res["sanksi"]):
            for item in bucket:
                if not item["justifikasi"] or not item["justifikasi"][0].get("rule_id"):
                    errors.append(f"missing provenance on {item['id']}")

        ok = len(errors) == 0
        if ok:
            passed += 1
        results.append({
            "code": sc["code"],
            "desc": sc["desc"],
            "ok": ok,
            "errors": errors,
            "elapsed_ms": res["elapsed_ms"],
            "inferred_classes": res["inferred_classes"],
            "tarif": [x["id"] for x in res["tarif"]],
            "fasilitas": [x["id"] for x in res["fasilitas"]],
            "kewajiban": [x["id"] for x in res["kewajiban"]],
            "sanksi": [x["id"] for x in res["sanksi"]],
        })

    latencies = [r["elapsed_ms"] for r in results]
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
        "max_latency_ms": max(latencies),
        "scenarios": results,
    }
    out_dir = ROOT / ("reports" if (ROOT / "reports").exists() else "docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "fase7_eval_results.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    summary = run_eval()
    print(f"Evaluasi Fase 7: {summary['passed']}/{summary['total']} lulus | avg={summary['avg_latency_ms']} ms | max={summary['max_latency_ms']} ms")
    for r in summary["scenarios"]:
        status = "PASS" if r["ok"] else f"FAIL ({r['errors']})"
        print(f"  [{r['code']:9s}] {status:10s} ({r['elapsed_ms']} ms) -> {r['desc']}")
    if summary["failed"] > 0:
        raise SystemExit(1)
