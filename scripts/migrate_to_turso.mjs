// Migrate local SQLite data to Turso cloud database.
// Usage: TURSO_DATABASE_URL=<turso-url> TURSO_AUTH_TOKEN=<token> node scripts/migrate_to_turso.mjs

import { createClient } from "@libsql/client";
import { createInterface } from "readline";
import { readFileSync } from "fs";

const TURSO_URL = process.env.TURSO_DATABASE_URL;
const TURSO_TOKEN = process.env.TURSO_AUTH_TOKEN;

if (!TURSO_URL) {
  console.error("Missing TURSO_DATABASE_URL");
  process.exit(1);
}

async function main() {
  // Open local DB
  const local = createClient({ url: "file:borr.db" });

  const totalResult = await local.execute("SELECT COUNT(*) AS n FROM papers WHERE verified = 1");
  const total = Number(totalResult.rows[0].n);
  console.log(`Local verified papers: ${total.toLocaleString()}`);

  if (process.stdin.isTTY) {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const proceed = await new Promise((resolve) => rl.question("Continue? (y/N) ", resolve));
    rl.close();
    if (proceed.toLowerCase() !== "y") { console.log("Aborted."); process.exit(0); }
  }

  // Open remote Turso DB
  const remote = createClient({ url: TURSO_URL, authToken: TURSO_TOKEN });

  console.log("Migrating data in batches...");
  const BATCH = 10000;

  // Resume from where we left off
  const remoteMax = await remote.execute("SELECT COALESCE(MAX(rowid), 0) AS n FROM papers");
  const startRowid = Number(remoteMax.rows[0].n);
  let lastRowid = startRowid;

  let inserted = 0;
  let errors = 0;
  const startTime = Date.now();

  while (true) {
    const rows = await local.execute({
      sql: `SELECT *, rowid FROM papers WHERE verified = 1 AND rowid > ? ORDER BY rowid LIMIT ?`,
      args: [lastRowid, BATCH],
    });

    if (rows.rows.length === 0) break;

    const batchStatements = [];
    for (const row of rows.rows) {
      const searchText = [row.title, row.abstract || "", row.authors_text || ""]
        .join(" ")
        .toLowerCase();

      batchStatements.push({
        sql: `INSERT OR IGNORE INTO papers (
          id, openalex_id, title, authors, abstract, doi, url, journal, year,
          institution, fields, paper_type, access_type, source, verified,
          citation_count, created_at, updated_at, external_ids, sources,
          last_harvested_at, authors_text, institution_text, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        args: [
          row.id, row.openalex_id, row.title, row.authors, row.abstract,
          row.doi, row.url, row.journal, row.year, row.institution,
          row.fields, row.paper_type, row.access_type, row.source,
          row.verified, row.citation_count, row.created_at, row.updated_at,
          row.external_ids || "{}", row.sources || "[]", row.last_harvested_at,
          row.authors_text, row.institution_text, searchText,
        ],
      });
      lastRowid = Number(row.rowid);
    }

    try {
      await remote.batch(batchStatements);
      inserted += batchStatements.length;
    } catch (e) {
      for (const stmt of batchStatements) {
        try {
          await remote.execute(stmt);
          inserted++;
        } catch (e2) {
          errors++;
          if (errors <= 5) console.error(`Insert error:`, e2.message);
        }
      }
    }

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
    const rate = (inserted / Math.max(1, (Date.now() - startTime) / 1000)).toFixed(0);
    const pct = Math.min(100, Math.round((inserted / total) * 100));
    process.stdout.write(`\r  ${inserted.toLocaleString()} inserted, ${errors} errors — ${pct}% (${rate} rows/s, ${elapsed}s)`);
  }

  console.log(`\n\nDone! ${inserted.toLocaleString()} papers migrated in ${((Date.now() - startTime) / 1000).toFixed(0)}s.`);

  const result = await remote.execute("SELECT COUNT(*) AS n FROM papers WHERE verified = 1");
  console.log(`Turso remote verified: ${Number(result.rows[0].n).toLocaleString()}`);

  local.close();
}

main().catch((e) => {
  console.error("Fatal:", e);
  process.exit(1);
});
