#!/usr/bin/env python3
"""Import normalized BORR/OpenAlex JSONL(.gz) into local PostgreSQL.

The importer uses openalex_id as the unique key and keeps DOI nullable. It is
intended for local testing with the large harvested VPS JSONL backup.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from psycopg2.extras import execute_values

DEFAULT_DB_URL = "postgresql://nehalhasnain@localhost:5432/borr_local"
BATCH_SIZE = 2_000


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def as_list(value: Any, *, key: str | None = None, limit: int | None = None) -> list[str]:
    if value is None:
        return []
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                if key:
                    text = str(item.get(key) or item.get("display_name") or item.get("name") or "").strip()
                else:
                    text = str(item.get("display_name") or item.get("name") or item.get("id") or "").strip()
            else:
                text = str(item).strip()
            if text and text not in out:
                out.append(text)
            if limit and len(out) >= limit:
                break
    elif isinstance(value, str):
        text = value.strip()
        if text:
            out.append(text)
    return out


def clean_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix) :]
            break
    doi = doi.removeprefix("doi:").strip().lower()
    return doi or None


def normalize_paper(record: dict[str, Any]) -> tuple[Any, ...] | None:
    openalex_id = str(record.get("openalex_id") or record.get("id") or "").strip()
    if not openalex_id:
        return None
    if openalex_id.startswith("W"):
        openalex_id = f"https://openalex.org/{openalex_id}"

    title = str(record.get("title") or "").strip()
    if not title:
        return None

    row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, openalex_id))
    authors = as_list(record.get("authors"), limit=50)
    institutions = as_list(record.get("institutions") or record.get("institution"), limit=50)
    fields = as_list(record.get("fields"), limit=20)

    year = record.get("year") or record.get("publication_year")
    try:
        year = int(year) if year is not None else None
    except (TypeError, ValueError):
        year = None

    citation_count = record.get("citation_count") or record.get("cited_by_count") or 0
    try:
        citation_count = int(citation_count or 0)
    except (TypeError, ValueError):
        citation_count = 0

    paper_type = str(record.get("paper_type") or record.get("openalex_type") or "Other").strip() or "Other"
    access_type = str(record.get("access_type") or "Unknown").strip() or "Unknown"
    source = str(record.get("source") or "OpenAlex").strip() or "OpenAlex"

    return (
        row_id,
        openalex_id,
        title,
        authors,
        str(record.get("abstract") or "").strip() or None,
        clean_doi(record.get("doi")),
        record.get("url") or openalex_id,
        record.get("journal"),
        year,
        institutions,
        fields,
        paper_type,
        access_type,
        source,
        True,
        citation_count,
    )


def iter_batches(path: Path, batch_size: int, skip_lines: int = 0) -> Iterable[list[tuple[Any, ...]]]:
    batch: list[tuple[Any, ...]] = []
    with open_text(path) as handle:
        for line_no, line in enumerate(handle, 1):
            if line_no <= skip_lines:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"WARN bad JSON line {line_no}: {exc}", file=sys.stderr)
                continue
            row = normalize_paper(record)
            if row is None:
                continue
            batch.append(row)
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def import_jsonl(path: Path, db_url: str, schema_path: Path | None, reset: bool, skip_lines: int = 0) -> None:
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if reset:
                if not schema_path:
                    raise ValueError("--reset requires --schema")
                print(f"Applying schema: {schema_path}")
                cur.execute(schema_path.read_text(encoding="utf-8"))
                conn.commit()

            sql = """
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
                    paper_type = EXCLUDED.paper_type,
                    access_type = EXCLUDED.access_type,
                    source = EXCLUDED.source,
                    verified = true,
                    citation_count = EXCLUDED.citation_count,
                    updated_at = timezone('utc'::text, now())
            """

            if skip_lines:
                print(f"Skipping first {skip_lines:,} JSONL lines before importing...")
            total = 0
            for batch in iter_batches(path, BATCH_SIZE, skip_lines=skip_lines):
                execute_values(cur, sql, batch, page_size=len(batch))
                total += len(batch)
                conn.commit()
                if total % 20_000 == 0:
                    print(f"Imported {total:,} rows...")
            print(f"Imported/updated {total:,} rows from {path}")

            print("Analyzing table...")
            cur.execute("ANALYZE papers")
            conn.commit()

            cur.execute(
                """
                SELECT
                  COUNT(*)::int,
                  COUNT(*) FILTER (WHERE abstract IS NOT NULL AND length(abstract) > 0)::int,
                  COUNT(*) FILTER (WHERE doi IS NULL)::int,
                  MIN(year),
                  MAX(year)
                FROM papers
                WHERE verified = true
                """
            )
            count, with_abstract, no_doi, min_year, max_year = cur.fetchone()
            print(f"Verified rows: {count:,}")
            print(f"Rows with abstract: {with_abstract:,}")
            print(f"Rows without DOI: {no_doi:,}")
            print(f"Year range: {min_year} - {max_year}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import BORR OpenAlex JSONL into local PostgreSQL")
    parser.add_argument("jsonl", type=Path, help="Path to .jsonl or .jsonl.gz file")
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL", DEFAULT_DB_URL))
    parser.add_argument("--schema", type=Path, default=Path(__file__).with_name("local_pg_schema.sql"))
    parser.add_argument("--reset", action="store_true", help="Drop/recreate local papers table before importing")
    parser.add_argument("--skip-lines", type=int, default=0, help="Skip this many JSONL lines before importing; useful for resuming a local test import")
    args = parser.parse_args()

    import_jsonl(args.jsonl, args.db_url, args.schema, args.reset, skip_lines=args.skip_lines)


if __name__ == "__main__":
    main()
