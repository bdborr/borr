-- Lean production schema for BORR (fits in a 1GB free Postgres instance, e.g. Aiven).
--
-- Differences from the full local schema:
--  - Only rows with a DOI are included (392,951 of 446,274) - a standard citable-record
--    quality bar that also gives headroom for years of incremental harvesting.
--  - abstract is truncated to ~200 characters (snippet + link to source for full text)
--  - fields/authors arrays are capped (top 8 / top 20) to bound row size from outlier rows
--  - drops external_ids/sources/last_harvested_at (multi-source bookkeeping, unused by
--    the app's read path; can be re-added later if the harvester needs them)
--  - drops papers_verified_title_prefix_idx (az-sort index); az sort still works, just
--    unindexed for full-corpus browsing without a search query
--  - drops the duplicate full-table search index (papers_search_idx in the original)
--    since every row is verified=true locally
--  - no Supabase-specific RLS policies (Aiven is plain Postgres; the app connects
--    with a single trusted role via DATABASE_URL)

CREATE TABLE IF NOT EXISTS public.papers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    openalex_id TEXT,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    search_vector tsvector
);

-- to_tsvector(regconfig, text) is STABLE, not IMMUTABLE, so search_vector can't be a
-- generated column in plain Postgres. Use a trigger instead (same approach as local db).
CREATE OR REPLACE FUNCTION public.papers_update_search_vector()
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

DROP TRIGGER IF EXISTS papers_search_vector_trigger ON public.papers;
CREATE TRIGGER papers_search_vector_trigger
    BEFORE INSERT OR UPDATE ON public.papers
    FOR EACH ROW
    EXECUTE FUNCTION public.papers_update_search_vector();

CREATE UNIQUE INDEX IF NOT EXISTS papers_openalex_id_key
    ON public.papers (openalex_id) WHERE openalex_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS papers_openalex_short_idx
    ON public.papers ((replace(openalex_id, 'https://openalex.org/', '')))
    WHERE openalex_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS papers_doi_lower_idx
    ON public.papers (lower(doi)) WHERE doi IS NOT NULL;

CREATE INDEX IF NOT EXISTS papers_search_idx
    ON public.papers USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS papers_verified_citations_idx
    ON public.papers (verified, citation_count DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS papers_verified_year_created_idx
    ON public.papers (verified, year DESC NULLS LAST, created_at DESC);

CREATE INDEX IF NOT EXISTS papers_fields_gin_idx
    ON public.papers USING GIN (fields);

CREATE INDEX IF NOT EXISTS papers_institution_gin_idx
    ON public.papers USING GIN (institution);
