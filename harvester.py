"""
BORR OpenAlex Harvester
======================
Downloads all papers with Bangladeshi institutional affiliation from OpenAlex
and outputs to CSV or directly upserts into Supabase/PostgreSQL.

Usage:
    python harvester.py                          # Dry run (count only)
    python harvester.py --download               # Download and save to CSV
    python harvester.py --download --format jsonl  # Save to JSONL instead
    python harvester.py --load-db                # Load CSV into database
    python harvester.py --download --load-db     # Download + load in one go

Requires: pip install requests psycopg2-binary
"""

import argparse
import csv
import gzip
import json
import logging
import os
import sys
import time
from datetime import datetime

import requests

# ─── Configuration ───────────────────────────────────────────────────────────

BATCH_SIZE = 200  # OpenAlex max per page
SLEEP_BETWEEN = 0.1  # seconds between requests (rate limit courtesy)
MAX_RETRIES = 5
RETRY_DELAY = 30  # seconds

# Database config — set via env vars or defaults
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/borr")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("borr-harvester")


# ─── API Fetching ────────────────────────────────────────────────────────────

def fetch_all_bd_papers(dry_run=False):
    """
    Paginate through OpenAlex API, collecting all papers with
    authorships.institutions.country_code:BD.

    Returns (total_count, papers_list_or_None).
    """
    url = "https://api.openalex.org/works"
    params = {
        "filter": "authorships.institutions.country_code:BD",
        "per_page": BATCH_SIZE,
        "cursor": "*",
        "select": "id,title,abstract_inverted_index,doi,authorships,primary_location,publication_year,type,cited_by_count,is_oa,open_access,locations,primary_topic,topics,concepts",
    }

    total_count = None
    papers = []
    cursor = "*"
    page = 0
    retries = 0

    while True:
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            retries += 1
            if retries >= MAX_RETRIES:
                log.error(f"Max retries hit after {page} pages: {e}")
                break
            log.warning(f"Request failed, retrying in {RETRY_DELAY}s: {e}")
            time.sleep(RETRY_DELAY)
            continue

        retries = 0

        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            log.warning(f"Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            log.error(f"API error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()

        if total_count is None:
            total_count = data.get("meta", {}).get("count", 0)
            log.info(f"Total Bangladeshi papers found: {total_count:,}")
            log.info(f"Estimated API calls: {(total_count // BATCH_SIZE) + 1}")
            if dry_run:
                return total_count, None

        results = data.get("results", [])
        if not results:
            break

        papers.extend(results)
        page += 1

        # Progress
        fetched = len(papers)
        pct = (fetched / total_count * 100) if total_count else 0
        log.info(f"Page {page}: fetched {fetched:,}/{total_count:,} ({pct:.1f}%)")

        # Cursor pagination
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            log.info("No more pages. Done.")
            break

        params["cursor"] = cursor
        time.sleep(SLEEP_BETWEEN)

    log.info(f"Download complete: {len(papers):,} papers")
    return total_count, papers


# ─── Data Transformation ────────────────────────────────────────────────────

def transform_paper(record):
    """
    Convert an OpenAlex work record to BORR schema format.
    """
    # Reconstruct abstract from inverted index
    abstract = reconstruct_abstract(record.get("abstract_inverted_index"))

    # Extract author names
    authors = []
    institutions = []
    for authorship in record.get("authorships", []):
        author_name = authorship.get("author", {}).get("display_name", "")
        if author_name:
            authors.append(author_name)
        for inst in authorship.get("institutions", []):
            inst_name = inst.get("display_name", "")
            if inst_name and inst_name not in institutions:
                institutions.append(inst_name)

    # Extract URL (prefer primary_location, fall back to DOI URL)
    url = None
    primary_location = record.get("primary_location", {})
    if primary_location and primary_location.get("landing_page_url"):
        url = primary_location["landing_page_url"]
    elif record.get("doi"):
        url = record["doi"]

    # Determine access type
    is_oa = record.get("is_oa", False)
    if is_oa:
        access_type = "Open Access"
    else:
        access_type = "Paywalled"

    # Map paper type
    type_map = {
        "journal-article": "Journal Article",
        "review-article": "Review",
        "proceedings-article": "Conference",
        "preprint": "Preprint",
        "dissertation": "Thesis",
        "book-chapter": "Book Chapter",
        "book": "Book Chapter",
        "dataset": "Journal Article",
        "other": "Journal Article",
    }
    paper_type = type_map.get(record.get("type", ""), "Journal Article")

    # Extract research fields from topics/concepts
    fields = []
    topics = record.get("topics", [])
    if topics:
        fields = [t.get("display_name", "") for t in topics[:5] if t.get("display_name")]
    else:
        concepts = record.get("concepts", [])
        fields = [c.get("display_name", "") for c in concepts[:5] if c.get("display_name")]

    # Journal name
    journal = None
    if primary_location and primary_location.get("source"):
        journal = primary_location["source"].get("display_name")

    return {
        "id": record.get("id", "").replace("https://openalex.org/", ""),
        "title": record.get("title") or "Untitled",
        "authors": authors,
        "abstract": abstract,
        "doi": record.get("doi", "").replace("https://doi.org/", "") if record.get("doi") else None,
        "url": url,
        "journal": journal,
        "year": record.get("publication_year"),
        "institution": institutions,
        "fields": fields,
        "paper_type": paper_type,
        "access_type": access_type,
        "source": "OpenAlex",
        "verified": False,
        "citation_count": record.get("cited_by_count", 0),
    }


def reconstruct_abstract(inverted_index):
    """
    Reconstruct abstract from OpenAlex inverted index format.
    """
    if not inverted_index:
        return None

    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))

    word_positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in word_positions)


# ─── Save to CSV or JSONL ───────────────────────────────────────────────────

CSV_FILE = "bangladeshi-papers.csv"
JSONL_FILE = "bangladeshi-papers.jsonl"

CSV_HEADERS = [
    "title", "authors", "abstract", "doi", "url", "journal",
    "year", "institution", "fields", "paper_type", "access_type",
    "source", "verified", "citation_count"
]
ARRAY_SEP = "|"  # Delimiter inside CSV array fields


def save_csv(papers, filepath):
    """Save transformed papers to CSV. Arrays use | as internal delimiter."""
    count = 0
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for paper in papers:
            transformed = transform_paper(paper)
            row = {}
            for key in CSV_HEADERS:
                val = transformed.get(key)
                if isinstance(val, list):
                    row[key] = ARRAY_SEP.join(str(v) for v in val if v)
                elif isinstance(val, bool):
                    row[key] = str(val).lower()
                else:
                    row[key] = val if val is not None else ""
            writer.writerow(row)
            count += 1
    log.info(f"Saved {count:,} papers to {filepath}")
    return count


def save_jsonl(papers, filepath):
    """Save transformed papers to a JSONL file."""
    count = 0
    with open(filepath, "w", encoding="utf-8") as f:
        for paper in papers:
            transformed = transform_paper(paper)
            f.write(json.dumps(transformed, ensure_ascii=False) + "\n")
            count += 1
    log.info(f"Saved {count:,} papers to {filepath}")
    return count


# ─── Database Loading ────────────────────────────────────────────────────────

def load_csv_to_db(csv_path, db_url):
    """
    Load CSV file into PostgreSQL.
    Arrays in CSV are split by ARRAY_SEP (|).
    """
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        log.error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    log.info(f"Connecting to database...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Create table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            openalex_id TEXT UNIQUE,
            title TEXT,
            authors TEXT[],
            abstract TEXT,
            doi TEXT UNIQUE,
            url TEXT,
            journal TEXT,
            year INTEGER,
            institution TEXT[],
            fields TEXT[],
            paper_type TEXT CHECK (paper_type IN ('Journal Article', 'Review', 'Conference', 'Preprint', 'Thesis', 'Book Chapter')),
            access_type TEXT CHECK (access_type IN ('Open Access', 'Free', 'Paywalled')),
            source TEXT CHECK (source IN ('OpenAlex', 'Crossref', 'Manual', 'Community', 'Institutional Feed')),
            verified BOOLEAN DEFAULT false,
            citation_count INTEGER DEFAULT 0,
            search_vector tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(abstract, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(array_to_string(authors, ' '), '')), 'C')
            ) STORED,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_papers_search ON papers USING GIN(search_vector);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);")
    conn.commit()

    # Read CSV and insert
    log.info(f"Loading {csv_path} into database...")
    count = 0
    batch = []
    batch_size = 500

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            import uuid
            doi = row.get("doi", "").strip() or None
            year_str = row.get("year", "").strip()
            year = int(year_str) if year_str and year_str.isdigit() else None
            citation_str = row.get("citation_count", "0").strip()
            citation_count = int(citation_str) if citation_str.isdigit() else 0

            # Generate deterministic UUID from DOI or title
            seed = doi if doi else row.get("title", "")
            row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, seed)) if seed else str(uuid.uuid4())

            batch.append((
                row_id,
                None,  # openalex_id (not in CSV)
                row.get("title", "").strip(),
                [v.strip() for v in row.get("authors", "").split(ARRAY_SEP) if v.strip()],
                row.get("abstract", "").strip() or None,
                doi,
                row.get("url", "").strip() or None,
                row.get("journal", "").strip() or None,
                year,
                [v.strip() for v in row.get("institution", "").split(ARRAY_SEP) if v.strip()],
                [v.strip() for v in row.get("fields", "").split(ARRAY_SEP) if v.strip()],
                row.get("paper_type", "Journal Article").strip(),
                row.get("access_type", "Paywalled").strip(),
                row.get("source", "OpenAlex").strip(),
                row.get("verified", "false").strip().lower() == "true",
                citation_count,
            ))

            if len(batch) >= batch_size:
                _upsert_batch(cur, batch)
                count += len(batch)
                log.info(f"Upserted {count:,} records...")
                batch = []
                conn.commit()

    if batch:
        _upsert_batch(cur, batch)
        count += len(batch)
        conn.commit()

    cur.execute("ANALYZE papers;")
    conn.commit()

    log.info(f"Database load complete: {count:,} papers")
    cur.close()
    conn.close()


def load_to_db(filepath, db_url):
    """
    Load JSONL file into PostgreSQL.

    Creates the papers table if it doesn't exist, then upserts records.
    """
    try:
        import psycopg2
        from psycopg2.extras import Json, execute_values
    except ImportError:
        log.error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    log.info(f"Connecting to database...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Create table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            openalex_id TEXT UNIQUE,
            title TEXT,
            authors TEXT[],
            abstract TEXT,
            doi TEXT UNIQUE,
            url TEXT,
            journal TEXT,
            year INTEGER,
            institution TEXT[],
            fields TEXT[],
            paper_type TEXT CHECK (paper_type IN ('Journal Article', 'Review', 'Conference', 'Preprint', 'Thesis', 'Book Chapter')),
            access_type TEXT CHECK (access_type IN ('Open Access', 'Free', 'Paywalled')),
            source TEXT CHECK (source IN ('OpenAlex', 'Crossref', 'Manual', 'Community', 'Institutional Feed')),
            verified BOOLEAN DEFAULT false,
            citation_count INTEGER DEFAULT 0,
            search_vector tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(abstract, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(array_to_string(authors, ' '), '')), 'C')
            ) STORED,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)

    # Create GIN index
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_papers_search ON papers USING GIN(search_vector);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
    """)

    conn.commit()

    # Load data
    log.info(f"Loading {filepath} into database...")
    count = 0
    batch = []
    batch_size = 500

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            paper = json.loads(line)

            # Generate UUID from openalex_id for deterministic IDs
            import uuid
            openalex_id = paper.get("id", "")
            row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://openalex.org/{openalex_id}"))

            batch.append((
                row_id,
                openalex_id,
                paper.get("title"),
                paper.get("authors", []),
                paper.get("abstract"),
                paper.get("doi") or None,
                paper.get("url"),
                paper.get("journal"),
                paper.get("year"),
                paper.get("institution", []),
                paper.get("fields", []),
                paper.get("paper_type", "Journal Article"),
                paper.get("access_type", "Paywalled"),
                "OpenAlex",
                False,
                paper.get("citation_count", 0),
            ))

            if len(batch) >= batch_size:
                _upsert_batch(cur, batch)
                count += len(batch)
                log.info(f"Upserted {count:,} records...")
                batch = []
                conn.commit()

    # Final batch
    if batch:
        _upsert_batch(cur, batch)
        count += len(batch)
        conn.commit()

    # Vacuum and analyze for search performance
    cur.execute("ANALYZE papers;")
    conn.commit()

    log.info(f"Database load complete: {count:,} papers")
    cur.close()
    conn.close()


def _upsert_batch(cur, batch):
    """Upsert a batch of papers. Handles openalex_id conflict (update) and existing DOI (skip)."""
    # First, remove records from this batch that have a DOI already in the DB
    # to avoid unique constraint violation on doi.
    dois_in_batch = [b[5] for b in batch if b[5]]  # doi is index 5
    if dois_in_batch:
        cur.execute(
            "SELECT doi FROM papers WHERE doi = ANY(%s)",
            (dois_in_batch,)
        )
        existing_dois = {row[0] for row in cur.fetchall()}
        batch = [b for b in batch if not (b[5] and b[5] in existing_dois)]

    if not batch:
        return

    execute_values(
        cur,
        """
        INSERT INTO papers (
            id, openalex_id, title, authors, abstract, doi, url, journal,
            year, institution, fields, paper_type, access_type, source,
            verified, citation_count
        ) VALUES %s
        ON CONFLICT (openalex_id) DO UPDATE SET
            title = EXCLUDED.title,
            authors = EXCLUDED.authors,
            abstract = COALESCE(EXCLUDED.abstract, papers.abstract),
            doi = COALESCE(EXCLUDED.doi, papers.doi),
            url = COALESCE(EXCLUDED.url, papers.url),
            journal = COALESCE(EXCLUDED.journal, papers.journal),
            year = COALESCE(EXCLUDED.year, papers.year),
            institution = EXCLUDED.institution,
            fields = EXCLUDED.fields,
            citation_count = EXCLUDED.citation_count,
            updated_at = now()
        """,
        batch,
    )


# ─── Bangladesh-Topic Papers (Secondary Harvest) ────────────────────────────

def fetch_bangladesh_topic_papers(existing_dois):
    """
    Secondary harvest: papers about Bangladesh (concept filter) that
    may not have a Bangladeshi institutional affiliation.
    """
    url = "https://api.openalex.org/works"
    params = {
        "filter": "concepts.display_name:Bangladesh",
        "per_page": BATCH_SIZE,
        "cursor": "*",
        "select": "id,title,abstract_inverted_index,doi,authorships,primary_location,publication_year,type,cited_by_count,is_oa,open_access,locations,primary_topic,topics,concepts",
    }

    papers = []
    page = 0
    retries = 0

    while True:
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException:
            retries += 1
            if retries >= MAX_RETRIES:
                break
            time.sleep(RETRY_DELAY)
            continue

        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", 60)))
            continue

        if resp.status_code != 200:
            break

        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        # Deduplicate against existing DOIs
        new_results = []
        for r in results:
            doi = r.get("doi", "").replace("https://doi.org/", "") if r.get("doi") else None
            if doi and doi not in existing_dois:
                new_results.append(r)

        papers.extend(new_results)
        page += 1
        log.info(f"Topic harvest page {page}: {len(papers):,} new papers (about Bangladesh)")

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break

        params["cursor"] = cursor
        time.sleep(SLEEP_BETWEEN)

    log.info(f"Topic harvest complete: {len(papers):,} additional papers")
    return papers


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BORR OpenAlex Harvester")
    parser.add_argument("--download", action="store_true", help="Download papers from OpenAlex API")
    parser.add_argument("--load-db", action="store_true", help="Load CSV/JSONL into PostgreSQL")
    parser.add_argument("--format", choices=["csv", "jsonl"], default="csv", help="Output format (default: csv)")
    parser.add_argument("--topic-harvest", action="store_true", help="Also harvest papers about Bangladesh")
    parser.add_argument("--db-url", type=str, default=None, help="PostgreSQL connection URL")
    args = parser.parse_args()

    db_url = args.db_url or DB_URL
    output_file = CSV_FILE if args.format == "csv" else JSONL_FILE

    if not args.download and not args.load_db:
        log.info("No action specified. Running dry run (count only)...")
        total, _ = fetch_all_bd_papers(dry_run=True)
        log.info(f"Estimated Bangladeshi papers available: {total:,}")
        log.info(f"Estimated CSV size: ~{total * 2 // 1000:,} KB")
        log.info("Run with --download to fetch, --load-db to insert into database.")
        return

    if args.download:
        log.info(f"Starting OpenAlex harvest for Bangladeshi papers (output: {args.format})...")
        total, papers = fetch_all_bd_papers(dry_run=False)

        if papers:
            if args.format == "csv":
                save_csv(papers, output_file)
            else:
                save_jsonl(papers, output_file)

            if args.topic_harvest:
                log.info("Starting secondary harvest (papers about Bangladesh)...")
                existing_dois = set()
                with open(output_file, "r", encoding="utf-8") as f:
                    if args.format == "csv":
                        reader = csv.DictReader(f)
                        for row in reader:
                            doi = row.get("doi", "").strip()
                            if doi:
                                existing_dois.add(doi)
                    else:
                        for line in f:
                            doi = json.loads(line).get("doi")
                            if doi:
                                existing_dois.add(doi)

                topic_papers = fetch_bangladesh_topic_papers(existing_dois)
                if topic_papers:
                    with open(output_file, "a", encoding="utf-8") as f:
                        if args.format == "csv":
                            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                            for paper in topic_papers:
                                transformed = transform_paper(paper)
                                row = {}
                                for key in CSV_HEADERS:
                                    val = transformed.get(key)
                                    if isinstance(val, list):
                                        row[key] = ARRAY_SEP.join(str(v) for v in val if v)
                                    elif isinstance(val, bool):
                                        row[key] = str(val).lower()
                                    else:
                                        row[key] = val if val is not None else ""
                                writer.writerow(row)
                        else:
                            for paper in topic_papers:
                                transformed = transform_paper(paper)
                                f.write(json.dumps(transformed, ensure_ascii=False) + "\n")
                    log.info(f"Appended {len(topic_papers):,} topic papers to {output_file}")

    if args.load_db:
        if not os.path.exists(output_file):
            log.error(f"{output_file} not found. Run with --download first.")
            sys.exit(1)
        if args.format == "csv":
            load_csv_to_db(output_file, db_url)
        else:
            load_to_db(output_file, db_url)


if __name__ == "__main__":
    main()
