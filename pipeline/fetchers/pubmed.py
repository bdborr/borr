import os
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

REQUEST_TIMEOUT = 30
NCBI_TOOL = "BORR-Harvester"
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "contact@borr.org.bd")


def node_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def clean_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    value = doi.strip().replace("https://doi.org/", "").replace("http://dx.doi.org/", "")
    value = value.removeprefix("doi:").strip().lower()
    return value or None


def fetch_pubmed_papers(max_results: int = 100) -> list[dict[str, Any]]:
    base_esearch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    base_efetch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    query = "Bangladesh[Affiliation] OR Bangladesh[Title/Abstract]"

    common_params: dict[str, Any] = {
        "tool": NCBI_TOOL,
        "email": NCBI_EMAIL,
    }
    if os.getenv("NCBI_API_KEY"):
        common_params["api_key"] = os.environ["NCBI_API_KEY"]

    search_params = {
        **common_params,
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "date",
    }

    try:
        search_res = requests.get(base_esearch, params=search_params, timeout=REQUEST_TIMEOUT)
        search_res.raise_for_status()
        id_list = search_res.json().get("esearchresult", {}).get("idlist", [])
    except requests.RequestException as e:
        raise RuntimeError(f"PubMed eSearch error: {e}") from e

    if not id_list:
        return []

    time.sleep(0.34)

    fetch_params = {
        **common_params,
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml",
    }

    papers: list[dict[str, Any]] = []
    try:
        fetch_res = requests.get(base_efetch, params=fetch_params, timeout=REQUEST_TIMEOUT)
        fetch_res.raise_for_status()
        root = ET.fromstring(fetch_res.content)
    except (requests.RequestException, ET.ParseError) as e:
        raise RuntimeError(f"PubMed eFetch error: {e}") from e

    for article in root.findall(".//PubmedArticle"):
        doi = None
        for article_id in article.findall(".//ArticleId"):
            if article_id.get("IdType") == "doi":
                doi = clean_doi(article_id.text)
                break

        if not doi:
            continue

        title = node_text(article.find(".//ArticleTitle")) or "Untitled"
        abstract_parts = [node_text(n) for n in article.findall(".//AbstractText")]
        abstract = " ".join(part for part in abstract_parts if part) or None

        authors = []
        for author_node in article.findall(".//Author"):
            last_name = node_text(author_node.find("LastName"))
            fore_name = node_text(author_node.find("ForeName"))
            collective_name = node_text(author_node.find("CollectiveName"))
            if last_name and fore_name:
                authors.append(f"{fore_name} {last_name}")
            elif collective_name:
                authors.append(collective_name)

        journal = node_text(article.find(".//Journal/Title"))
        year_text = node_text(article.find(".//PubDate/Year"))
        year = int(year_text) if year_text and year_text.isdigit() else None
        pmid = node_text(article.find(".//PMID"))
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else f"https://doi.org/{doi}"

        papers.append({
            "doi": doi,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "journal": journal,
            "year": year,
            "institution": [],
            "fields": ["Medicine", "Health"],
            "paper_type": "Journal Article",
            "access_type": "Unknown",
            "source": "PubMed",
            "verified": False,
            "citation_count": 0,
        })

    return papers


def run_pubmed_sync(max_results: int = 100) -> list[dict[str, Any]]:
    print("Fetching PubMed...")
    return fetch_pubmed_papers(max_results)
