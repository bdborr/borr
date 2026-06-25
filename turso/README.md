# BORR Turso Migration Guide

This guide covers everything you need to do tomorrow morning to finalize the migration from Supabase/Postgres to Turso/SQLite.

## 1. Create your Turso Account
1. Go to [turso.tech](https://turso.tech/) and sign up with GitHub.
2. Install the Turso CLI:
   ```bash
   # On macOS/Linux
   curl -sSfL https://get.tur.so/install.sh | bash
   ```
3. Authenticate the CLI:
   ```bash
   turso auth login
   ```

## 2. Create the Production Database
Create a database for BORR:
```bash
turso db create borr-db
```

Get your database URL (looks like `libsql://borr-db-yourusername.turso.io`):
```bash
turso db show borr-db --url
```

Get an auth token (this is your secret password, do not share it):
```bash
turso db tokens create borr-db
```

## 3. Push the Schema to Production
The schema is defined in `turso/schema.sql`. Apply it to your new production database:
```bash
turso db shell borr-db < turso/schema.sql
```

## 4. Setup Local Testing (Optional)
The data migration script `turso/migrate_from_postgres.py` exports your local 440k papers from Postgres into a local SQLite file `borr.db`. 

To test locally, your `.env.local` or `.env` should look like this:
```env
TURSO_DATABASE_URL=file:borr.db
# TURSO_AUTH_TOKEN is not needed for local file databases
```

Run the dev server to test search locally:
```bash
npm run dev
```

## 5. Migrate Data to Production
*Since you have 440k papers, the best way to move them to Turso is to use the Python migration script but pointing it at the production Turso DB URL instead of the local file. The `pipeline/main.py` harvester already has the logic for upserting to Turso using HTTP/Python.*

However, the fastest way to seed Turso is via Turso's native import if you have a SQL dump, or using the Turso CLI. Since you're running this locally, the easiest path is:
1. Copy the local `borr.db` we generated.
2. Use Turso's edge sync or write a small python script using `libsql-experimental` to batch push the records. 
*Note: Due to the FTS indexes and size (440k rows), doing this over HTTP might take an hour. Consider pushing the local SQLite file directly to Turso using `turso db create borr-db --from-file borr.db` if they support it on your tier.*

## 6. Update Vercel Secrets
When deploying to Vercel, you need to add these Environment Variables in your Vercel Project Settings:
- `TURSO_DATABASE_URL` (e.g. `libsql://borr-db-yourusername.turso.io`)
- `TURSO_AUTH_TOKEN` (the token you generated)
- `ADMIN_SECRET_KEY` (generate one with `openssl rand -hex 32`)

*Remove the old `NEXT_PUBLIC_SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` vars.*

## 7. Update GitHub Actions
Go to your GitHub Repo -> Settings -> Secrets and Variables -> Actions.
Add/Update:
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `NCBI_EMAIL`
- `NCBI_API_KEY`

The daily `automated-sync.yml` workflow will automatically use these to fetch from OpenAlex/PubMed and push to Turso.
