# -*- coding: utf-8 -*-
"""Benchmark latensi API KBR Pajak (B6) + verifikasi gate.

    python3 scripts/benchmark_api.py --in-process            # tanpa uvicorn
    python3 scripts/benchmark_api.py --base-url http://host:8000

Gate default (hasil kesepakatan B6, hardware 2 vCPU):
    cache-hit  p95 < 1.000 ms
    cache-miss p95 < 10.000 ms
Target PRD §10 (p95 < 3.000 ms) dilaporkan terpisah sebagai `--prd-target-ms`.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _profiles() -> List[Tuple[str, dict]]:
    return [
        ("UMKM_OP", {
            "wp_id": "BENCH_UMKM", "wp_kind": "OrangPribadi",
            "pekerjaan_utama": {"nama": "Warung", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_200_000_000.0},
            "is_umkm_pp55": True,
        }),
        ("PRD_GURU", {
            "wp_id": "BENCH_PRD", "wp_kind": "OrangPribadi", "tahun_pajak": 2026,
            "pemda_id": "KOTA_BANDUNG",
            "pekerjaan_utama": {"nama": "Guru", "jenis": "PEGAWAI_TETAP", "kbli": "85121", "gaji_bulanan": 8_500_000.0},
            "pekerjaan_sekunder": {"nama": "Dev", "jenis": "PEKERJA_BEBAS", "kbli": "62019",
                                    "omzet_tahunan": 180_000_000.0, "hpp_tahunan": 25_000_000.0,
                                    "biaya_operasional_tahunan": 15_000_000.0},
            "is_kawin": True, "has_jumlah_tanggungan": 1,
            "kredit_pajak_1721a1": 1_530_000.0,
        }),
        ("CV_31E", {
            "wp_id": "BENCH_31E", "wp_kind": "CV",
            "has_omzet_tahunan": 10_000_000_000.0, "has_penghasilan_kena_pajak_tahunan": 1_000_000_000.0,
            "has_dpp_ppn": 2_000_000_000.0, "is_penyerahan_non_mewah_ppn": True,
        }),
        ("PT_KONSTRUKSI", {
            "wp_id": "BENCH_KONST", "wp_kind": "PT", "kode_kbli": "41011",
            "penghasilan_final": {
                "jasa_konstruksi": {"jenis": "NON_KECIL_SBU", "nilai_bruto": 1_000_000_000.0},
                "pengalihan_tanah_bangunan": {"jenis": "RUMAH_SEDERHANA", "nilai": 500_000_000.0},
            },
        }),
        ("KOPERASI_4TH", {
            "wp_id": "BENCH_KOP", "wp_kind": "Koperasi", "tahun_pajak": 2026, "tahun_terdaftar": 2021,
            "pekerjaan_sekunder": {"nama": "Unit", "jenis": "USAHA_UMKM", "omzet_tahunan": 1_000_000_000.0},
            "cbr_kueri": "koreksi biaya promosi",
        }),
    ]


def _client(base_url: str, in_process: bool):
    if in_process:
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)
    import httpx

    return httpx.Client(base_url=base_url, timeout=120.0)


def _stats(xs: List[float]) -> dict:
    if not xs:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    s = sorted(xs)
    def pct(p: float) -> float:
        return round(s[min(len(s) - 1, int(round(p * (len(s) - 1))))], 2)
    return {"n": len(xs), "p50": pct(0.50), "p95": pct(0.95), "max": round(max(s), 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark latensi KBR Pajak API")
    ap.add_argument("--in-process", action="store_true")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--repeat", type=int, default=1, help="pengulangan per profil (cache-hit)")
    ap.add_argument("--gate-hit-ms", type=float, default=1000.0)
    ap.add_argument("--gate-miss-ms", type=float, default=10000.0)
    ap.add_argument("--prd-target-ms", type=float, default=3000.0, help="target PRD §10 (informasional)")
    args = ap.parse_args()

    client = _client(args.base_url, args.in_process)
    miss: List[float] = []
    hit: List[float] = []
    rows = []

    for name, payload in _profiles():
        t = time.perf_counter()
        r = client.post("/api/reason", json=payload)
        ms = (time.perf_counter() - t) * 1000
        if r.status_code != 200:
            print(f"[FAIL] {name}: HTTP {r.status_code} {r.text[:200]}")
            return 1
        miss.append(ms)
        reps = []
        for _ in range(max(0, args.repeat)):
            t = time.perf_counter()
            rr = client.post("/api/reason", json=payload)
            hms = (time.perf_counter() - t) * 1000
            if rr.status_code != 200 or not rr.json().get("cache_hit"):
                print(f"[FAIL] {name}: repeat bukan cache-hit")
                return 1
            hit.append(hms)
            reps.append(hms)
        rows.append((name, round(ms, 1), round(statistics.mean(reps), 2) if reps else None))

    m_stats, h_stats = _stats(miss), _stats(hit)
    print("\nProfil                     miss(ms)   hit-rata(ms)")
    for name, m, h in rows:
        print(f"{name:<26} {m:>8.0f}   {'' if h is None else f'{h:>8.2f}'}")

    print("\nCache-miss :", json.dumps(m_stats))
    print("Cache-hit  :", json.dumps(h_stats))

    metrics = client.get("/api/metrics")
    if metrics.status_code == 200:
        print("Metrics    :", json.dumps(metrics.json().get("cache"), ensure_ascii=False))

    ok = True
    if m_stats["p95"] is not None and m_stats["p95"] > args.gate_miss_ms:
        print(f"[FAIL] cache-miss p95 {m_stats['p95']} ms > gate {args.gate_miss_ms} ms")
        ok = False
    if h_stats["p95"] is not None and h_stats["p95"] > args.gate_hit_ms:
        print(f"[FAIL] cache-hit p95 {h_stats['p95']} ms > gate {args.gate_hit_ms} ms")
        ok = False
    if m_stats["p95"] is not None and m_stats["p95"] > args.prd_target_ms:
        print(f"[INFO] target PRD p95 < {args.prd_target_ms} ms BELUM tercapai (aktual {m_stats['p95']} ms)")
    print("\nHASIL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
