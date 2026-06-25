#!/usr/bin/env python3
"""Phase 2: Fast merge from borr_staging into papers. Skips array expansion for speed."""
import psycopg2
from psycopg2.extras import execute_values
import time

conn = psycopg2.connect("dbname=borr_local")
cur = conn.cursor()

# First: get existing openalex_ids
cur.execute("SELECT openalex_id FROM papers")
existing = set(row[0] for row in cur.fetchall())
print(f"Existing papers: {len(existing):,}")

# Get staging count
cur.execute("SELECT COUNT(*) FROM borr_staging")
total_staging = cur.fetchone()[0]
print(f"Staging records: {total_staging:,}")

# Find new ones
cur.execute("SELECT openalex_id FROM borr_staging")
staging_ids = [row[0] for row in cur.fetchall()]
new_ids = [oid for oid in staging_ids if oid not in existing]
print(f"New records to insert: {len(new_ids):,}")
print(f"Already exist (skipped): {len(staging_ids) - len(new_ids):,}")

if not new_ids:
    print("Nothing to insert — DB already has all records.")
else:
    # Insert new records in batches
    BATCH = 500
    total = len(new_ids)
    inserted = 0
    t0 = time.time()

    for i in range(0, total, BATCH):
        batch = new_ids[i:i+BATCH]
        placeholders = ','.join(['%s'] * len(batch))
        
        cur.execute(f"""
            INSERT INTO papers (id, openalex_id, title, abstract, doi, url, journal, year, paper_type, access_type, source, citation_count, created_at, updated_at)
            SELECT 
                s.id::uuid, s.openalex_id, s.title, s.abstract,
                s.doi, s.url,
                s.journal, s.year,
                s.paper_type, s.access_type, s.source,
                s.citation_count, NOW(), NOW()
            FROM borr_staging s
            WHERE s.openalex_id IN ({placeholders})
        """, batch)
        
        inserted += cur.rowcount
        conn.commit()
        
        elapsed = time.time() - t0
        rate = inserted / elapsed if elapsed > 0 else 0
        pct = (inserted / total) * 100
        print(f"  {inserted:,}/{total:,} ({pct:.1f}%) | {rate:.0f} rec/s", flush=True)

    print(f"\nInserted {inserted:,} new records in {time.time()-t0:.1f}s")
    
    # Populate arrays for new records from staging
    print("Populating arrays (authors, institutions, fields)...")
    cur.execute("""
        UPDATE papers p SET
            authors = COALESCE((SELECT array_agg(value) FROM json_array_elements_text(s.authors::json) WHERE value != ''), '{}'),
            institution = COALESCE((SELECT array_agg(value) FROM json_array_elements_text(s.institutions::json) WHERE value != ''), '{}'),
            fields = COALESCE((SELECT array_agg(value) FROM json_array_elements_text(s.fields::json) WHERE value != ''), '{}')
        FROM borr_staging s
        WHERE p.openalex_id = s.openalex_id
          AND p.authors = '{}'
    """)
    conn.commit()
    print("Arrays populated.")

# Final count
cur.execute("SELECT COUNT(*) FROM papers")
final = cur.fetchone()[0]
print(f"Final papers count: {final:,}")

# Re-enable trigger and rebuild search vector
cur.execute("ALTER TABLE papers ENABLE TRIGGER papers_search_vector_trigger;")
print("\nRebuilding search vectors (this may take a while)...")
cur.execute("UPDATE papers SET search_vector = to_tsvector('english', coalesce(title,'') || ' ' || coalesce(abstract,''));")
conn.commit()
print("Search vectors rebuilt.")

# Clean up
cur.execute("DROP TABLE IF EXISTS borr_staging;")
conn.commit()
print("Staging table dropped.")
conn.close()
