#!/usr/bin/env python3
"""
BORR VM + Local Merge Script
─────────────────────────────
Merges all data sources into a single deduplicated master JSONL:
  1. VM clean corpus (439k records, schema: institutions/countries/etc.)
  2. VPS multi-source files (PubMed, Crossref, DOAJ, arXiv)
  3. Local OpenAlex corpus (403k records, original schema)

Deduplicates by: openalex_id first, then DOI, then title+year hash.
Outputs a clean combined file ready for Supabase upload.

Usage:
  python scripts/merge_vm_local.py --stats
  python scripts/merge_vm_local.py --output data/combined/borr_master.jsonl.gz --stats
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Source priority for field conflict resolution
SOURCE_PRIORITY = {
    "OpenAlex": 4,
    "PubMed": 3,
    "Crossref": 2,
    "arXiv": 1,
    "DOAJ": 1,
    "Community": 0,
    "Manual": 0,
}

TYPE_MAP = {
    "article": "Journal Article",
    "review": "Review",
    "proceedings-article": "Conference",
    "posted-content": "Preprint",
    "dissertation": "Thesis",
    "book-chapter": "Book Chapter",
}


def open_input(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open_input(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def clean_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip()
    for prefix in (
        "https://doi.org/", "http://doi.org/",
        "http://dx.doi.org/", "https://dx.doi.org/",
        "doi:",
    ):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    doi = doi.strip().lower()
    if not doi.startswith("10.") or "/" not in doi:
        return None
    return doi


def title_year_hash(title: str, year: int | None) -> str | None:
    """Conservative dedup key for records without DOI or OpenAlex ID."""
    if not title or not year:
        return None
    normalized = " ".join(title.lower().split())
    return hashlib.sha256(f"{normalized}|{year}".encode()).hexdigest()[:32]


def normalize_vm_record(row: dict[str, Any]) -> dict[str, Any]:
    """Convert VM clean/normalized schema to local/Supabase schema."""
    doi = clean_doi(row.get("doi"))
    openalex_id = row.get("openalex_id") or None

    # Map paper_type
    paper_type = row.get("paper_type", "Other")
    if paper_type not in ("Journal Article", "Review", "Conference", "Preprint", "Thesis", "Book Chapter", "Other"):
        paper_type = TYPE_MAP.get(paper_type, "Other")

    # Map access_type
    access_type = row.get("access_type", "Unknown")
    if row.get("is_open_access") is True and access_type == "Unknown":
        access_type = "Open Access"

    return {
        "id": row.get("id", ""),
        "openalex_id": openalex_id,
        "doi": doi,
        "title": row.get("title", "Untitled"),
        "abstract": row.get("abstract"),
        "authors": row.get("authors") or [],
        "institution": row.get("institutions") or row.get("institution") or [],
        "journal": row.get("journal"),
        "year": row.get("year"),
        "fields": (row.get("fields") or [])[:12],
        "paper_type": paper_type,
        "access_type": access_type,
        "url": row.get("url"),
        "citation_count": int(row.get("citation_count") or 0),
        "source": row.get("source", "OpenAlex"),
        "sources": row.get("sources") or [row.get("source", "OpenAlex")],
        "external_ids": row.get("external_ids") or ({"openalex": openalex_id} if openalex_id else {}),
        "last_harvested_at": row.get("last_harvested_at") or row.get("harvested_at"),
        "verified": row.get("verified", True),
    }


def normalize_local_record(row: dict[str, Any]) -> dict[str, Any]:
    """Ensure local/original schema records have all fields."""
    doi = clean_doi(row.get("doi"))
    openalex_id = row.get("openalex_id") or None

    return {
        "id": row.get("id", ""),
        "openalex_id": openalex_id,
        "doi": doi,
        "title": row.get("title", "Untitled"),
        "abstract": row.get("abstract"),
        "authors": row.get("authors") or [],
        "institution": row.get("institution") or row.get("institutions") or [],
        "journal": row.get("journal"),
        "year": row.get("year"),
        "fields": (row.get("fields") or [])[:12],
        "paper_type": row.get("paper_type", "Other"),
        "access_type": row.get("access_type", "Unknown"),
        "url": row.get("url"),
        "citation_count": int(row.get("citation_count") or 0),
        "source": row.get("source", "OpenAlex"),
        "sources": row.get("sources") or [row.get("source", "OpenAlex")],
        "external_ids": row.get("external_ids") or ({"openalex": openalex_id} if openalex_id else {}),
        "last_harvested_at": row.get("last_harvested_at") or row.get("harvested_at"),
        "verified": row.get("verified", True),
    }


def normalize_vps_record(row: dict[str, Any]) -> dict[str, Any]:
    """VPS multi-source records already follow the local schema closely."""
    doi = clean_doi(row.get("doi"))
    return {
        "id": row.get("id", ""),
        "openalex_id": row.get("openalex_id"),
        "doi": doi,
        "title": row.get("title", "Untitled"),
        "abstract": row.get("abstract"),
        "authors": row.get("authors") or [],
        "institution": row.get("institution") or [],
        "journal": row.get("journal"),
        "year": row.get("year"),
        "fields": (row.get("fields") or [])[:12],
        "paper_type": row.get("paper_type", "Other"),
        "access_type": row.get("access_type", "Unknown"),
        "url": row.get("url"),
        "citation_count": int(row.get("citation_count") or 0),
        "source": row.get("source", "Manual"),
        "sources": row.get("sources") or [row.get("source", "Manual")],
        "external_ids": row.get("external_ids") or {},
        "last_harvested_at": row.get("last_harvested_at"),
        "verified": row.get("verified", False),
    }


def meaningful(value: Any) -> bool:
    if value is None:
        return False
    if value == "" or value == [] or value == {}:
        return False
    return True


def merge_into(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Merge new record into existing, keeping higher-quality values."""
    merged = dict(existing)

    # Combine sources
    merged["sources"] = sorted(set(merged.get("sources", [])) | set(new.get("sources", [])))

    # External IDs accumulate
    merged["external_ids"] = {**(merged.get("external_ids") or {}), **(new.get("external_ids") or {})}

    # Keep most recent harvest date
    new_date = new.get("last_harvested_at", "")
    old_date = merged.get("last_harvested_at", "")
    if new_date and (not old_date or new_date > old_date):
        merged["last_harvested_at"] = new_date

    # Field-level merge based on source priority
    old_prio = SOURCE_PRIORITY.get(merged.get("source", ""), 0)
    new_prio = SOURCE_PRIORITY.get(new.get("source", ""), 0)

    for field in ("title", "abstract", "journal", "url", "paper_type", "access_type"):
        # Always fill blanks; if both have values, prefer higher priority source
        if not meaningful(merged.get(field)) and meaningful(new.get(field)):
            merged[field] = new[field]
        elif meaningful(new.get(field)) and new_prio > old_prio:
            # Prefer longer abstract
            if field == "abstract" and meaningful(merged.get(field)):
                if len(str(new[field])) > len(str(merged[field])):
                    merged[field] = new[field]
            elif not meaningful(merged.get(field)):
                merged[field] = new[field]

    # Authors/institutions: combine and deduplicate
    merged["authors"] = sorted(set(merged.get("authors", [])) | set(new.get("authors", [])))
    merged["institution"] = sorted(set(merged.get("institution", [])) | set(new.get("institution", [])))
    merged["fields"] = sorted(set(merged.get("fields", [])) | set(new.get("fields", [])))[:12]

    # Citation count: max
    merged["citation_count"] = max(merged.get("citation_count", 0) or 0, new.get("citation_count", 0) or 0)

    # Verified: any True wins
    merged["verified"] = bool(merged.get("verified")) or bool(new.get("verified"))

    # OpenAlex ID: prefer non-None
    merged["openalex_id"] = merged.get("openalex_id") or new.get("openalex_id")

    # Source label: keep highest priority
    if new_prio > old_prio:
        merged["source"] = new["source"]

    return merged


def index_record(record: dict[str, Any],
                 by_openalex: dict[str, dict],
                 by_doi: dict[str, dict],
                 by_title_hash: dict[str, dict],
                 stats: Counter) -> None:
    """Index a single record into dedup maps, merging if duplicate found."""
    openalex_id = record.get("openalex_id")
    doi = record.get("doi")
    th = title_year_hash(record.get("title", ""), record.get("year"))

    # Check for existing record in priority order
    existing = None
    existing_key = None
    existing_map = None

    if openalex_id and openalex_id in by_openalex:
        existing = by_openalex[openalex_id]
        existing_key = openalex_id
        existing_map = "openalex"
    elif doi and doi in by_doi:
        existing = by_doi[doi]
        existing_key = doi
        existing_map = "doi"
    elif th and th in by_title_hash:
        existing = by_title_hash[th]
        existing_key = th
        existing_map = "title_hash"

    if existing:
        merged = merge_into(existing, record)
        # Update all maps to point to merged record
        if openalex_id:
            by_openalex[openalex_id] = merged
        if doi:
            by_doi[doi] = merged
        if th:
            by_title_hash[th] = merged
        # Also update the map where we found the original
        if existing_map == "openalex" and existing_key:
            by_openalex[existing_key] = merged
        elif existing_map == "doi" and existing_key:
            by_doi[existing_key] = merged
        elif existing_map == "title_hash" and existing_key:
            by_title_hash[existing_key] = merged
        stats["merged"] += 1
    else:
        # New record
        if openalex_id:
            by_openalex[openalex_id] = record
        if doi:
            by_doi[doi] = record
        if th:
            by_title_hash[th] = record
        stats["new"] += 1


def collect_unique(by_openalex: dict, by_doi: dict, by_title_hash: dict) -> list[dict]:
    """Collect unique records from all maps (they share references)."""
    seen_ids = set()
    unique = []
    for mapping in [by_openalex, by_doi, by_title_hash]:
        for record in mapping.values():
            rid = id(record)
            if rid not in seen_ids:
                seen_ids.add(rid)
                unique.append(record)
    return unique


def main():
    parser = argparse.ArgumentParser(description="BORR VM + Local Merge")
    parser.add_argument("--output", default=str(DATA_DIR / "combined" / "borr_master.jsonl.gz"),
                        help="Output merged JSONL.gz path")
    parser.add_argument("--stats", action="store_true", help="Print detailed statistics")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't write output")
    args = parser.parse_args()

    by_openalex: dict[str, dict] = {}
    by_doi: dict[str, dict] = {}
    by_title_hash: dict[str, dict] = {}
    stats = Counter()
    source_counts = Counter()

    # ── Step 1: Load VM clean corpus (439k) ──
    vm_clean = DATA_DIR / "vm-download" / "harvest" / "borr_papers.clean.jsonl.gz"
    if vm_clean.exists():
        print(f"Loading VM clean corpus: {vm_clean}")
        count = 0
        for row in iter_jsonl(vm_clean):
            record = normalize_vm_record(row)
            index_record(record, by_openalex, by_doi, by_title_hash, stats)
            count += 1
            if count % 50000 == 0:
                print(f"  ...{count:,} records loaded")
        source_counts["vm_clean"] = count
        print(f"  VM clean: {count:,} records loaded")
    else:
        print(f"  [SKIP] VM clean file not found: {vm_clean}")

    # ── Step 2: Load original local corpus (403k) ──
    local_file = DATA_DIR / "openalex" / "local-test" / "borr_papers.harvested_403321.jsonl.gz"
    if local_file.exists():
        print(f"\nLoading local OpenAlex corpus: {local_file}")
        count = 0
        for row in iter_jsonl(local_file):
            record = normalize_local_record(row)
            index_record(record, by_openalex, by_doi, by_title_hash, stats)
            count += 1
            if count % 50000 == 0:
                print(f"  ...{count:,} records loaded")
        source_counts["local_openalex"] = count
        print(f"  Local OpenAlex: {count:,} records loaded")
    else:
        print(f"  [SKIP] Local file not found: {local_file}")

    # ── Step 3: Load VPS multi-source files ──
    vps_dir = DATA_DIR / "vm-download" / "vps"
    if vps_dir.exists():
        print(f"\nLoading VPS multi-source files from: {vps_dir}")
        for source_dir in sorted(vps_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            source_name = source_dir.name
            count = 0
            for gz_file in sorted(source_dir.glob("*.jsonl.gz")):
                for row in iter_jsonl(gz_file):
                    record = normalize_vps_record(row)
                    index_record(record, by_openalex, by_doi, by_title_hash, stats)
                    count += 1
            source_counts[f"vps_{source_name}"] = count
            if count > 0:
                print(f"  VPS {source_name}: {count:,} records loaded")
    else:
        print(f"  [SKIP] VPS directory not found: {vps_dir}")

    # ── Step 4: Collect unique records ──
    print(f"\nDeduplicating...")
    all_records = collect_unique(by_openalex, by_doi, by_title_hash)
    print(f"  Total unique records: {len(all_records):,}")

    # ── Step 5: Write output ──
    if not args.dry_run:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nWriting merged output to: {out_path}")
        with gzip.open(out_path, "wt", encoding="utf-8") as f:
            for i, record in enumerate(all_records):
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                if (i + 1) % 50000 == 0:
                    print(f"  ...{i+1:,} records written")
        print(f"  Done: {len(all_records):,} records → {out_path}")
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  File size: {size_mb:.1f} MB")

    # ── Stats ──
    if args.stats or True:  # Always show summary
        print(f"\n{'='*60}")
        print(f"MERGE SUMMARY")
        print(f"{'='*60}")
        print(f"  Input sources:")
        for src, cnt in source_counts.most_common():
            print(f"    {src}: {cnt:,}")
        print(f"  Total raw records: {sum(source_counts.values()):,}")
        print(f"  New (unique):      {stats['new']:,}")
        print(f"  Merged (deduped):  {stats['merged']:,}")
        print(f"  Final unique:      {len(all_records):,}")

        # Breakdown by primary source
        final_sources = Counter(r.get("source") for r in all_records)
        print(f"\n  Final records by primary source:")
        for src, cnt in final_sources.most_common():
            print(f"    {src}: {cnt:,}")

        with_abstract = sum(1 for r in all_records if r.get("abstract"))
        with_doi = sum(1 for r in all_records if r.get("doi"))
        with_openalex = sum(1 for r in all_records if r.get("openalex_id"))
        multi_source = sum(1 for r in all_records if len(r.get("sources", [])) > 1)
        print(f"\n  With abstract:      {with_abstract:,}")
        print(f"  With DOI:           {with_doi:,}")
        print(f"  With OpenAlex ID:   {with_openalex:,}")
        print(f"  Multi-source:       {multi_source:,}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
