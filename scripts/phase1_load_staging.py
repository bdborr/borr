#!/usr/bin/env python3
"""Phase 1: Load clean JSONL into staging table (persistent, survives disconnect)."""
import json, sys, time
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

DB = "borr_local"
JSONL = Path("/Users/nehalhasnain/Desktop/BORR PROJECT/data/clean/borr_papers.clean.jsonl")
BATCH = 2000

def safe(v, default=None):
    return v if v else default

conn = psycopg2.connect(f"dbname={DB}")
cur = conn.cursor()
cur.execute("DROP TABLE IF EXISTS borr_staging")
cur.execute("""
    CREATE TABLE borr_staging (
        id TEXT, openalex_id TEXT NOT NULL, title TEXT NOT NULL,
        abstract TEXT, authors TEXT, doi TEXT, url TEXT,
        journal TEXT, year INTEGER, institutions TEXT,
        fields TEXT, paper_type TEXT, access_type TEXT,
        source TEXT, citation_count INTEGER
    )
""")
conn.commit()

total = 0
batch = []
t0 = time.time()

with open(JSONL, "r", encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        line = line.strip()
        if not line: continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        title = safe(str(r.get("title", "")).strip())
        if not title: continue

        oa_id = safe(r.get("openalex_id"))
        if not oa_id:
            doi = safe(r.get("doi"))
            oa_id = f"doi:{doi}" if doi else f"uuid:{safe(r.get('id',''))}"

        batch.append((
            safe(r.get("id")), oa_id, title[:2000],
            safe(str(r.get("abstract","")).strip(),"")[:5000],
            json.dumps([str(x) for x in r.get("authors",[]) if x] if r.get("authors") else []),
            safe(r.get("doi")), safe(r.get("url")), safe(r.get("journal")),
            int(r["year"]) if r.get("year") else None,
            json.dumps([str(x) for x in r.get("institutions",[]) if x] if r.get("institutions") else []),
            json.dumps([str(x) for x in r.get("fields",[]) if x] if r.get("fields") else []),
            safe(r.get("paper_type"),"Other"), safe(r.get("access_type"),"Unknown"),
            safe(r.get("source"),"Unknown"), int(r.get("citation_count",0)) if r.get("citation_count") else 0,
        ))
        total += 1

        if len(batch) >= BATCH:
            execute_values(cur, """INSERT INTO borr_staging (id,openalex_id,title,abstract,authors,doi,url,journal,year,institutions,fields,paper_type,access_type,source,citation_count) VALUES %s""", batch, page_size=BATCH)
            conn.commit()
            batch = []
            elapsed = time.time() - t0
            print(f"  {line_no:,} lines | {total:,} valid | {total/elapsed:.0f} rec/s", flush=True)

if batch:
    execute_values(cur, """INSERT INTO borr_staging (id,openalex_id,title,abstract,authors,doi,url,journal,year,institutions,fields,paper_type,access_type,source,citation_count) VALUES %s""", batch, page_size=BATCH)
    conn.commit()

elapsed = time.time() - t0
print(f"\nLoaded {total:,} records in {elapsed:.1f}s ({total/elapsed:.0f} rec/s)")
conn.close()
print("Phase 1 complete — staging table ready.")
