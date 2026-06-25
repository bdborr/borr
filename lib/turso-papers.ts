import { createClient, Client, Row } from "@libsql/client";

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
  return {
    id: String(row.id),
    openalex_id: row.openalex_id ? String(row.openalex_id) : null,
    title: String(row.title),
    authors: parseJsonArray(row.authors),
    abstract: row.abstract ? String(row.abstract) : null,
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
      SELECT 
        COUNT(*) as papers,
        0 as researchers,
        0 as institutions
      FROM papers
      WHERE verified = 1
    `);

    // We skip exact researcher/institution counts for now as it's slow in SQLite 
    // without the tablesample + lateral unnest tricks. The total count is fast.
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
  const result = await db.execute(`SELECT count(*) AS n FROM papers WHERE verified = 1`);
  const value = Number(result.rows[0]?.n ?? 0);
  cachedTotalCount = { value, expiresAt: now + TOTAL_COUNT_TTL_MS };
  return value;
}

export async function searchLocalPapers(options: SearchPapersOptions): Promise<SearchPapersResult> {
  const params: (string | number)[] = [];
  const where: string[] = ["p.verified = 1"];

  if (options.query) {
    const terms = options.query.split(/\s+/).filter(Boolean);
    for (const term of terms) {
      const likeTerm = `%${term}%`;
      params.push(likeTerm);
      where.push(`p.search_text LIKE ?`);
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

  let orderBy = "citation_count DESC, year DESC";

  if (options.sort === "newest") {
    orderBy = "year DESC, id ASC";
  } else if (options.sort === "relevance" && options.query) {
    orderBy = "CASE WHEN title LIKE ? THEN 100 ELSE 0 END + citation_count DESC, year DESC";
    params.push(`%${options.query}%`);
  }

  const selectColumns = `
    id, openalex_id, title, authors, abstract, doi, url, journal, year,
    institution, fields, paper_type, access_type, source, verified,
    citation_count, created_at
  `;

  const sql = `
    SELECT ${selectColumns}
    FROM papers p
    WHERE ${whereSql}
    ORDER BY ${orderBy}
    LIMIT ? OFFSET ?
  `;

  params.push(fetchLimit, offset);

  const db = getClient();
  let result;
  try {
    console.log("EXECUTING SQL:", sql);
    console.log("WITH ARGS:", params);
    result = await db.execute({ sql, args: params });
    console.log("RESULT ROWS:", result.rows.length);
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
    papers: visibleRows.map(normalizePaper),
    count,
    countMode,
    hasNextPage,
  };
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function getLocalPaperByKey(key: string): Promise<LocalPaperRow | null> {
  const decoded = decodeURIComponent(key);
  const selectColumns = `
    id, openalex_id, title, authors, abstract, doi, url, journal, year,
    institution, fields, paper_type, access_type, source, verified,
    citation_count, created_at
  `;

  const sql = UUID_RE.test(decoded)
    ? `SELECT ${selectColumns} FROM papers WHERE verified = 1 AND id = ? LIMIT 1`
    : `
      SELECT ${selectColumns}
      FROM papers
      WHERE verified = 1
        AND (
          lower(coalesce(doi, '')) = lower(?)
          OR openalex_id = ?
          OR replace(openalex_id, 'https://openalex.org/', '') = ?
        )
      LIMIT 1
    `;

  const db = getClient();
  const result = await db.execute({ sql, args: [decoded, decoded, decoded, decoded].slice(0, UUID_RE.test(decoded) ? 1 : 4) });
  return result.rows[0] ? normalizePaper(result.rows[0]) : null;
}

export async function getLocalPaperCount(): Promise<number> {
  return await getTotalPaperCount();
}

let cachedTypeCounts: { value: Record<string, number>; expiresAt: number } | null = null;

export async function getLocalTypeCounts(): Promise<Record<string, number>> {
  const now = Date.now();
  if (cachedTypeCounts && cachedTypeCounts.expiresAt > now) return cachedTypeCounts.value;
  
  const db = getClient();
  const result = await db.execute(`
    SELECT coalesce(paper_type, 'Other') AS paper_type, count(*) AS n
    FROM papers
    WHERE verified = 1
    GROUP BY 1
  `);
  
  const counts: Record<string, number> = {};
  for (const row of result.rows) counts[String(row.paper_type)] = Number(row.n);
  
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
