import psycopg2
import psycopg2.extras
import sqlite3
import json
import time

POSTGRES_URL = "postgresql://nehalhasnain@localhost:5432/borr_lean"
SQLITE_FILE = "borr.db"
BATCH_SIZE = 5000

def run_migration():
    print(f"Connecting to PostgreSQL at {POSTGRES_URL}")
    try:
        pg_conn = psycopg2.connect(POSTGRES_URL)
        # Use a named cursor (server-side) to prevent fetching all 440k rows into memory at once
        pg_cursor = pg_conn.cursor("migrator", cursor_factory=psycopg2.extras.DictCursor)
    except Exception as e:
        print(f"Failed to connect to Postgres: {e}")
        return

    print(f"Connecting to SQLite at {SQLITE_FILE}")
    sqlite_conn = sqlite3.connect(SQLITE_FILE)
    sqlite_conn.execute("PRAGMA journal_mode=WAL")
    sqlite_cursor = sqlite_conn.cursor()

    print("Creating SQLite schema...")
    with open("turso/schema.sql", "r") as f:
        schema_sql = f.read()
    sqlite_cursor.executescript(schema_sql)
    sqlite_conn.commit()

    print("Counting rows in PostgreSQL...")
    count_cursor = pg_conn.cursor()
    count_cursor.execute("SELECT count(*) FROM papers")
    total_rows = count_cursor.fetchone()[0]
    count_cursor.close()
    print(f"Found {total_rows} papers to migrate.")

    print("Starting migration...")
    pg_cursor.itersize = BATCH_SIZE
    pg_cursor.execute("SELECT * FROM papers")

    insert_sql = """
        INSERT OR IGNORE INTO papers (
            id, openalex_id, title, authors, abstract, doi, url, journal, year, 
            institution, fields, paper_type, access_type, source, verified, 
            citation_count, created_at, external_ids, sources, authors_text, institution_text
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """

    start_time = time.time()
    processed = 0

    while True:
        rows = pg_cursor.fetchmany(BATCH_SIZE)
        if not rows:
            break

        for row in rows:
            # Postgres TEXT[] -> Python list -> JSON string
            authors = row['authors'] or []
            fields = row['fields'] or []
            institution = row['institution'] or []
            # Postgres columns that don't exist in borr_lean
            sources = []
            
            # Postgres JSONB -> Python dict -> JSON string
            external_ids = {}
            
            # Timestamp conversion
            created_at = row['created_at'].isoformat() if row['created_at'] else None
            
            # Text for FTS and ILIKE
            authors_text = " ".join(authors)
            institution_text = " ".join(institution)
            
            # Verified boolean -> integer
            verified = 1 if row['verified'] else 0

            sqlite_cursor.execute(insert_sql, (
                str(row['id']),
                row['openalex_id'],
                row['title'],
                json.dumps(authors),
                row['abstract'],
                row['doi'],
                row['url'],
                row['journal'],
                row['year'],
                json.dumps(institution),
                json.dumps(fields),
                row['paper_type'] or 'Other',
                row['access_type'] or 'Unknown',
                row['source'] or 'Manual',
                verified,
                row['citation_count'] or 0,
                created_at,
                json.dumps(external_ids),
                json.dumps(sources),
                authors_text,
                institution_text
            ))
            processed += 1
            
        sqlite_conn.commit()
        
        if processed % 10000 == 0 or processed == total_rows:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"Migrated {processed}/{total_rows} papers ({rate:.0f} rows/sec)")

    print("Rebuilding FTS5 index (this may take a minute)...")
    sqlite_cursor.execute("INSERT INTO papers_fts(papers_fts) VALUES('rebuild')")
    sqlite_conn.commit()

    total_time = time.time() - start_time
    print(f"Migration completed in {total_time:.1f} seconds.")

    pg_cursor.close()
    pg_conn.close()
    sqlite_cursor.close()
    sqlite_conn.close()

if __name__ == "__main__":
    run_migration()
