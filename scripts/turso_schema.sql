-- Turso schema for BORR (libSQL-compatible, no FTS5 virtual tables).
-- Search is done via LIKE on a combined search_text column.

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    openalex_id TEXT UNIQUE,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '[]',
    abstract TEXT,
    doi TEXT,
    url TEXT,
    journal TEXT,
    year INTEGER,
    institution TEXT DEFAULT '[]',
    fields TEXT DEFAULT '[]',
    paper_type TEXT DEFAULT 'Other',
    access_type TEXT DEFAULT 'Unknown',
    source TEXT DEFAULT 'Manual',
    verified INTEGER DEFAULT 0,
    citation_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    external_ids TEXT NOT NULL DEFAULT '{}',
    sources TEXT NOT NULL DEFAULT '[]',
    last_harvested_at TEXT,
    authors_text TEXT,
    institution_text TEXT,
    search_text TEXT
);

CREATE INDEX IF NOT EXISTS papers_verified_year_idx ON papers (verified, year DESC);
CREATE INDEX IF NOT EXISTS papers_verified_citations_idx ON papers (verified, citation_count DESC);
CREATE INDEX IF NOT EXISTS papers_doi_lower_idx ON papers (lower(doi)) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS papers_openalex_short_idx ON papers (replace(openalex_id, 'https://openalex.org/', '')) WHERE openalex_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS papers_search_text_idx ON papers (search_text);
