#!/usr/bin/env python3
"""
BORR Incremental Monthly Harvester
==================================
Fetches new papers from OpenAlex since the last harvest date,
transforms to BORR schema, and upserts directly into Turso.

Key design:
- openalex_id is the canonical merge key (every paper has one)
- Two filters: Bangladesh institution affiliation + "Bangladesh" title/abstract
- Incremental via from_publication_date filter
- Checkpoint file stores last harvest date
- Direct Turso insert via shell pipe (proven reliable)

Usage:
    python scripts/harvest_incremental.py          # Normal run
    python scripts/harvest_incremental.py --dry-run # Count only, no DB write
    python scripts/harvest_incremental.py --since 2026-01-01  # Override date
    python scripts/harvest_incremental.py --max-pages 50       # Limit pages per filter

Authentication:
    Log in once with `~/.turso/turso auth login`. The scheduled job uses the
    Turso CLI credential store; it does not read Vercel's encrypted secrets.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ─── Configuration ────────────────────────────────────────────────────────

OPENALEX_API = "https://api.openalex.org/works"
PER_PAGE = 100  # 100 per page avoids OpenAlex 504 timeout on deep offsets
SLEEP_BETWEEN = 0.2  # courtesy delay between pages
MAX_RETRIES = 5
RETRY_DELAY = 10
REQUEST_TIMEOUT = 45
USER_AGENT = "BORR-Harvester/1.0 (mailto:bdborr@gmail.com)"

# Checkpoint file
CHECKPOINT_DIR = Path.home() / ".hermes" / "data"
CHECKPOINT_FILE = CHECKPOINT_DIR / "borr_last_harvest.txt"

# Turso CLI
TURSO_CLI = Path.home() / ".turso" / "turso"

# SQL temp file for batch insert
BATCH_SQL_FILE = "/tmp/borr_harvest_batch.sql"
BATCH_SIZE = 500  # rows per INSERT statement

# ─── Filters ────────────────────────────────────────────────────────────

FILTER_INSTITUTION = "authorships.institutions.country_code:BD"
FILTER_BANGLADESH = "title_and_abstract.search:Bangladesh"

# ─── Type mapping ────────────────────────────────────────────────────────

TYPE_MAP = {
    "article": "Journal Article",
    "review": "Review",
    "proceedings-article": "Conference",
    "posted-content": "Preprint",
    "dissertation": "Thesis",
    "book-chapter": "Book Chapter",
}


# ─── Helpers ─────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_checkpoint() -> date:
    """Load the last harvest date from checkpoint file."""
    if CHECKPOINT_FILE.exists():
        text = CHECKPOINT_FILE.read_text().strip()
        try:
            return date.fromisoformat(text)
        except ValueError:
            log(f"WARNING: Invalid checkpoint date '{text}', using 30 days ago")
    return date.today() - timedelta(days=30)


def save_checkpoint(d: date) -> None:
    """Save the harvest date checkpoint."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(d.isoformat())


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Reconstruct abstract from OpenAlex inverted index."""
    if not inverted_index:
        return None
    positions = []
    for word, pos_list in inverted_index.items():
        for p in pos_list:
            positions.append((p, word))
    positions.sort()
    result = " ".join(w for _, w in positions).strip()
    return result if result else None


def clean_doi(raw: str | None) -> str | None:
    """Normalize DOI string."""
    if not raw:
        return None
    val = raw.strip().replace("https://doi.org/", "").lower()
    return val or None


def generate_uuid(seed: str) -> str:
    """Generate deterministic UUID v5 from seed string."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def escape_sql(val: str) -> str:
    """Escape a string for SQL insertion."""
    return val.replace("'", "''")


# ─── OpenAlex API Fetch ────────────────────────────────────────────────

def fetch_papers(filter_str: str, since: date, max_pages: int | None = None) -> list[dict]:
    """
    Fetch papers from OpenAlex matching a filter, published on or after `since`.
    Uses cursor pagination if OPENALEX_API_KEY is provided; otherwise uses
    standard page-based pagination to avoid OpenAlex 401/504 errors on anonymous queries.
    """
    papers: list[dict] = []
    page = 1
    since_str = since.isoformat()
    filter_with_date = f"{filter_str},from_publication_date:{since_str}"

    api_key = os.environ.get("OPENALEX_API_KEY")
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    use_cursor = bool(api_key)
    cursor = "*" if use_cursor else None

    retries = 0

    while True:
        if max_pages and page > max_pages:
            log(f"  Reached max_pages={max_pages}, stopping")
            break

        params: dict = {
            "filter": filter_with_date,
            "per_page": PER_PAGE,
        }

        if use_cursor:
            params["cursor"] = cursor
            params["sort"] = "publication_date:desc"
        else:
            params["page"] = page
            # OpenAlex times out with 504 on anonymous requests when sorting by date on large filters.
            # Filtering by from_publication_date already restricts the set to the target period.

        try:
            resp = requests.get(
                OPENALEX_API,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                log(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code in (500, 502, 503, 504, 524):
                retries += 1
                if retries >= MAX_RETRIES:
                    log(f"  ERROR: Max retries exceeded on HTTP {resp.status_code}")
                    raise RuntimeError(f"OpenAlex fetch aborted on page {page} after {MAX_RETRIES} retries with HTTP {resp.status_code}")
                log(f"  Transient server error (HTTP {resp.status_code}), retrying {retries}/{MAX_RETRIES} in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
                continue

            if resp.status_code != 200:
                log(f"  ERROR: HTTP {resp.status_code}")
                log(f"  {resp.text[:300]}")
                raise RuntimeError(f"OpenAlex fetch aborted on page {page} with HTTP {resp.status_code}")

            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            retries += 1
            if retries >= MAX_RETRIES:
                log(f"  ERROR: Max retries exceeded: {e}")
                raise RuntimeError(f"OpenAlex fetch failed after {MAX_RETRIES} retries: {e}")
            log(f"  RETRY {retries}/{MAX_RETRIES} on network/JSON error: {e}")
            time.sleep(RETRY_DELAY)
            continue

        retries = 0
        results = data.get("results", [])

        if not results:
            log(f"  No more results")
            break

        papers.extend(results)

        total_available = data.get("meta", {}).get("count", 0)
        count = len(papers)
        log(f"  Page {page}: {count:,} papers collected (of ~{total_available:,} available)")

        if use_cursor:
            next_cursor = data.get("meta", {}).get("next_cursor")
            if not next_cursor:
                log(f"  No more cursors, done")
                break
            cursor = next_cursor
        else:
            if len(results) < PER_PAGE or count >= total_available:
                log(f"  All available results retrieved")
                break

        page += 1
        time.sleep(SLEEP_BETWEEN)

    return papers


# ─── Transform ────────────────────────────────────────────────────────────

def transform_work(work: dict) -> dict | None:
    """Convert an OpenAlex work to BORR Turso schema row."""
    openalex_id = work.get("id", "")
    if not openalex_id:
        return None

    # Short openalex_id (e.g., "W123456789")
    short_id = openalex_id.replace("https://openalex.org/", "")

    doi = clean_doi(work.get("doi"))

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    landing_url = primary_location.get("landing_page_url")

    # Authors
    authors = []
    for auth in work.get("authorships", []):
        name = (auth.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    # Institutions
    institutions = set()
    for auth in work.get("authorships", []):
        for inst in auth.get("institutions", []):
            n = inst.get("display_name")
            if n:
                institutions.add(n)

    # Fields (topics/concepts)
    fields = []
    for concept in (work.get("concepts") or [])[:5]:
        f = concept.get("display_name")
        if f:
            fields.append(f)

    # Paper type
    raw_type = work.get("type", "other")
    paper_type = TYPE_MAP.get(raw_type, "Other")

    # Open access
    oa_info = work.get("open_access") or {}
    is_oa = oa_info.get("is_oa", False)
    access_type = "Open Access" if is_oa else "Unknown"

    # Year
    year = work.get("publication_year")

    # Title
    title = work.get("title") or "Untitled"

    # Abstract
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    # URL
    url = landing_url or (f"https://doi.org/{doi}" if doi else None)

    # Journal
    journal = source.get("display_name")

    # Generate deterministic UUID
    row_id = generate_uuid(f"openalex:{short_id}")

    # JSON array fields
    authors_json = json.dumps(authors, ensure_ascii=False)
    institution_json = json.dumps(sorted(institutions), ensure_ascii=False)
    fields_json = json.dumps(fields, ensure_ascii=False)

    # Text fields for FTS
    authors_text = " ".join(authors)
    institution_text = " ".join(sorted(institutions))

    return {
        "id": row_id,
        "openalex_id": short_id,
        "title": title,
        "authors": authors_json,
        "abstract": abstract,
        "doi": doi,
        "url": url,
        "journal": journal,
        "year": year,
        "institution": institution_json,
        "fields": fields_json,
        "paper_type": paper_type,
        "access_type": access_type,
        "source": "OpenAlex",
        "verified": 1,
        "citation_count": work.get("cited_by_count", 0) or 0,
        "authors_text": authors_text,
        "institution_text": institution_text,
        "external_ids": json.dumps({"openalex": openalex_id}),
        "sources": json.dumps(["OpenAlex"]),
        "last_harvested_at": date.today().isoformat(),
    }


# ─── Turso Upsert ─────────────────────────────────────────────────────────

def sql_value(val) -> str:
    """Convert a Python value to a safe SQL literal."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, int):
        return str(val)
    # String: escape single quotes
    return "'" + str(val).replace("'", "''") + "'"


def check_turso_cli_auth() -> None:
    """Fail before harvesting when the Turso CLI cannot access the account."""
    if not TURSO_CLI.exists():
        raise RuntimeError(f"Turso CLI not found: {TURSO_CLI}")

    result = subprocess.run(
        [str(TURSO_CLI), "auth", "whoami"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    detail = (result.stderr or result.stdout).strip()
    if result.returncode != 0 or "not logged in" in detail.lower():
        raise RuntimeError(
            "Turso CLI is not authenticated. Run '~/.turso/turso auth login'. "
            f"Details: {detail[:300]}"
        )


def upsert_to_turso(rows: list[dict], turso_db: str = "borr-v2") -> int:
    """
    Batch upsert papers into Turso using INSERT OR IGNORE.
    Returns the number of rows submitted successfully. Existing openalex_id
    values are ignored by SQLite; paper_stats triggers count only real inserts.
    """
    if not rows:
        return 0

    columns = [
        "id", "openalex_id", "title", "authors", "abstract", "doi",
        "url", "journal", "year", "institution", "fields",
        "paper_type", "access_type", "source", "verified",
        "citation_count", "authors_text", "institution_text",
        "external_ids", "sources", "last_harvested_at",
    ]

    processed = 0
    batch_rows = []

    def run_batch(values: list[str]) -> None:
        nonlocal processed
        sql = (
            "INSERT OR IGNORE INTO papers ("
            + ", ".join(columns)
            + ") VALUES "
            + ",\n".join(values)
            + ";"
        )
        Path(BATCH_SQL_FILE).write_text(sql)
        command = (
            f"{shlex.quote(str(TURSO_CLI))} db shell {shlex.quote(turso_db)} "
            f"< {shlex.quote(BATCH_SQL_FILE)}"
        )
        result = subprocess.run(
            ["sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                f"Turso batch write failed (exit {result.returncode}): {detail[:500]}"
            )
        processed += len(values)

    try:
        for row in rows:
            vals = ", ".join(sql_value(row.get(col)) for col in columns)
            batch_rows.append(f"({vals})")

            if len(batch_rows) >= BATCH_SIZE:
                run_batch(batch_rows)
                batch_rows = []

        # Remaining batch
        if batch_rows:
            run_batch(batch_rows)
    finally:
        # Never leave harvested metadata in a predictable temporary SQL file.
        if Path(BATCH_SQL_FILE).exists():
            Path(BATCH_SQL_FILE).unlink()

    return processed


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="BORR Incremental Monthly Harvester — OpenAlex → Turso"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and transform but do not push to Turso")
    parser.add_argument("--since", type=str, default=None,
                        help="Override harvest start date (YYYY-MM-DD)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Max pages per filter (default: unlimited)")
    parser.add_argument("--turso-db", type=str, default="borr-v2",
                        help="Turso database name (default: borr-v2)")
    args = parser.parse_args()

    if not args.dry_run:
        check_turso_cli_auth()

    # Determine harvest start date
    if args.since:
        since = date.fromisoformat(args.since)
        log(f"Using override date: {since}")
    else:
        since = load_checkpoint()
        log(f"Last harvest date (from checkpoint): {since}")

    # For initial runs with a fresh checkpoint, we might want a shorter window
    days_since = (date.today() - since).days
    if days_since > 90 and not args.since:
        log(f"WARNING: Last harvest was {days_since} days ago.")
        log(f"This may pull a large number of papers.")
        log(f"Consider using --since to limit the window.")

    log(f"Fetching papers published since: {since}")

    # ── Fetch from both filters ──
    log("═" * 60)
    log("FILTER 1: Bangladesh institutional affiliation")
    log(f"  {FILTER_INSTITUTION}")
    papers_inst = fetch_papers(FILTER_INSTITUTION, since, args.max_pages)
    log(f"  Got {len(papers_inst):,} papers")

    log("")
    log("FILTER 2: 'Bangladesh' in title/abstract")
    log(f"  {FILTER_BANGLADESH}")
    papers_search = fetch_papers(FILTER_BANGLADESH, since, args.max_pages)
    log(f"  Got {len(papers_search):,} papers")

    # ── Deduplicate by openalex_id ──
    log("")
    log("═" * 60)
    log("DEDUPLICATING...")
    merged: dict[str, dict] = {}

    for work in papers_inst + papers_search:
        oa_id = work.get("id", "")
        if not oa_id:
            continue
        short_id = oa_id.replace("https://openalex.org/", "")
        if short_id not in merged:
            merged[short_id] = work

    log(f"  Unique papers after dedup: {len(merged):,}")
    log(f"  Overlap between filters: {len(papers_inst) + len(papers_search) - len(merged):,}")

    # ── Transform ──
    log("")
    log("TRANSFORMING to BORR schema...")
    rows = []
    transform_errors = 0
    for oa_id, work in merged.items():
        try:
            row = transform_work(work)
            if row:
                rows.append(row)
            else:
                transform_errors += 1
        except Exception as e:
            transform_errors += 1
            log(f"  ERROR transforming {oa_id}: {e}")

    log(f"  Transformed: {len(rows):,} papers")
    if transform_errors:
        log(f"  Transform errors: {transform_errors}")

    # ── Sample ──
    if rows:
        log("")
        log("SAMPLE (first 3):")
        for i, r in enumerate(rows[:3]):
            log(f"  {i+1}. [{r['year']}] {r['title'][:80]}...")
            log(f"     openalex:{r['openalex_id']}  doi:{r.get('doi')}")

    if args.dry_run:
        log("")
        log("═══ DRY RUN — not pushing to Turso ═══")
        log(f"Would push {len(rows):,} papers to {args.turso_db}")
        log(f"Source: OpenAlex, since {since}")
        return 0

    # ── Upsert to Turso ──
    if not rows:
        log("")
        log("No new papers to push. Database is up to date.")
        # Still save checkpoint
        save_checkpoint(date.today())
        return 0

    log("")
    log("═" * 60)
    log(f"UPSERTING {len(rows):,} papers into Turso ({args.turso_db})...")

    processed = upsert_to_turso(rows, args.turso_db)

    log("")
    log("═" * 60)
    log("RESULTS:")
    log(f"  Successfully submitted: {processed:,}")
    log("  Existing OpenAlex IDs were ignored automatically")
    log(f"  Total harvested: {len(rows):,}")

    # ── Save checkpoint ──
    save_checkpoint(date.today())
    log(f"  Checkpoint saved: {date.today()}")

    # ── Quick verification ──
    log("")
    log("Verifying Turso row count...")
    result = os.popen(
        f"echo 'SELECT SUM(total_count) FROM paper_stats;' | {TURSO_CLI} db shell {args.turso_db}"
    ).read()
    for line in result.strip().split("\n"):
        if line.strip().isdigit():
            log(f"  Turso papers total: {int(line):,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
