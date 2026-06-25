CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS papers;

CREATE TABLE papers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  openalex_id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  authors TEXT[] NOT NULL DEFAULT '{}',
  abstract TEXT,
  doi TEXT,
  url TEXT,
  journal TEXT,
  year INTEGER,
  institution TEXT[] NOT NULL DEFAULT '{}',
  fields TEXT[] NOT NULL DEFAULT '{}',
  paper_type TEXT DEFAULT 'Other',
  access_type TEXT DEFAULT 'Unknown',
  source TEXT DEFAULT 'OpenAlex',
  verified BOOLEAN NOT NULL DEFAULT true,
  citation_count INTEGER DEFAULT 0,
  search_vector tsvector,
  created_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
  updated_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now())
);

-- openalex_id is the durable unique key. DOI is intentionally nullable and not
-- used as the primary dedupe key because many OpenAlex records have no DOI and
-- some DOI strings are duplicated across repository/version records.
CREATE INDEX papers_doi_lower_idx ON papers (lower(doi)) WHERE doi IS NOT NULL;
CREATE INDEX papers_search_idx ON papers USING GIN (search_vector);
CREATE INDEX papers_verified_year_idx ON papers (verified, year DESC NULLS LAST);
CREATE INDEX papers_verified_citations_idx ON papers (verified, citation_count DESC NULLS LAST);
CREATE INDEX papers_fields_gin_idx ON papers USING GIN (fields);
CREATE INDEX papers_institution_gin_idx ON papers USING GIN (institution);
CREATE INDEX papers_openalex_short_idx ON papers ((replace(openalex_id, 'https://openalex.org/', '')));

CREATE OR REPLACE FUNCTION papers_update_search_vector()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(NEW.abstract, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(array_to_string(NEW.authors, ' '), '')), 'C') ||
    setweight(to_tsvector('simple', coalesce(array_to_string(NEW.institution, ' '), '')), 'C');
  NEW.updated_at := timezone('utc'::text, now());
  RETURN NEW;
END;
$$;

CREATE TRIGGER papers_search_vector_trigger
BEFORE INSERT OR UPDATE ON papers
FOR EACH ROW
EXECUTE FUNCTION papers_update_search_vector();
