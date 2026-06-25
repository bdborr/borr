-- Migration: 03_production_openalex_multisource.sql
-- Description: Aligns production Supabase schema with the large OpenAlex corpus and prepares multi-source enrichment.

-- The app and local importer use OpenAlex IDs as durable IDs because DOI is often missing
-- and some DOI values appear on more than one OpenAlex work/version.
ALTER TABLE public.papers
ADD COLUMN IF NOT EXISTS openalex_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS papers_openalex_id_key
ON public.papers (openalex_id)
WHERE openalex_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS papers_openalex_short_idx
ON public.papers ((replace(openalex_id, 'https://openalex.org/', '')))
WHERE openalex_id IS NOT NULL;

-- Keep DOI indexed for lookup/dedupe. Do not drop the existing unique DOI constraint here;
-- loaders should null duplicate DOI values when importing OpenAlex rows into a DOI-unique database.
CREATE INDEX IF NOT EXISTS papers_doi_lower_idx
ON public.papers (lower(doi))
WHERE doi IS NOT NULL;

-- Multi-source metadata bookkeeping. `source` remains the primary/current source;
-- `sources` records all sources that have contributed metadata.
ALTER TABLE public.papers
ADD COLUMN IF NOT EXISTS external_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
ADD COLUMN IF NOT EXISTS sources TEXT[] NOT NULL DEFAULT '{}'::text[],
ADD COLUMN IF NOT EXISTS last_harvested_at TIMESTAMPTZ;

-- Extend the existing source enum for direct rows created by future fetchers.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_enum') THEN
        ALTER TYPE public.source_enum ADD VALUE IF NOT EXISTS 'Semantic Scholar';
        ALTER TYPE public.source_enum ADD VALUE IF NOT EXISTS 'arXiv';
        ALTER TYPE public.source_enum ADD VALUE IF NOT EXISTS 'DOAJ';
        ALTER TYPE public.source_enum ADD VALUE IF NOT EXISTS 'BASE';
    END IF;
END $$;

-- Optional audit/enrichment table: one paper can have records from many providers.
CREATE TABLE IF NOT EXISTS public.paper_source_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    paper_id UUID REFERENCES public.papers(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('OpenAlex', 'PubMed', 'Crossref', 'Semantic Scholar', 'arXiv', 'DOAJ', 'BASE', 'Manual', 'Community', 'Institutional Feed')),
    source_record_id TEXT NOT NULL,
    doi TEXT,
    title TEXT,
    year INTEGER,
    url TEXT,
    raw_metadata JSONB,
    harvested_at TIMESTAMPTZ DEFAULT timezone('utc'::text, now()),
    UNIQUE (source, source_record_id)
);

CREATE INDEX IF NOT EXISTS paper_source_records_paper_id_idx
ON public.paper_source_records (paper_id);

CREATE INDEX IF NOT EXISTS paper_source_records_doi_lower_idx
ON public.paper_source_records (lower(doi))
WHERE doi IS NOT NULL;

CREATE INDEX IF NOT EXISTS paper_source_records_source_idx
ON public.paper_source_records (source);
