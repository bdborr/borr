#!/usr/bin/env python3
"""
BORR Dedup & Merge Tool
────────────────────────
Run on LOCAL machine after downloading VPS JSONL files.
Takes all source JSONL files, deduplicates by DOI, merges fields
(from higher-priority sources preserve their values for each field),
and outputs a clean combined JSONL ready for Supabase upload.

Usage:
  # Merge all VPS JSONL files into one combined file
  python scripts/borr_dedup_merge.py --input data/*/vps/*.jsonl.gz --output data/combined/borr_master.jsonl.gz

  # Merge and also show source breakdown
  python scripts/borr_dedup_merge.py --input data/*/vps/*.jsonl.gz --output data/combined/borr_master.jsonl.gz --stats

  # Upload merged file to Supabase
  python scripts/borr_dedup_merge.py --input data/combined/borr_master.jsonl.gz --upload
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

# Source priority: higher number = wins when merging conflicting fields
SOURCE_PRIORITY = {
    "OpenAlex": 3,
    "PubMed": 2,
    "Crossref": 1,
    "arXiv": 1,
    "DOAJ": 1,
}


def open_input(path: str | Path):
    """Open a file regardless of .gz or plain .jsonl."""
    p = Path(path)
    if p.suffix == ".gz":
        return gzip.open(p, "rt", encoding="utf-8")
    return p.open("rt", encoding="utf-8")


def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Iterate over JSONL lines from a file."""
    with open_input(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def meaningful(value: Any) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    if value == {}:
        return False
    return True


def merge_records(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge `new` into `existing`, keeping higher-quality values."""
    merged = dict(existing)

    # Combine source lists (deduped)
    existing_sources = set(merged.get("sources", []))
    new_sources = set(new.get("sources", []))
    merged["sources"] = sorted(existing_sources | new_sources)

    # Keep the last_harvested_at as the most recent
    existing_date = merged.get("last_harvested_at", "")
    new_date = new.get("last_harvested_at", "")
    if new_date and (not existing_date or new_date > existing_date):
        merged["last_harvested_at"] = new_date

    # External IDs accumulate
    existing_ids = merged.get("external_ids", {}) or {}
    new_ids = new.get("external_ids", {}) or {}
    merged["external_ids"] = {**existing_ids, **new_ids}

    # For each field: prefer the value from higher-priority source
    existing_prio = SOURCE_PRIORITY.get(merged.get("source", ""), 0)
    new_prio = SOURCE_PRIORITY.get(new.get("source", ""), 0)

    fields_to_merge = [
        "title", "abstract", "journal", "url", "paper_type", "access_type",
    ]
    for field in fields_to_merge:
        if new_prio >= existing_prio:
            if meaningful(new.get(field)) and not meaningful(merged.get(field)):
                merged[field] = new[field]
        if not meaningful(merged.get(field)) and meaningful(new.get(field)):
            merged[field] = new[field]

    # Authors: combine and deduplicate
    existing_authors = set(merged.get("authors", []))
    new_authors = set(new.get("authors", []))
    merged["authors"] = sorted(existing_authors | new_authors)

    # Institutions: combine and deduplicate
    existing_inst = set(merged.get("institution", []))
    new_inst = set(new.get("institution", []))
    merged["institution"] = sorted(existing_inst | new_inst)

    # Fields: combine and deduplicate (max 12)
    existing_fields = set(merged.get("fields", []))
    new_fields = set(new.get("fields", []))
    merged["fields"] = sorted(existing_fields | new_fields)[:12]

    # Citation count: max
    merged["citation_count"] = max(
        merged.get("citation_count", 0) or 0,
        new.get("citation_count", 0) or 0,
    )

    # Verified: any True makes it True
    merged["verified"] = bool(merged.get("verified")) or bool(new.get("verified"))

    # OpenAlex ID: if set (even if existing has it, prefer the non-None)
    merged["openalex_id"] = merged.get("openalex_id") or new.get("openalex_id")

    # Source label: keep the highest-priority source name
    if new_prio > existing_prio:
        merged["source"] = new["source"]

    return merged


def dedup_and_merge(input_paths: list[str], output_path: str | None = None,
                    stats: bool = False) -> tuple[list[dict[str, Any]], dict]:
    """Load all JSONL files, dedup by DOI, merge fields, return records."""
    by_doi: dict[str, dict[str, Any]] = {}
    source_counts: Counter = Counter()
    no_doi_count = 0

    for path in input_paths:
        p = Path(path)
        source_name = p.parent.parent.name if p.parent.parent.name != "vps" else "unknown"
        file_count = 0
        for row in iter_jsonl(path):
            doi = row.get("doi")
            if not doi:
                no_doi_count += 1
                continue

            if doi in by_doi:
                by_doi[doi] = merge_records(by_doi[doi], row)
            else:
                by_doi[doi] = row
            source_counts[source_name] += 1
            file_count += 1
        print(f"  {path}: {file_count:,} records")

    all_records = list(by_doi.values())

    if output_path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(out_path, "wt", encoding="utf-8") as f:
            for row in all_records:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(all_records):,} deduped records to {out_path}")

    if stats:
        print(f"\nSTATISTICS:")
        print(f"  Total input files:     {len(input_paths)}")
        print(f"  Total raw records:     {sum(source_counts.values()):,}")
        print(f"  No-DOI skipped:        {no_doi_count:,}")
        print(f"  Unique by DOI:         {len(all_records):,}")
        print(f"  Source breakdown (raw):")
        for src, cnt in source_counts.most_common():
            print(f"    {src}: {cnt:,}")
        print(f"  Final source breakdown:")
        final_sources = Counter(r.get("source") for r in all_records)
        for src, cnt in final_sources.most_common():
            print(f"    {src}: {cnt:,}")
        print(f"  With abstract: {sum(1 for r in all_records if r.get('abstract')):,}")
        print(f"  With journal:  {sum(1 for r in all_records if r.get('journal')):,}")
        print(f"  With year:     {sum(1 for r in all_records if r.get('year')):,}")
        print(f"  Multiple sources: {sum(1 for r in all_records if len(r.get('sources', [])) > 1):,}")

    return all_records, {"source_counts": dict(source_counts), "total_unique": len(all_records)}


def upload_supabase(records: list[dict[str, Any]], batch_size: int = 500) -> int:
    """Upload deduped records to Supabase papers table."""
    import requests

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")

    endpoint = f"{url.rstrip('/')}/rest/v1/papers?on_conflict=doi"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    total = len(records)
    uploaded = 0
    errors = 0

    for i in range(0, total, batch_size):
        batch = records[i : i + batch_size]
        try:
            resp = requests.post(endpoint, headers=headers,
                                data=json.dumps(batch), timeout=120)
            if resp.status_code not in (200, 201, 204):
                print(f"  HTTP {resp.status_code} on batch {i//batch_size + 1}: {resp.text[:200]}")
                errors += len(batch)
            else:
                uploaded += len(batch)
        except Exception as e:
            print(f"  Error on batch {i//batch_size + 1}: {e}")
            errors += len(batch)

        progress = (i + len(batch)) / total * 100
        print(f"  Upload: {uploaded:,}/{total:,} ({progress:.0f}%)", end="\r", flush=True)

    print()
    print(f"Upload complete: {uploaded:,} success, {errors:,} errors")
    return errors


def main():
    parser = argparse.ArgumentParser(description="BORR Dedup & Merge Tool")
    parser.add_argument("--input", nargs="+", required=True,
                        help="Input JSONL files or globs")
    parser.add_argument("--output", default=None,
                        help="Output merged JSONL.gz path")
    parser.add_argument("--stats", action="store_true",
                        help="Print detailed statistics")
    parser.add_argument("--upload", action="store_true",
                        help="Upload merged records to Supabase")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Supabase upsert batch size")
    args = parser.parse_args()

    # Expand globs
    from glob import glob
    expanded: list[str] = []
    for p in args.input:
        matches = glob(p, recursive=True)
        if matches:
            expanded.extend(sorted(matches))
        else:
            expanded.append(p)

    if not expanded:
        print("No input files found.")
        sys.exit(1)

    print(f"Merging {len(expanded)} files...")
    records, _ = dedup_and_merge(expanded, output_path=args.output, stats=args.stats)

    if args.upload:
        print(f"\nUploading {len(records):,} records to Supabase...")
        errors = upload_supabase(records, batch_size=args.batch_size)
        if errors:
            sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
