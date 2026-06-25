#!/usr/bin/env python3
"""Starter utilities for the OpenAlex public S3 snapshot.

This intentionally avoids downloading the whole snapshot by default. Use it to:
1. download small manifest files,
2. inspect compressed sizes/record counts,
3. stream works files directly from S3 and keep only Bangladesh-target records.

Examples:
  python scripts/openalex_snapshot_starter.py manifests
  python scripts/openalex_snapshot_starter.py stream-bangladesh --limit-files 1
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import requests

S3_HTTP_BASE = "https://openalex.s3.amazonaws.com"
DEFAULT_ENTITIES = [
    "works",
    "authors",
    "institutions",
    "sources",
    "topics",
    "concepts",
    "publishers",
    "funders",
]
USER_AGENT = "BORR-OpenAlex-Snapshot-Starter/1.0 (mailto:contact@borr.org.bd)"


def s3_to_https(url: str) -> str:
    if not url.startswith("s3://openalex/"):
        raise ValueError(f"Unsupported snapshot URL: {url}")
    return f"{S3_HTTP_BASE}/{url.removeprefix('s3://openalex/')}"


def request_get(url: str, *, stream: bool = False) -> requests.Response:
    response = requests.get(
        url,
        headers={"User-Agent": os.getenv("BORR_USER_AGENT", USER_AGENT)},
        timeout=60,
        stream=stream,
    )
    response.raise_for_status()
    return response


def download_manifest(entity: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"{S3_HTTP_BASE}/data/{entity}/manifest"
    response = request_get(url)
    out_path = out_dir / f"{entity}-manifest.json"
    out_path.write_bytes(response.content)
    return out_path


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def summarize_manifest(path: Path) -> tuple[int, int, int]:
    manifest = load_manifest(path)
    entries = manifest.get("entries", [])
    compressed_bytes = sum(e.get("meta", {}).get("content_length", 0) for e in entries)
    records = sum(e.get("meta", {}).get("record_count", 0) for e in entries)
    return len(entries), compressed_bytes, records


def abstract_has_target(abstract_inverted_index: dict[str, Any] | None, target_re: re.Pattern[str]) -> bool:
    if not abstract_inverted_index:
        return False
    # The inverted index keys are words. This avoids rebuilding large abstracts unless needed.
    return any(target_re.search(str(word)) for word in abstract_inverted_index.keys())


def work_matches_bangladesh(work: dict[str, Any]) -> bool:
    target_re = re.compile(r"bangladesh|bangladeshi", re.IGNORECASE)

    if target_re.search(str(work.get("title") or "")):
        return True
    if abstract_has_target(work.get("abstract_inverted_index"), target_re):
        return True

    for country in work.get("countries_distinct") or []:
        if str(country).upper() == "BD":
            return True

    for authorship in work.get("authorships") or []:
        for inst in authorship.get("institutions") or []:
            if str(inst.get("country_code") or "").upper() == "BD":
                return True
            if target_re.search(str(inst.get("display_name") or "")):
                return True

    return False


def iter_jsonl_gz_from_url(url: str) -> Iterable[dict[str, Any]]:
    with request_get(url, stream=True) as response:
        response.raw.decode_content = True
        with gzip.GzipFile(fileobj=response.raw) as gz:
            for raw_line in gz:
                if not raw_line.strip():
                    continue
                yield json.loads(raw_line)


def command_manifests(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    for entity in args.entities:
        path = download_manifest(entity, out_dir)
        file_count, compressed_bytes, records = summarize_manifest(path)
        print(
            f"{entity:12s} manifest={path} files={file_count:,} "
            f"compressed={compressed_bytes / 1024**3:.2f} GiB records={records:,}"
        )
    return 0


def command_stream_bangladesh(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        manifest_path = download_manifest("works", manifest_path.parent)

    manifest = load_manifest(manifest_path)
    entries = manifest.get("entries", [])
    if args.limit_files:
        entries = entries[: args.limit_files]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scanned_records = 0
    matched_records = 0
    scanned_files = 0

    with out_path.open("a", encoding="utf-8") as out:
        for entry in entries:
            s3_url = entry["url"]
            http_url = s3_to_https(s3_url)
            scanned_files += 1
            print(f"Streaming {scanned_files}/{len(entries)} {s3_url}", flush=True)
            for work in iter_jsonl_gz_from_url(http_url):
                scanned_records += 1
                if work_matches_bangladesh(work):
                    out.write(json.dumps(work, ensure_ascii=False) + "\n")
                    matched_records += 1
            print(
                f"  cumulative scanned={scanned_records:,} matched={matched_records:,}",
                flush=True,
            )

    print(
        f"Done. files={scanned_files:,} scanned={scanned_records:,} "
        f"matched={matched_records:,} output={out_path}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAlex snapshot starter for BORR")
    sub = parser.add_subparsers(dest="command", required=True)

    manifests = sub.add_parser("manifests", help="Download entity manifests and print sizes")
    manifests.add_argument("--out", default="data/openalex/manifests", help="Manifest output directory")
    manifests.add_argument("--entities", nargs="+", default=DEFAULT_ENTITIES, help="Entities to download")
    manifests.set_defaults(func=command_manifests)

    stream = sub.add_parser("stream-bangladesh", help="Stream works snapshot files and keep Bangladesh-target records")
    stream.add_argument("--manifest", default="data/openalex/manifests/works-manifest.json")
    stream.add_argument("--out", default="data/openalex/filtered/bangladesh_works.raw.jsonl")
    stream.add_argument("--limit-files", type=int, default=1, help="Safety limit. Omit/0 only when ready for the full scan.")
    stream.set_defaults(func=command_stream_bangladesh)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
