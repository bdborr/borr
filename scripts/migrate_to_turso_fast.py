#!/usr/bin/env python3
"""
Fast migration: reads from local borr.db, writes INSERT statements to stdout.
Pipe to: python3 migrate_to_turso_fast.py | turso db shell borr

Usage:
    python3 scripts/migrate_to_turso_fast.py | ~/.turso/turso db shell borr

Skips rows already migrated (past max rowid in remote).
"""

import sqlite3
import sys
import os
import json

LOCAL_DB = os.path.join(os.path.dirname(__file__) or ".", "..", "borr.db")
CHUNK = 500

def quote(val):
    """Quote a value for SQL insertion, handling None and escaping."""
    if val is None:
        return "NULL"
    if isinstance(val, int):
        return str(val)
    s = str(val).replace("'", "''")
    return f"'{s}'"

def main():
    local = sqlite3.connect(LOCAL_DB)
    local.row_factory = sqlite3.Row

    # Get starting offset from remote
    try:
        remote_url = os.environ.get("TURSO_REMOTE")
        if remote_url:
            import subprocess
            result = subprocess.run(
                ["sqlite3", remote_url, "SELECT COALESCE(MAX(rowid), 0) FROM papers"],
                capture_output=True, text=True, timeout=10
            )
            start_rowid = int(result.stdout.strip())
        else:
            start_rowid = 0
    except:
        start_rowid = 0

    total = local.execute("SELECT COUNT(*) FROM papers WHERE verified = 1 AND rowid > ?", (start_rowid,)).fetchone()[0]
    print(f"-- Migrating {total} papers starting from rowid {start_rowid}", file=sys.stderr)

    offset = 0
    last_rowid = start_rowid

    while True:
        rows = local.execute("""
            SELECT *, rowid FROM papers 
            WHERE verified = 1 AND rowid > ?
            ORDER BY rowid LIMIT ?
        """, (last_rowid, CHUNK)).fetchall()

        if not rows:
            break

        for row in rows:
            search_text = f"{row['title']} {row['abstract'] or ''} {row['authors_text'] or ''}"
            search_text = search_text.lower()

            print(f"""INSERT OR IGNORE INTO papers (
    id, openalex_id, title, authors, abstract, doi, url, journal, year,
    institution, fields, paper_type, access_type, source, verified,
    citation_count, created_at, updated_at, external_ids, sources,
    last_harvested_at, authors_text, institution_text, search_text
) VALUES (
    {quote(row['id'])}, {quote(row['openalex_id'])}, {quote(row['title'])},
    {quote(row['authors'])}, {quote(row['abstract'])}, {quote(row['doi'])},
    {quote(row['url'])}, {quote(row['journal'])}, {row['year'] if row['year'] else 'NULL'},
    {quote(row['institution'])}, {quote(row['fields'])},
    {quote(row['paper_type'])}, {quote(row['access_type'])},
    {quote(row['source'])}, {row['verified']},
    {row['citation_count'] if row['citation_count'] else 'NULL'},
    {quote(row['created_at'])}, {quote(row['updated_at'])},
    {quote(row['external_ids'] or '{}')}, {quote(row['sources'] or '[]')},
    {quote(row['last_harvested_at'])}, {quote(row['authors_text'])},
    {quote(row['institution_text'])}, {quote(search_text)}
);""")

            last_rowid = row['rowid']
            offset += 1

        pct = min(100, int(offset / total * 100)) if total else 0
        print(f"-- Progress: {offset}/{total} ({pct}%)", file=sys.stderr)

    print(f"-- Done! Migrated {offset} papers.", file=sys.stderr)

if __name__ == "__main__":
    main()
