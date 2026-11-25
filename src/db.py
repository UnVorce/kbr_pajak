# -*- coding: utf-8 -*-
"""DDL dan akses SQLite (data/kbr.sqlite) — KBR_Extraction_Spec.md Bagian 5.

Konvensi:
- Semua tabel di SQLite kecuali dinyatakan lain (hasil ekstraksi isi ketentuan
  T2 disimpan di data/legal_rules.jsonl, spec 5.12).
- Tanggal ISO YYYY-MM-DD (TEXT). Boolean 0/1. Kolom *_json berisi JSON (TEXT).
- Status memakai enumerasi 5.10 spec. JANGAN membuat nilai status baru tanpa
  persetujuan manusia.

CATATAN UNTUK G0 (ditambahkan di luar teks eksplisit spec, mohon tinjau):
- Tabel `schema_meta` untuk versi skema (mendukung migrasi).
- `crawl_queue` diperluas dengan kolom resumability (attempts, error, enqueued_at).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "0.1"

# Nilai status yang diizinkan (spec 5.10). Dipakai untuk dokumentasi dan review.
SCOPE_STATUS = ("UNDECIDED", "IN_SCOPE", "BOUNDARY", "OUT_OF_SCOPE")
DISCOVERY_STATUS = ("DISCOVERED", "METADATA_FETCHED", "METADATA_VERIFIED", "FAILED", "NEEDS_REVIEW")
INGESTION_STATUS = ("PENDING", "INGESTED", "FAILED", "NEEDS_REVIEW")
EXTRACTION_STATUS = ("PENDING", "EXTRACTED", "FAILED", "NEEDS_REVIEW")
VALIDATION_STATUS = ("PENDING", "SCHEMA_VALID", "SOURCE_VERIFIED", "REVIEW_REQUIRED", "VALIDATED", "REJECTED")
LEGAL_STATUS = ("NEEDS_VERIFICATION", "BERLAKU", "DIUBAH_SEBAGIAN", "DICABUT", "TIDAK_DIKETAHUI")
REVIEW_STATUS = ("PENDING", "APPROVED", "REJECTED")

DDL_STATEMENTS = [
    # -- infomasi skema (tambahan Fase 0, mohon konfirmasi di G0) -------------
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    # -- 5.2 documents (registry) ---------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS documents (
        document_id            TEXT PRIMARY KEY,
        jenis                  TEXT NOT NULL,
        nomor_raw              TEXT,
        nomor_norm             TEXT,
        tahun                  INTEGER,
        judul                  TEXT,
        tempat_penetapan       TEXT,
        tanggal_penetapan      TEXT,
        tanggal_pengundangan   TEXT,
        tanggal_berlaku_sumber TEXT,
        sumber_publikasi       TEXT,
        subjek_sumber          TEXT,
        bidang_sumber          TEXT,
        status_sumber          TEXT,
        hierarchy_level        INTEGER,
        source_urls_json       TEXT,
        primary_source         TEXT,
        content_hash           TEXT,
        scope_status           TEXT,
        owner_domain           TEXT,
        claimed_by             TEXT,
        claimed_at             TEXT,
        discovery_status       TEXT,
        ingestion_status       TEXT,
        extraction_status      TEXT,
        validation_status      TEXT,
        legal_status           TEXT,
        first_seen_at          TEXT,
        last_checked_at        TEXT,
        notes                  TEXT
    )
    """,
    # -- 5.1 document_aliases --------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS document_aliases (
        alias_id    TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE
    )
    """,
    # -- 5.3 relations (bentuk aktif) ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS relations (
        relation_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        from_document_id  TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
        to_document_id    TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
        relation_type     TEXT NOT NULL,
        origin            TEXT NOT NULL,
        evidence          TEXT,
        confidence        REAL NOT NULL DEFAULT 0,
        verified          INTEGER NOT NULL DEFAULT 0,
        discovered_at     TEXT,
        UNIQUE (from_document_id, to_document_id, relation_type)
    )
    """,
    # -- 5.4 provisions (struktur peraturan) -----------------------------------
    """
    CREATE TABLE IF NOT EXISTS provisions (
        provision_id        TEXT PRIMARY KEY,
        document_id         TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
        part                TEXT NOT NULL,
        level               TEXT NOT NULL,
        nomor               TEXT NOT NULL,
        parent_provision_id TEXT REFERENCES provisions(provision_id) ON DELETE CASCADE,
        ordinal             INTEGER,
        locator_text        TEXT,
        role                TEXT,
        heading             TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_provisions_document ON provisions (document_id, ordinal)
    """,
    # -- 5.6 amendments (peristiwa perubahan) ----------------------------------
    """
    CREATE TABLE IF NOT EXISTS amendments (
        amendment_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        amending_document_id  TEXT NOT NULL REFERENCES documents(document_id),
        amending_locator      TEXT,
        target_document_id    TEXT NOT NULL REFERENCES documents(document_id),
        target_locator        TEXT,
        target_part           TEXT,
        action                TEXT NOT NULL,
        new_text              TEXT,
        effective_from        TEXT,
        effective_basis       TEXT,
        parse_method          TEXT NOT NULL,
        confidence            REAL,
        source_quote          TEXT,
        review_status         TEXT NOT NULL DEFAULT 'PENDING'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_amendments_target ON amendments (target_document_id, target_locator)
    """,
    # -- 5.5 provision_versions (riwayat teks) ---------------------------------
    """
    CREATE TABLE IF NOT EXISTS provision_versions (
        version_id              TEXT PRIMARY KEY,
        provision_id            TEXT NOT NULL REFERENCES provisions(provision_id) ON DELETE CASCADE,
        version_no              INTEGER NOT NULL,
        text                    TEXT,
        text_hash              TEXT,
        is_deleted              INTEGER NOT NULL DEFAULT 0,
        valid_from              TEXT,
        valid_to                TEXT,
        created_by_document_id  TEXT REFERENCES documents(document_id),
        created_by_amendment_id INTEGER REFERENCES amendments(amendment_id),
        reconstruction_method   TEXT,
        verification_status     TEXT NOT NULL DEFAULT 'UNVERIFIED',
        effective_basis         TEXT,
        applicability_notes     TEXT,
        UNIQUE (provision_id, version_no)
    )
    """,
    # -- 5.7 domain_tags --------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS domain_tags (
        tag_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type   TEXT NOT NULL,
        entity_id     TEXT NOT NULL,
        domain_id     TEXT NOT NULL,
        score         REAL,
        method        TEXT NOT NULL,
        review_status TEXT NOT NULL DEFAULT 'AUTO_ACCEPTED'
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_domain_tags_entity ON domain_tags (entity_type, entity_id)
    """,
    # -- 5.8 unresolved_citations (pendeteksi lubang) ---------------------------
    """
    CREATE TABLE IF NOT EXISTS unresolved_citations (
        citation_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        in_document_id      TEXT REFERENCES documents(document_id),
        in_locator          TEXT,
        raw_text            TEXT NOT NULL,
        parsed_jenis        TEXT,
        parsed_nomor        TEXT,
        parsed_tahun        TEXT,
        context_type        TEXT,
        resolved_document_id TEXT REFERENCES documents(document_id),
        status              TEXT NOT NULL DEFAULT 'UNRESOLVED',
        resolved_at         TEXT
    )
    """,
    # -- 5.9 chunks -------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id    TEXT PRIMARY KEY,
        task_type   TEXT NOT NULL,
        document_id TEXT REFERENCES documents(document_id),
        locator     TEXT,
        text        TEXT NOT NULL,
        context     TEXT,
        domain_hint TEXT,
        text_hash   TEXT,
        created_at  TEXT
    )
    """,
    # -- 5.9 llm_results (append-only dari Colab, lalu diimpor) -----------------
    """
    CREATE TABLE IF NOT EXISTS llm_results (
        result_key     TEXT PRIMARY KEY,
        chunk_id       TEXT NOT NULL REFERENCES chunks(chunk_id),
        task_type      TEXT NOT NULL,
        model_id       TEXT,
        prompt_version TEXT,
        raw_output     TEXT,
        parsed_output  TEXT,
        parse_error    TEXT,
        latency_s      REAL,
        tokens_in      INTEGER,
        tokens_out     INTEGER,
        created_at     TEXT
    )
    """,
    # -- 5.11 review_queue -------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS review_queue (
        item_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type     TEXT NOT NULL,
        entity_id       TEXT NOT NULL,
        reason          TEXT,
        priority        INTEGER NOT NULL DEFAULT 3,
        assigned_to     TEXT,
        status          TEXT NOT NULL DEFAULT 'OPEN',
        created_at      TEXT,
        resolved_at     TEXT,
        resolution_note TEXT
    )
    """,
    # -- S1 crawl_queue (resumable; kolom attempts/error adalah tambahan) --------
    """
    CREATE TABLE IF NOT EXISTS crawl_queue (
        crawl_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id       TEXT,
        url               TEXT NOT NULL,
        depth             INTEGER NOT NULL DEFAULT 0,
        origin_document_id TEXT,
        status            TEXT NOT NULL DEFAULT 'QUEUED',
        attempts          INTEGER NOT NULL DEFAULT 0,
        last_attempt_at   TEXT,
        error             TEXT,
        enqueued_at       TEXT
    )
    """,
]


def connect(db_path):
    """Buka koneksi SQLite dengan foreign_keys aktif dan Row factory."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path) -> sqlite3.Connection:
    """Buat berkas SQLite (bila belum ada) dan semua tabel. Idempoten."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    with conn:
        script = ";\n".join(s.strip() for s in DDL_STATEMENTS) + ";"
        conn.executescript(script)
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (SCHEMA_VERSION,),
        )
    return conn


def list_tables(conn) -> list:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]
