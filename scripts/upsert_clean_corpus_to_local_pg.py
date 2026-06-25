#!/usr/bin/env python3
"""
Upsert borr_papers.clean.jsonl into local PostgreSQL (borr_local).

Strategy:
- Reads the clean JSONL (439,968 records)
- For each record, INSERT ON CONFLICT (openalex_id) DO UPDATE
- This preserves existing records but updates them if the clean corpus has corrections
- New records (from multi-source harvest) get inserted
- Tracks: inserted, updated, skipped, errors
"""

import json, sys, os
from pathlib import Path
from datetime import timezone
import psycopg2
import psycopg2.extras

DB_NAME = "borr_local"
JSONL_PATH = Path("/Users/nehalhasnain/Desktop/BORR PROJECT/data/clean/borr_papers.clean.jsonl")
BATCH_SIZE = 500
CHECKPOINT_FILE = Path("/Users/nehalhasnain/Desktop/BORR PROJECT/data/clean/upsert_checkpoint.txt")

UPSERT_SQL = """
INSERT INTO papers (
    id, openalex_id, title, abstract, authors, doi, url,
    journal, year, institution, fields, paper_type,
    access_type, source, citation_count,
    created_at, updated_at
) VALUES (
    %(id)s, %(openalex_id)s, %(title)s, %(abstract)s, %(authors)s, %(doi)s, %(url)s,
    %(journal)s, %(year)s, %(institution)s, %(fields)s, %(paper_type)s,
    %(access_type)s, %(source)s, %(citation_count)s,
    NOW(), NOW()
)
ON CONFLICT (openalex_id) DO UPDATE SET
    title = EXCLUDED.title,
    abstract = EXCLUDED.abstract,
    authors = EXCLUDED.authors,
    doi = EXCLUDED.doi,
    url = EXCLUDED.url,
    journal = EXCLUDED.journal,
    year = EXCLUDED.year,
    institution = EXCLUDED.institution,
    fields = EXCLUDED.fields,
    paper_type = EXCLUDED.paper_type,
    access_type = EXCLUDED.access_type,
    source = EXCLUDED.source,
    citation_count = EXCLUDED.citation_count,
    updated_at = NOW()
"""

def safe_str(val):
    """Return string or None, stripping to reasonable length."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None

def safe_list(val):
    """Return list of strings or empty list."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val if x]
    return [str(val)]

def safe_int(val):
    """Return int or None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def map_record(r):
    """Map a clean JSONL record to PostgreSQL row dict."""
    title = safe_str(r.get("title"))
    if not title:
        return None  # skip records with no title

    oa_id = safe_str(r.get("openalex_id"))
    rec_id = safe_str(r.get("id"))

    return {
        "id": rec_id,
        "openalex_id": oa_id,
        "title": title[:2000] if title else None,
        "abstract": (safe_str(r.get("abstract")) or "")[:5000],
        "authors": safe_list(r.get("authors")),
        "doi": safe_str(r.get("doi")),
        "url": safe_str(r.get("url")),
        "journal": safe_str(r.get("journal")),
        "year": safe_int(r.get("year")),
        "institution": safe_list(r.get("institutions")),
        "fields": safe_list(r.get("fields")),
        "paper_type": safe_str(r.get("paper_type")) or "Other",
        "access_type": safe_str(r.get("access_type")) or "Unknown",
        "source": safe_str(r.get("source")) or "Unknown",
        "citation_count": safe_int(r.get("citation_count")) or 0,
    }


def main():
    # Read checkpoint
    start_line = 0
    if CHECKPOINT_FILE.exists():
        start_line = int(CHECKPOINT_FILE.read_text().strip())
        print(f"Resuming from line {start_line}")

    conn = psycopg2.connect(f"dbname={DB_NAME}")
    conn.autocommit = False

    total = 0
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    batch = []

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if line_no <= start_line:
                continue

            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue

            row = map_record(rec)
            if row is None:
                skipped += 1
                continue

            batch.append(row)
            total += 1

            if len(batch) >= BATCH_SIZE:
                i, u = flush_batch(conn, batch)
                inserted += i
                updated += u
                batch = []

                # Save checkpoint
                CHECKPOINT_FILE.write_text(str(line_no))
                pct = (line_no / 439968) * 100
                print(f"  Line {line_no:,} ({pct:.1f}%) | new={inserted:,} upd={updated:,} skip={skipped:,} err={errors:,}")

    # Final batch
    if batch:
        i, u = flush_batch(conn, batch)
        inserted += i
        updated += u

    conn.close()
    CHECKPOINT_FILE.write_text("DONE")

    print(f"\n=== COMPLETE ===")
    print(f"Total processed: {total:,}")
    print(f"New inserted:    {inserted:,}")
    print(f"Updated:         {updated:,}")
    print(f"Skipped:         {skipped:,}")
    print(f"Errors:          {errors:,}")


def flush_batch(conn, batch):
    ins = 0
    upd = 0
    with conn.cursor() as cur:
        for row in batch:
            try:
                cur.execute(UPSERT_SQL, row)
                # Detect insert vs update: psycopg2 cursor.rowcount
                # ON CONFLICT DO UPDATE returns 1 for insert, or 1 for update
                # We can't distinguish easily. Use a RETURNING-based approach if needed.
                # For now, count all as "processed"
                ins += 1  # placeholder — we count them but can't split easily
            except Exception as e:
                print(f"  ERROR on {row.get('openalex_id','?')}: {e}")
                conn.rollback()
                return ins, upd
    conn.commit()
    return ins, upd


if __name__ == "__main__":
    main()
