# BORR - Bangladesh Open Research Repository

**"Research for a Better Bangladesh."**

BORR is an open-source, metadata-only repository indexing research papers by Bangladeshi authors, institutions, or about Bangladesh. It functions like Google Scholar scoped to Bangladesh, aiming to centralize and make discoverable the nation's research output.

## Features
- **Centralized Search**: Search by title, author, institution, and keyword across all Bangladeshi research.
- **Automated Harvester**: Daily indexing from the OpenAlex API to keep the repository up-to-date.
- **Community Submissions**: Researchers can submit their DOIs to have their work indexed.
- **Open Metadata**: Metadata is free and open to all (CC0).
- **SEO & Discoverability**: Semantic HTML and Schema.org markup ensures papers rank well on search engines.

## Tech Stack
- Next.js 14 (App Router)
- Tailwind CSS
- Supabase (PostgreSQL + RLS)
- Python (Harvester Script)

## Local Setup

### 1. Prerequisites
- Node.js 18+
- Python 3.11+
- A Supabase Project

### 2. Install Dependencies
```bash
npm install
```

### 3. Environment Variables
Copy the example file and populate with your Supabase credentials:
```bash
cp .env.example .env.local
```
Add:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (Only needed for the harvester script)

### 4. Database Setup
Run the SQL migration file in your Supabase SQL editor:
`supabase/migrations/00_init_papers.sql`

### 5. Run Development Server
```bash
npm run dev
```

## Contributing
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to the codebase.

## License
MIT License. The data itself is released under the CC0 Public Domain Dedication.
