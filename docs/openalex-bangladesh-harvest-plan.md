# BORR OpenAlex Bangladesh harvest plan

Goal: build the BORR `papers` database without downloading the full OpenAlex snapshot to a 20 GB laptop.

## Do not mirror the snapshot locally

The OpenAlex works snapshot is hundreds of GiB compressed and much larger after decompression. A 20 GB laptop should not download it.

Use the OpenAlex API with server-side filters instead. OpenAlex sends only matching Bangladesh candidate records, and BORR maps those records directly into the `papers` table.

## What to harvest

Use these OpenAlex filters:

1. `authorships.institutions.country_code:BD`
   - papers with at least one Bangladesh-affiliated institution/author affiliation.

2. `title_and_abstract.search:Bangladesh`
   - papers about Bangladesh, even if the authors are outside Bangladesh.

`institutions.country_code:BD` currently returns the same count as `authorships.institutions.country_code:BD`, so the default script skips it to avoid duplicate API work.

The script also adds:

- `is_retracted:false`
- `to_publication_date:<today>`

This avoids retracted and future-dated records.

Important limitation: OpenAlex usually does not know author nationality. So “Bangladeshi author” can be harvested reliably only when the paper has a Bangladesh affiliation, Bangladesh institution, or Bangladesh-related title/abstract. A Bangladeshi national publishing with only a foreign affiliation is not reliably detectable from OpenAlex alone.

## Database schema

The project already has the compatible Supabase migration:

`supabase/migrations/00_init_papers.sql`

It creates:

- `papers.id UUID`
- `title TEXT`
- `authors TEXT[]`
- `abstract TEXT`
- `doi TEXT UNIQUE`
- `url TEXT`
- `journal TEXT`
- `year INTEGER`
- `institution TEXT[]`
- `fields TEXT[]`
- `paper_type paper_type_enum`
- `access_type access_type_enum`
- `source source_enum`
- `verified BOOLEAN DEFAULT false`
- `citation_count INTEGER`
- generated `search_vector TSVECTOR`
- GIN index on `search_vector`

Recommended future improvement: add `openalex_id TEXT UNIQUE`, because some Bangladesh records may not have DOI. The current safe upsert path uses DOI to avoid duplicates.

## Commands

From project root:

```bash
cd "/Users/nehalhasnain/Desktop/BORR PROJECT"
```

### 1. Tiny dry run

```bash
./venv/bin/python scripts/harvest_openalex_bangladesh.py \
  --dry-run \
  --no-resume \
  --max-records 1000 \
  --jsonl-out data/openalex/filtered/borr_papers.preview.jsonl
```

Inspect output:

```bash
wc -l data/openalex/filtered/borr_papers.preview.jsonl
```

### 2. Full dry run to JSONL only

This still does not download the snapshot. It saves only normalized matching rows.

```bash
./venv/bin/python scripts/harvest_openalex_bangladesh.py \
  --dry-run \
  --jsonl-out data/openalex/filtered/borr_papers.normalized.jsonl
```

The script writes a checkpoint to:

`data/openalex/checkpoints/bangladesh_openalex_api_checkpoint.json`

If interrupted, rerun the same command and it resumes.

### 3. Full Supabase upsert

Set credentials first:

```bash
export NEXT_PUBLIC_SUPABASE_URL="https://YOUR-PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="YOUR-SERVICE-ROLE-KEY"
```

Then run:

```bash
./venv/bin/python scripts/harvest_openalex_bangladesh.py --upsert
```

Run in background with logging:

```bash
mkdir -p logs
nohup ./venv/bin/python scripts/harvest_openalex_bangladesh.py --upsert \
  > logs/openalex_bangladesh_api_harvest.log 2>&1 &

tail -f logs/openalex_bangladesh_api_harvest.log
```

## Why this is cheap

- No cloud VM required.
- No 330+ GB / 595+ GB local snapshot download.
- No decompressed files stored.
- Local storage is only checkpoint + optional normalized JSONL.
- Supabase receives only BORR-relevant rows.

## Current script

`/Users/nehalhasnain/Desktop/BORR PROJECT/scripts/harvest_openalex_bangladesh.py`

Verified with:

```bash
./venv/bin/python -m py_compile scripts/harvest_openalex_bangladesh.py
./venv/bin/python scripts/harvest_openalex_bangladesh.py --dry-run --no-resume --max-records 10 --jsonl-out data/openalex/filtered/borr_papers.preview2.jsonl
```

The test fetched one OpenAlex API page and wrote 200 normalized BORR-compatible rows.
