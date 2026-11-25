# -*- coding: utf-8 -*-
"""S1 — penjelajah graf relasi (KBR spec 7.1) + gerbang S2 (src/scope.py).

Fase 1 (pilot): satu seed, batas max_documents_per_run (default 20), dry-run dulu.
- Patuhi config/crawl.yaml: jeda >= 1,5 dtk, retry backoff, cache HTML.
- robots.txt dicek sebelum run (hasil tercatat di config/sources.yaml).
- Resumable: antrean & status di SQLite (tabel crawl_queue).
- Metadata relasi sumber TIDAK lengkap (V3) — pelengkapnya S6 di Fase 4.

CLI:
  python3 -m src.crawl --card config/scope_cards/DOMAIN_A.yaml \
      --limit 20 --dry-run            # pratinjau tanpa menulis DB
  python3 -m src.crawl --card ... --limit 20 --no-dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import yaml
from bs4 import BeautifulSoup

from src import ids
from src.db import connect, init_db
from src.scope import decide_scope, hierarchy_level, load_card, score_document

BULAN_ID = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
}

DEFAULT_CRAWL_CONFIG = {
    "min_delay_seconds": 1.5,
    "user_agent": "KBR-Tax-Extraction/0.1 (proyek mahasiswa)",
    "max_documents_per_run": 20,
    "dry_run": True,
    "retry_max": 3,
    "retry_backoff_seconds": [2, 5, 10],
    "cache_ttl_days": 7,
    "max_depth": None,
}


def load_yaml(path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_date_id(s: Optional[str]) -> Optional[str]:
    """'29 Oktober 2021' -> '2021-10-29'; '01 Januari 1984' -> '1984-01-01'."""
    if not s:
        return None
    m = re.match(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*$", s.strip())
    if not m:
        return None
    hari, bulan, tahun = m.group(1), m.group(2).casefold(), m.group(3)
    if bulan not in BULAN_ID:
        return None
    return f"{tahun}-{BULAN_ID[bulan]}-{int(hari):02d}"


def normalize_relation_label(label: str, relation_map: dict) -> Optional[dict]:
    """Label sumber -> (internal, direction, note). None bila label tidak dikenal."""
    key = label.strip().rstrip(":").strip()
    entry = relation_map.get("source_labels", {}).get(key)
    if entry is None:
        return None
    return {
        "label_raw": label.strip(),
        "internal": entry["internal"],
        "direction": entry["direction"],
        "note": entry.get("note"),
    }


class BpkDetailParser:
    """Parser halaman Detail peraturan.bpk.go.id (selector terverifikasi Fase 1)."""

    def parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        meta: Dict[str, str] = {}
        for row in soup.select("div.row.g-4.g-xl-9"):
            lab = row.select_one("div.col-lg-3")
            val = row.select_one("div.col-lg-9, div.col-lg-12")
            if lab and val:
                meta[lab.get_text(" ", strip=True)] = val.get_text(" ", strip=True)

        relations: List[dict] = []
        cur_label: Optional[str] = None
        # Container relasi = container berlabel yang labelnya diawali kata relasi
        # (menghindari blok lain seperti "Putusan MK" yang strukturnya mirip).
        rel_prefix = re.compile(
            r"^(Diubah|Mengubah|Dicabut|Mencabut|Melaksanakan|Dilaksanakan|"
            r"Pelaksanaan|Terkait|Merujuk|Menetapkan)", re.IGNORECASE)
        container = None
        for c in soup.select("div.container.fs-6"):
            lab = c.select_one("div.col-12.fw-semibold.bg-light-primary")
            if lab and rel_prefix.match(lab.get_text(" ", strip=True)):
                container = c
                break
        if container:
            for child in container.find_all("div", recursive=False):
                lab = child.select_one("div.col-12.fw-semibold")
                if lab:
                    cur_label = lab.get_text(" ", strip=True).rstrip(":").strip()
                elif cur_label:
                    for a in child.select("ol a[href^='/Details/']"):
                        relations.append(
                            {"label": cur_label, "text": a.get_text(" ", strip=True),
                             "href": a["href"]}
                        )

        pdf_links: List[str] = []
        for sel in ("a[href^='/Download/']", "a[href^='/Read/']"):
            for a in soup.select(sel):
                href = a["href"]
                if href not in pdf_links:
                    pdf_links.append(href)

        return {"meta": meta, "relations": relations, "pdf_links": pdf_links,
                "url": url, "title": soup.title.get_text(strip=True) if soup.title else None}


def page_document_id(meta: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (document_id, jenis, nomor_raw) dari metadata halaman BPK.

    Prioritas: metadata TERSTRUKTUR (Bentuk Singkat + Tahun + Nomor) lebih
    andal daripada parse judul — judul dapat menyebut peraturan lain
    (mis. "UU No. 6 Tahun 2023 tentang Penetapan PERPU No. 2 Tahun 2022").
    """
    bentuk = (meta.get("Bentuk Singkat") or "").strip().upper()
    tahun = (meta.get("Tahun") or "").strip()
    nomor_raw = (meta.get("Nomor") or "").strip()
    norm = None
    m = re.search(r"\d{1,4}[A-Za-z]?", nomor_raw)
    if m:
        norm = m.group(0)

    jenis = None
    if bentuk in ids.JENIS_KNOWN:
        jenis = bentuk
    elif bentuk in ("PERPPU", "PERPU"):
        jenis = "PERPU"
    elif bentuk in ("SE", "PER"):
        judul = (meta.get("Judul") or "").casefold()
        if "pajak" in judul or re.search(r"/?\s*PJ\b", nomor_raw, re.IGNORECASE):
            jenis = "SE-DJP" if bentuk == "SE" else "PER-DJP"
    if jenis and tahun and norm:
        return f"{jenis}-{tahun}-{norm}", jenis, nomor_raw

    # fallback: parse judul (kurang andal, lihat docstring)
    judul = meta.get("Judul") or ""
    parsed = ids.parse_document_ref(judul)
    if parsed:
        return parsed["document_id"], parsed["jenis"], parsed["nomor_raw"]
    return None, None, None


def relation_to_active_form(
    page_doc_id: str,
    target_doc_id: str,
    target_ref: str,
    norm: dict,
    origin: str,
    evidence: str,
) -> dict:
    """Ubah relasi halaman menjadi bentuk aktif (spec 5.3)."""
    if norm["direction"] == "passive":
        from_doc, to_doc = target_doc_id, page_doc_id
    else:
        from_doc, to_doc = page_doc_id, target_doc_id
    return {
        "from_document_id": from_doc,
        "to_document_id": to_doc,
        "relation_type": norm["internal"],
        "origin": origin,
        "evidence": f"{evidence} | label sumber: {norm['label_raw']}"
                    + (f" | catatan: {norm['note']}" if norm.get("note") else ""),
        "confidence": 1.0,
        "target_ref": target_ref,
    }


class Fetcher:
    """HTTP dengan jeda, retry backoff, dan cache berkas HTML (spec 7.1/11)."""

    def __init__(self, cfg: dict, cache_dir: Path):
        self.delay = cfg.get("min_delay_seconds", 1.5)
        self.ua = {"User-Agent": cfg.get("user_agent", "KBR-Tax-Extraction/0.1")}
        self.retry_max = cfg.get("retry_max", 3)
        self.backoff = cfg.get("retry_backoff_seconds", [2, 5, 10])
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(days=cfg.get("cache_ttl_days", 7))
        self._last_request_at = 0.0

    def _throttle(self):
        wait = self.delay - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str) -> bytes:
        key = re.sub(r"[^a-zA-Z0-9_.-]", "_", url)[:120]
        cache_path = self.cache_dir / key
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age < self.ttl.total_seconds():
                return cache_path.read_bytes()
        last_err = None
        for attempt in range(self.retry_max + 1):
            self._throttle()
            try:
                r = requests.get(url, headers=self.ua, timeout=30)
                self._last_request_at = time.monotonic()
                if r.status_code == 200:
                    cache_path.write_bytes(r.content)
                    return r.content
                last_err = RuntimeError(f"HTTP {r.status_code} untuk {url}")
            except requests.RequestException as e:
                last_err = e
            if attempt < self.retry_max:
                time.sleep(self.backoff[min(attempt, len(self.backoff) - 1)])
        raise RuntimeError(f"gagal fetch {url}: {last_err}")


def upsert_document(conn, doc: dict):
    """Insert/update dokumen. Pada konflik, hanya kolom METADATA yang diperbarui;
    keputusan kepemilikan/lingkup/status proses yang sudah ada TIDAK ditimpa."""
    cols = list(doc.keys())
    update_cols = [
        "jenis", "nomor_raw", "nomor_norm", "tahun", "judul", "tempat_penetapan",
        "tanggal_penetapan", "tanggal_pengundangan", "tanggal_berlaku_sumber",
        "sumber_publikasi", "subjek_sumber", "bidang_sumber", "status_sumber",
        "hierarchy_level", "source_urls_json", "primary_source", "last_checked_at",
    ]
    sets = ", ".join(f"{c} = excluded.{c}" for c in update_cols if c in cols)
    sets += (", scope_status = CASE WHEN documents.scope_status IS NULL "
             "OR documents.scope_status = 'UNDECIDED' THEN excluded.scope_status "
             "ELSE documents.scope_status END"
             ", owner_domain = COALESCE(documents.owner_domain, excluded.owner_domain)"
             ", discovery_status = CASE WHEN documents.discovery_status = 'DISCOVERED' "
             "THEN excluded.discovery_status ELSE documents.discovery_status END"
             ", first_seen_at = COALESCE(documents.first_seen_at, excluded.first_seen_at)")
    sql = (f"INSERT INTO documents ({', '.join(cols)}) "
           f"VALUES ({', '.join('?' for _ in cols)}) "
           f"ON CONFLICT(document_id) DO UPDATE SET {sets}")
    conn.execute(sql, [doc[c] for c in cols])


def upsert_relation(conn, rel: dict, now: str):
    existing = conn.execute(
        "SELECT relation_id, origin, evidence FROM relations "
        "WHERE from_document_id = ? AND to_document_id = ? AND relation_type = ?",
        (rel["from_document_id"], rel["to_document_id"], rel["relation_type"]),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO relations (from_document_id, to_document_id, relation_type, "
            "origin, evidence, confidence, verified, discovered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (rel["from_document_id"], rel["to_document_id"], rel["relation_type"],
             rel["origin"], rel["evidence"], rel["confidence"], now),
        )
    elif rel["origin"] not in (existing["origin"] or ""):
        # spec 5.3: relasi dari dua asal -> gabungkan dan catat kedua asal
        conn.execute(
            "UPDATE relations SET origin = ?, evidence = ? WHERE relation_id = ?",
            (existing["origin"] + "|" + rel["origin"],
             (existing["evidence"] or "") + " || " + rel["evidence"],
             existing["relation_id"]),
        )


class Crawler:
    def __init__(self, card: dict, crawl_cfg: dict, sources: dict,
                 relation_map: dict, db_path: str, dry_run: bool):
        self.card = card
        self.cfg = {**DEFAULT_CRAWL_CONFIG, **crawl_cfg.get("crawl", {})}
        self.sources = sources
        self.relation_map = relation_map
        self.db_path = db_path
        self.dry_run = dry_run
        self.fetcher = Fetcher(self.cfg, Path("data/cache/html"))
        self.follow = set(card.get("follow_relations", []))
        self.seeds = {s["document_id"]: s for s in card.get("seeds", [])}
        self.visited: set = set()
        self.stats = {"fetched": 0, "in_scope": 0, "boundary": 0, "undecided": 0,
                      "failed": 0, "relations_found": 0, "relations_unknown_label": 0,
                      "no_doc_id": 0}

    # -- antrean --------------------------------------------------------------
    def _ensure_placeholder(self, conn, doc_id: str, parsed: Optional[dict]):
        """Baris minimal untuk dokumen yang BARU ditemukan lewat relasi (belum diambil
        halamannya). discovery_status=DISCOVERED, scope UNDECIDED. Metadata lengkap
        diisi saat halaman diproses; scope diputuskan ulang saat itu juga."""
        if doc_id is None:
            return
        jenis = parsed["jenis"] if parsed else None
        tahun = parsed["tahun"] if parsed else None
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO documents (document_id, jenis, tahun, "
            "discovery_status, scope_status, owner_domain, ingestion_status, "
            "extraction_status, validation_status, legal_status, first_seen_at) "
            "VALUES (?, ?, ?, 'DISCOVERED', 'UNDECIDED', NULL, 'PENDING', "
            "'PENDING', 'PENDING', 'NEEDS_VERIFICATION', ?)",
            (doc_id, jenis, tahun, now),
        )

    def _enqueue(self, conn, doc_id: Optional[str], url: str, depth: int,
                 origin: Optional[str], parsed: Optional[dict] = None):
        self._ensure_placeholder(conn, doc_id, parsed)
        conn.execute(
            "INSERT INTO crawl_queue (document_id, url, depth, origin_document_id, "
            "status, enqueued_at) VALUES (?, ?, ?, ?, 'QUEUED', ?)",
            (doc_id, url, depth, origin, datetime.utcnow().isoformat()),
        )

    def _next_queue(self, conn) -> Optional[dict]:
        row = conn.execute(
            "SELECT * FROM crawl_queue WHERE status = 'QUEUED' ORDER BY crawl_id LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def _set_queue(self, conn, crawl_id: int, status: str, error: Optional[str] = None):
        conn.execute(
            "UPDATE crawl_queue SET status = ?, error = ?, last_attempt_at = ? "
            "WHERE crawl_id = ?",
            (status, error, datetime.utcnow().isoformat(), crawl_id),
        )

    # -- satu halaman ----------------------------------------------------------
    def process_one(self, conn, item: dict) -> None:
        """Fetch + parse + S2 + simpan + enqueue tetangga (spec 7.1 langkah 1-6)."""
        url = item["url"]
        origin = item.get("origin_document_id")
        try:
            html = self.fetcher.get(url).decode("utf-8", "replace")
        except RuntimeError as e:
            self.stats["failed"] += 1
            if not self.dry_run:
                self._set_queue(conn, item["crawl_id"], "FAILED", str(e))
            print(f"  [FAILED] {url}: {e}")
            return
        self.stats["fetched"] += 1

        page = BpkDetailParser().parse(html, url)
        meta = page["meta"]
        meta["url"] = url  # URL halaman dipakai untuk source_urls_json
        doc_id, jenis, nomor_raw = page_document_id(meta)
        if doc_id is None:
            self.stats["no_doc_id"] += 1
            if not self.dry_run:
                self._set_queue(conn, item["crawl_id"], "NEEDS_REVIEW",
                                "document_id tidak dapat dinormalisasi")
            print(f"  [NEEDS_REVIEW] document_id gagal: {meta.get('Judul', url)[:80]}")
            return

        is_seed = doc_id in self.seeds
        neighbor_in_scope = origin is not None  # ditemukan lewat relasi dokumen IN_SCOPE
        score, signals = score_document(meta, self.card, neighbor_in_scope)
        scope = decide_scope(score, self.card, is_seed=is_seed)

        print(f"  [{scope}] {doc_id} skor={score} sinyal={signals} "
              f"status_sumber={meta.get('Status')!r} judul={meta.get('Judul','')[:60]!r}")

        if scope == "IN_SCOPE":
            self.stats["in_scope"] += 1
        elif scope == "UNDECIDED":
            self.stats["undecided"] += 1
        else:
            self.stats["boundary"] += 1

        if self.dry_run:
            self._print_relations(doc_id, page)
            self._enqueue_dry(page, doc_id, scope, item.get("depth", 0))
            return

        now = datetime.utcnow().isoformat()
        doc = self._document_row(doc_id, jenis, nomor_raw, meta, scope)
        upsert_document(conn, doc)
        if scope == "BOUNDARY":
            # I3: setiap BOUNDARY mencatat domain asal temuannya (konvensi ISSUES #3)
            conn.execute(
                "INSERT OR IGNORE INTO domain_tags (entity_type, entity_id, domain_id, "
                "score, method, review_status) VALUES ('DOCUMENT', ?, ?, ?, "
                "'SOURCE_METADATA', 'AUTO_ACCEPTED')",
                (doc_id, self.card["domain_id"], score),
            )

        # relasi -> bentuk aktif + normalisasi label
        for rel in page["relations"]:
            norm = normalize_relation_label(rel["label"], self.relation_map)
            if norm is None:
                self.stats["relations_unknown_label"] += 1
                print(f"    [LABEL TAK DIKENAL] {rel['label']!r} -> {rel['text'][:60]}")
                continue
            parsed = ids.parse_document_ref(rel["text"])
            if parsed is None:
                print(f"    [TARGET TAK TERPARSE] {rel['text'][:80]}")
                continue
            target_id = parsed["document_id"]
            # placeholder dulu agar FK relations terpenuhi (untuk SEMUA target,
            # termasuk dari dokumen BOUNDARY — relasinya tetap dicatat)
            self._ensure_placeholder(conn, target_id, parsed)
            # target bisa jadi dokumen baru -> masuk antrean bila relasi diikuti
            active = relation_to_active_form(doc_id, target_id, rel["text"], norm,
                                             "SOURCE_METADATA", url)
            upsert_relation(conn, active, now)
            self.stats["relations_found"] += 1
            if scope == "IN_SCOPE" and active["relation_type"] in self.follow:
                row = conn.execute(
                    "SELECT discovery_status FROM documents WHERE document_id = ?",
                    (target_id,),
                ).fetchone()
                if row["discovery_status"] == "DISCOVERED":
                    # target belum pernah diambil halamannya -> antrekan
                    target_url = requests.compat.urljoin(self._bpk_base(), rel["href"])
                    self._enqueue(conn, target_id, target_url,
                                  (item.get("depth") or 0) + 1, doc_id, parsed)
        self._set_queue(conn, item["crawl_id"], "DONE")

    def _bpk_base(self) -> str:
        for s in self.sources.get("sources", []):
            if s.get("key") == "BPK":
                return s.get("base_url", "https://peraturan.bpk.go.id")
        return "https://peraturan.bpk.go.id"

    def _document_row(self, doc_id: str, jenis: str, nomor_raw: str,
                      meta: dict, scope: str) -> dict:
        tahun = meta.get("Tahun")
        return {
            "document_id": doc_id,
            "jenis": jenis,
            "nomor_raw": nomor_raw,
            "nomor_norm": (ids.parse_document_ref(doc_id) or {}).get("nomor_norm", ""),
            "tahun": int(tahun) if tahun else None,
            "judul": meta.get("Judul"),
            "tempat_penetapan": meta.get("Tempat Penetapan"),
            "tanggal_penetapan": parse_date_id(meta.get("Tanggal Penetapan")),
            "tanggal_pengundangan": parse_date_id(meta.get("Tanggal Pengundangan")),
            "tanggal_berlaku_sumber": parse_date_id(meta.get("Tanggal Berlaku")),
            "sumber_publikasi": meta.get("Sumber"),
            "subjek_sumber": meta.get("Subjek"),
            "bidang_sumber": meta.get("Bidang"),
            "status_sumber": meta.get("Status"),
            "hierarchy_level": hierarchy_level(jenis),
            "source_urls_json": json.dumps(
                [{"source": "peraturan.bpk.go.id", "url": meta.get("url", "")}],
                ensure_ascii=False),
            "primary_source": "peraturan.bpk.go.id",
            "scope_status": scope,
            "owner_domain": (self.card["domain_id"] if scope == "IN_SCOPE" else None),
            "discovery_status": "METADATA_FETCHED",
            "ingestion_status": "PENDING",
            "extraction_status": "PENDING",
            "validation_status": "PENDING",
            "legal_status": "NEEDS_VERIFICATION",
            "first_seen_at": datetime.utcnow().isoformat(),
            "last_checked_at": datetime.utcnow().isoformat(),
        }

    def _print_relations(self, doc_id: str, page: dict):
        for rel in page["relations"]:
            norm = normalize_relation_label(rel["label"], self.relation_map)
            parsed = ids.parse_document_ref(rel["text"])
            print(f"    RELASI [{rel['label']}] -> {rel['text'][:60]} "
                  f"({parsed['document_id'] if parsed else '?'}"
                  f"{' label TAK DIKENAL' if norm is None else ''})")

    def _enqueue_dry(self, page: dict, doc_id: str, scope: str, depth: int):
        if scope != "IN_SCOPE":
            return
        queued = {q["document_id"] for q in self._dry_queue}
        for rel in page["relations"]:
            norm = normalize_relation_label(rel["label"], self.relation_map)
            if norm is None or norm["internal"] not in self.follow:
                continue
            parsed = ids.parse_document_ref(rel["text"])
            if parsed is None:
                continue
            target = parsed["document_id"]
            # visited ditandai saat POP (di run()), bukan di sini
            if target in self.visited or target in queued or target == doc_id:
                continue
            queued.add(target)
            self._dry_queue.append({
                "document_id": target, "depth": depth + 1,
                "url": requests.compat.urljoin(self._bpk_base(), rel["href"]),
                "origin_document_id": doc_id,
            })

    # -- run ------------------------------------------------------------------
    def run(self, limit: int) -> dict:
        self._dry_queue: List[dict] = []
        conn = None if self.dry_run else connect(self.db_path)
        if conn is not None and conn.execute(
                "SELECT COUNT(*) AS n FROM crawl_queue WHERE status = 'QUEUED'"
        ).fetchone()["n"] == 0:
            for seed_id, seed in self.seeds.items():
                url = seed.get("url")
                if url and conn.execute(
                        "SELECT 1 FROM documents WHERE document_id = ?", (seed_id,)
                ).fetchone() is None:
                    self._enqueue(conn, seed_id, url, 0, None,
                                  ids.parse_document_ref(seed_id))

        processed = 0
        queue: List[dict] = []
        if self.dry_run:
            # antrean awal dari seed kartu
            for seed_id, seed in self.seeds.items():
                if seed.get("url"):
                    queue.append({"document_id": seed_id, "url": seed["url"],
                                  "depth": 0, "origin_document_id": None,
                                  "crawl_id": -1})
        while processed < limit:
            if self.dry_run:
                if not queue:
                    break
                item = queue.pop(0)
                if item["document_id"] in self.visited:
                    continue
                self.visited.add(item["document_id"])
            else:
                item = self._next_queue(conn)
                if item is None:
                    break
                if item["document_id"] and item["document_id"] in self.visited:
                    self._set_queue(conn, item["crawl_id"], "SKIPPED")
                    continue
                self.visited.add(item["document_id"])
                self._set_queue(conn, item["crawl_id"], "PROCESSING")
            print(f"[{processed + 1}/{limit}] {item.get('document_id') or '?'} <- "
                  f"{item.get('origin_document_id') or 'SEED'} ({item['url']})")
            try:
                self.process_one(conn, item)
            except Exception as e:  # satu dokumen gagal TIDAK boleh menghentikan run
                self.stats["failed"] += 1
                print(f"  [ERROR] {item.get('document_id')}: {type(e).__name__}: {e}")
                if not self.dry_run:
                    self._set_queue(conn, item["crawl_id"], "FAILED",
                                    f"{type(e).__name__}: {e}")
            if not self.dry_run:
                conn.commit()
            processed += 1
            if self.dry_run:
                queue.extend(self._dry_queue)
                self._dry_queue = []
        if conn is not None:
            conn.close()
        return self.stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="S1 penjelajah graf relasi + S2 gerbang")
    parser.add_argument("--card", required=True, help="kartu lingkup (YAML)")
    parser.add_argument("--limit", type=int, default=None, help="batas dokumen per run")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.add_argument("--init-db", action="store_true", help="inisialisasi DB bila belum ada")
    parser.add_argument("--db", default="data/kbr.sqlite")
    parser.add_argument("--seed", default=None,
                        help="document_id seed tunggal untuk pilot (default: semua seed kartu)")
    args = parser.parse_args(argv)

    card = load_card(args.card)
    if args.seed:
        seeds = [s for s in card.get("seeds", []) if s["document_id"] == args.seed]
        if not seeds:
            parser.error(f"seed {args.seed} tidak ada di kartu lingkup")
        card["seeds"] = seeds
    crawl_cfg = load_yaml("config/crawl.yaml")
    sources = load_yaml("config/sources.yaml")
    relation_map = load_yaml("config/relation_map.yaml")
    limit = args.limit or crawl_cfg.get("crawl", {}).get("max_documents_per_run", 20)
    dry_run = args.dry_run if args.dry_run is not None else crawl_cfg.get("crawl", {}).get("dry_run", True)

    if args.init_db or not Path(args.db).exists():
        c = init_db(args.db)
        c.close()

    print(f"== S1/S2: kartu={card['domain_id']} limit={limit} dry_run={dry_run} ==")
    crawler = Crawler(card, crawl_cfg, sources, relation_map, args.db, dry_run)
    stats = crawler.run(limit)
    print("== Ringkasan ==")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if dry_run:
        print("== (dry-run: TIDAK ada yang ditulis ke DB) ==")
    else:
        print(f"== (hasil ditulis ke {args.db}) ==")


if __name__ == "__main__":
    main()
