import argparse
import os
import sys
import json
import sqlite3
import uuid
from typing import Any

from fetchers.openalex import run_openalex_sync
from fetchers.pubmed import run_pubmed_sync

# For production, we would use libsql_experimental or HTTP API.
# For now, local sqlite3 works perfectly with Turso's local file mode.
# We expect TURSO_DATABASE_URL to be set, e.g. "file:borr.db"
def get_db_connection() -> sqlite3.Connection:
    url = os.environ.get("TURSO_DATABASE_URL")
    if not url:
        print("Error: TURSO_DATABASE_URL must be set (e.g. file:borr.db)")
        sys.exit(1)
    
    # Simple extraction for local testing
    if url.startswith("file:"):
        db_path = url[5:]
        return sqlite3.connect(db_path)
    else:
        # For remote Turso in production, we should ideally use libsql_experimental
        # Here we just raise an error indicating it needs that package
        raise NotImplementedError("For remote Turso connections, please install and use libsql_experimental.")


def meaningful(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if isinstance(value, list) and len(value) == 0:
        return False
    return True


def merge_paper_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    source_rank = {"OpenAlex": 3, "PubMed": 2, "Community": 1, "Manual": 1}

    for record in records:
        doi = record.get("doi")
        if not doi:
            continue

        if doi not in merged:
            merged[doi] = record.copy()
            continue

        current = merged[doi]
        for key, value in record.items():
            if key == "doi":
                continue
            if key == "citation_count":
                current[key] = max(current.get(key) or 0, value or 0)
                continue
            if key == "verified":
                current[key] = bool(current.get(key)) or bool(value)
                continue
            if key == "source":
                if source_rank.get(str(value), 0) > source_rank.get(str(current.get(key)), 0):
                    current[key] = value
                continue
            if not meaningful(current.get(key)) and meaningful(value):
                current[key] = value

    return list(merged.values())


def chunks(items: list[dict[str, Any]], size: int = 200):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def upsert_papers(db: sqlite3.Connection, papers: list[dict[str, Any]]) -> tuple[int, int]:
    if not papers:
        return 0, 0

    print(f"Attempting to upsert {len(papers)} papers into Turso/SQLite...")
    upserted_count = 0
    error_count = 0

    cursor = db.cursor()

    upsert_sql = """
        INSERT INTO papers (
            id, title, authors, abstract, doi, url, journal, year, 
            institution, fields, paper_type, access_type, source, 
            verified, citation_count, authors_text, institution_text
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(doi) DO UPDATE SET
            title = excluded.title,
            authors = excluded.authors,
            abstract = excluded.abstract,
            url = excluded.url,
            journal = excluded.journal,
            year = excluded.year,
            institution = excluded.institution,
            fields = excluded.fields,
            paper_type = excluded.paper_type,
            access_type = excluded.access_type,
            source = excluded.source,
            verified = excluded.verified,
            citation_count = excluded.citation_count,
            authors_text = excluded.authors_text,
            institution_text = excluded.institution_text,
            updated_at = CURRENT_TIMESTAMP
    """

    for batch in chunks(papers):
        try:
            db.execute("BEGIN TRANSACTION")
            for p in batch:
                authors_list = p.get("authors") or []
                institution_list = p.get("institution") or []
                fields_list = p.get("fields") or []
                
                authors_json = json.dumps(authors_list)
                institution_json = json.dumps(institution_list)
                fields_json = json.dumps(fields_list)
                
                authors_text = " ".join(authors_list)
                institution_text = " ".join(institution_list)
                
                # Default values for missing keys
                title = p.get("title", "Untitled")
                abstract = p.get("abstract")
                doi = p.get("doi")
                url = p.get("url")
                journal = p.get("journal")
                year = p.get("year")
                paper_type = p.get("paper_type", "Other")
                access_type = p.get("access_type", "Unknown")
                source = p.get("source", "Manual")
                verified = 1 if p.get("verified", False) else 0
                citation_count = p.get("citation_count", 0)

                cursor.execute(upsert_sql, (
                    str(uuid.uuid4()), # Generates a new UUID string for id
                    title,
                    authors_json,
                    abstract,
                    doi,
                    url,
                    journal,
                    year,
                    institution_json,
                    fields_json,
                    paper_type,
                    access_type,
                    source,
                    verified,
                    citation_count,
                    authors_text,
                    institution_text
                ))
            db.execute("COMMIT")
            upserted_count += len(batch)
        except Exception as e:
            db.execute("ROLLBACK")
            print(f"Error upserting batch containing {len(batch)} papers: {e}")
            error_count += len(batch)

    print(f"Upsert complete. Success: {upserted_count}, Errors: {error_count}")
    return upserted_count, error_count


def main():
    parser = argparse.ArgumentParser(description="BORR Automated Data Sync Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Fetch data but do not write to Database")
    parser.add_argument("--openalex-pages", type=int, default=None, help="Override OpenAlex page count")
    parser.add_argument("--pubmed-results", type=int, default=None, help="Override PubMed result count")
    args = parser.parse_args()

    print("Starting BORR Automated Data Sync Pipeline...")
    db = None if args.dry_run else get_db_connection()
    if args.dry_run:
        print("DRY RUN MODE: Data will be fetched but not inserted into the database.")

    openalex_pages = args.openalex_pages if args.openalex_pages is not None else (2 if args.dry_run else 5)
    pubmed_results = args.pubmed_results if args.pubmed_results is not None else (20 if args.dry_run else 100)

    print("\n--- Phase 1: OpenAlex ---")
    openalex_papers = run_openalex_sync(max_pages=openalex_pages)
    print(f"Found {len(openalex_papers)} unique papers from OpenAlex.")

    print("\n--- Phase 2: PubMed ---")
    pubmed_papers = run_pubmed_sync(max_results=pubmed_results)
    print(f"Found {len(pubmed_papers)} unique papers from PubMed.")

    merged_papers = merge_paper_records(openalex_papers + pubmed_papers)
    print(f"Prepared {len(merged_papers)} unique merged papers for {'inspection' if args.dry_run else 'upsert'}.")

    if not args.dry_run and db:
        _, errors = upsert_papers(db, merged_papers)
        db.close()
        if errors:
            raise RuntimeError(f"{errors} database upserts failed")

    print("\nPipeline execution finished successfully.")


if __name__ == "__main__":
    main()
