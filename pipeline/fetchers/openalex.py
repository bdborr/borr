import os
import time
from typing import Any

import requests

OPENALEX_API_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = 30
USER_AGENT = "BORR-Harvester/1.0 (mailto:contact@borr.org.bd)"


def reconstruct_abstract(abstract_inverted_index: dict[str, list[int]] | None) -> str | None:
    if not abstract_inverted_index:
        return None
    word_pos: list[tuple[int, str]] = []
    for word, positions in abstract_inverted_index.items():
        for pos in positions:
            word_pos.append((pos, word))
    word_pos.sort()
    return " ".join(word for _, word in word_pos) or None


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    value = value.removeprefix("doi:").strip().lower()
    return value or None


def extract_institutions(work: dict[str, Any]) -> list[str]:
    institutions: set[str] = set()
    for authorship in work.get("authorships", []):
        for inst in authorship.get("institutions", []):
            name = inst.get("display_name")
            if name:
                institutions.add(name)
    return sorted(institutions)


def map_work(work: dict[str, Any]) -> dict[str, Any] | None:
    doi = clean_doi(work.get("doi"))
    if not doi:
        return None

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    url = primary_location.get("landing_page_url") or f"https://doi.org/{doi}"

    authors = []
    for auth in work.get("authorships", []):
        name = auth.get("author", {}).get("display_name")
        if name:
            authors.append(name)

    raw_type = work.get("type", "other")
    type_mapping = {
        "article": "Journal Article",
        "review": "Review",
        "proceedings-article": "Conference",
        "posted-content": "Preprint",
        "dissertation": "Thesis",
        "book-chapter": "Book Chapter",
    }

    fields = [c.get("display_name") for c in work.get("concepts", []) if c.get("display_name")][:5]
    is_oa = work.get("open_access", {}).get("is_oa", False)

    return {
        "doi": doi,
        "title": work.get("title") or "Untitled",
        "authors": authors,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "url": url,
        "journal": source.get("display_name"),
        "year": work.get("publication_year"),
        "institution": extract_institutions(work),
        "fields": fields,
        "paper_type": type_mapping.get(raw_type, "Other"),
        "access_type": "Open Access" if is_oa else "Unknown",
        "source": "OpenAlex",
        "verified": True,
        "citation_count": work.get("cited_by_count", 0),
    }


def fetch_openalex_papers(filter_query: str, max_pages: int = 10) -> list[dict[str, Any]]:
    papers: list[dict[str, Any]] = []
    headers = {"User-Agent": os.getenv("BORR_USER_AGENT", USER_AGENT)}

    for page in range(1, max_pages + 1):
        params = {
            "filter": filter_query,
            "per-page": 50,
            "page": page,
            "sort": "publication_date:desc",
        }

        try:
            response = requests.get(OPENALEX_API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise RuntimeError(f"OpenAlex API error for filter={filter_query!r} page={page}: {e}") from e

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            paper = map_work(work)
            if paper:
                papers.append(paper)

        time.sleep(0.5)

    return papers


def run_openalex_sync(max_pages: int = 10) -> list[dict[str, Any]]:
    print("Fetching OpenAlex: Bangladesh Institutions...")
    papers_inst = fetch_openalex_papers("authorships.institutions.country_code:BD", max_pages)

    print("Fetching OpenAlex: Bangladesh title/abstract...")
    papers_bangladesh = fetch_openalex_papers("title_and_abstract.search:Bangladesh", max_pages)

    merged: dict[str, dict[str, Any]] = {}
    for paper in papers_inst + papers_bangladesh:
        merged[paper["doi"]] = paper

    return list(merged.values())
