# -*- coding: utf-8 -*-
"""Perbaikan metadata BPK yang keliru (temuan Fase 3).

Latar: enrichment Fase 1 memakai hasil pencarian BPK yang kadang salah dokumen,
sehingga `judul`/`subjek`/`status` tidak cocok dengan isi. Skrip ini:
1. Mengambil ulang metadata dari URL detail yang BENAR (dicek dulu document_id-nya).
2. Re-key PMK-2024-69 -> PMK-2024-127 (file korpus tim salah label; isinya PMK 127).
3. Menetapkan judul manual PER-DJP-2015-17 (tidak ada di BPK) dan membuang URL salah.

Output: data/metadata_repair_log.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import http_get  # noqa: E402
from src.crawl import BpkDetailParser, page_document_id, parse_date_id  # noqa: E402

DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"
LOG = ROOT / "data" / "metadata_repair_log.json"

BPK = "https://peraturan.bpk.go.id"

# document_id -> URL detail yang benar
REPAIRS = {
    "UU-2009-42": f"{BPK}/Details/38787/uu-no-42-tahun-2009",
    "UU-2022-1": f"{BPK}/Details/195696/uu-no-1-tahun-2022",
    "PMK-2026-6": f"{BPK}/Details/345004/pmk-no-6-tahun-2026",
    "PMK-2024-127": f"{BPK}/Details/313088/pmk-no-127-tahun-2024",
    "PP-2016-55": f"{BPK}/Details/5776/pp-no-55-tahun-2016",
}

REKEY = {"PMK-2024-69": "PMK-2024-127"}

MANUAL_TITLE = {
    "PER-DJP-2015-17":
        "Peraturan Direktur Jenderal Pajak Nomor PER-17/PJ/2015 tentang "
        "Norma Penghitungan Penghasilan Neto",
}


def apply_meta(doc: dict, meta: dict, url: str) -> None:
    doc["judul"] = meta.get("Judul") or doc.get("judul")
    doc["status_sumber"] = meta.get("Status")
    doc["tanggal_penetapan"] = parse_date_id(meta.get("Tanggal Penetapan"))
    doc["tanggal_pengundangan"] = parse_date_id(meta.get("Tanggal Pengundangan"))
    doc["tanggal_berlaku_sumber"] = parse_date_id(meta.get("Tanggal Berlaku"))
    doc["sumber_publikasi"] = meta.get("Sumber")
    doc["subjek_sumber"] = meta.get("Subjek")
    doc["source_urls"] = [{"source": "peraturan.bpk.go.id", "url": url}]
    doc.setdefault("quality", {})["garbled_title"] = False


def main() -> int:
    log = {"repairs": [], "rekey": [], "manual": []}

    # 1. Re-key file yang salah label SEBELUM repair metadata.
    for old, new in REKEY.items():
        src = DOCS / f"{old}.json"
        if not src.exists():
            log["rekey"].append({"from": old, "to": new, "status": "tidak ada"})
            continue
        d = json.loads(src.read_text(encoding="utf-8"))
        d["document_id"] = new
        for p in d.get("provisions", []):
            p["locator"] = str(p.get("locator", "")).replace(f"{old}#", f"{new}#")
        for a in d.get("articles", []):
            if isinstance(a, dict):
                a["locator"] = str(a.get("locator", "")).replace(f"{old}#", f"{new}#")
        dst = DOCS / f"{new}.json"
        dst.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        src.unlink()
        old_txt = TEXT / f"{old}.txt"
        if old_txt.exists():
            old_txt.rename(TEXT / f"{new}.txt")
        log["rekey"].append({"from": old, "to": new, "status": "ok"})
        print(f"[REKEY] {old} -> {new}")

    # 2. Repair metadata dari URL BPK yang benar.
    for doc_id, url in REPAIRS.items():
        path = DOCS / f"{doc_id}.json"
        if not path.exists():
            log["repairs"].append({"document_id": doc_id, "status": "tidak ada"})
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        html = http_get(url).text
        page = BpkDetailParser().parse(html, url)
        meta = page["meta"]
        page_id, _, _ = page_document_id(meta)
        if page_id != doc_id:
            log["repairs"].append({"document_id": doc_id, "status": "konflik",
                                   "page_id": page_id, "url": url})
            print(f"[KONFLIK] {doc_id}: halaman BPK = {page_id}")
            continue
        apply_meta(d, meta, url)
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        log["repairs"].append({"document_id": doc_id, "status": "ok",
                               "judul": d["judul"], "url": url})
        print(f"[REPAIR] {doc_id}: {d['judul'][:80]}")

    # 3. Judul manual (dokumen tidak ada di BPK / URL salah).
    for doc_id, judul in MANUAL_TITLE.items():
        path = DOCS / f"{doc_id}.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        d["judul"] = judul
        d["source_urls"] = []
        d.setdefault("quality", {})["metadata_manual"] = True
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        log["manual"].append({"document_id": doc_id, "judul": judul})
        print(f"[MANUAL] {doc_id}: {judul[:80]}")

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nLog: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
