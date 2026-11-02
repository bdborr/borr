#!/usr/bin/env python3
"""Regression checks for BORR's Turso read-quota safeguards."""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReadQuotaGuardTests(unittest.TestCase):
    def test_source_guards_remain_enabled(self) -> None:
        data_source = (ROOT / "lib" / "turso-papers.ts").read_text()
        middleware = (ROOT / "proxy.ts").read_text()
        paper_page = (ROOT / "app" / "paper" / "[doi]" / "page.tsx").read_text()
        paper_card = (ROOT / "components" / "PaperCard.tsx").read_text()
        home_page = (ROOT / "app" / "page.tsx").read_text()
        harvester = (ROOT / "scripts" / "harvest_incremental.py").read_text()

        self.assertIn("const MAX_FTS_CANDIDATES = 128", data_source)
        self.assertIn("let ftsCandidateRowids: number[] | null = null", data_source)
        self.assertIn("!options.query && (options.field || options.institution)", data_source)
        self.assertIn('pathname.startsWith("/search")) return 5', middleware)
        self.assertIn('request.headers.get("next-router-prefetch")', middleware)
        self.assertIn("export async function generateMetadata", paper_page)
        self.assertIn("<Link prefetch={false} href={paperHref}", paper_card)
        self.assertNotIn("href={`/search?field=", paper_card)
        self.assertIn("getLocalPaperCount", home_page)
        self.assertIn("Updated automatically after each database harvest", home_page)
        self.assertNotIn('href="/search?type=', home_page)
        self.assertIn("check_turso_cli_auth()", harvester)
        self.assertNotIn("2>/dev/null", harvester)

    def test_schema_and_migration_are_valid(self) -> None:
        con = sqlite3.connect(":memory:")
        con.executescript((ROOT / "turso" / "schema.sql").read_text())
        con.executescript((ROOT / "turso" / "read_quota_hardening.sql").read_text())

        indexes = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
        self.assertIn("papers_verified_type_citations_idx", indexes)
        self.assertIn("papers_verified_access_citations_idx", indexes)

        trigger_sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='papers_au'"
        ).fetchone()[0]
        self.assertIn("UPDATE OF title, abstract, authors_text", trigger_sql)

    def test_fts_stage_is_hard_bounded_and_lookup_is_by_rowid(self) -> None:
        con = sqlite3.connect(":memory:")
        con.executescript(
            """
            CREATE TABLE papers (
              id TEXT, title TEXT, abstract TEXT, authors_text TEXT,
              verified INTEGER, citation_count INTEGER, year INTEGER
            );
            CREATE INDEX papers_verified_citations_idx
            ON papers(verified, citation_count DESC, id ASC);
            CREATE VIRTUAL TABLE papers_fts USING fts5(
              title, abstract, authors_text, content='papers', content_rowid='rowid'
            );
            """
        )
        rows = [
            (str(i), f"Bangladesh paper {i}", "public health research", "Author", 1, i, 2000 + i % 25)
            for i in range(50_000)
        ]
        con.executemany(
            "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?)", rows
        )
        con.execute("INSERT INTO papers_fts(papers_fts) VALUES ('rebuild')")

        candidates = con.execute(
            "SELECT rowid, rank FROM papers_fts WHERE papers_fts MATCH ? LIMIT 128",
            ('"bangladesh"*',),
        ).fetchall()
        self.assertEqual(128, len(candidates))

        placeholders = ",".join("?" for _ in candidates)
        plan = con.execute(
            f"EXPLAIN QUERY PLAN SELECT p.rowid FROM papers p NOT INDEXED "
            f"WHERE p.verified=1 AND p.rowid IN ({placeholders}) "
            "ORDER BY p.citation_count DESC LIMIT 16",
            [row[0] for row in candidates],
        ).fetchall()
        plan_text = " ".join(str(item) for row in plan for item in row)
        self.assertIn("INTEGER PRIMARY KEY", plan_text)
        self.assertNotIn("SCAN p", plan_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
