#!/usr/bin/env python3
"""
BORR VPS Multi-Source Harvester
────────────────────────────────
Runs on VPS overnight. Fetches from multiple sources incrementally
and saves to compressed JSONL files in data/<source>/vps/.
No database writes — just raw data collection.
Downloads to local machine later for dedup/merge/Supabase upload.

Usage:
  # Dry-run (show counts, no JSONL)
  python scripts/borr_vps_harvester.py --source openalex --dry-run --max-records 100

  # Harvest 500 papers from PubMed, save to JSONL
  python scripts/borr_vps_harvester.py --source pubmed --max-records 500

  # Harvest incremental OpenAlex (resume from latest)
  python scripts/borr_vps_harvester.py --source openalex --incremental

  # Full rotation: run all sources one after another (for cron)
  python scripts/borr_vps_harvester.py --rotate --max-records 500

  # Checkpoint-based resume per source
  python scripts/borr_vps_harvester.py --source crossref --resume
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHECKPOINT_DIR = BASE_DIR / "data" / "checkpoints"

SOURCE_CONFIGS: dict[str, dict[str, Any]] = {
    "openalex": {
        "name": "OpenAlex",
        "priority": 1,
        "base_delay": 0.2,
        "rate_limit_429": True,
    },
    "pubmed": {
        "name": "PubMed",
        "priority": 2,
        "base_delay": 0.4,
        "rate_limit_429": False,
    },
    "crossref": {
        "name": "Crossref",
        "priority": 3,
        "base_delay": 0.3,
        "rate_limit_429": True,
    },
    "arxiv": {
        "name": "arXiv",
        "priority": 4,
        "base_delay": 0.3,
        "rate_limit_429": False,
    },
    "doaj": {
        "name": "DOAJ",
        "priority": 5,
        "base_delay": 0.2,
        "rate_limit_429": False,
    },
}

# ─── CORE HELPERS ──────────────────────────────────

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


def stable_id(doi: str | None, openalex_id: str | None, title: str) -> str:
    key = doi or openalex_id or title
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def load_checkpoint(source: str) -> dict[str, Any]:
    path = CHECKPOINT_DIR / f"vps_{source}.json"
    if path.exists():
        return json.loads(path.read_text("utf-8"))
    return {}


def save_checkpoint(source: str, cp: dict[str, Any]) -> None:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    (CHECKPOINT_DIR / f"vps_{source}.json").write_text(
        json.dumps(cp, indent=2, sort_keys=True, default=str), "utf-8"
    )


def open_jsonl_out(source: str, append: bool = False):
    """Return (file_handle, path) to a gzipped JSONL output file dated by run."""
    out_dir = DATA_DIR / source / "vps"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"borr_{source}_{ts}.jsonl.gz"
    mode = "ab" if append else "wb"
    return gzip.open(out_path, mode), out_path


def write_row(gz: gzip.GzipFile, row: dict[str, Any]) -> None:
    gz.write((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))


def safe_request(url: str, params: dict | None = None,
                 headers: dict | None = None, timeout: int = 60) -> dict[str, Any]:
    """Make a request with retry-on-429 for sources that support it."""
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "10"))
                print(f"  429 rate limit, sleeping {retry_after}s...", flush=True)
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt+1}/3 after error: {e}", flush=True)
            time.sleep(2)
    return {}  # unreachable


def chunked(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ─── OPENALEX ──────────────────────────────────────

HARVEST_OPENALEX = "https://api.openalex.org/works"

def harvest_openalex(max_records: int = 0, incremental: bool = False,
                     resume: bool = False, dry_run: bool = False) -> int:
    cp = load_checkpoint("openalex") if resume else {}
    seen_doi: set[str] = set(cp.get("seen_doi", []))
    total = int(cp.get("total", 0))

    filters = [
        "authorships.institutions.country_code:BD,is_retracted:false",
        "title_and_abstract.search:Bangladesh,is_retracted:false",
    ]
    user_agent = os.getenv("BORR_USER_AGENT", "BORR-Harvester/1.0 (mailto:contact@borr.org.bd)")
    headers = {"User-Agent": user_agent}

    gz_file: gzip.GzipFile | None = None
    out_path: Path | None = None
    if not dry_run:
        gz_file, out_path = open_jsonl_out("openalex")

    try:
        for fq in filters:
            cursor = "*"
            while cursor:
                params = {
                    "filter": fq,
                    "cursor": cursor,
                    "per-page": 200,
                    "sort": "publication_date:desc",
                }
                data = safe_request(HARVEST_OPENALEX, params=params, headers=headers)
                results = data.get("results") or []
                meta = data.get("meta") or {}
                if not results:
                    break

                for work in results:
                    total += 1
                    doi = clean_doi(work.get("doi"))
                    if doi and doi in seen_doi:
                        continue
                    if doi:
                        seen_doi.add(doi)

                    row = _map_openalex_work(work)
                    if row and gz_file:
                        write_row(gz_file, row)

                    if max_records and total >= max_records:
                        break

                cursor = meta.get("next_cursor")
                print(f"  openalex: {total:,} records, cursor={'yes' if cursor else 'no'}", flush=True)

                if max_records and total >= max_records:
                    break
                time.sleep(0.2)
    finally:
        if gz_file:
            gz_file.close()

    cp["seen_doi"] = sorted(seen_doi)
    cp["total"] = total
    cp["last_run"] = datetime.now().isoformat()
    save_checkpoint("openalex", cp)
    print(f"OpenAlex: {total:,} records, file={out_path}" if out_path else f"OpenAlex: {total:,} records (dry-run)")
    return total


def _map_openalex_work(work: dict[str, Any]) -> dict[str, Any] | None:
    doi = clean_doi(work.get("doi"))
    openalex_id = str(work.get("id") or "")

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    landing = primary_location.get("landing_page_url")

    authors = []
    for auth in work.get("authorships") or []:
        name = (auth.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    institutions = set()
    for auth in work.get("authorships") or []:
        for inst in (auth.get("institutions") or []):
            n = inst.get("display_name")
            if n:
                institutions.add(n)

    fields = []
    for concept in (work.get("concepts") or [])[:5]:
        f = concept.get("display_name")
        if f:
            fields.append(f)

    return {
        "id": stable_id(doi, openalex_id, work.get("title", "")),
        "doi": doi,
        "openalex_id": openalex_id or None,
        "external_ids": {"openalex": openalex_id} if openalex_id else {},
        "sources": ["OpenAlex"],
        "last_harvested_at": date.today().isoformat(),
        "title": work.get("title") or "Untitled",
        "authors": authors,
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "url": landing or (f"https://doi.org/{doi}" if doi else None),
        "journal": source.get("display_name"),
        "year": work.get("publication_year"),
        "institution": sorted(institutions),
        "fields": fields,
        "paper_type": _map_type(work.get("type", "other")),
        "access_type": "Open Access" if (work.get("open_access") or {}).get("is_oa") else "Unknown",
        "source": "OpenAlex",
        "verified": True,
        "citation_count": int(work.get("cited_by_count") or 0),
    }


def _reconstruct_abstract(inv_idx: dict[str, list[int]] | None) -> str | None:
    if not inv_idx:
        return None
    pos = [(int(p), w) for w, pl in inv_idx.items() for p in pl]
    pos.sort()
    return " ".join(w for _, w in pos).strip() or None


TYPE_MAP = {
    "article": "Journal Article", "review": "Review",
    "proceedings-article": "Conference", "posted-content": "Preprint",
    "dissertation": "Thesis", "book-chapter": "Book Chapter",
}

def _map_type(raw: str) -> str:
    return TYPE_MAP.get(raw, "Other")


# ─── PUBMED ────────────────────────────────────────

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def harvest_pubmed(max_records: int = 500, resume: bool = False,
                   dry_run: bool = False, incremental: bool = False) -> int:
    email = os.getenv("NCBI_EMAIL", "contact@borr.org.bd")
    api_key = os.getenv("NCBI_API_KEY", "")
    query = "Bangladesh[Affiliation] OR Bangladesh[Title/Abstract]"

    cp = load_checkpoint("pubmed") if resume else {}
    seen_pmids = set(cp.get("seen_pmids", []))
    total = int(cp.get("total", 0))
    retstart = int(cp.get("retstart", 0))
    done = bool(cp.get("done", False))

    if done:
        if dry_run:
            print(f"PubMed: already done ({total:,} records)")
        return total

    common = {"tool": "BORR-Harvester", "email": email}
    if api_key:
        common["api_key"] = api_key

    # Search: get total count
    search_params = {
        **common, "db": "pubmed", "term": query,
        "retmode": "json", "retmax": 0, "retstart": 0,
    }
    search_resp = safe_request(PUBMED_SEARCH, params=search_params)
    total_count = int(search_resp.get("esearchresult", {}).get("count", 0))
    print(f"PubMed: {total_count:,} total results")

    retmax = min(500, max_records or total_count)
    if dry_run:
        print(f"PubMed: {total_count:,} total (dry-run, would fetch {retmax})")
        return retmax

    gz_file, out_path = open_jsonl_out("pubmed")
    try:
        while retstart < total_count and (not max_records or total < max_records):
            search_params = {
                **common, "db": "pubmed", "term": query,
                "retmode": "json", "retmax": retmax, "retstart": retstart,
                "sort": "date",
            }
            search_data = safe_request(PUBMED_SEARCH, params=search_params)
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                break

            # Filter out already-seen PMIDs
            new_ids = [pid for pid in id_list if pid not in seen_pmids]
            if not new_ids:
                retstart += len(id_list)
                continue

            # Fetch in smaller batches via POST to avoid 414 URI too long
            batch_size = 50
            for bstart in range(0, len(new_ids), batch_size):
                batch_ids = new_ids[bstart:bstart + batch_size]
                fetch_params = {
                    **common, "db": "pubmed", "id": ",".join(batch_ids), "retmode": "xml",
                }
                fetch_resp = requests.post(PUBMED_FETCH, data=fetch_params, timeout=90)
                if fetch_resp.status_code == 429:
                    time.sleep(10)
                    fetch_resp = requests.post(PUBMED_FETCH, data=fetch_params, timeout=90)
                fetch_resp.raise_for_status()
                import xml.etree.ElementTree as ET
                root = ET.fromstring(fetch_resp.content)

                for article in root.findall(".//PubmedArticle"):
                    pmid = _node_text(article.find(".//PMID"))
                    if not pmid or pmid in seen_pmids:
                        continue
                    seen_pmids.add(pmid)

                doi = None
                for aid in article.findall(".//ArticleId"):
                    if aid.get("IdType") == "doi":
                        doi = clean_doi(aid.text)
                        break

                if not doi:
                    continue  # skip no-DOI records for now

                title = _node_text(article.find(".//ArticleTitle")) or "Untitled"
                abstract_parts = [_node_text(n) for n in article.findall(".//AbstractText")]
                abstract = " ".join(p for p in abstract_parts if p) or None

                authors = []
                for an in article.findall(".//Author"):
                    ln = _node_text(an.find("LastName"))
                    fn = _node_text(an.find("ForeName"))
                    if ln and fn:
                        authors.append(f"{fn} {ln}")

                journal = _node_text(article.find(".//Journal/Title"))
                year_text = _node_text(article.find(".//PubDate/Year"))
                year = int(year_text) if year_text and year_text.isdigit() else None

                row = {
                    "id": stable_id(doi, None, title),
                    "doi": doi,
                    "openalex_id": None,
                    "external_ids": {"pmid": pmid, "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"},
                    "sources": ["PubMed"],
                    "last_harvested_at": date.today().isoformat(),
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "journal": journal,
                    "year": year,
                    "institution": [],
                    "fields": ["Medicine", "Health"],
                    "paper_type": "Journal Article",
                    "access_type": "Unknown",
                    "source": "PubMed",
                    "verified": False,
                    "citation_count": 0,
                }
                write_row(gz_file, row)
                total += 1

            retstart += len(id_list)
            cp["seen_pmids"] = sorted(seen_pmids)
            cp["retstart"] = retstart
            cp["total"] = total
            cp["last_run"] = datetime.now().isoformat()
            save_checkpoint("pubmed", cp)
            print(f"  pubmed: {total:,} records, {retstart}/{total_count}", flush=True)

            if max_records and total >= max_records:
                break
            time.sleep(0.4)

        if retstart >= total_count:
            cp["done"] = True
            save_checkpoint("pubmed", cp)

    finally:
        gz_file.close()

    print(f"PubMed: {total:,} records, file={out_path}")
    return total


def _node_text(node) -> str | None:
    if node is None:
        return None
    val = "".join(node.itertext()).strip()
    return val or None


# ─── CROSSREF ──────────────────────────────────────

CROSSREF_WORKS = "https://api.crossref.org/works"

def harvest_crossref(max_records: int = 500, resume: bool = False,
                     dry_run: bool = False, incremental: bool = False) -> int:
    cp = load_checkpoint("crossref") if resume else {}
    seen_doi = set(cp.get("seen_doi", []))
    total = int(cp.get("total", 0))
    cursor = cp.get("cursor", "*")

    query_params = {
        "query.affiliation": "Bangladesh",
        "filter": "type:journal-article,from-pub-date:2000-01-01",
        "rows": 100,
        "cursor": cursor,
        "sort": "published",
        "order": "desc",
    }
    headers = {
        "User-Agent": "BORR-Harvester/1.0 (mailto:contact@borr.org.bd)",
    }

    if dry_run:
        data = safe_request(CRossREF_WORKS, params={**query_params, "rows": 1}, headers=headers)
        total_res = data.get("message", {}).get("total-results", 0)
        print(f"Crossref: ~{total_res:,} total results (dry-run)")
        return min(max_records or total_res, total_res)

    gz_file, out_path = open_jsonl_out("crossref")
    try:
        max_iter = (max_records // 100) + 1 if max_records else 9999
        for _ in range(max_iter):
            data = safe_request(CROSSREF_WORKS, params=query_params, headers=headers)
            msg = data.get("message") or {}
            items = msg.get("items") or []
            if not items:
                break

            for item in items:
                doi = clean_doi(item.get("DOI"))
                if not doi or doi in seen_doi:
                    continue
                seen_doi.add(doi)

                authors = []
                for a in item.get("author") or []:
                    given = a.get("given", "")
                    family = a.get("family", "")
                    if given and family:
                        authors.append(f"{given} {family}")

                row = {
                    "id": stable_id(doi, None, item.get("title", [""])[0] or ""),
                    "doi": doi,
                    "openalex_id": None,
                    "external_ids": {"crossref": item.get("URL")},
                    "sources": ["Crossref"],
                    "last_harvested_at": date.today().isoformat(),
                    "title": (item.get("title") or ["Untitled"])[0],
                    "authors": authors,
                    "abstract": item.get("abstract") or None,
                    "url": item.get("URL") or f"https://doi.org/{doi}",
                    "journal": (item.get("container-title") or [None])[0],
                    "year": (item.get("published-print") or item.get("published-online") or {}).get("date-parts", [[None]])[0][0],
                    "institution": [],
                    "fields": (item.get("subject") or [])[:5],
                    "paper_type": "Journal Article",
                    "access_type": "Unknown",
                    "source": "Crossref",
                    "verified": False,
                    "citation_count": int(item.get("is-referenced-by-count") or 0),
                }
                write_row(gz_file, row)
                total += 1

            cursor = msg.get("next-cursor") or ""
            query_params["cursor"] = cursor
            cp["seen_doi"] = sorted(seen_doi)
            cp["cursor"] = cursor
            cp["total"] = total
            cp["last_run"] = datetime.now().isoformat()
            save_checkpoint("crossref", cp)
            print(f"  crossref: {total:,} records, cursor={'yes' if cursor else 'no'}", flush=True)

            if max_records and total >= max_records:
                break
            time.sleep(0.3)

    finally:
        gz_file.close()

    print(f"Crossref: {total:,} records, file={out_path}")
    return total


# ─── ARXIV ─────────────────────────────────────────

ARXIV_API = "http://export.arxiv.org/api/query"

def harvest_arxiv(max_records: int = 500, resume: bool = False,
                  dry_run: bool = False, incremental: bool = False) -> int:
    cp = load_checkpoint("arxiv") if resume else {}
    total = int(cp.get("total", 0))
    start = int(cp.get("start", 0))
    seen_ids = set(cp.get("seen_ids", []))

    query = "cat:q-bio*+AND+abs:Bangladesh"
    max_results = min(100, max_records or 1000)
    total_results = 0

    if dry_run:
        params = f"search_query={query}&start=0&max_results=1"
        resp = requests.get(f"{ARXIV_API}?{params}", timeout=30)
        if resp.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.content)
            ns = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
            total_el = root.find(".//o:totalResults", ns)
            if total_el is not None:
                total_results = int(total_el.text)
        print(f"arXiv: ~{total_results:,} total results (dry-run)")
        return min(max_records or total_results, total_results)

    import xml.etree.ElementTree as ET
    gz_file, out_path = open_jsonl_out("arxiv")
    try:
        while start < (max_records or 99999):
            params = f"search_query={query}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
            resp = requests.get(f"{ARXIV_API}?{params}", timeout=30)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"a": "http://www.w3.org/2005/Atom"}

            entries = root.findall("a:entry", ns)
            if not entries:
                break
            if total_results == 0:
                total_el = root.find(".//{http://a9.com/-/spec/opensearch/1.1/}totalResults")
                if total_el is not None:
                    total_results = int(total_el.text)

            for entry in entries:
                arxiv_id = entry.find("a:id", ns)
                if arxiv_id is not None:
                    aid = arxiv_id.text.strip()
                    if aid in seen_ids:
                        continue
                    seen_ids.add(aid)

                title = (entry.find("a:title", ns).text or "").strip().replace("\n", " ") or "Untitled"
                summary = (entry.find("a:summary", ns).text or "").strip().replace("\n", " ") or None

                authors = []
                for ael in entry.findall("a:author", ns):
                    name = ael.find("a:name", ns)
                    if name is not None:
                        authors.append(name.text)

                doi_link = None
                for link in entry.findall("a:link", ns):
                    if link.get("title") == "doi":
                        doi_link = link.get("href")
                        break
                doi = clean_doi(doi_link) if doi_link else None

                published = entry.find("a:published", ns)
                year = int(published.text[:4]) if published is not None else None

                row = {
                    "id": stable_id(doi, aid, title),
                    "doi": doi,
                    "openalex_id": None,
                    "external_ids": {"arxiv": aid},
                    "sources": ["arXiv"],
                    "last_harvested_at": date.today().isoformat(),
                    "title": title,
                    "authors": authors,
                    "abstract": summary,
                    "url": aid,
                    "journal": "arXiv",
                    "year": year,
                    "institution": [],
                    "fields": ["Quantitative Biology"],
                    "paper_type": "Preprint",
                    "access_type": "Open Access",
                    "source": "arXiv",
                    "verified": False,
                    "citation_count": 0,
                }
                write_row(gz_file, row)
                total += 1

            start += max_results
            cp["start"] = start
            cp["total"] = total
            cp["last_run"] = datetime.now().isoformat()
            cp["seen_ids"] = sorted(seen_ids)
            save_checkpoint("arxiv", cp)
            print(f"  arxiv: {total:,} records, start={start}", flush=True)

            if max_records and total >= max_records:
                break
            time.sleep(0.3)

    finally:
        gz_file.close()

    print(f"arXiv: {total:,} records, file={out_path}")
    return total


# ─── DOAJ ──────────────────────────────────────────

DOAJ_API = "https://doaj.org/api/v1/search/articles/everything"

def harvest_doaj(max_records: int = 500, resume: bool = False,
                 dry_run: bool = False, incremental: bool = False) -> int:
    cp = load_checkpoint("doaj") if resume else {}
    total = int(cp.get("total", 0))
    page = int(cp.get("page", 1))
    seen_ids = set(cp.get("seen_ids", []))

    query = "Bangladesh"
    page_size = 100

    if dry_run:
        params = {"query": query, "page": 1, "pageSize": 1}
        data = safe_request(DOAJ_API, params=params, headers={"User-Agent": "BORR-Harvester/1.0"})
        total_res = data.get("total", 0)
        print(f"DOAJ: ~{total_res:,} total results (dry-run)")
        return min(max_records or total_res, total_res)

    gz_file, out_path = open_jsonl_out("doaj")
    try:
        max_pages = (max_records // page_size) + 1 if max_records else 9999
        for _ in range(max_pages):
            params = {
                "query": query,
                "page": page,
                "pageSize": page_size,
                "sort": "last_updated",
                "order": "descending",
            }
            data = safe_request(DOAJ_API, params=params, headers={"User-Agent": "BORR-Harvester/1.0"})
            results = data.get("results") or []
            if not results:
                break
            total_res = data.get("total", 0)

            for r in results:
                bj = r.get("bibjson", {})
                # Extract DOI from identifier[] field (DOAJ v1)
                doi = clean_doi(bj.get("doi"))
                if not doi:
                    for ident in bj.get("identifier") or []:
                        if ident.get("type") == "doi":
                            doi = clean_doi(ident.get("id"))
                            break
                eid = r.get("id", "")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)

                if not doi:
                    # Use DOAJ ID as key (no-DOI records still useful)
                    pass

                authors = []
                for a in bj.get("author") or []:
                    name = a.get("name", "")
                    if name:
                        authors.append(name)

                doi_stable = doi or eid
                row = {
                    "id": stable_id(doi_stable, None, bj.get("title", "")),
                    "doi": doi,
                    "openalex_id": None,
                    "external_ids": {"doaj": eid},
                    "sources": ["DOAJ"],
                    "last_harvested_at": date.today().isoformat(),
                    "title": bj.get("title") or "Untitled",
                    "authors": authors,
                    "abstract": bj.get("abstract") or None,
                    "url": bj.get("link", [{}])[0].get("url") if bj.get("link") else None,
                    "journal": (bj.get("journal") or {}).get("title"),
                    "year": (bj.get("year") or bj.get("publication_date") or "")[:4] or None,
                    "institution": [],
                    "fields": (bj.get("subject", []))[:5] if isinstance(bj.get("subject"), list) else [],
                    "paper_type": "Journal Article",
                    "access_type": "Open Access",
                    "source": "DOAJ",
                    "verified": False,
                    "citation_count": 0,
                }
                write_row(gz_file, row)
                total += 1

            page += 1
            cp["page"] = page
            cp["total"] = total
            cp["last_run"] = datetime.now().isoformat()
            cp["seen_ids"] = sorted(seen_ids)
            save_checkpoint("doaj", cp)
            print(f"  doaj: {total:,} records, page={page}/{max(1, total_res//page_size)}", flush=True)

            if max_records and total >= max_records:
                break
            time.sleep(0.2)

    finally:
        gz_file.close()

    print(f"DOAJ: {total:,} records, file={out_path}")
    return total


# ─── ROTATION ──────────────────────────────────────

HARVESTERS: dict[str, Callable[..., int]] = {
    "openalex": harvest_openalex,
    "pubmed": harvest_pubmed,
    "crossref": harvest_crossref,
    "arxiv": harvest_arxiv,
    "doaj": harvest_doaj,
}

def rotate(max_records: int = 500, resume: bool = True) -> dict[str, int]:
    """Run all sources in priority order, one after another."""
    results: dict[str, int] = {}
    sorted_sources = sorted(SOURCE_CONFIGS.items(), key=lambda x: x[1]["priority"])
    for name, cfg in sorted_sources:
        print(f"\n{'='*60}")
        print(f"--- {cfg['name']} (priority {cfg['priority']}) ---")
        print(f"{'='*60}")
        try:
            count = HARVESTERS[name](max_records=max_records, resume=resume, dry_run=False)
            results[name] = count
        except Exception as e:
            print(f"ERROR harvesting {name}: {e}", flush=True)
            results[name] = -1
        print()
    return results


def list_harvested_files() -> list[Path]:
    """List all VPS-harvested JSONL files across sources."""
    files = []
    for source in SOURCE_CONFIGS:
        dir_path = DATA_DIR / source / "vps"
        if dir_path.exists():
            for f in sorted(dir_path.glob("*.jsonl.gz")):
                files.append(f)
    return files


# ─── CLI ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BORR VPS Multi-Source Harvester")
    parser.add_argument("--source", choices=[*HARVESTERS, "all"],
                        default="all", help="Source to harvest")
    parser.add_argument("--max-records", type=int, default=500,
                        help="Max records to fetch per source (0 = unlimited)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show counts only, no file output")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint (save/load seen IDs)")
    parser.add_argument("--rotate", action="store_true",
                        help="Run all sources in priority order")
    parser.add_argument("--incremental", action="store_true",
                        help="OpenAlex: fetch latest by date")
    parser.add_argument("--list-files", action="store_true",
                        help="List all harvested JSONL files")
    args = parser.parse_args()

    if args.list_files:
        files = list_harvested_files()
        if not files:
            print("No harvested files found.")
        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"{f}  ({size_mb:.1f} MB)")
        return

    if args.rotate or args.source == "all":
        results = rotate(max_records=args.max_records, resume=args.resume)
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        for name, count in results.items():
            cfg = SOURCE_CONFIGS.get(name, {})
            status = "OK" if count >= 0 else "ERROR"
            print(f"  {cfg.get('name', name):<15} {count:>6,} records  [{status}]")
        return

    if args.source in HARVESTERS:
        print(f"\n--- Harvesting {args.source} ---")
        count = HARVESTERS[args.source](
            max_records=args.max_records,
            resume=args.resume,
            dry_run=args.dry_run,
            incremental=args.incremental,
        )
        print(f"Done: {count:,} records")


if __name__ == "__main__":
    main()
