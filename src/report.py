# -*- coding: utf-8 -*-
"""S10 — laporan cakupan & kualitas (KBR_Extraction_Spec.md Bagian 9).

Fase 0: KERANGKA. Menghitung metrik M1–M8 (9.1) dan invarian I1–I3 (6.4) dari
SQLite. Pada DB kosong semua bernilai 0/N/A — itu hasil yang benar dan jujur.

M5 (cocok dengan naskah konsolidasi) butuh data sampel Fase 7 -> dilaporkan N/A.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.db import connect, init_db

# Sumber yang direncanakan (spec 7.1) — dipakai M3 rekonsiliasi antar-sumber.
SOURCE_KEYS = (
    ("peraturan.bpk.go.id", "BPK"),
    ("jdih.kemenkeu.go.id", "KEMENKEU"),
    ("pajak.go.id", "DJP"),
)

STAGE_COLUMNS = ("discovery_status", "ingestion_status", "extraction_status", "validation_status")


# ---------------------------------------------------------------------------
# M1–M8
# ---------------------------------------------------------------------------

def m1_crawl_queue_remaining(conn) -> dict:
    rows = conn.execute(
        """
        SELECT COALESCE(d.owner_domain, 'UNASSIGNED') AS domain, COUNT(*) AS n
        FROM crawl_queue q
        LEFT JOIN documents d ON d.document_id = q.document_id
        WHERE q.status NOT IN ('DONE', 'SKIPPED')
        GROUP BY domain
        """
    ).fetchall()
    return {r["domain"]: r["n"] for r in rows}


def m2_unresolved_citations(conn) -> dict:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM unresolved_citations GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def m3_cross_source_diff(conn) -> dict:
    """Dokumen yang ada di sumber A tetapi tidak di sumber B, per pasangan."""
    docs = conn.execute("SELECT document_id, source_urls_json FROM documents").fetchall()
    present = {key: set() for _, key in SOURCE_KEYS}
    for r in docs:
        urls = _extract_urls(r["source_urls_json"])
        for domain, key in SOURCE_KEYS:
            if any(domain in u for u in urls):
                present[key].add(r["document_id"])
    diffs = {}
    keys = [k for _, k in SOURCE_KEYS]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            only_a = sorted(present[a] - present[b])
            only_b = sorted(present[b] - present[a])
            diffs[f"{a}_minus_{b}"] = only_a
            diffs[f"{b}_minus_{a}"] = only_b
    return diffs


def m4_version_chain_complete(conn) -> dict:
    total = conn.execute("SELECT COUNT(*) AS n FROM provisions").fetchone()["n"]
    with_versions = conn.execute(
        "SELECT COUNT(DISTINCT provision_id) AS n FROM provision_versions"
    ).fetchone()["n"]
    overlap = conn.execute(
        """
        SELECT COUNT(*) AS n FROM (
            SELECT provision_id
            FROM provision_versions
            WHERE valid_from IS NOT NULL AND valid_to IS NOT NULL AND valid_from >= valid_to
            UNION
            SELECT v1.provision_id
            FROM provision_versions v1
            JOIN provision_versions v2
              ON v2.provision_id = v1.provision_id AND v2.version_no > v1.version_no
            WHERE v1.valid_to IS NOT NULL AND v2.valid_from IS NOT NULL
              AND v2.valid_from < v1.valid_to
        )
        """
    ).fetchone()["n"]
    complete = with_versions - overlap if with_versions > overlap else 0
    return {
        "total_provisions": total,
        "with_versions": with_versions,
        "with_interval_overlap": overlap,
        "chain_complete": complete,
        "percent": round(100.0 * complete / total, 2) if total else None,
    }


def m5_consolidation_match(conn) -> dict:
    return {"status": "N/A", "note": "Dihitung Fase 7 setelah verifikasi naskah konsolidasi"}


def m6_invariant_violations(conn) -> dict:
    i1 = conn.execute(
        """
        SELECT COUNT(*) AS n FROM documents
        WHERE scope_status = 'IN_SCOPE' AND (owner_domain IS NULL OR owner_domain = '')
        """
    ).fetchone()["n"]
    i2 = conn.execute(
        """
        SELECT COUNT(*) AS n FROM documents
        WHERE claimed_by IS NOT NULL AND claimed_by != ''
          AND claimed_by != owner_domain
        """
    ).fetchone()["n"]
    # Konvensi (ISSUES.md): asal domain temuan BOUNDARY dicatat sebagai domain_tags
    # (entity_type='DOCUMENT', method='MANUAL'/'SOURCE_METADATA').
    i3 = conn.execute(
        """
        SELECT COUNT(*) AS n FROM documents d
        WHERE d.scope_status = 'BOUNDARY'
          AND NOT EXISTS (
              SELECT 1 FROM domain_tags t
              WHERE t.entity_type = 'DOCUMENT' AND t.entity_id = d.document_id
          )
        """
    ).fetchone()["n"]
    return {"I1_in_scope_without_owner": i1, "I2_claimed_by_mismatch_owner": i2, "I3_boundary_without_origin": i3}


def m7_failed_needs_review(conn) -> dict:
    out = {}
    for col in STAGE_COLUMNS:
        rows = conn.execute(
            f"SELECT {col} AS status, COUNT(*) AS n FROM documents GROUP BY {col}"
        ).fetchall()
        out[col] = {r["status"]: r["n"] for r in rows if r["status"] in ("FAILED", "NEEDS_REVIEW")}
    return out


def m8_unreviewed_boundary_undecided(conn) -> dict:
    boundary = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE scope_status = 'BOUNDARY'"
    ).fetchone()["n"]
    undecided = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE scope_status = 'UNDECIDED'"
    ).fetchone()["n"]
    unreviewed = conn.execute(
        """
        SELECT COUNT(*) AS n FROM documents d
        WHERE d.scope_status IN ('BOUNDARY', 'UNDECIDED')
          AND NOT EXISTS (
              SELECT 1 FROM review_queue q
              WHERE q.entity_type = 'DOCUMENT' AND q.entity_id = d.document_id AND q.status = 'DONE'
          )
        """
    ).fetchone()["n"]
    return {"boundary": boundary, "undecided": undecided, "unreviewed": unreviewed}


# ---------------------------------------------------------------------------
# Status terpakai (untuk review disiplin enumerasi 5.10 di G0)
# ---------------------------------------------------------------------------

def status_usage(conn) -> dict:
    out = {}
    for col in ("scope_status", "discovery_status", "ingestion_status",
                "extraction_status", "validation_status", "legal_status"):
        rows = conn.execute(f"SELECT {col} AS v, COUNT(*) AS n FROM documents GROUP BY {col}").fetchall()
        out[col] = {r["v"]: r["n"] for r in rows}
    rows = conn.execute("SELECT status AS v, COUNT(*) AS n FROM review_queue GROUP BY v").fetchall()
    out["review_queue.status"] = {r["v"]: r["n"] for r in rows}
    return out


# ---------------------------------------------------------------------------
# Rangkai laporan
# ---------------------------------------------------------------------------

def _extract_urls(source_urls_json):
    if not source_urls_json:
        return []
    try:
        data = json.loads(source_urls_json)
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return [str(item.get("url", "")) if isinstance(item, dict) else str(item) for item in data]
    return []


def compute_metrics(db_path) -> dict:
    conn = connect(db_path)
    try:
        return {
            "M1_crawl_queue_remaining": m1_crawl_queue_remaining(conn),
            "M2_unresolved_citations": m2_unresolved_citations(conn),
            "M3_cross_source_diff": m3_cross_source_diff(conn),
            "M4_version_chain_complete": m4_version_chain_complete(conn),
            "M5_consolidation_match": m5_consolidation_match(conn),
            "M6_invariant_violations": m6_invariant_violations(conn),
            "M7_failed_needs_review": m7_failed_needs_review(conn),
            "M8_unreviewed_boundary_undecided": m8_unreviewed_boundary_undecided(conn),
            "status_usage": status_usage(conn),
        }
    finally:
        conn.close()


def render_markdown(metrics: dict) -> str:
    lines = [
        "# Source Coverage & Quality (dihasilkan report.py)",
        "",
        f"*Target metrik: spec Bagian 9.1 (M1–M8) dan invarian 6.4 (I1–I3).*",
        "",
        "## M1 — Antrean kunjungan tersisa (target: kosong)",
    ]
    m1 = metrics["M1_crawl_queue_remaining"]
    lines.append(f"- total: **{sum(m1.values())}**" + (f" — per domain: {m1}" if m1 else " (antrean kosong)"))
    lines += ["", "## M2 — Kutipan belum terselesaikan (target: tidak ada UNRESOLVED)"]
    m2 = metrics["M2_unresolved_citations"]
    lines.append("- " + (", ".join(f"{k}={v}" for k, v in sorted(m2.items())) if m2 else "tidak ada baris"))
    lines += ["", "## M3 — Selisih daftar dokumen antar-sumber (target: setiap selisih dijelaskan)"]
    m3 = metrics["M3_cross_source_diff"]
    for pair, ids in m3.items():
        lines.append(f"- {pair}: {len(ids)} dokumen{(' — ' + ', '.join(ids[:10]) + ('…' if len(ids) > 10 else '')) if ids else ' (kosong)'}")
    lines += ["", "## M4 — Rantai versi pasal lengkap (dilaporkan persentasenya)"]
    m4 = metrics["M4_version_chain_complete"]
    lines.append(
        f"- total pasal: {m4['total_provisions']}, punya versi: {m4['with_versions']}, "
        f"tumpang tindih interval: {m4['with_interval_overlap']}, lengkap: {m4['chain_complete']} "
        f"({m4['percent'] if m4['percent'] is not None else 'N/A'}%)"
    )
    lines += ["", "## M5 — Kecocokan naskah konsolidasi (Fase 7)"]
    lines.append(f"- status: {metrics['M5_consolidation_match']['status']} — {metrics['M5_consolidation_match']['note']}")
    lines += ["", "## M6 — Pelanggaran invarian (target: 0)"]
    for k, v in metrics["M6_invariant_violations"].items():
        lines.append(f"- {k}: **{v}**" + (" ✅" if v == 0 else " ❌"))
    lines += ["", "## M7 — Dokumen FAILED / NEEDS_REVIEW per tahap"]
    m7 = metrics["M7_failed_needs_review"]
    for col, counts in m7.items():
        lines.append(f"- {col}: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else "tidak ada"))
    lines += ["", "## M8 — BOUNDARY/UNDECIDED belum ditinjau"]
    m8 = metrics["M8_unreviewed_boundary_undecided"]
    lines.append(f"- BOUNDARY: {m8['boundary']}, UNDECIDED: {m8['undecided']}, belum ditinjau: **{m8['unreviewed']}**")
    lines += ["", "## Status terpakai (review disiplin enumerasi 5.10)"]
    for col, counts in metrics["status_usage"].items():
        lines.append(f"- {col}: " + (", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda x: str(x[0]))) if counts else "tidak ada baris"))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Laporan metrik M1–M8 (spec Bagian 9).")
    parser.add_argument("--db", default="data/kbr.sqlite", help="Path SQLite (default: data/kbr.sqlite)")
    parser.add_argument("--init", action="store_true", help="Inisialisasi DB bila belum ada")
    parser.add_argument("--out", default="reports/source_coverage.md", help="Path laporan markdown (default: reports/source_coverage.md)")
    args = parser.parse_args(argv)

    if args.init:
        conn = init_db(args.db)
        conn.close()
    db_path = Path(args.db)
    if not db_path.exists():
        parser.error(f"DB tidak ditemukan: {args.db}. Jalankan dengan --init atau init_db() dulu.")

    md = render_markdown(compute_metrics(db_path))
    print(md)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[report] ditulis ke {out}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
