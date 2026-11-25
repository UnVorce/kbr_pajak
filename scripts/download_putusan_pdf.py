# -*- coding: utf-8 -*-
"""Download PDF Putusan Pengadilan Pajak (SetPP Kemenkeu) secara terstrata.

Menyimpan file .pdf langsung ke download-pdf/putusan/<klaster>/ beserta
download-pdf/putusan/index.json (metadata + abstraksi pokok sengketa).
Resumable, sopan (jeda >= 1.5 detik), dan cek header %PDF sebelum menulis.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "download-pdf" / "putusan"
BASE = "https://setpp.kemenkeu.go.id"

KLASTER_MAP = {
    "15": "pph_badan",
    "16": "ppn",
    "99": "kup_gugatan",
    "18": "pbb",
    "10": "pph_potput",
    "12": "pph_potput",
    "13": "pph_potput",
    "14": "pph_potput",
    "35": "pph_potput",
    "19": "kepabeanan_cukai",
    "45": "kepabeanan_cukai",
    "47": "kepabeanan_cukai",
}

DEFAULT_QUOTA = {
    "pph_badan": 40,
    "ppn": 40,
    "kup_gugatan": 40,
    "pph_potput": 25,
    "pbb": 25,
    "kepabeanan_cukai": 30,
}


def detect_kode(noput: str) -> str:
    m = re.search(r"\.(\d{2})/|/(\d{2})/\d{4}", noput or "")
    if not m:
        return "lainnya"
    return m.group(1) or m.group(2) or "lainnya"


def safe_name(noput: str, rec_id: int) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", (noput or f"put_{rec_id}")).strip("_")
    return f"{rec_id}_{slug[:90]}.pdf"


def get_with_retry(sess: requests.Session, url: str, timeout: int = 35) -> requests.Response:
    for attempt in range(3):
        try:
            time.sleep(1.5)
            r = sess.get(url, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2.5 * (attempt + 1))
            print(f"  [RETRY] {url}: {e}")
    raise RuntimeError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-scan-pages", type=int, default=20,
                    help="maks halaman katalog Risalah_Read (200 baris/halaman)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="pengali kuota (mis. 0.5 untuk 100 PDF, 1.0 untuk 200 PDF)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    idx_path = OUT_DIR / "index.json"
    existing = {}
    if idx_path.exists():
        for rec in json.loads(idx_path.read_text(encoding="utf-8")):
            existing[rec["id"]] = rec

    quota = {k: max(1, int(round(v * args.scale))) for k, v in DEFAULT_QUOTA.items()}
    counts = {k: 0 for k in quota}
    for rec in existing.values():
        kl = rec.get("klaster")
        pdf_p = OUT_DIR / rec.get("rel_path", "")
        if kl in counts and pdf_p.exists():
            counts[kl] += 1

    sess = requests.Session()
    sess.headers.update({"User-Agent": "KBR-Tax-Extraction/0.1 (academic research)"})

    candidates = []
    for pg in range(1, args.max_scan_pages + 1):
        if all(counts[k] >= quota[k] for k in quota):
            break
        url = f"{BASE}/risalah/Risalah_Read?page={pg}&pageSize=200&sort=id-desc"
        rows = get_with_retry(sess, url).json().get("Data", [])
        if not rows:
            break
        for row in rows:
            rid = int(row["id"])
            if rid in existing and (OUT_DIR / existing[rid].get("rel_path", "")).exists():
                continue
            kode = detect_kode(row.get("noput", ""))
            kl = KLASTER_MAP.get(kode)
            if not kl:
                continue
            if counts[kl] < quota[kl]:
                candidates.append((row, kode, kl))
                # sementara reservasi slot supaya tidak berlebih
                counts[kl] += 1
        print(f"[KATALOG] page={pg} terreservasi={len(candidates)} status={counts}")

    # Hitung ulang counts riil sebelum mengunduh
    real_counts = {k: 0 for k in quota}
    for rec in existing.values():
        kl = rec.get("klaster")
        if kl in real_counts and (OUT_DIR / rec.get("rel_path", "")).exists():
            real_counts[kl] += 1

    downloaded = 0
    for row, kode, kl in candidates:
        rid = int(row["id"])
        if rid in existing and (OUT_DIR / existing[rid].get("rel_path", "")).exists():
            continue
        sub_dir = OUT_DIR / kl
        sub_dir.mkdir(parents=True, exist_ok=True)
        fname = safe_name(row.get("noput", ""), rid)
        rel_path = f"{kl}/{fname}"
        pdf_url = f"{BASE}/risalah/ambilFileDariDisk/{rid}"
        try:
            resp = get_with_retry(sess, pdf_url, timeout=45)
            if not resp.content.startswith(b"%PDF"):
                print(f"  [SKIP-NONPDF] id={rid} ({row.get('noput')})")
                continue
            (OUT_DIR / rel_path).write_bytes(resp.content)
        except Exception as e:
            print(f"  [GAGAL] id={rid} ({row.get('noput')}): {e}")
            continue

        existing[rid] = {
            "id": rid,
            "noput": row.get("noput"),
            "kode_pajak": kode,
            "klaster": kl,
            "tahun_sengketa": row.get("tahun"),
            "abstraksi": row.get("absris"),
            "pdf_file": fname,
            "rel_path": rel_path,
            "size_bytes": len(resp.content),
            "url": pdf_url,
        }
        downloaded += 1
        real_counts[kl] += 1
        if downloaded % 10 == 0:
            idx_path.write_text(
                json.dumps(sorted(existing.values(), key=lambda x: -x["id"]),
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [PROGRES] {downloaded} PDF baru | total={len(existing)} | {real_counts}")

    idx_path.write_text(
        json.dumps(sorted(existing.values(), key=lambda x: -x["id"]),
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSelesai: {downloaded} PDF baru | total arsip={len(existing)} | {real_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
