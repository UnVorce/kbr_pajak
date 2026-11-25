# -*- coding: utf-8 -*-
"""Tes DDL SQLite (src/db.py) — spec Bagian 5.

Bisa dijalankan lewat pytest ATAU langsung:  python3 tests/test_db.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import SCHEMA_VERSION, connect, init_db, list_tables

TABLES_WAJIB = {
    "amendments",
    "chunks",
    "crawl_queue",
    "document_aliases",
    "documents",
    "domain_tags",
    "llm_results",
    "provision_versions",
    "provisions",
    "relations",
    "review_queue",
    "schema_meta",
    "unresolved_citations",
}


def test_semua_tabel_ada():
    conn = init_db(":memory:")
    tables = set(list_tables(conn))
    assert TABLES_WAJIB <= tables, f"kurang tabel: {TABLES_WAJIB - tables}"
    conn.close()


def test_schema_version_tercatat():
    conn = init_db(":memory:")
    v = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    assert v is not None and v["value"] == SCHEMA_VERSION
    conn.close()


def test_foreign_keys_aktif():
    conn = connect(":memory:")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_insert_dokumen_dan_ambil_kembali():
    conn = init_db(":memory:")
    with conn:
        conn.execute(
            """
            INSERT INTO documents (document_id, jenis, nomor_raw, nomor_norm, tahun, judul,
                                   scope_status, owner_domain, discovery_status, legal_status)
            VALUES ('UU-1983-7', 'UU', '7', '7', 1983, 'Undang-Undang Pajak Penghasilan',
                    'IN_SCOPE', 'DOMAIN_A', 'DISCOVERED', 'NEEDS_VERIFICATION')
            """
        )
    row = conn.execute("SELECT * FROM documents WHERE document_id = 'UU-1983-7'").fetchone()
    assert row["jenis"] == "UU"
    assert row["tahun"] == 1983
    assert row["owner_domain"] == "DOMAIN_A"
    conn.close()


def test_relasi_duplikat_ditolak():
    conn = init_db(":memory:")
    with conn:
        conn.execute(
            "INSERT INTO documents (document_id, jenis, tahun) VALUES ('UU-2021-7', 'UU', 2021)"
        )
        conn.execute(
            "INSERT INTO documents (document_id, jenis, tahun) VALUES ('UU-1983-7', 'UU', 1983)"
        )
        conn.execute(
            """
            INSERT INTO relations (from_document_id, to_document_id, relation_type, origin)
            VALUES ('UU-2021-7', 'UU-1983-7', 'MENGUBAH', 'SOURCE_METADATA')
            """
        )
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO relations (from_document_id, to_document_id, relation_type, origin)
                VALUES ('UU-2021-7', 'UU-1983-7', 'MENGUBAH', 'TEXT_PATTERN')
                """
            )
        assert False, "duplikat (from, to, type) harusnya ditolak unique index"
    except sqlite3.IntegrityError:
        pass
    conn.close()


def test_init_db_idempoten():
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        c1 = init_db(path)
        with c1:
            c1.execute(
                "INSERT INTO documents (document_id, jenis, tahun) VALUES ('PP-2022-55', 'PP', 2022)"
            )
        c1.close()
        init_db(path)  # jalankan lagi di berkas sama
        c2 = connect(path)
        assert c2.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"] == 1
        c2.close()
    finally:
        os.remove(path)


def _main():
    import traceback

    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"ERROR {name}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} lulus")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    _main()
