import os
import time
from typing import Any

import requests

# WARNING: This is the legacy harvester script for Supabase.
# The new Turso-compatible harvester is located at pipeline/main.py.
# This script is kept for reference only and should not be used in production.

try:
    from supabase import Client, create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    print("Warning: Supabase library not installed. Running in pure dry-run mode.")
    class Client:  # type: ignore[no-redef]
        pass

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
OPENALEX_API_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = 30
USER_AGENT = os.getenv("BORR_USER_AGENT", "BORR-Harvester/1.0 (mailto:contact@borr.org.bd)")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: Supabase credentials not found. Running in dry-run mode.")

supabase: Client | None = None
if HAS_SUPABASE and SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def reconstruct_abstract(abstract_inverted: dict[str, list[int]] | None) -> str | None:
    if not abstract_inverted:
        return None
    word_index: list[tuple[int, str]] = []
    for word, positions in abstract_inverted.items():
        for pos in positions:
            word_index.append((pos, word))
    word_index.sort()
    return " ".join(word for _, word in word_index) or None


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    value = value.removeprefix("doi:").strip().lower()
    return value or None


def map_work(work: dict[str, Any]) -> dict[str, Any] | None:
    doi = clean_doi(work.get("doi"))
    if not doi:
        return None

    authors = []
    institutions = set()
    for authorship in work.get("authorships", []):
        author_name = authorship.get("author", {}).get("display_name")
        if author_name:
            authors.append(author_name)
        for inst in authorship.get("institutions", []):
            inst_name = inst.get("display_name")
            if inst_name:
                institutions.add(inst_name)

    fields = [concept.get("display_name") for concept in work.get("concepts", []) if concept.get("level", 99) <= 1 and concept.get("display_name")]
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    raw_type = work.get("type", "other")
    type_mapping = {
        "article": "Journal Article",
        "review": "Review",
        "proceedings-article": "Conference",
        "posted-content": "Preprint",
        "dissertation": "Thesis",
        "book-chapter": "Book Chapter",
    }

    return {
        "title": work.get("title", "Untitled"),
        "authors": authors,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "doi": doi,
        "url": primary_location.get("landing_page_url") or f"https://doi.org/{doi}",
        "journal": source.get("display_name"),
        "year": work.get("publication_year"),
        "institution": sorted(institutions),
        "fields": fields,
        "paper_type": type_mapping.get(raw_type, "Other"),
        "access_type": "Open Access" if work.get("open_access", {}).get("is_oa", False) else "Unknown",
        "source": "OpenAlex",
        "verified": True,
        "citation_count": work.get("cited_by_count", 0),
    }


def harvest_papers(filter_query: str, max_pages: int = 5) -> int:
    cursor = "*"
    page = 1
    total_upserted = 0

    while page <= max_pages:
        print(f"Fetching page {page} for filter: {filter_query}")
        params = {"filter": filter_query, "per-page": 200, "cursor": cursor}
        headers = {"User-Agent": USER_AGENT}

        response = requests.get(OPENALEX_API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            raise RuntimeError(f"OpenAlex error for filter={filter_query!r}: {response.status_code} - {response.text[:500]}")

        data = response.json()
        results = data.get("results", [])
        if not results:
            print("No more results.")
            break

        papers_to_upsert = [paper for work in results if (paper := map_work(work))]

        if papers_to_upsert and supabase:
            try:
                supabase.table("papers").upsert(papers_to_upsert, on_conflict="doi").execute()
                print(f"Upserted {len(papers_to_upsert)} papers.")
                total_upserted += len(papers_to_upsert)
            except Exception as e:
                raise RuntimeError(f"Error during upsert: {e}") from e
        elif papers_to_upsert:
            print(f"Dry run: Would upsert {len(papers_to_upsert)} papers.")
            total_upserted += len(papers_to_upsert)

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break

        page += 1
        time.sleep(1)

    return total_upserted


if __name__ == "__main__":
    print("Starting BORR Harvester...")
    max_pages = int(os.getenv("HARVEST_MAX_PAGES", "50"))

    print("--- Harvesting based on BD Institutions ---")
    count1 = harvest_papers("authorships.institutions.country_code:BD", max_pages=max_pages)

    print("--- Harvesting based on Bangladesh title/abstract ---")
    count2 = harvest_papers("title_and_abstract.search:Bangladesh", max_pages=max_pages)

    print(f"Harvest complete. Total papers processed: {count1 + count2}")
