// Migrate local SQLite data to Turso cloud database.
// Usage: TURSO_DATABASE_URL=<url> TURSO_AUTH_TOKEN=<token> node scripts/migrate_to_turso.js

import { createClient } from "@libsql/client";
import sqlite3 from "sqlite3";
import { open } from "sqlite/promise";
import { createInterface } from "readline";

const TURSO_URL = process.env.TURSO_DATABASE_URL;
const TURSO_TOKEN = process.env.TURSO_AUTH_TOKEN;
const LOCAL_PATH = process.env.LOCAL_DB_PATH || "borr.db";
const BATCH_SIZE = 500;
const VERIFY_PAUSE = 2000;

if (!TURSO_URL) {
  console.error("Missing TURSO_DATABASE_URL");
  process.exit(1);
}

const rl = createInterface({ input: process.stdin, output: process.stdout });
function ask(q) {
  return new Promise((resolve) => rl.question(q, resolve));
}

async function main() {
  console.log("Opening local DB:", LOCAL_PATH);
  const local = await open({ filename: LOCAL_PATH, driver: sqlite3.Database });

  const total = await local.get("SELECT COUNT(*) AS n FROM papers WHERE verified = 1");
  console.log(`Local verified papers: ${total.n}`);

  const proceed = await ask(`This will copy ${total.n} papers to Turso. Continue? (y/N) `);
  if (proceed.toLowerCase() !== "y") {
    console.log("Aborted.");
    await local.close();
    process.exit(0);
  }

  const remote = createClient({ url: TURSO_URL, authToken: TURSO_TOKEN });

  console.log("Applying schema...");
  const fs = await import("fs");
  const schema = fs.readFileSync("scripts/turso_schema.sql", "utf-8");
  for (const stmt of schema.split(";").filter(Boolean)) {
    try {
      await remote.execute(stmt.trim() + ";");
    } catch (e) {
      console.warn("Schema statement warning (may be benign):", e.message);
    }
  }

  console.log("Migrating data...");
  let offset = 0;
  let inserted = 0;
  let errors = 0;

  while (true) {
    const rows = await local.all(
      `SELECT * FROM papers WHERE verified = 1 ORDER BY rowid LIMIT ? OFFSET ?`,
      [BATCH_SIZE, offset]
    );

    if (rows.length === 0) break;

    for (const row of rows) {
      const searchText = [row.title, row.abstract || "", (row.authors_text || "")].join(" ").toLowerCase();

      try {
        await remote.execute({
          sql: `INSERT OR IGNORE INTO papers (
            id, openalex_id, title, authors, abstract, doi, url, journal, year,
            institution, fields, paper_type, access_type, source, verified,
            citation_count, created_at, updated_at, external_ids, sources,
            last_harvested_at, authors_text, institution_text, search_text
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          args: [
            row.id, row.openalex_id, row.title, row.authors, row.abstract,
            row.doi, row.url, row.journal, row.year, row.institution,
            row.fields, row.paper_type, row.access_type, row.source, row.verified,
            row.citation_count, row.created_at, row.updated_at, row.external_ids || "{}",
            row.sources || "[]", row.last_harvested_at, row.authors_text,
            row.institution_text, searchText,
          ],
        });
        inserted++;
      } catch (e) {
        errors++;
        if (errors <= 10) console.error(`Insert error for ${row.id}:`, e.message);
      }
    }

    offset += BATCH_SIZE;
    const pct = Math.min(100, Math.round((offset / total.n) * 100));
    process.stdout.write(`\r  ${inserted} inserted, ${errors} errors — ${pct}%`);
  }

  console.log(`\n\nDone! ${inserted} papers migrated. ${errors} errors.`);

  if (errors === 0) {
    console.log("Verifying...");
    await new Promise((r) => setTimeout(r, VERIFY_PAUSE));
    const result = await remote.execute("SELECT COUNT(*) AS n FROM papers WHERE verified = 1");
    console.log(`Turso remote count: ${result.rows[0].n}`);
  }

  await local.close();
  rl.close();
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
