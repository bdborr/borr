#!/usr/bin/env python3
"""
Overnight abstract enrichment for papers where abstract IS NULL and doi IS NOT NULL.

Two phases, in order of throughput:
  1. Semantic Scholar batch API (500 DOIs per call)
  2. Europe PMC REST API (per-DOI, ~4 req/s) for DOIs S2 didn't cover

Safe to stop and restart at any time: each phase checkpoints processed DOIs to
data/enrich_s2_done.txt and data/enrich_epmc_done.txt and skips them on resume.

Usage:
  DATABASE_URL=... venv/bin/python scripts/enrich_abstracts.py
"""

import html
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

import psycopg2
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
S2_DONE = PROJECT_ROOT / "data" / "enrich_s2_done.txt"
EPMC_DONE = PROJECT_ROOT / "data" / "enrich_epmc_done.txt"
USER_AGENT = "BORR/1.0 (https://github.com/borr-archive; mailto:contact@borr.org.bd)"
MIN_CHARS = 60
S2_BATCH = 500
S2_PAUSE = 2.0        # seconds between batch calls (unauthenticated pool)
EPMC_WORKERS = 4
EPMC_RPS = 4.0
COMMIT_EVERY = 200

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
LABEL_RE = re.compile(r"^\s*(abstract|summary)\s*[:.\-]?\s*", re.IGNORECASE)


def clean_text(raw: str) -> str:
    text = TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text).strip()
    return LABEL_RE.sub("", text).strip()


def load_done(path: Path) -> set:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def get_todo(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, doi FROM papers WHERE abstract IS NULL AND doi IS NOT NULL "
            "ORDER BY citation_count DESC NULLS LAST"
        )
        return cur.fetchall()


def save_abstract(cur, pid, abstract):
    cur.execute("UPDATE papers SET abstract = %s WHERE id = %s AND abstract IS NULL", (abstract, pid))


def phase_s2(conn, session):
    done = load_done(S2_DONE)
    todo = [(pid, doi) for pid, doi in get_todo(conn) if doi not in done]
    print(f"\n[S2] to process: {len(todo):,} (batch={S2_BATCH})", flush=True)
    found = 0
    fh = open(S2_DONE, "a")
    with conn.cursor() as cur:
        for start in range(0, len(todo), S2_BATCH):
            chunk = todo[start : start + S2_BATCH]
            ids = [f"DOI:{doi}" for _, doi in chunk]
            for attempt in range(5):
                try:
                    res = session.post(
                        "https://api.semanticscholar.org/graph/v1/paper/batch",
                        params={"fields": "abstract"},
                        json={"ids": ids},
                        timeout=120,
                    )
                except requests.RequestException:
                    time.sleep(15 * (attempt + 1))
                    continue
                if res.status_code == 429 or res.status_code >= 500:
                    time.sleep(60)
                    continue
                break
            else:
                print("[S2] giving up on this chunk after retries", flush=True)
                continue
            if not res.ok:
                print(f"[S2] chunk failed: HTTP {res.status_code}", flush=True)
                continue
            items = res.json()
            for (pid, doi), item in zip(chunk, items):
                abstract = (item or {}).get("abstract") or ""
                cleaned = clean_text(abstract) if abstract else ""
                if len(cleaned) >= MIN_CHARS:
                    save_abstract(cur, pid, cleaned)
                    found += 1
                fh.write(doi + "\n")
            conn.commit()
            fh.flush()
            processed = min(start + S2_BATCH, len(todo))
            print(f"[S2] {processed:,}/{len(todo):,} | found={found:,}", flush=True)
            time.sleep(S2_PAUSE)
    fh.close()
    print(f"[S2] done. recovered {found:,}", flush=True)


def phase_epmc(conn, base_headers):
    done = load_done(EPMC_DONE)
    todo = [(pid, doi) for pid, doi in get_todo(conn) if doi not in done]
    total = len(todo)
    print(f"\n[EPMC] to process: {total:,} (workers={EPMC_WORKERS}, ~{EPMC_RPS}/s)", flush=True)

    rate_lock = Lock()
    last = [0.0]

    def polite_wait():
        with rate_lock:
            now = time.monotonic()
            wait = last[0] + (1.0 / EPMC_RPS) - now
            if wait > 0:
                time.sleep(wait)
            last[0] = max(now, last[0] + (1.0 / EPMC_RPS))

    sessions = []
    for _ in range(EPMC_WORKERS):
        s = requests.Session()
        s.headers.update(base_headers)
        sessions.append(s)

    def fetch(item):
        idx, (pid, doi) = item
        sess = sessions[idx % EPMC_WORKERS]
        for attempt in range(3):
            polite_wait()
            try:
                res = sess.get(
                    "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                    params={"query": f'DOI:"{doi}"', "resultType": "core", "format": "json", "pageSize": 1},
                    timeout=30,
                )
            except requests.RequestException:
                time.sleep(3 * (attempt + 1))
                continue
            if res.status_code == 429 or res.status_code >= 500:
                time.sleep(30)
                continue
            if not res.ok:
                return pid, doi, "error", None
            try:
                results = res.json().get("resultList", {}).get("result", [])
            except ValueError:
                return pid, doi, "error", None
            raw = (results[0].get("abstractText") or "") if results else ""
            cleaned = clean_text(raw) if raw else ""
            if len(cleaned) >= MIN_CHARS:
                return pid, doi, "found", cleaned
            return pid, doi, "none", None
        return pid, doi, "error", None

    stats = {"found": 0, "none": 0, "error": 0}
    started = time.time()
    pending = 0
    fh = open(EPMC_DONE, "a")
    with conn.cursor() as cur, ThreadPoolExecutor(max_workers=EPMC_WORKERS) as pool:
        for i, (pid, doi, status, abstract) in enumerate(pool.map(fetch, enumerate(todo)), 1):
            stats[status] += 1
            if status == "found":
                save_abstract(cur, pid, abstract)
            if status != "error":
                fh.write(doi + "\n")
            pending += 1
            if pending >= COMMIT_EVERY:
                conn.commit()
                fh.flush()
                pending = 0
            if i % 1000 == 0:
                rate = i / (time.time() - started)
                eta_h = (total - i) / rate / 3600 if rate else 0
                print(
                    f"[EPMC] {i:,}/{total:,} | found={stats['found']:,} none={stats['none']:,} "
                    f"err={stats['error']:,} | {rate:.1f}/s | ETA {eta_h:.1f}h",
                    flush=True,
                )
    conn.commit()
    fh.close()
    print(f"[EPMC] done. recovered {stats['found']:,} (none={stats['none']:,}, errors={stats['error']:,})", flush=True)


def main():
    db_uri = os.environ.get("DATABASE_URL")
    if not db_uri:
        sys.exit("DATABASE_URL is required")
    conn = psycopg2.connect(db_uri)

    headers = {"User-Agent": USER_AGENT}
    s2_session = requests.Session()
    s2_session.headers.update(headers)

    started = time.time()
    phase_s2(conn, s2_session)
    phase_epmc(conn, headers)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FILTER (WHERE abstract IS NOT NULL), count(*) FILTER (WHERE abstract IS NULL) FROM papers"
        )
        with_abs, without = cur.fetchone()
    conn.close()
    print("\n=== ENRICHMENT COMPLETE ===", flush=True)
    print(f"total time: {(time.time()-started)/3600:.1f}h", flush=True)
    print(f"papers with abstract: {with_abs:,}", flush=True)
    print(f"papers still without: {without:,}", flush=True)


if __name__ == "__main__":
    main()
