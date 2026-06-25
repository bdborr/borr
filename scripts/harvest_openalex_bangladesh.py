#!/usr/bin/env python3
"""Harvest Bangladesh-related papers from OpenAlex without downloading the snapshot.

This uses the filtered OpenAlex Works API with cursor pagination. It does NOT
store the 300+ GiB / 500+ GiB OpenAlex snapshot. It only receives matched
records and can stream them directly into Supabase.

Examples:
  # Count/test first, no database write
  python scripts/harvest_openalex_bangladesh.py --dry-run --max-records 1000

  # Save normalized rows locally for inspection
  python scripts/harvest_openalex_bangladesh.py --dry-run --max-records 1000 --jsonl-out data/openalex/filtered/borr_papers.preview.jsonl

  # Full database upsert, using NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
  python scripts/harvest_openalex_bangladesh.py --upsert
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import requests

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_USER_AGENT = "BORR-OpenAlex-Bangladesh-Harvester/1.0 (mailto:contact@borr.org.bd)"
CHECKPOINT_PATH = Path("data/openalex/checkpoints/bangladesh_openalex_api_checkpoint.json")

# These are API-side filters, so OpenAlex sends us only candidate Bangladesh records.
# This avoids downloading/scanning the whole snapshot locally.
DEFAULT_FILTERS = [
    # Papers with at least one Bangladesh-affiliated institution/author affiliation.
    "authorships.institutions.country_code:BD",
    # Papers about Bangladesh even if author affiliation is outside Bangladesh.
    "title_and_abstract.search:Bangladesh",
]

TYPE_MAPPING = {
    "article": "Journal Article",
    "review": "Review",
    "proceedings-article": "Conference",
    "posted-content": "Preprint",
    "dissertation": "Thesis",
    "book-chapter": "Book Chapter",
}

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


def normalized_filters(raw_filters: list[str]) -> list[str]:
    """Add cheap API-side quality filters to every OpenAlex query."""
    today = date.today().isoformat()
    normalized: list[str] = []
    for raw_filter in raw_filters:
        parts = [part.strip() for part in raw_filter.split(",") if part.strip()]
        keys = {part.split(":", 1)[0] for part in parts if ":" in part}
        if "is_retracted" not in keys:
            parts.append("is_retracted:false")
        if "to_publication_date" not in keys:
            parts.append(f"to_publication_date:{today}")
        normalized.append(",".join(parts))
    return normalized


def request_headers() -> dict[str, str]:
    return {"User-Agent": os.getenv("BORR_USER_AGENT", DEFAULT_USER_AGENT)}


def clean_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    doi = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    doi = doi.removeprefix("doi:").strip().lower()
    if not doi.startswith("10.") or "/" not in doi:
        return None
    return doi


def reconstruct_abstract(abstract_inverted_index: dict[str, list[int]] | None) -> str | None:
    if not abstract_inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, word_positions in abstract_inverted_index.items():
        for pos in word_positions:
            positions.append((int(pos), word))
    positions.sort()
    abstract = " ".join(word for _, word in positions).strip()
    return abstract or None


def unique_keep_order(values: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = " ".join(str(value).split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def extract_authors(work: dict[str, Any]) -> list[str]:
    return unique_keep_order(
        (authorship.get("author") or {}).get("display_name")
        for authorship in work.get("authorships") or []
    )


def extract_institutions(work: dict[str, Any]) -> list[str]:
    institutions: list[str | None] = []
    for authorship in work.get("authorships") or []:
        for inst in authorship.get("institutions") or []:
            institutions.append(inst.get("display_name"))
    return unique_keep_order(institutions)


def extract_fields(work: dict[str, Any]) -> list[str]:
    fields: list[str | None] = []
    primary_topic = work.get("primary_topic") or {}
    for key in ("domain", "field", "subfield"):
        item = primary_topic.get(key) or {}
        fields.append(item.get("display_name"))
    for topic in work.get("topics") or []:
        fields.append(topic.get("display_name"))
    # Legacy concepts still exist in many records; keep a few broad ones.
    for concept in work.get("concepts") or []:
        if int(concept.get("level") or 99) <= 1:
            fields.append(concept.get("display_name"))
    return unique_keep_order(fields)[:12]


def map_work_to_paper(work: dict[str, Any], *, require_doi: bool = True) -> dict[str, Any] | None:
    doi = clean_doi(work.get("doi"))
    if require_doi and not doi:
        return None

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    openalex_id = str(work.get("id") or "")
    fallback_url = f"https://doi.org/{doi}" if doi else openalex_id or None
    raw_type = str(work.get("type") or "other")
    paper_type = TYPE_MAPPING.get(raw_type, "Other")
    if paper_type not in ALLOWED_PAPER_TYPES:
        paper_type = "Other"

    oa = work.get("open_access") or {}
    if oa.get("is_oa"):
        access_type = "Open Access"
    elif primary_location.get("is_oa"):
        access_type = "Free"
    else:
        access_type = "Unknown"
    if access_type not in ALLOWED_ACCESS_TYPES:
        access_type = "Unknown"

    # Keep id deterministic for non-DOI previews. Supabase upsert still uses DOI by default.
    stable_key = doi or openalex_id or str(work.get("display_name") or work.get("title") or "")
    row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))

    return {
        "id": row_id,
        "openalex_id": openalex_id or None,
        "external_ids": {"openalex": openalex_id} if openalex_id else {},
        "sources": ["OpenAlex"],
        "last_harvested_at": date.today().isoformat(),
        "title": work.get("display_name") or work.get("title") or "Untitled",
        "authors": extract_authors(work),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "doi": doi,
        "url": primary_location.get("landing_page_url") or fallback_url,
        "journal": source.get("display_name"),
        "year": work.get("publication_year"),
        "institution": extract_institutions(work),
        "fields": extract_fields(work),
        "paper_type": paper_type,
        "access_type": access_type,
        "source": "OpenAlex",
        "verified": True,
        "citation_count": int(work.get("cited_by_count") or 0),
    }


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checkpoint, indent=2, sort_keys=True), encoding="utf-8")


def fetch_openalex_page(filter_query: str, cursor: str, per_page: int) -> dict[str, Any]:
    params = {
        "filter": filter_query,
        "cursor": cursor,
        "per-page": per_page,
        "sort": "publication_date:desc",
    }
    response = requests.get(OPENALEX_WORKS_URL, params=params, headers=request_headers(), timeout=60)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After") or "10")
        print(f"Rate limited. Sleeping {retry_after}s...", flush=True)
        time.sleep(retry_after)
        response = requests.get(OPENALEX_WORKS_URL, params=params, headers=request_headers(), timeout=60)
    response.raise_for_status()
    return response.json()


def upsert_supabase(rows: list[dict[str, Any]]) -> None:
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY before using --upsert")

    endpoint = f"{url.rstrip('/')}/rest/v1/papers?on_conflict=openalex_id"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    response = requests.post(endpoint, headers=headers, data=json.dumps(rows), timeout=60)
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"Supabase upsert failed: HTTP {response.status_code}: {response.text[:1000]}")


def chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def harvest(args: argparse.Namespace) -> int:
    filters = normalized_filters(args.filters or DEFAULT_FILTERS)
    checkpoint_path = Path(args.checkpoint)
    checkpoint = {} if args.no_resume else load_checkpoint(checkpoint_path)
    seen_doi: set[str] = set(checkpoint.get("seen_doi", []))
    total_fetched = int(checkpoint.get("total_fetched", 0))
    total_mapped = int(checkpoint.get("total_mapped", 0))
    total_upserted = int(checkpoint.get("total_upserted", 0))
    skipped_no_doi = int(checkpoint.get("skipped_no_doi", 0))

    jsonl_file = None
    if args.jsonl_out:
        out_path = Path(args.jsonl_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_file = out_path.open("a", encoding="utf-8")

    try:
        for filter_query in filters:
            filter_state = checkpoint.setdefault("filters", {}).setdefault(filter_query, {})
            cursor = "*" if args.no_resume else filter_state.get("cursor", "*")
            done = False if args.no_resume else bool(filter_state.get("done", False))
            if done:
                print(f"Skipping completed filter: {filter_query}")
                continue

            print(f"\n=== OpenAlex filter: {filter_query} ===", flush=True)
            while cursor:
                data = fetch_openalex_page(filter_query, cursor, args.per_page)
                results = data.get("results") or []
                meta = data.get("meta") or {}
                if not results:
                    filter_state["done"] = True
                    break

                rows: list[dict[str, Any]] = []
                for work in results:
                    total_fetched += 1
                    row = map_work_to_paper(work, require_doi=not args.include_no_doi)
                    if not row:
                        skipped_no_doi += 1
                        continue
                    doi = row.get("doi")
                    if doi and doi in seen_doi:
                        continue
                    if doi:
                        seen_doi.add(doi)
                    rows.append(row)

                total_mapped += len(rows)
                if jsonl_file:
                    for row in rows:
                        jsonl_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                    jsonl_file.flush()

                if args.upsert and rows:
                    upsert_rows = [row for row in rows if row.get("openalex_id")]
                    for batch in chunks(upsert_rows, args.batch_size):
                        upsert_supabase(batch)
                        total_upserted += len(batch)

                cursor = meta.get("next_cursor")
                filter_state["cursor"] = cursor
                checkpoint.update(
                    {
                        "seen_doi": sorted(seen_doi),
                        "total_fetched": total_fetched,
                        "total_mapped": total_mapped,
                        "total_upserted": total_upserted,
                        "skipped_no_doi": skipped_no_doi,
                    }
                )
                save_checkpoint(checkpoint_path, checkpoint)
                print(
                    f"fetched={total_fetched:,} mapped_unique={total_mapped:,} "
                    f"upserted={total_upserted:,} skipped_no_doi={skipped_no_doi:,} "
                    f"next_cursor={'yes' if cursor else 'no'}",
                    flush=True,
                )

                if args.max_records and total_fetched >= args.max_records:
                    print("Reached --max-records safety limit.")
                    return 0
                time.sleep(args.sleep)

            filter_state["done"] = True
            save_checkpoint(checkpoint_path, checkpoint)

    finally:
        if jsonl_file:
            jsonl_file.close()

    print(
        f"\nDone. fetched={total_fetched:,} mapped_unique={total_mapped:,} "
        f"upserted={total_upserted:,} skipped_no_doi={skipped_no_doi:,}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest Bangladesh OpenAlex papers into BORR schema")
    parser.add_argument("--filters", nargs="+", help="Override OpenAlex filter queries")
    parser.add_argument("--per-page", type=int, default=200, help="OpenAlex page size, max 200")
    parser.add_argument("--sleep", type=float, default=0.2, help="Polite delay between API calls")
    parser.add_argument("--max-records", type=int, default=0, help="Safety cap on fetched records; 0 means no cap")
    parser.add_argument("--checkpoint", default=str(CHECKPOINT_PATH), help="Resume checkpoint path")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing checkpoint and start over")
    parser.add_argument("--jsonl-out", help="Optional normalized BORR rows output path")
    parser.add_argument("--include-no-doi", action="store_true", help="Include no-DOI records in JSONL; database upsert still only uses DOI rows")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Supabase. This is the default unless --upsert is supplied.")
    parser.add_argument("--upsert", action="store_true", help="Upsert normalized DOI records directly into Supabase papers table")
    parser.add_argument("--batch-size", type=int, default=200, help="Supabase upsert batch size")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.per_page < 1 or args.per_page > 200:
        parser.error("--per-page must be between 1 and 200")
    if args.dry_run and args.upsert:
        parser.error("Choose either --dry-run or --upsert, not both")
    return harvest(args)


if __name__ == "__main__":
    raise SystemExit(main())
