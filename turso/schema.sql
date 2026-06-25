-- Migration: BORR Turso Schema
-- Description: Creates the papers table, FTS index, and triggers for BORR.

-- Create Papers Table
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY, -- UUIDs stored as hex strings
    openalex_id TEXT UNIQUE,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '[]', -- JSON array
    abstract TEXT,
    doi TEXT,
    url TEXT,
    journal TEXT,
    year INTEGER,
    institution TEXT DEFAULT '[]', -- JSON array
    fields TEXT DEFAULT '[]', -- JSON array
    paper_type TEXT DEFAULT 'Other' CHECK (paper_type IN ('Journal Article', 'Review', 'Conference', 'Preprint', 'Thesis', 'Book Chapter', 'Other')),
    access_type TEXT DEFAULT 'Unknown' CHECK (access_type IN ('Open Access', 'Free', 'Paywalled', 'Unknown')),
    source TEXT DEFAULT 'Manual' CHECK (source IN ('OpenAlex', 'PubMed', 'Crossref', 'Manual', 'Community', 'Institutional Feed', 'Semantic Scholar', 'arXiv', 'DOAJ', 'BASE')),
    verified INTEGER DEFAULT 0 CHECK (verified IN (0, 1)),
    citation_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    external_ids TEXT NOT NULL DEFAULT '{}', -- JSON object
    sources TEXT NOT NULL DEFAULT '[]', -- JSON array
    last_harvested_at TEXT,
    authors_text TEXT, -- Space-separated author names for FTS
    institution_text TEXT -- Space-separated institution names for search
);

-- Indexes
CREATE INDEX IF NOT EXISTS papers_verified_year_idx ON papers (verified, year DESC);
CREATE INDEX IF NOT EXISTS papers_verified_citations_idx ON papers (verified, citation_count DESC);
CREATE INDEX IF NOT EXISTS papers_doi_lower_idx ON papers (lower(doi)) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS papers_openalex_short_idx ON papers (replace(openalex_id, 'https://openalex.org/', '')) WHERE openalex_id IS NOT NULL;

-- Create FTS Virtual Table
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    abstract,
    authors_text,
    content='papers',
    content_rowid='rowid'
);

-- Triggers to keep FTS table in sync
CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, abstract, authors_text)
    VALUES (new.rowid, new.title, new.abstract, new.authors_text);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, authors_text)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.authors_text);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract, authors_text)
    VALUES ('delete', old.rowid, old.title, old.abstract, old.authors_text);
    INSERT INTO papers_fts(rowid, title, abstract, authors_text)
    VALUES (new.rowid, new.title, new.abstract, new.authors_text);
END;

-- Trigger to auto-update updated_at on row modification
CREATE TRIGGER IF NOT EXISTS papers_updated_at AFTER UPDATE ON papers BEGIN
    UPDATE papers SET updated_at = CURRENT_TIMESTAMP WHERE rowid = new.rowid;
END;

-- Create Paper Source Records Table
CREATE TABLE IF NOT EXISTS paper_source_records (
    id TEXT PRIMARY KEY,
    paper_id TEXT REFERENCES papers(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('OpenAlex', 'PubMed', 'Crossref', 'Semantic Scholar', 'arXiv', 'DOAJ', 'BASE', 'Manual', 'Community', 'Institutional Feed')),
    source_record_id TEXT NOT NULL,
    doi TEXT,
    title TEXT,
    year INTEGER,
    url TEXT,
    raw_metadata TEXT, -- JSON
    harvested_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source, source_record_id)
);

CREATE INDEX IF NOT EXISTS paper_source_records_paper_id_idx ON paper_source_records (paper_id);
CREATE INDEX IF NOT EXISTS paper_source_records_doi_lower_idx ON paper_source_records (lower(doi)) WHERE doi IS NOT NULL;
CREATE INDEX IF NOT EXISTS paper_source_records_source_idx ON paper_source_records (source);
