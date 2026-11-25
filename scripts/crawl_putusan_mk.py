# -*- coding: utf-8 -*-
"""Crawl Putusan MK yang DIKABULKAN terkait UU Pajak, Peradilan Pajak, PDRD/HKPD,
Kepabeanan, dan Cukai dari jdih.mkri.id (via geckodriver lokal untuk melewati
Cloudflare katalog) + unduh PDF langsung dari s.mkri.id.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "download-pdf" / "putusan_mk"
CATALOG_RAW = OUT_DIR / "catalog_all_dikabulkan.json"
INDEX_PATH = OUT_DIR / "index.json"

GECKO_PORT = 4449

QUERIES = [
    ("2026", "", "", range(1, 5)),
    ("2025", "", "", range(1, 5)),
    ("2024", "", "", range(1, 5)),
    ("", "Cukai", "1", range(3, 5)),
    ("", "pajak", "1", range(5, 13)),
]

# Mode cepat: hanya halaman pertama pencarian "pajak" per tahun terbaru.
QUICK_QUERIES = [
    ("2026", "pajak", "1", range(1, 2)),
    ("2025", "pajak", "1", range(1, 2)),
    ("2024", "pajak", "1", range(1, 2)),
]

TAX_SCOPE_RE = re.compile(
    r"(?i)\b(?:pajak|perpajakan|pengadilan pajak|pajak daerah|retribusi|"
    r"pajak bumi dan bangunan|pajak penghasilan|pajak pertambahan nilai|"
    r"ketentuan umum dan tata cara perpajakan|pengampunan pajak|"
    r"penagihan pajak|kepabeanan|cukai|bea masuk|bea keluar|"
    r"akses informasi keuangan|hubungan keuangan antara pemerintah pusat)\b"
)
EXPLICIT_INCLUDE = {"24/PUU-XXII/2024", "37/PUU-XVIII/2020", "91/PUU-XVIII/2020"}
# Untuk UU Cipta Kerja (91/PUU-XVIII/2020 dkk), hanya loloskan bila amarnya relevan pajak/umum
NON_TAX_STRONG_RE = re.compile(
    r"(?i)\b(?:pemilihan umum|pemilu|pilkada|partai politik|presiden dan wakil|"
    r"pemerintahan desa|kepala desa|ketenagakerjaan|serikat pekerja|"
    r"mahkamah konstitusi|kejaksaan|kepolisian|tentara nasional|advokat|"
    r"notaris|kehutanan|pertambangan mineral|minyak dan gas|ketenagalistrikan|"
    r"jaminan sosial|kesehatan|pendidikan|perkawinan|narkotika|terorisme)\b"
)


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Browser:
    """Satu geckodriver + satu sesi Firefox per halaman (hindari lock 'Session already started')."""

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self.port = 0
        self.sid = ""

    def __enter__(self) -> "_Browser":
        self.port = _free_port()
        self.proc = subprocess.Popen(
            ["/snap/bin/geckodriver", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            time.sleep(0.25)
            try:
                r = requests.get(f"http://127.0.0.1:{self.port}/status", timeout=1)
                if r.status_code == 200 and r.json().get("value", {}).get("ready"):
                    break
            except Exception:
                pass
        opts = {
            "args": ["-headless"],
            "prefs": {
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
                "general.useragent.override": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
                ),
            },
        }
        r = requests.post(
            f"http://127.0.0.1:{self.port}/session",
            json={"capabilities": {"alwaysMatch": {"browserName": "firefox", "moz:firefoxOptions": opts}}},
            timeout=60,
        )
        r.raise_for_status()
        self.sid = r.json()["value"]["sessionId"]
        return self

    def get(self, url: str, wait: float) -> str:
        requests.post(f"http://127.0.0.1:{self.port}/session/{self.sid}/url",
                      json={"url": url}, timeout=45)
        time.sleep(wait)
        return requests.get(f"http://127.0.0.1:{self.port}/session/{self.sid}/source",
                            timeout=30).json()["value"]

    def __exit__(self, *exc) -> None:
        try:
            requests.delete(f"http://127.0.0.1:{self.port}/session/{self.sid}", timeout=10)
        except Exception:
            pass
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=10)
            except Exception:
                pass


def _parse_cards(html: str) -> tuple[int, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    txt = soup.get_text(" ", strip=True)
    m_tot = re.search(r"Showing\s+\d+\s+to\s+\d+\s+of\s+(\d+)\s+items", txt)
    total = int(m_tot.group(1)) if m_tot else 0

    cards = []
    for tbl in soup.find_all("table"):
        row_map = {}
        pdf_url = ""
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                k = tds[0].get_text(" ", strip=True)
                v = re.sub(r"\s+", " ", tds[2].get_text(" ", strip=True)).strip()
                row_map[k] = v
                a = tds[2].find("a", href=re.compile(r"\.pdf", re.I))
                if a and a.get("href"):
                    pdf_url = a["href"]
        if not row_map.get("Pokok Perkara"):
            continue
        # Cari heading "Nomor XX/PUU-..." di sibling / parent sebelum table
        nomor = ""
        prev = tbl.find_previous(string=re.compile(r"Nomor\s+\d+/PUU-[IVX]+/\d{4}", re.I))
        if prev:
            mn = re.search(r"Nomor\s+(\d+/PUU-[IVX]+/\d{4})", prev, re.I)
            if mn:
                nomor = mn.group(1).upper()
        if not nomor:
            continue
        cards.append({
            "nomor_perkara": nomor,
            "pokok_perkara": row_map.get("Pokok Perkara", ""),
            "pemohon": row_map.get("Pemohon", ""),
            "amar_putusan": row_map.get("Amar Putusan", ""),
            "jenis_amar": row_map.get("Jenis Amar Putusan", ""),
            "tanggal_putusan": row_map.get("Tanggal Putusan", ""),
            "pdf_url": pdf_url,
        })
    return total, cards


def _fetch_page_html(url: str) -> str:
    """Buka halaman dengan geckodriver+sesi Firefox baru agar lolos tantangan Cloudflare."""
    for attempt in range(4):
        try:
            with _Browser() as b:
                src = b.get(url, wait=5.0 + attempt * 2.0)
                if "Just a moment" not in src and ("<table" in src or "Showing" in src or "No data" in src):
                    return src
        except Exception as e:
            print(f"    [retry {attempt + 1}] {type(e).__name__}: {str(e)[:120]}")
        time.sleep(1.5 + attempt)
    return ""


def is_tax_relevant(card: dict) -> bool:
    pokok = card.get("pokok_perkara") or ""
    if "dikabulkan" not in (card.get("jenis_amar") or "").lower():
        return False
    if card.get("nomor_perkara") in EXPLICIT_INCLUDE:
        return True
    if not TAX_SCOPE_RE.search(pokok):
        return False
    if NON_TAX_STRONG_RE.search(pokok) and not re.search(
        r"(?i)\b(?:pajak|retribusi|kepabeanan|cukai|pengadilan pajak|hubungan keuangan)\b", pokok
    ):
        return False
    return True


def make_mk_id(nomor: str) -> str:
    m = re.match(r"(\d+)/(PUU-[IVX]+)/(\d{4})", nomor.upper())
    if m:
        return f"MK-{m.group(3)}-{m.group(1)}-{m.group(2)}"
    return "MK-" + re.sub(r"[^A-Z0-9-]+", "-", nomor.upper()).strip("-")


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="hanya halaman pertama 'pajak' untuk 2024-2026 (fokus unduh, cepat)")
    args = ap.parse_args()
    queries = QUICK_QUERIES if args.quick else QUERIES

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    if CATALOG_RAW.exists():
        for rec in json.loads(CATALOG_RAW.read_text(encoding="utf-8")):
            seen[rec["nomor_perkara"]] = rec

    for tahun, kw, frase, page_rng in queries:
        for pno in page_rng:
            up = (f"https://jdih.mkri.id/produk-hukum/putusan?tahun={tahun}&search="
                  f"{requests.utils.quote(kw)}&jenis=PUU&frase={frase}&status=Dikabulkan&page={pno}")
            htmlp = _fetch_page_html(up)
            tot, cardsp = _parse_cards(htmlp)
            for c in cardsp:
                seen[c["nomor_perkara"]] = c
            print(f"  [tahun={tahun or '-'} kw={kw or '-'}] page {pno} (tot={tot}) | cards={len(cardsp)} | unik={len(seen)}")
            if not cardsp or (tot and pno * 10 >= tot):
                break
        CATALOG_RAW.write_text(
            json.dumps(list(seen.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    CATALOG_RAW.write_text(json.dumps(list(seen.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    relevant = [c for c in seen.values() if is_tax_relevant(c)]
    relevant.sort(key=lambda c: (c["nomor_perkara"].split("/")[-1], c["nomor_perkara"]))
    print(f"\n[FILTER] total_unik={len(seen)} -> relevan_pajak_dikabulkan={len(relevant)}")

    downloaded = []
    for c in relevant:
        cid = make_mk_id(c["nomor_perkara"])
        pdf_url = c.get("pdf_url") or ""
        pdf_path = OUT_DIR / f"{cid}.pdf"
        ok = pdf_path.exists()
        if not ok and pdf_url:
            try:
                time.sleep(1.0)
                resp = requests.get(pdf_url, headers={"User-Agent": "KBR-Tax-Extraction/0.1"}, timeout=45)
                if resp.status_code == 200 and resp.content.startswith(b"%PDF"):
                    pdf_path.write_bytes(resp.content)
                    ok = True
                else:
                    print(f"  [NON-PDF] {cid}: status={resp.status_code} url={pdf_url}")
            except Exception as e:
                print(f"  [ERR] {cid}: {e}")
        print(f"  {'[OK]' if ok else '[NO]'} {cid:20} | {c['tanggal_putusan']:18} | {c['pokok_perkara'][:75]}")
        downloaded.append({
            "case_id": cid,
            **c,
            "pdf_file": f"{cid}.pdf" if ok else None,
            "downloaded": ok,
        })

    INDEX_PATH.write_text(json.dumps(downloaded, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSelesai: {sum(1 for x in downloaded if x['downloaded'])}/{len(downloaded)} PDF MK di {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
