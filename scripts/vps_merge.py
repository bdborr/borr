#!/usr/bin/env python3
"""
Memory-safe VPS Dedup & Merge Tool using SQLite
─────────────────────────────────────────────────
Processes large JSONL datasets sequentially and deduplicates them using a 
SQLite index (DOI and normalized Title) to avoid crashing the VPS.
"""
import json
import gzip
import sqlite3
import os
import re

DB_FILE = "/home/nehal_hasnain1_gmail_com/borr-harvest/state/merge_state.sqlite"
OUTPUT_FILE = "/home/nehal_hasnain1_gmail_com/borr-harvest/data/borr_master.jsonl.gz"

INPUTS = [
    ("/home/nehal_hasnain1_gmail_com/borr-harvest/data/borr_papers.enriched.jsonl", "OpenAlex", 3),
    ("/home/nehal_hasnain1_gmail_com/borr-harvest/data/borr_banglajol_harvested.jsonl.gz", "BanglaJOL", 2)
]

def normalize_title(title):
    if not title: return ""
    title = title.lower()
    return re.sub(r'[^a-z0-9]', '', title)

def init_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE papers (
        local_id INTEGER PRIMARY KEY AUTOINCREMENT,
        doi TEXT,
        norm_title TEXT,
        priority INTEGER,
        record_json TEXT
    )''')
    c.execute('CREATE INDEX idx_doi ON papers(doi)')
    c.execute('CREATE INDEX idx_title ON papers(norm_title)')
    conn.commit()
    return conn

def merge_json(existing_json, new_dict, existing_prio, new_prio):
    existing = json.loads(existing_json)
    
    if new_prio < existing_prio:
        url = new_dict.get("primary_location", {}).get("landing_page_url")
        if url:
            locs = existing.get("locations", [])
            if locs is None: locs = []
            if url not in [l.get("landing_page_url") for l in locs if l]:
                locs.append(new_dict["primary_location"])
                existing["locations"] = locs
        return json.dumps(existing)
    else:
        # If priority is equal or higher, just prefer new dict (in our order, OpenAlex is first anyway)
        return json.dumps(new_dict)

def process_files(conn):
    c = conn.cursor()
    total_inserted = 0
    total_merged = 0
    total_no_doi_merged = 0
    
    for filepath, source_name, priority in INPUTS:
        print(f"Processing {filepath} (Priority {priority})...")
        if not os.path.exists(filepath):
            print(f"File missing: {filepath}")
            continue
            
        opener = gzip.open if filepath.endswith('.gz') else open
        count = 0
        with opener(filepath, 'rt', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                try:
                    record = json.loads(line)
                except:
                    continue
                
                doi = record.get("doi")
                norm_title = normalize_title(record.get("title", ""))
                
                row_id = None
                existing_prio = 0
                existing_json = ""
                
                if doi:
                    c.execute('SELECT local_id, priority, record_json FROM papers WHERE doi=? LIMIT 1', (doi,))
                    row = c.fetchone()
                    if row:
                        row_id, existing_prio, existing_json = row
                
                if not row_id and norm_title and len(norm_title) > 10:
                    c.execute('SELECT local_id, priority, record_json FROM papers WHERE norm_title=? LIMIT 1', (norm_title,))
                    row = c.fetchone()
                    if row:
                        row_id, existing_prio, existing_json = row
                        if not doi: total_no_doi_merged += 1
                        
                if row_id is not None:
                    merged_json = merge_json(existing_json, record, existing_prio, priority)
                    new_prio = max(priority, existing_prio)
                    c.execute('UPDATE papers SET record_json=?, priority=? WHERE local_id=?', (merged_json, new_prio, row_id))
                    total_merged += 1
                else:
                    if "source" not in record:
                        record["source"] = source_name
                    c.execute('INSERT INTO papers (doi, norm_title, priority, record_json) VALUES (?, ?, ?, ?)',
                              (doi, norm_title, priority, json.dumps(record)))
                    total_inserted += 1
                    
                count += 1
                if count % 50000 == 0:
                    conn.commit()
                    print(f"  Processed {count} rows from {source_name}...")
                    
        conn.commit()
        
    print(f"\\nStats:")
    print(f"  Total distinct records inserted: {total_inserted}")
    print(f"  Total records merged into existing: {total_merged}")
    print(f"  Total non-DOI records merged by title: {total_no_doi_merged}")

    print(f"Writing output to {OUTPUT_FILE}...")
    c.execute('SELECT record_json FROM papers')
    with gzip.open(OUTPUT_FILE, 'wt', encoding='utf-8') as out:
        for row in c:
            out.write(row[0] + "\\n")
            
    print("Done!")

if __name__ == "__main__":
    conn = init_db()
    process_files(conn)
    conn.close()
