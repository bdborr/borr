#!/usr/bin/env python3
"""Upload normalized BORR JSONL(.gz) rows to Supabase.

Use this for the existing large OpenAlex backup, e.g.:

  python scripts/upsert_jsonl_to_supabase.py \
    data/openalex/local-test/borr_papers.harvested_403321.jsonl.gz \
    --checkpoint data/openalex/checkpoints/supabase_upload.json

Required env:
  NEXT_PUBLIC_SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY

The script upserts by openalex_id and keeps DOI nullable. If the production
Supabase schema still has a unique DOI constraint, duplicate DOI values are
nulled after the first occurrence so all OpenAlex records can still load.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests

ALLOWED_PAPER_TYPES = {
    "Journal Article",
    "Review",
    "Conference",
    "Preprint",
    "Thesis",
    "Book Chapter",
    "Other",
}
ALLOWED_ACCESS_TYPES = {"Open Access", "Free", "Paywalled", "Unknown"}
ALLOWED_SOURCES = {"OpenAlex", "PubMed", "Crossref", "Semantic Scholar", "arXiv", "DOAJ", "BASE", "Manual", "Community", "Institutional Feed"}


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def clean_doi(value: Any) -> str | None:
    if not value:
        return None
    doi = str(value).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    doi = doi.removeprefix("doi:").strip().lower()
    return doi if doi.startswith("10.") and "/" in doi else None


def as_list(value: Any, limit: int = 50) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            text = str(item.get("display_name") or item.get("name") or item.get("id") or "").strip()
        else:
            text = str(item).strip()
        text = " ".join(text.split())
        if text and text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) >= limit:
            break
    return out


def normalize_record(record: dict[str, Any], seen_doi: set[str], null_duplicate_doi: bool) -> dict[str, Any] | None:
    openalex_id = str(record.get("openalex_id") or record.get("id") or "").strip()
    if openalex_id.startswith("W"):
        openalex_id = f"https://openalex.org/{openalex_id}"
    if not openalex_id.startswith("https://openalex.org/"):
        return None

    title = str(record.get("title") or "").strip()
    if not title:
        return None

    doi = clean_doi(record.get("doi"))
    if doi and null_duplicate_doi:
        if doi in seen_doi:
            doi = None
        else:
            seen_doi.add(doi)

    paper_type = str(record.get("paper_type") or record.get("openalex_type") or "Other").strip() or "Other"
    if paper_type not in ALLOWED_PAPER_TYPES:
        paper_type = "Other"
    access_type = str(record.get("access_type") or "Unknown").strip() or "Unknown"
    if access_type not in ALLOWED_ACCESS_TYPES:
        access_type = "Unknown"
    source = str(record.get("source") or "OpenAlex").strip() or "OpenAlex"
    if source not in ALLOWED_SOURCES:
        source = "OpenAlex"

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

    external_ids = record.get("external_ids") if isinstance(record.get("external_ids"), dict) else {}
    external_ids = {**external_ids, "openalex": openalex_id}

    return {
        "id": record.get("id"),
        "openalex_id": openalex_id,
        "external_ids": external_ids,
        "sources": as_list(record.get("sources") or [source], limit=20),
        "last_harvested_at": record.get("harvested_at") or record.get("last_harvested_at"),
        "title": title,
        "authors": as_list(record.get("authors"), limit=50),
        "abstract": str(record.get("abstract") or "").strip() or None,
        "doi": doi,
        "url": record.get("url") or openalex_id,
        "journal": record.get("journal"),
        "year": year,
        "institution": as_list(record.get("institution") or record.get("institutions"), limit=50),
        "fields": as_list(record.get("fields"), limit=20),
        "paper_type": paper_type,
        "access_type": access_type,
        "source": source,
        "verified": bool(record.get("verified", True)),
        "citation_count": citation_count,
    }


def chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def load_checkpoint(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {"uploaded_lines": 0, "seen_doi": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path | None, uploaded_lines: int, seen_doi: set[str]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"uploaded_lines": uploaded_lines, "seen_doi": sorted(seen_doi)}, indent=2), encoding="utf-8")


def upsert_batch(rows: list[dict[str, Any]], retries: int = 4) -> None:
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")

    endpoint = f"{url.rstrip('/')}/rest/v1/papers?on_conflict=openalex_id"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    for attempt in range(1, retries + 1):
        response = requests.post(endpoint, headers=headers, data=json.dumps(rows), timeout=120)
        if response.status_code in (200, 201, 204):
            return
        if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            sleep = min(60, 2 ** attempt)
            print(f"Transient Supabase HTTP {response.status_code}; retrying in {sleep}s...", flush=True)
            time.sleep(sleep)
            continue
        raise RuntimeError(f"Supabase upsert failed: HTTP {response.status_code}: {response.text[:1000]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload BORR JSONL(.gz) into Supabase by openalex_id")
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--max-lines", type=int, default=0, help="Safety cap; 0 means all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-duplicate-doi", action="store_true", help="Do not null later duplicate DOI values")
    args = parser.parse_args()

    checkpoint = load_checkpoint(args.checkpoint)
    uploaded_lines = int(checkpoint.get("uploaded_lines", 0))
    start_line = uploaded_lines
    max_line = start_line + args.max_lines if args.max_lines else 0
    seen_doi = set(checkpoint.get("seen_doi", []))
    batch: list[dict[str, Any]] = []
    total_valid = 0
    total_skipped = 0

    last_line = uploaded_lines

    with open_text(args.jsonl) as handle:
        for line_no, line in enumerate(handle, 1):
            if line_no <= start_line:
                continue
            if max_line and line_no > max_line:
                break
            last_line = line_no
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                total_skipped += 1
                continue
            row = normalize_record(record, seen_doi, null_duplicate_doi=not args.keep_duplicate_doi)
            if row is None:
                total_skipped += 1
                continue
            batch.append(row)
            total_valid += 1
            if len(batch) >= args.batch_size:
                if args.dry_run:
                    print(f"DRY RUN would upsert batch ending at line {line_no:,} ({len(batch)} rows)")
                else:
                    upsert_batch(batch)
                uploaded_lines = line_no
                save_checkpoint(args.checkpoint, uploaded_lines, seen_doi)
                print(f"Uploaded/validated {total_valid:,} rows; skipped={total_skipped:,}; line={line_no:,}", flush=True)
                batch = []

    if batch:
        if args.dry_run:
            print(f"DRY RUN would upsert final batch ({len(batch)} rows)")
        else:
            upsert_batch(batch)
        uploaded_lines = last_line
        save_checkpoint(args.checkpoint, uploaded_lines, seen_doi)

    print(f"Done. valid={total_valid:,} skipped={total_skipped:,} resumed_from_line={start_line:,} stopped_at_line={uploaded_lines:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
