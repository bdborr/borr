# BORR deployment and data-completion plan

This document is the practical next-step plan for taking BORR from the fast local site to a deployed site with a larger, multi-source research database.

Current verified local state

- Local project: `/Users/nehalhasnain/Desktop/BORR PROJECT`
- Local database: `borr_local`
- Current local `papers` rows: 403,320
- Current local source coverage: OpenAlex only
- Rows with DOI: 371,195
- Rows with OpenAlex ID: 403,320
- Rows with abstract: 317,197
- Existing full OpenAlex JSONL backup: `data/openalex/local-test/borr_papers.harvested_403321.jsonl.gz`
- Local performance is already good after the previous optimization pass.

Recommended completion strategy

Use a two-layer data strategy:

1. Core corpus layer
   - OpenAlex is the backbone source because it already covers Bangladesh affiliation/title-abstract records at large scale and includes DOI, authors, institutions, fields, citation counts, open access, and abstracts for many records.
   - Production should first receive the existing ~403k OpenAlex corpus.

2. Enrichment / extra-source layer
   - PubMed, Crossref, Semantic Scholar, arXiv, DOAJ, and BASE should mostly enrich or add records that OpenAlex misses.
   - Do not put every provider into the main table as unrelated duplicates. Match by DOI first, then by external IDs, then by conservative title+year matching.
   - Store provider raw metadata in `paper_source_records` for auditability, while the public site reads the normalized `papers` table.

Phase 1 — Deploy the database schema

Apply migrations to production Supabase in this order:

```bash
cd "/Users/nehalhasnain/Desktop/BORR PROJECT"

# If using Supabase CLI linked to the production project:
supabase db push

# Or manually run SQL from these files in Supabase SQL Editor:
# supabase/migrations/00_init_papers.sql
# supabase/migrations/01_security_pipeline_fixes.sql
# supabase/migrations/02_search_performance_indexes.sql
# supabase/migrations/03_production_openalex_multisource.sql
```

Important production schema notes:

- `03_production_openalex_multisource.sql` adds `openalex_id`, `external_ids`, `sources`, `last_harvested_at`, and `paper_source_records`.
- The OpenAlex upload should upsert by `openalex_id`, not DOI, because DOI is missing in many records and duplicate DOI values exist across some OpenAlex records.
- If production already has many rows, take a Supabase backup before uploading 403k rows.

Phase 2 — Upload the existing OpenAlex corpus to production

Set secrets locally first. Do not commit these values.

```bash
cd "/Users/nehalhasnain/Desktop/BORR PROJECT"

export NEXT_PUBLIC_SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="YOUR-SERVICE-ROLE-KEY"
```

Dry-run a small slice:

```bash
python3 scripts/upsert_jsonl_to_supabase.py \
  data/openalex/local-test/borr_papers.harvested_403321.jsonl.gz \
  --dry-run \
  --max-lines 1200 \
  --batch-size 500 \
  --checkpoint /tmp/borr_openalex_upload_dryrun.json
```

Upload all rows:

```bash
python3 scripts/upsert_jsonl_to_supabase.py \
  data/openalex/local-test/borr_papers.harvested_403321.jsonl.gz \
  --batch-size 500 \
  --checkpoint data/openalex/checkpoints/supabase_upload.json
```

If the process stops, rerun the same command. It resumes from the checkpoint.

After upload, run in Supabase SQL Editor:

```sql
ANALYZE public.papers;

SELECT source, count(*)
FROM public.papers
GROUP BY source
ORDER BY count(*) DESC;

SELECT
  count(*) AS total,
  count(doi) AS with_doi,
  count(openalex_id) AS with_openalex_id,
  count(abstract) AS with_abstract
FROM public.papers;
```

Phase 3 — Deploy the Next.js site

Vercel is the simplest path for this Next.js app.

```bash
cd "/Users/nehalhasnain/Desktop/BORR PROJECT"

npm run lint
npm run build

# If Vercel CLI is installed and logged in:
vercel
vercel --prod
```

Required Vercel environment variables:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ADMIN_SECRET_KEY`
- `DATABASE_URL` only if the deployed site should use direct PostgreSQL instead of Supabase API. Usually leave this unset for Vercel unless you intentionally expose a pooled Postgres connection.

After deploy, test:

```bash
curl -w "home %{time_total}s\n" -o /dev/null -s https://YOUR-DOMAIN/
curl -w "search %{time_total}s\n" -o /dev/null -s "https://YOUR-DOMAIN/search?q=Bangladesh"
curl -w "goat %{time_total}s\n" -o /dev/null -s "https://YOUR-DOMAIN/search?q=goat"
```

Phase 4 — OpenAlex incremental harvesting

After the first 403k upload, use incremental API harvesting for new or missed OpenAlex rows.

Existing script:

```bash
python3 scripts/harvest_openalex_bangladesh.py --dry-run --max-records 1000
```

Production upsert:

```bash
python3 scripts/harvest_openalex_bangladesh.py --upsert
```

Recommended filters:

- `authorships.institutions.country_code:BD`
- `title_and_abstract.search:Bangladesh`
- optional additions later: Bangladesh-specific institution OpenAlex IDs, city names, district names, and Bangla-language/vernacular title terms.

Phase 5 — Multi-source harvesting design

Provider priority:

1. PubMed
   - Best for biomedical, public health, veterinary, AMR, infectious disease records.
   - API: NCBI E-utilities.
   - Needs `NCBI_EMAIL`; `NCBI_API_KEY` recommended.
   - Match keys: DOI, PMID.

2. Crossref
   - Best for DOI metadata and missing publisher fields.
   - API is public; use polite mailto in requests.
   - Match key: DOI.

3. Semantic Scholar
   - Best for citations, abstracts, fields, influential citations.
   - Public unauthenticated API is rate-limited; an API key is strongly recommended.
   - Match keys: DOI, Semantic Scholar paperId, externalIds.OpenAlex, PMID, ArXiv.

4. arXiv
   - Best for preprints.
   - API is public Atom feed.
   - Match keys: arXiv ID, DOI if available.

5. DOAJ
   - Best for open-access journal articles.
   - API is public.
   - Match keys: DOI, title+year.

6. BASE
   - Best for repository records/theses/grey literature.
   - Often requires registered API access or OAI-PMH endpoint configuration.
   - Treat as later-phase, not launch blocker.

Recommended normalized merge policy:

- If DOI exists and matches an existing paper: update missing fields and append source to `sources`.
- If OpenAlex ID exists and matches: update same row.
- If PMID/arXiv/S2 ID exists in `external_ids`: update same row.
- If no DOI/external ID: only merge on very conservative title normalization + same year; otherwise insert as unverified or keep only in `paper_source_records` for review.
- Prefer longer abstracts over shorter ones, but do not overwrite a good existing abstract with a blank one.
- Citation count should use the maximum known count or source-specific fields later.
- Keep raw provider records in `paper_source_records` for traceability.

Phase 6 — Automation

Use GitHub Actions for daily small syncs, not for first-time 403k uploads.

- First-time big upload: run locally or on a VPS because it can take a while and may need resuming.
- Daily incremental sync: GitHub Actions is OK.
- Required GitHub secrets:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `NCBI_EMAIL`
  - `NCBI_API_KEY` optional but recommended
  - `SEMANTIC_SCHOLAR_API_KEY` recommended

Suggested implementation order

1. Deploy schema migrations.
2. Upload the existing 403k OpenAlex corpus.
3. Deploy the Next.js site to Vercel.
4. Verify production search speed and row counts.
5. Add PubMed and Crossref enrichment first.
6. Add Semantic Scholar with an API key.
7. Add arXiv and DOAJ.
8. Add BASE after confirming API access.
9. Add dashboards/logs for harvest counts and failed records.

What is already added in this repo

- `supabase/migrations/03_production_openalex_multisource.sql`
  - Adds production fields and `paper_source_records` for multi-source metadata.

- `scripts/upsert_jsonl_to_supabase.py`
  - Uploads the existing large OpenAlex JSONL backup to Supabase by `openalex_id`.
  - Supports checkpoint resume.
  - Nulls later duplicate DOI values by default so production DOI uniqueness is less likely to block upload.

- `scripts/harvest_openalex_bangladesh.py`
  - Updated to include `openalex_id`, `external_ids`, `sources`, and `last_harvested_at`.
  - Updated to upsert by `openalex_id`.
