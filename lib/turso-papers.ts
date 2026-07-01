import { createClient, Client, Row } from "@libsql/client";
import { cache } from "react";

export const isTursoDatabaseConfigured = Boolean(process.env.TURSO_DATABASE_URL);

let client: Client | null = null;

function getClient(): Client {
  if (!client) {
    const url = process.env.TURSO_DATABASE_URL;
    const authToken = process.env.TURSO_AUTH_TOKEN;

    if (!url) {
      throw new Error("Missing TURSO_DATABASE_URL");
    }

    client = createClient({
      url,
      authToken,
    });
  }

  return client;
}

export type LocalPaperRow = {
  id: string;
  openalex_id: string | null;
  title: string;
  authors: string[] | null;
  abstract: string | null;
  doi: string | null;
  url: string | null;
  journal: string | null;
  year: number | null;
  institution: string[] | null;
  fields: string[] | null;
  paper_type: string | null;
  access_type: string | null;
  source: string | null;
  verified: boolean;
  citation_count: number | null;
  created_at: string;
};

export type SearchPapersOptions = {
  query: string;
  sort: string;
  page: number;
  field: string;
  year: string;
  yearFrom: string;
  yearTo: string;
  type?: string;
  access: string;
  institution: string;
  limit?: number;
};

export type SearchPapersResult = {
  papers: LocalPaperRow[];
  count: number;
  countMode: "exact" | "estimated" | "lower-bound";
  hasNextPage: boolean;
};

function parseJsonArray(val: unknown): string[] {
  if (!val) return [];
  if (typeof val === 'string') {
    try {
      return JSON.parse(val);
    } catch {
      return [];
    }
  }
  return [];
}

function normalizePaper(row: Row): LocalPaperRow {
  const abstract = row.abstract ? String(row.abstract) : null;
  return {
    id: String(row.id),
    openalex_id: row.openalex_id ? String(row.openalex_id) : null,
    title: String(row.title),
    authors: parseJsonArray(row.authors),
    abstract,
    doi: row.doi ? String(row.doi) : null,
    url: row.url ? String(row.url) : null,
    journal: row.journal ? String(row.journal) : null,
    year: row.year ? Number(row.year) : null,
    institution: parseJsonArray(row.institution),
    fields: parseJsonArray(row.fields),
    paper_type: row.paper_type ? String(row.paper_type) : null,
    access_type: row.access_type ? String(row.access_type) : null,
    source: row.source ? String(row.source) : null,
    verified: Boolean(row.verified),
    citation_count: row.citation_count ? Number(row.citation_count) : null,
    created_at: String(row.created_at),
  };
}

function normalizePaperShort(row: Row): LocalPaperRow {
  const abstract = row.abstract ? String(row.abstract) : null;
  return {
    id: String(row.id),
    openalex_id: row.openalex_id ? String(row.openalex_id) : null,
    title: String(row.title),
    authors: parseJsonArray(row.authors),
    abstract: abstract ? abstract.slice(0, 300) + (abstract.length > 300 ? "..." : "") : null,
    doi: row.doi ? String(row.doi) : null,
    url: row.url ? String(row.url) : null,
    journal: row.journal ? String(row.journal) : null,
    year: row.year ? Number(row.year) : null,
    institution: parseJsonArray(row.institution),
    fields: parseJsonArray(row.fields),
    paper_type: row.paper_type ? String(row.paper_type) : null,
    access_type: row.access_type ? String(row.access_type) : null,
    source: row.source ? String(row.source) : null,
    verified: Boolean(row.verified),
    citation_count: row.citation_count ? Number(row.citation_count) : null,
    created_at: String(row.created_at),
  };
}

export async function getLocalStats() {
  const db = getClient();
  try {
    const result = await db.execute(`
      SELECT SUM(total_count) as papers 
      FROM paper_stats
    `);

    return {
      papers: Number(result.rows[0]?.papers ?? 0),
      researchers: 0,
      institutions: 0,
    };
  } catch {
    return { papers: 0, researchers: 0, institutions: 0 };
  }
}

// Cache total count
let cachedTotalCount: { value: number; expiresAt: number } | null = null;
const TOTAL_COUNT_TTL_MS = 10 * 60_000;

async function getTotalPaperCount(): Promise<number> {
  const now = Date.now();
  if (cachedTotalCount && cachedTotalCount.expiresAt > now) return cachedTotalCount.value;
  const db = getClient();
  try {
    const result = await db.execute(`SELECT SUM(total_count) AS n FROM paper_stats`);
    const value = Number(result.rows[0]?.n ?? 0);
    cachedTotalCount = { value, expiresAt: now + TOTAL_COUNT_TTL_MS };
    return value;
  } catch (e) {
    // Fallback if table doesn't exist yet
    return 0;
  }
}

let schemaStatus: {
  hasFts: boolean;
  hasSearchText: boolean;
} = { hasFts: true, hasSearchText: false };  // production Turso always has FTS

async function checkSchema(db: Client) {
  return schemaStatus;  // hardcoded — saves a PRAGMA query on every search
}

export async function searchLocalPapers(options: SearchPapersOptions): Promise<SearchPapersResult> {
  const db = getClient();
  const schema = await checkSchema(db);

  const params: (string | number)[] = [];
  const where: string[] = ["p.verified = 1"];
  let isFtsUsed = false;

  if (options.query) {
    if (schema.hasFts) {
      const cleanQuery = options.query
        .replace(/["'*]/g, "") // Strip characters that might break FTS syntax
        .split(/\s+/)
        .filter(Boolean)
        .map((term) => `"${term}"*`)
        .join(" AND ");

      if (cleanQuery) {
        where.push(`f.papers_fts MATCH ?`);
        params.push(cleanQuery);
        isFtsUsed = true;
      }
    } else {
      const terms = options.query.split(/\s+/).filter(Boolean);
      for (const term of terms) {
        const likeTerm = `%${term}%`;
        if (schema.hasSearchText) {
          where.push(`p.search_text LIKE ?`);
          params.push(likeTerm);
        } else {
          where.push(`(p.title LIKE ? OR coalesce(p.abstract, '') LIKE ? OR coalesce(p.authors_text, '') LIKE ?)`);
          params.push(likeTerm, likeTerm, likeTerm);
        }
      }
    }
  }

  if (options.field) {
    params.push(options.field);
    where.push(`EXISTS (SELECT 1 FROM json_each(p.fields) WHERE value = ?)`);
  }

  if (options.yearFrom) {
    const parsed = Number.parseInt(options.yearFrom, 10);
    if (!Number.isNaN(parsed)) {
      params.push(parsed);
      where.push(`p.year >= ?`);
    }
  }

  if (options.yearTo) {
    const parsed = Number.parseInt(options.yearTo, 10);
    if (!Number.isNaN(parsed)) {
      params.push(parsed);
      where.push(`p.year <= ?`);
    }
  }

  if (options.year && !options.yearFrom && !options.yearTo) {
    const parsedYear = Number.parseInt(options.year, 10);
    if (!Number.isNaN(parsedYear)) {
      params.push(parsedYear);
      where.push(`p.year = ?`);
    }
  }

  if (options.type) {
    params.push(options.type);
    where.push(`p.paper_type = ?`);
  }

  if (options.access) {
    params.push(options.access);
    where.push(`p.access_type = ?`);
  }

  if (options.institution) {
    params.push(`%${options.institution}%`);
    // SQLite LIKE is case-insensitive for ASCII
    where.push(`p.institution_text LIKE ?`);
  }

  const whereSql = where.join(" AND ");
  const limit = options.limit ?? 20;
  const offset = (Math.max(options.page, 1) - 1) * limit;
  const fetchLimit = limit + 1;

  let orderBy = "p.citation_count DESC, p.id ASC";

  if (options.sort === "newest") {
    orderBy = "p.year DESC, p.id ASC";
  } else if (options.sort === "relevance" && options.query) {
    orderBy = "CASE WHEN p.title LIKE ? THEN 100 ELSE 0 END + p.citation_count DESC, p.year DESC";
    params.push(`%${options.query}%`);
  }

  const selectColumns = `
    p.id, p.openalex_id, p.title, p.authors, p.abstract, p.doi, p.url, p.journal, p.year,
    p.institution, p.fields, p.paper_type, p.access_type, p.source, p.verified,
    p.citation_count, p.created_at
  `;

  const sql = isFtsUsed
    ? `
      SELECT ${selectColumns}
      FROM papers_fts f
      CROSS JOIN papers p ON p.rowid = f.rowid
      WHERE ${whereSql}
      ORDER BY ${orderBy}
      LIMIT ? OFFSET ?
    `
    : `
      SELECT ${selectColumns}
      FROM papers p
      WHERE ${whereSql}
      ORDER BY ${orderBy}
      LIMIT ? OFFSET ?
    `;

  params.push(fetchLimit, offset);

  let result;
  try {
    result = await db.execute({ sql, args: params });
  } catch (e) {
    console.error("SQL ERROR:", e);
    throw e;
  }
  
  const visibleRows = result.rows.slice(0, limit);
  const hasNextPage = result.rows.length > limit;

  let count = offset + visibleRows.length + (hasNextPage ? 1 : 0);
  let countMode: SearchPapersResult["countMode"] = "lower-bound";

  const hasFilters = Boolean(
    options.field || options.year || options.yearFrom || options.yearTo || options.type || options.access || options.institution
  );

  const onlyTypeFilter =
    !options.query && options.type &&
    !options.field && !options.year && !options.yearFrom && !options.yearTo && !options.access && !options.institution;

  if (!options.query && !hasFilters) {
    count = await getTotalPaperCount();
    countMode = "exact";
  } else if (onlyTypeFilter) {
    const exact = (await getLocalTypeCounts())[options.type!];
    if (exact != null) {
      count = exact;
      countMode = "exact";
    }
  } else if (!hasNextPage) {
    countMode = "exact";
  }

  return {
    papers: visibleRows.map(normalizePaperShort),
    count,
    countMode,
    hasNextPage,
  };
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const getLocalPaperByKey = cache(async (key: string): Promise<LocalPaperRow | null> => {
  const decoded = decodeURIComponent(key);
  const selectColumns = `
    id, openalex_id, title, authors, abstract, doi, url, journal, year,
    institution, fields, paper_type, access_type, source, verified,
    citation_count, created_at
  `;

  const db = getClient();

  // UUID → primary-key lookup.
  if (UUID_RE.test(decoded)) {
    const result = await db.execute({
      sql: `SELECT ${selectColumns} FROM papers WHERE id = ? AND verified = 1 LIMIT 1`,
      args: [decoded],
    });
    return result.rows[0] ? normalizePaper(result.rows[0]) : null;
  }

  // Otherwise probe each indexed identifier in turn and short-circuit on the
  // first hit. Each query is an index point-lookup (papers_doi_lower_idx /
  // openalex_id unique / papers_openalex_short_idx), so it reads ~1 row.
  // The previous single OR-query filtered on lower(coalesce(doi,'')), which
  // does NOT match the lower(doi) index expression, so it forced a full table
  // scan of every row on every /paper/... request — the main read-quota sink.
  // The `IS NOT NULL` guards let SQLite pick the partial indexes.
  const lookups: { sql: string; args: string[] }[] = [
    {
      sql: `SELECT ${selectColumns} FROM papers WHERE doi IS NOT NULL AND lower(doi) = lower(?) AND verified = 1 LIMIT 1`,
      args: [decoded],
    },
    {
      sql: `SELECT ${selectColumns} FROM papers WHERE openalex_id = ? AND verified = 1 LIMIT 1`,
      args: [decoded],
    },
    {
      sql: `SELECT ${selectColumns} FROM papers WHERE openalex_id IS NOT NULL AND replace(openalex_id, 'https://openalex.org/', '') = ? AND verified = 1 LIMIT 1`,
      args: [decoded],
    },
  ];

  for (const lookup of lookups) {
    const result = await db.execute(lookup);
    if (result.rows[0]) return normalizePaper(result.rows[0]);
  }
  return null;
});

export async function getLocalPaperCount(): Promise<number> {
  return await getTotalPaperCount();
}

let cachedTypeCounts: { value: Record<string, number>; expiresAt: number } | null = null;

export async function getLocalTypeCounts(): Promise<Record<string, number>> {
  const now = Date.now();
  if (cachedTypeCounts && cachedTypeCounts.expiresAt > now) return cachedTypeCounts.value;
  
  const db = getClient();
  const counts: Record<string, number> = {};
  
  try {
    const result = await db.execute(`
      SELECT paper_type, total_count AS n
      FROM paper_stats
    `);
    
    for (const row of result.rows) {
      counts[String(row.paper_type)] = Number(row.n);
    }
  } catch (e) {
    // If the table doesn't exist yet, return empty
  }
  
  cachedTypeCounts = { value: counts, expiresAt: now + TOTAL_COUNT_TTL_MS };
  return counts;
}

export async function getLocalPaperSitemapPage(
  offset: number,
  limit: number,
): Promise<{ id: string; updated_at: string | null }[]> {
  const db = getClient();
  const result = await db.execute({
    sql: `SELECT id, updated_at FROM papers WHERE verified = 1 ORDER BY id LIMIT ? OFFSET ?`,
    args: [limit, offset],
  });
  
  return result.rows.map((row) => ({
    id: String(row.id),
    updated_at: row.updated_at ? String(row.updated_at) : null,
  }));
}

export async function localDoiExists(doi: string): Promise<boolean> {
  const db = getClient();
  const result = await db.execute({
    sql: `SELECT 1 FROM papers WHERE lower(doi) = lower(?) LIMIT 1`,
    args: [doi],
  });
  return result.rows.length > 0;
}

export type NewPaperRecord = {
  title: string;
  authors: string[];
  abstract: string | null;
  doi: string;
  url: string;
  journal: string | null;
  year: number | null;
  institution: string[];
  fields: string[];
  paper_type: string;
  access_type: string;
  source: string;
  verified: boolean;
  citation_count: number;
};

export async function insertLocalPaper(paper: NewPaperRecord): Promise<void> {
  const db = getClient();
  await db.execute({
    sql: `INSERT INTO papers (
      id, title, authors, abstract, doi, url, journal, year, institution, fields, 
      paper_type, access_type, source, verified, citation_count, authors_text, institution_text
    ) VALUES (
      lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || substr(lower(hex(randomblob(2))),2) || '-' || substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || lower(hex(randomblob(6))),
      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )`,
    args: [
      paper.title,
      JSON.stringify(paper.authors),
      paper.abstract,
      paper.doi,
      paper.url,
      paper.journal,
      paper.year,
      JSON.stringify(paper.institution),
      JSON.stringify(paper.fields),
      paper.paper_type,
      paper.access_type,
      paper.source,
      paper.verified ? 1 : 0,
      paper.citation_count,
      paper.authors.join(" "),
      paper.institution.join(" "),
    ],
  });
}

export type UnverifiedPaper = {
  id: string;
  title: string;
  authors: string[] | null;
  doi: string | null;
  source: string | null;
  abstract: string | null;
  created_at: string;
};

export async function getUnverifiedLocalPapers(): Promise<UnverifiedPaper[]> {
  const db = getClient();
  const result = await db.execute(`
    SELECT id, title, authors, doi, source, abstract, created_at
    FROM papers
    WHERE verified = 0
    ORDER BY created_at DESC
    LIMIT 100
  `);

  return result.rows.map((row) => ({
    id: String(row.id),
    title: String(row.title),
    authors: parseJsonArray(row.authors),
    doi: row.doi ? String(row.doi) : null,
    source: row.source ? String(row.source) : null,
    abstract: row.abstract ? String(row.abstract) : null,
    created_at: String(row.created_at),
  }));
}

export async function setLocalPaperVerified(id: string): Promise<void> {
  const db = getClient();
  await db.execute({
    sql: `UPDATE papers SET verified = 1 WHERE id = ?`,
    args: [id],
  });
}

export async function deleteLocalPaper(id: string): Promise<void> {
  const db = getClient();
  await db.execute({
    sql: `DELETE FROM papers WHERE id = ?`,
    args: [id],
  });
}
