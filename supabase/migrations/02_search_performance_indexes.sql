-- Migration: 02_search_performance_indexes.sql
-- Description: Adds read-path indexes needed once BORR has hundreds of thousands of OpenAlex rows.

-- Speeds /search?sort=az and title-ordered pagination for verified public papers.
-- Use a prefix expression instead of the full title because some OpenAlex titles are
-- longer than PostgreSQL's maximum btree index row size.
CREATE INDEX IF NOT EXISTS papers_verified_title_prefix_idx
ON public.papers (verified, left(title, 512));

-- Speeds newest sorting when many papers have the same year.
CREATE INDEX IF NOT EXISTS papers_verified_year_created_idx
ON public.papers (verified, year DESC NULLS LAST, created_at DESC);

-- Smaller GIN index for public search queries. The full papers_search_idx remains useful
-- for admin/unverified workflows, but public search always has verified=true.
CREATE INDEX IF NOT EXISTS papers_verified_search_idx
ON public.papers USING GIN (search_vector)
WHERE verified = true;
