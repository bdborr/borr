-- Migration: 01_security_pipeline_fixes.sql
-- Description: Applies security and pipeline fixes to existing BORR databases.

ALTER TYPE source_enum ADD VALUE IF NOT EXISTS 'PubMed';

DROP POLICY IF EXISTS "Public profiles are viewable by everyone." ON public.papers;
DROP POLICY IF EXISTS "Public can read verified papers" ON public.papers;
DROP POLICY IF EXISTS "Authenticated users can insert papers" ON public.papers;
DROP POLICY IF EXISTS "Authenticated users can insert unverified papers" ON public.papers;
DROP POLICY IF EXISTS "Service role can update" ON public.papers;
DROP POLICY IF EXISTS "Service role can update papers" ON public.papers;
DROP POLICY IF EXISTS "Service role can delete" ON public.papers;
DROP POLICY IF EXISTS "Service role can delete papers" ON public.papers;

ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can read verified papers"
ON public.papers FOR SELECT
USING (verified = true);

CREATE POLICY "Authenticated users can insert unverified papers"
ON public.papers FOR INSERT
WITH CHECK (auth.role() = 'authenticated' AND verified = false);

CREATE POLICY "Service role can update papers"
ON public.papers FOR UPDATE
USING (auth.role() = 'service_role')
WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "Service role can delete papers"
ON public.papers FOR DELETE
USING (auth.role() = 'service_role');

CREATE INDEX IF NOT EXISTS papers_verified_year_idx ON public.papers (verified, year DESC);
CREATE INDEX IF NOT EXISTS papers_verified_citations_idx ON public.papers (verified, citation_count DESC);
CREATE INDEX IF NOT EXISTS papers_fields_gin_idx ON public.papers USING GIN (fields);
CREATE INDEX IF NOT EXISTS papers_institution_gin_idx ON public.papers USING GIN (institution);
CREATE UNIQUE INDEX IF NOT EXISTS papers_doi_lower_unique ON public.papers (lower(doi)) WHERE doi IS NOT NULL;

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
