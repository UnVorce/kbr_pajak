# -*- coding: utf-8 -*-
"""Download seluruh PDF Perda Pajak & Retribusi Daerah (2023-2026, Berlaku)
dari JDIH BPK (tema=48 & jenis=19) ke download-pdf/perda/<tahun>/.

- Fase 1: kumpulkan katalog dari semua halaman pencarian (55 halaman).
- Fase 2: buka halaman Detail, cek Status != 'Tidak Berlaku', unduh PDF ke
  download-pdf/perda/<tahun>/<bpk_id>_<slug>.pdf dan catat index.json.
- Resumable: menyimpan progres berkala setiap 15 dokumen.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import BPK, http_get  # noqa: E402
from src.crawl import BpkDetailParser, parse_date_id  # noqa: E402

OUT_DIR = ROOT / "download-pdf" / "perda"
YEARS = (2023, 2024, 2025, 2026)

CARD_LINK_RE = re.compile(
    r'class="text-gray-600 text-decoration-none"\s+href="(/Details/(\d+)/([^"]+))">'
    r'\s*([^<]+?)\s*</a>',
    re.S,
)
LAST_PAGE_RE = re.compile(r'href="[^"]*p=(\d+)[^"]*"[^>]*>\s*Last\s*</a>', re.I)


def build_catalog(years: tuple[int, ...]) -> list[dict]:
    cat_path = OUT_DIR / "catalog.json"
    if cat_path.exists():
        cat = json.loads(cat_path.read_text(encoding="utf-8"))
        print(f"[KATALOG] Muat dari cache: {len(cat)} Perda")
        return cat

    seen: set[str] = set()
    items: list[dict] = []
    for yr in years:
        first_url = f"{BPK}/Search?tema=48&jenis=19&tahun={yr}&p=1"
        r1 = http_get(first_url)
        lm = LAST_PAGE_RE.search(r1.text)
        last_p = int(lm.group(1)) if lm else 1
        print(f"[KATALOG] Tahun {yr}: {last_p} halaman")
        for pno in range(1, last_p + 1):
            html_txt = r1.text if pno == 1 else http_get(
                f"{BPK}/Search?tema=48&jenis=19&tahun={yr}&p={pno}"
            ).text
            for href, bpk_id, slug, label in CARD_LINK_RE.findall(html_txt):
                if href in seen:
                    continue
                seen.add(href)
                items.append({
                    "bpk_id": bpk_id,
                    "slug": slug,
                    "tahun": yr,
                    "href": href,
                    "label": re.sub(r"\s+", " ", label).strip(),
                })
    cat_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[KATALOG] Total terkumpul: {len(items)} Perda")
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-catalog", action="store_true",
                    help="ambil ulang daftar katalog BPK")
    ap.add_argument("--limit", type=int, default=0,
                    help="batas jumlah dokumen (0 = semua)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.refresh_catalog and (OUT_DIR / "catalog.json").exists():
        (OUT_DIR / "catalog.json").unlink()

    catalog = build_catalog(YEARS)
    if args.limit > 0:
        catalog = catalog[:args.limit]

    idx_path = OUT_DIR / "index.json"
    state = {"downloaded": {}, "skipped_revoked": {}, "failed": {}}
    if idx_path.exists():
        loaded = json.loads(idx_path.read_text(encoding="utf-8"))
        for k in state:
            if isinstance(loaded.get(k), dict):
                state[k] = loaded[k]

    def save_state() -> None:
        summary = {
            "total_catalog": len(catalog),
            "downloaded_count": len(state["downloaded"]),
            "skipped_revoked_count": len(state["skipped_revoked"]),
            "failed_count": len(state["failed"]),
        }
        idx_path.write_text(
            json.dumps({"summary": summary, **state}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    new_dl = 0
    for i, item in enumerate(catalog, 1):
        bid = item["bpk_id"]
        if bid in state["downloaded"]:
            p = OUT_DIR / state["downloaded"][bid]["rel_path"]
            if p.exists():
                continue
        if bid in state["skipped_revoked"]:
            continue

        detail_url = BPK + item["href"]
        try:
            page = BpkDetailParser().parse(http_get(detail_url).text, detail_url)
        except Exception as e:
            state["failed"][bid] = {"href": item["href"], "reason": f"detail_err: {e}"}
            continue

        meta = page["meta"]
        status = (meta.get("Status") or "").strip()
        if status.lower() == "tidak berlaku":
            state["skipped_revoked"][bid] = {
                "bpk_id": bid,
                "tahun": item["tahun"],
                "judul": meta.get("Judul") or item["label"],
                "status": status,
                "url": detail_url,
            }
            continue

        dl = next((a for a in page["pdf_links"] if a.startswith("/Download/")),
                  next((a for a in page["pdf_links"] if a.startswith("/Read/")), None))
        if not dl:
            state["failed"][bid] = {"href": item["href"], "reason": "no_pdf_link",
                                    "judul": meta.get("Judul")}
            continue

        yr_dir = OUT_DIR / str(item["tahun"])
        yr_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{bid}_{item['slug'][:85]}.pdf"
        rel_path = f"{item['tahun']}/{fname}"
        pdf_url = BPK + dl
        try:
            pdf_bytes = http_get(pdf_url).content
        except Exception as e:
            state["failed"][bid] = {"href": item["href"], "reason": f"pdf_err: {e}"}
            continue

        if not pdf_bytes.startswith(b"%PDF"):
            state["failed"][bid] = {"href": item["href"], "reason": "non_pdf_response",
                                    "pdf_url": pdf_url}
            continue

        (OUT_DIR / rel_path).write_bytes(pdf_bytes)
        state["downloaded"][bid] = {
            "bpk_id": bid,
            "tahun": item["tahun"],
            "slug": item["slug"],
            "judul": meta.get("Judul") or item["label"],
            "status_sumber": status or "Berlaku",
            "tanggal_penetapan": parse_date_id(meta.get("Tanggal Penetapan")),
            "tanggal_pengundangan": parse_date_id(meta.get("Tanggal Pengundangan")),
            "subjek_sumber": meta.get("Subjek"),
            "rel_path": rel_path,
            "size_bytes": len(pdf_bytes),
            "detail_url": detail_url,
            "pdf_url": pdf_url,
        }
        state["failed"].pop(bid, None)
        new_dl += 1
        if new_dl % 15 == 0:
            save_state()
            print(f"[PROGRES] {i}/{len(catalog)} | baru={new_dl} | "
                  f"total_dl={len(state['downloaded'])} | revoked={len(state['skipped_revoked'])} | "
                  f"fail={len(state['failed'])}")

    save_state()
    print(f"\nSelesai: baru={new_dl} | total_dl={len(state['downloaded'])} | "
          f"revoked={len(state['skipped_revoked'])} | fail={len(state['failed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
