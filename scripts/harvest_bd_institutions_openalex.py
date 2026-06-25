#!/usr/bin/env python3
"""Harvest Bangladesh institution metadata from OpenAlex and dedupe against a supplied HTML list.

Inputs:
  - Google Sheets-style HTML table with columns: SL, University, Website

Outputs:
  - supplied_list_openalex_enriched.csv/jsonl
  - openalex_bd_institutions_all.csv/jsonl
  - openalex_new_not_in_supplied_list.csv
  - duplicate_report.csv
  - summary.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

OPENALEX_INSTITUTIONS = "https://api.openalex.org/institutions"
DEFAULT_MAILTO = "nehalhasnain@gmail.com"

STOP_CHARS = re.compile(r"[^a-z0-9]+")
PAREN_RE = re.compile(r"\(([^)]+)\)")


def norm_domain(value: str | None) -> str:
    if not value:
        return ""
    v = value.strip()
    if not v:
        return ""
    if not re.match(r"https?://", v, flags=re.I):
        v = "https://" + v
    host = urlparse(v).netloc.lower()
    host = host.split("@")[(-1)].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip("/")


def normalize_name(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower().strip()
    s = s.replace("&", " and ")
    s = s.replace("’", "'")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = STOP_CHARS.sub(" ", s)
    words = [w for w in s.split() if w]
    # Keep meaningful words; only remove very generic legal suffixes/noise.
    remove = {"the", "of", "for", "and", "in", "at", "bd", "bangladesh"}
    words = [w for w in words if w not in remove]
    return " ".join(words)


def token_sort(s: str | None) -> str:
    return " ".join(sorted(normalize_name(s).split()))


def ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def acronyms_from_name(name: str) -> set[str]:
    out: set[str] = set()
    if not name:
        return out
    for m in PAREN_RE.finditer(name):
        token = re.sub(r"[^A-Za-z0-9]", "", m.group(1)).upper()
        if 2 <= len(token) <= 12:
            out.add(token)
    words = re.findall(r"[A-Za-z]+", name)
    ignore = {"and", "of", "the", "for", "in", "at"}
    ac = "".join(w[0].upper() for w in words if w.lower() not in ignore)
    if 2 <= len(ac) <= 12:
        out.add(ac)
    return out


def parse_html_list(path: Path) -> list[dict[str, Any]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    rows: list[dict[str, Any]] = []
    for tr in soup.select("tbody tr"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all("td")]
        if not any(cells):
            continue
        if len(cells) < 3:
            cells += [""] * (3 - len(cells))
        sl, name, website = cells[0], cells[1], cells[2]
        if name.strip().lower() in {"university", "institute", "institution"} or name.strip().lower() == "university":
            continue
        if name.strip().upper() == "SL":
            continue
        if not name.strip():
            continue
        rows.append({
            "source_row": len(rows) + 1,
            "sl": sl,
            "list_name": name.strip().rstrip("."),
            "list_website": website.strip(),
            "list_domain": norm_domain(website),
            "list_acronyms": sorted(acronyms_from_name(name)),
            "list_norm": normalize_name(name),
            "list_token_sort": token_sort(name),
        })
    return rows


def openalex_get(params: dict[str, Any], max_attempts: int = 5) -> dict[str, Any]:
    headers = {"User-Agent": f"BORR-Harvester/1.0 (mailto:{DEFAULT_MAILTO})"}
    for attempt in range(max_attempts):
        try:
            resp = requests.get(OPENALEX_INSTITUTIONS, params=params, headers=headers, timeout=60)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", "10"))
                print(f"OpenAlex 429, sleeping {wait}s", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            print(f"OpenAlex retry {attempt + 1}/{max_attempts} after error: {e}", flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def harvest_openalex_bd() -> list[dict[str, Any]]:
    cursor = "*"
    all_rows: list[dict[str, Any]] = []
    page = 0
    while cursor:
        params = {
            "filter": "country_code:BD",
            "per-page": 200,
            "cursor": cursor,
            "mailto": DEFAULT_MAILTO,
            "select": ",".join([
                "id", "ror", "display_name", "display_name_acronyms", "display_name_alternatives",
                "country_code", "type", "homepage_url", "image_url", "image_thumbnail_url",
                "works_count", "cited_by_count", "summary_stats", "ids", "geo",
                "associated_institutions", "counts_by_year", "updated_date", "created_date",
            ]),
        }
        data = openalex_get(params)
        results = data.get("results") or []
        all_rows.extend(results)
        page += 1
        meta = data.get("meta") or {}
        cursor = meta.get("next_cursor")
        print(f"OpenAlex page {page}: +{len(results)} institutions, total={len(all_rows)}", flush=True)
        if not cursor or not results:
            break
        time.sleep(0.12)
    return all_rows


def flatten_openalex(inst: dict[str, Any]) -> dict[str, Any]:
    geo = inst.get("geo") or {}
    ids = inst.get("ids") or {}
    stats = inst.get("summary_stats") or {}
    acronyms = inst.get("display_name_acronyms") or []
    alts = inst.get("display_name_alternatives") or []
    assoc = inst.get("associated_institutions") or []
    return {
        "openalex_id": inst.get("id") or "",
        "ror": inst.get("ror") or ids.get("ror") or "",
        "display_name": inst.get("display_name") or "",
        "display_name_acronyms": "; ".join(acronyms),
        "display_name_alternatives": "; ".join(alts[:20]),
        "country_code": inst.get("country_code") or "",
        "type": inst.get("type") or "",
        "homepage_url": inst.get("homepage_url") or "",
        "homepage_domain": norm_domain(inst.get("homepage_url")),
        "works_count": inst.get("works_count") or 0,
        "cited_by_count": inst.get("cited_by_count") or 0,
        "h_index": stats.get("h_index") or "",
        "i10_index": stats.get("i10_index") or "",
        "2yr_mean_citedness": stats.get("2yr_mean_citedness") or "",
        "city": geo.get("city") or "",
        "region": geo.get("region") or "",
        "country": geo.get("country") or "",
        "latitude": geo.get("latitude") or "",
        "longitude": geo.get("longitude") or "",
        "wikipedia": ids.get("wikipedia") or "",
        "wikidata": ids.get("wikidata") or "",
        "mag": ids.get("mag") or "",
        "associated_institution_ids": "; ".join([a.get("id", "") for a in assoc[:20] if a.get("id")]),
        "associated_institution_names": "; ".join([a.get("display_name", "") for a in assoc[:20] if a.get("display_name")]),
        "updated_date": inst.get("updated_date") or "",
        "created_date": inst.get("created_date") or "",
        "openalex_norm": normalize_name(inst.get("display_name")),
        "openalex_token_sort": token_sort(inst.get("display_name")),
    }


def best_match(inst_flat: dict[str, Any], list_rows: list[dict[str, Any]]) -> dict[str, Any]:
    oa_name = inst_flat["display_name"]
    oa_norm = inst_flat["openalex_norm"]
    oa_token = inst_flat["openalex_token_sort"]
    oa_domain = inst_flat["homepage_domain"]
    oa_acronyms = set(a.strip().upper() for a in inst_flat["display_name_acronyms"].split(";") if a.strip())
    oa_acronyms |= acronyms_from_name(oa_name)
    best = {"score": 0.0, "method": "none", "matched_source_row": "", "matched_list_name": "", "matched_list_website": ""}
    for r in list_rows:
        score = 0.0
        methods: list[str] = []
        if oa_domain and r["list_domain"] and (oa_domain == r["list_domain"] or oa_domain.endswith("." + r["list_domain"]) or r["list_domain"].endswith("." + oa_domain)):
            score = max(score, 1.0)
            methods.append("domain_exact")
        if oa_norm and r["list_norm"] and oa_norm == r["list_norm"]:
            score = max(score, 0.99)
            methods.append("name_exact")
        ts = ratio(oa_token, r["list_token_sort"])
        ns = ratio(oa_norm, r["list_norm"])
        fuzzy = max(ts, ns)
        if fuzzy >= 0.92:
            score = max(score, 0.92 + min((fuzzy - 0.92) * 0.5, 0.07))
            methods.append(f"fuzzy_{fuzzy:.3f}")
        list_ac = set(r.get("list_acronyms") or [])
        if oa_acronyms and list_ac and (oa_acronyms & list_ac):
            # Acronyms alone are risky in Bangladesh university names (e.g., DIU can
            # mean multiple institutions). Use them as supporting evidence only.
            ac_score = 0.91 if fuzzy >= 0.70 else 0.78
            score = max(score, ac_score)
            methods.append("acronym_overlap")
        # Boost if one normalized name genuinely contains the other. This catches
        # cases like "Dhaka Medical College" vs "Dhaka Medical College and Hospital"
        # without accepting weak fuzzy pairs like "Asian University of Bangladesh"
        # vs "Asian University for Women".
        if oa_norm and r["list_norm"]:
            small, big = sorted([oa_norm, r["list_norm"]], key=len)
            small_tokens = small.split()
            if len(small) >= 12 and len(small_tokens) >= 2 and small in big:
                big_tokens = big.split()
                extra_tokens = set(big_tokens) - set(small_tokens)
                generic_terminal = small_tokens[-1] in {"university", "college", "institute", "academy", "school"}
                allowed_descriptive_extra = {"hospital", "center", "centre", "research", "science", "technology"}
                if (not generic_terminal) or (not extra_tokens) or extra_tokens <= allowed_descriptive_extra:
                    score = max(score, 0.94)
                    methods.append("name_contains")
        if score > best["score"]:
            best = {
                "score": round(score, 4),
                "method": "+".join(methods) if methods else "ratio",
                "matched_source_row": r["source_row"],
                "matched_list_name": r["list_name"],
                "matched_list_website": r["list_website"],
            }
    best["match_status"] = "matched" if best["score"] >= 0.92 else "openalex_only"
    return best


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        for r in rows:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)
        fieldnames = fields
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def dedupe_supplied_list(list_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seen: dict[str, dict[str, Any]] = {}
    unique: list[dict[str, Any]] = []
    dupes: list[dict[str, Any]] = []
    for r in list_rows:
        key = r["list_domain"] or r["list_norm"]
        if key in seen:
            dupes.append({
                "duplicate_type": "input_list_duplicate",
                "source_row": r["source_row"],
                "name": r["list_name"],
                "website": r["list_website"],
                "duplicate_of_row": seen[key]["source_row"],
                "duplicate_of_name": seen[key]["list_name"],
                "dedupe_key": key,
            })
        else:
            seen[key] = r
            unique.append(r)
    return unique, dupes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()

    html_path = args.html.expanduser().resolve()
    run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = args.outdir or (html_path.parent / f"openalex_institution_metadata_{run_ts}")
    outdir.mkdir(parents=True, exist_ok=True)

    list_rows_raw = parse_html_list(html_path)
    list_rows, input_dupes = dedupe_supplied_list(list_rows_raw)
    print(f"Parsed supplied list: raw={len(list_rows_raw)}, unique={len(list_rows)}, input_duplicates={len(input_dupes)}", flush=True)

    openalex_raw = harvest_openalex_bd()
    # Deduplicate OpenAlex by ID defensively.
    by_id: dict[str, dict[str, Any]] = {}
    for inst in openalex_raw:
        oid = inst.get("id") or ""
        if oid and oid not in by_id:
            by_id[oid] = inst
    openalex_flat = [flatten_openalex(v) for v in by_id.values()]

    all_oa_rows: list[dict[str, Any]] = []
    for inst in openalex_flat:
        m = best_match(inst, list_rows)
        all_oa_rows.append({**inst, **m})

    matched_oa = [r for r in all_oa_rows if r["match_status"] == "matched"]
    openalex_new = [r for r in all_oa_rows if r["match_status"] != "matched"]

    # For each supplied list row, choose best matched OpenAlex institution, if any.
    candidates_by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in matched_oa:
        candidates_by_row[int(r["matched_source_row"] or 0)].append(r)
    enriched: list[dict[str, Any]] = []
    openalex_duplicate_matches: list[dict[str, Any]] = []
    for lr in list_rows:
        cands = sorted(candidates_by_row.get(lr["source_row"], []), key=lambda x: (float(x["score"]), int(x.get("works_count") or 0)), reverse=True)
        best = cands[0] if cands else None
        if len(cands) > 1:
            for extra in cands[1:]:
                openalex_duplicate_matches.append({
                    "duplicate_type": "multiple_openalex_matches_for_one_list_row",
                    "source_row": lr["source_row"],
                    "list_name": lr["list_name"],
                    "kept_openalex_id": best["openalex_id"] if best else "",
                    "kept_display_name": best["display_name"] if best else "",
                    "duplicate_openalex_id": extra["openalex_id"],
                    "duplicate_display_name": extra["display_name"],
                    "duplicate_score": extra["score"],
                })
        enriched.append({
            **lr,
            "openalex_match_status": "matched" if best else "unmatched",
            "openalex_match_score": best["score"] if best else "",
            "openalex_match_method": best["method"] if best else "",
            "openalex_id": best["openalex_id"] if best else "",
            "ror": best["ror"] if best else "",
            "openalex_display_name": best["display_name"] if best else "",
            "openalex_type": best["type"] if best else "",
            "openalex_homepage_url": best["homepage_url"] if best else "",
            "openalex_works_count": best["works_count"] if best else "",
            "openalex_cited_by_count": best["cited_by_count"] if best else "",
            "openalex_h_index": best["h_index"] if best else "",
            "openalex_city": best["city"] if best else "",
            "openalex_region": best["region"] if best else "",
            "openalex_latitude": best["latitude"] if best else "",
            "openalex_longitude": best["longitude"] if best else "",
        })

    duplicate_report = input_dupes + openalex_duplicate_matches
    # Also report repeated OpenAlex IDs matched to multiple list rows.
    rows_by_oid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in enriched:
        if r.get("openalex_id"):
            rows_by_oid[r["openalex_id"]].append(r)
    for oid, rows in rows_by_oid.items():
        if len(rows) > 1:
            kept = rows[0]
            for r in rows[1:]:
                duplicate_report.append({
                    "duplicate_type": "same_openalex_id_on_multiple_list_rows",
                    "source_row": r["source_row"],
                    "name": r["list_name"],
                    "website": r["list_website"],
                    "duplicate_of_row": kept["source_row"],
                    "duplicate_of_name": kept["list_name"],
                    "dedupe_key": oid,
                })

    write_csv(outdir / "supplied_list_openalex_enriched.csv", enriched)
    write_jsonl(outdir / "supplied_list_openalex_enriched.jsonl", enriched)
    write_csv(outdir / "openalex_bd_institutions_all.csv", all_oa_rows)
    write_jsonl(outdir / "openalex_bd_institutions_all.jsonl", all_oa_rows)
    write_csv(outdir / "openalex_new_not_in_supplied_list.csv", openalex_new)
    write_csv(outdir / "duplicate_report.csv", duplicate_report)

    summary = {
        "run_ts_utc": run_ts,
        "input_html": str(html_path),
        "output_dir": str(outdir),
        "supplied_rows_raw": len(list_rows_raw),
        "supplied_rows_unique_by_domain_or_name": len(list_rows),
        "input_list_duplicates": len(input_dupes),
        "openalex_bd_institutions_raw": len(openalex_raw),
        "openalex_bd_institutions_unique_by_id": len(openalex_flat),
        "openalex_matched_to_supplied_list": len(matched_oa),
        "openalex_not_in_supplied_list": len(openalex_new),
        "supplied_list_rows_matched": sum(1 for r in enriched if r["openalex_match_status"] == "matched"),
        "supplied_list_rows_unmatched": sum(1 for r in enriched if r["openalex_match_status"] == "unmatched"),
        "duplicate_report_rows": len(duplicate_report),
        "openalex_types": Counter(r.get("type") or "" for r in all_oa_rows),
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
