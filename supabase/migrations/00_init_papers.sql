-- Migration: 00_init_papers.sql
-- Description: Creates the papers table, enums, indexes, RLS policies, and search vector for BORR.

-- Create Enums
CREATE TYPE paper_type_enum AS ENUM ('Journal Article', 'Review', 'Conference', 'Preprint', 'Thesis', 'Book Chapter', 'Other');
CREATE TYPE access_type_enum AS ENUM ('Open Access', 'Free', 'Paywalled', 'Unknown');
CREATE TYPE source_enum AS ENUM ('OpenAlex', 'PubMed', 'Crossref', 'Manual', 'Community', 'Institutional Feed');

-- Create Papers Table
CREATE TABLE IF NOT EXISTS public.papers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT[] NOT NULL DEFAULT '{}',
    abstract TEXT,
    doi TEXT UNIQUE,
    url TEXT,
    journal TEXT,
    year INTEGER,
    institution TEXT[] DEFAULT '{}',
    fields TEXT[] DEFAULT '{}',
    paper_type paper_type_enum DEFAULT 'Other',
    access_type access_type_enum DEFAULT 'Unknown',
    source source_enum DEFAULT 'Manual',
    verified BOOLEAN DEFAULT false,
    citation_count INTEGER DEFAULT 0,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(abstract, '') || ' ' || coalesce(array_to_string(authors, ' '), ''))
    ) STORED,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Indexes
CREATE INDEX IF NOT EXISTS papers_search_idx ON public.papers USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS papers_verified_year_idx ON public.papers (verified, year DESC);
CREATE INDEX IF NOT EXISTS papers_verified_citations_idx ON public.papers (verified, citation_count DESC);
CREATE INDEX IF NOT EXISTS papers_fields_gin_idx ON public.papers USING GIN (fields);
CREATE INDEX IF NOT EXISTS papers_institution_gin_idx ON public.papers USING GIN (institution);
CREATE UNIQUE INDEX IF NOT EXISTS papers_doi_lower_unique ON public.papers (lower(doi)) WHERE doi IS NOT NULL;

-- Enable Row Level Security
ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;

-- Public read access only for moderated/verified records.
CREATE POLICY "Public can read verified papers"
ON public.papers FOR SELECT
USING (verified = true);

-- Authenticated users may submit unverified papers only. The public web API uses
-- the service-role client server-side and forces verified=false as well.
CREATE POLICY "Authenticated users can insert unverified papers"
ON public.papers FOR INSERT
WITH CHECK (auth.role() = 'authenticated' AND verified = false);

-- Service role can update or delete for admin moderation and harvesters.
CREATE POLICY "Service role can update papers"
ON public.papers FOR UPDATE
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can delete papers"
ON public.papers FOR DELETE
USING (auth.role() = 'service_role');

-- Trigger to auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$;

CREATE TRIGGER papers_updated_at
    BEFORE UPDATE ON public.papers
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();
