#!/usr/bin/env python3
"""
Fast bulk load: JSONL → temp table → upsert into papers.
Uses execute_values for batch insert (much faster than row-by-row).
"""

import json, sys, time
from pathlib import Path
import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

DB_NAME = "borr_local"
JSONL_PATH = Path("/Users/nehalhasnain/Desktop/BORR PROJECT/data/clean/borr_papers.clean.jsonl")
BATCH_SIZE = 2000

def safe(v, default=None):
    return v if v else default
import os

def main():
    db_uri = os.environ.get("DATABASE_URL", f"dbname={DB_NAME}")
    conn = psycopg2.connect(db_uri)
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM papers")
        initial_count = cur.fetchone()[0]

    # Drop temp table if exists
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS _borr_import")
        cur.execute("""
            CREATE TEMP TABLE _borr_import (LIKE papers INCLUDING DEFAULTS);
            ALTER TABLE _borr_import DROP COLUMN search_vector;
        """)
    conn.commit()

    total = 0
    batch = []
    t0 = time.time()

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue

            title = safe(str(r.get("title", "")).strip())
            if not title:
                continue

            # Some Crossref/PubMed/DOAJ records lack openalex_id
            oa_id = safe(r.get("openalex_id"))
            if not oa_id:
                doi = safe(r.get("doi"))
                if doi:
                    oa_id = f"doi:{doi}"
                else:
                    oa_id = f"uuid:{safe(r.get('id', ''))}"

            row = (
                safe(r.get("id")),
                oa_id,
                title[:2000],
                # JSON null must stay NULL — str(None) would store the string "None".
                (str(r["abstract"]).strip() or None) if r.get("abstract") is not None else None,
                [str(x) for x in r.get("authors", []) if x] if r.get("authors") else [],
                safe(r.get("doi")),
                safe(r.get("url")),
                safe(r.get("journal")),
                int(r["year"]) if r.get("year") else None,
                [str(x) for x in r.get("institutions", []) if x] if r.get("institutions") else [],
                [str(x) for x in r.get("fields", []) if x] if r.get("fields") else [],
                safe(r.get("paper_type"), "Other"),
                safe(r.get("access_type"), "Unknown"),
                safe(r.get("source"), "Unknown"),
                int(r.get("citation_count", 0)) if r.get("citation_count") else 0,
            )

            batch.append(row)
            total += 1

            if len(batch) >= BATCH_SIZE:
                flush(conn, batch)
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed > 0 else 0
                print(f"  {line_no:,} lines | {total:,} valid | {rate:.0f} rec/s", flush=True)
                batch = []

    if batch:
        flush(conn, batch)

    elapsed = time.time() - t0
    print(f"\nLoaded {total:,} records into temp table in {elapsed:.1f}s ({total/elapsed:.0f} rec/s)")

    # Now upsert from temp into papers
    print("\nUpserting into papers table...")
    t1 = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO papers (
                id, openalex_id, title, abstract, authors, doi, url,
                journal, year, institution, fields, paper_type,
                access_type, source, citation_count, created_at, updated_at
            )
            SELECT
                id, openalex_id, title, abstract, authors, doi, url,
                journal, year, institution, fields, paper_type,
                access_type, source, citation_count, NOW(), NOW()
            FROM _borr_import
            ON CONFLICT (openalex_id) WHERE openalex_id IS NOT NULL DO UPDATE SET
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
        """)
        cur.execute("SELECT COUNT(*) FROM _borr_import")
        imported = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM papers")
        final = cur.fetchone()[0]
        cur.execute("DROP TABLE IF EXISTS _borr_import")
    conn.commit()
    conn.close()

    print(f"Imported {imported:,} from temp table")
    print(f"Final papers count: {final:,}")
    print(f"New records: {final - initial_count:,}")
    print(f"Upsert time: {time.time()-t1:.1f}s")
    print(f"Total time: {time.time()-t0:.1f}s")


def flush(conn, batch):
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO _borr_import (
                id, openalex_id, title, abstract, authors, doi, url,
                journal, year, institution, fields, paper_type,
                access_type, source, citation_count
            ) VALUES %s
        """, batch, page_size=BATCH_SIZE)
    conn.commit()


if __name__ == "__main__":
    main()
