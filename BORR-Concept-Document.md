**BORR**

**Bangladesh Open Research Repository**

*"Research for Better Bangladesh."*

Product Concept, Build Document & Legal Framework  ·  v1.0

| Project Name | BORR — Bangladesh Open Research Repository |
| :---- | :---- |
| **Tagline** | Research for Better Bangladesh. |
| **Type** | Open-Source Web Application — Metadata Repository |
| **Long-Term Vision** | BORR Archive \+ BORR Academy — Bangladesh as a research & education leader |
| **License** | MIT License (software) · CC-BY 4.0 (metadata) |
| **Model** | Metadata-only. All papers link to original publishers. No PDFs hosted. |
| **Governed by** | Bangladesh Open Research Foundation (to be established) |

# **1\. Mission, Vision & Values**

## **Mission**

BORR exists to make all research from Bangladesh — and about Bangladesh — discoverable, accessible, and free for anyone in the world to find. We aggregate all research metadata from global publishers into a single, searchable, open platform maintained by and for the people of Bangladesh.

## **Vision**

***To make Bangladesh a global leader in research and education by 2035\. A country whose knowledge output is as celebrated as its people, its rivers, and its resilience.***


## **Core Values**

* Openness — All metadata is freely accessible. The platform itself is open-source forever.

* Accuracy — Human verification of community submissions. No hallucinated records.

* Inclusivity — Every Bangladeshi institution, from BUET to rural colleges, is equally represented.

* Sovereignty — Bangladeshi researchers own their narrative. BORR is built for them, not about them.

* Longevity — Built to last decades, not just a project. BORR is infrastructure, not a product.

* Accessibility — WCAG 2.1 AA compliant. The platform works for people with disabilities and on low-bandwidth connections common in rural Bangladesh.

* Performance — Search results in < 500ms, page load < 2s, support 100+ concurrent users. BORR must feel fast even on 3G connections.

# **2\. What Is BORR?**

BORR (Bangladesh Open Research Repository) is an open-source, searchable metadata repository of research papers that meet at least one of these criteria:

* Authored by Bangladeshi researchers (regardless of where they work globally)

* Published by Bangladeshi institutions or journals

* About Bangladesh as a subject — geography, society, ecology, health, economy, language, culture, etc.

BORR works like Google Scholar, scoped entirely to Bangladesh. The platform stores metadata only — title, authors, abstract, DOI, institution, journal, year, keywords, and a link. Clicking a paper takes the user to the original publisher. BORR never hosts copyrighted PDFs.

| What BORR IS A searchable metadata index A discovery and aggregation layer A link-out platform to publishers An open-source community project A tool for researchers, students & policymakers The foundation for BORR Academy | What BORR is NOT A PDF hosting platform A journal or publisher A paywall bypasser or piracy tool A proprietary or closed system A replacement for publishers A for-profit service |
| :---- | :---- |

# **3\. The Problem BORR Solves**

Bangladesh produces thousands of research papers annually across medicine, agriculture, engineering, climate science, social sciences, and more. Yet they are scattered across hundreds of publisher websites, institutional repositories, and preprint servers. There is no single place to:

* Search all Bangladeshi research at once

* Discover what has been published about a Bangladesh-specific topic

* Find a researcher's full output if you only know their name

* Track which institutions lead in which fields

* Share Bangladesh-specific research with the diaspora or policymakers

* Build on the existing body of Bangladeshi knowledge systematically

The result: duplicated research efforts, invisible scholars, missed citations, and a fragmented national knowledge base. BORR fixes this by being the missing front page for Bangladeshi science.

# **4\. Who Uses BORR?**

| User Type | How They Use BORR |
| :---- | :---- |
| **Bangladeshi Researchers** | Find related work; avoid duplication; discover collaborators; build their scholarly profile |
| **Graduate Students** | Literature reviews; finding citations; exploring the state of their field within Bangladesh |
| **International Researchers** | Discover Bangladesh-focused studies; identify local co-authors; access ground-truth data |
| **Bangladeshi Diaspora** | Stay connected to knowledge from home; discover opportunities to contribute remotely |
| **Journalists & Media** | Find evidence-based sources on Bangladesh topics; cite authoritative local research |
| **Policymakers & NGOs** | Access data and findings directly relevant to Bangladesh's development challenges |
| **Universities & Institutions** | Showcase research output; benchmark departments; demonstrate impact to funders |
| **BORR Academy (Future)** | Curated reading lists; course materials; research training linked directly to papers |

# **5\. Data Model — What Gets Stored**

Every paper in BORR is a metadata record. No PDFs are stored. The PostgreSQL schema:

| Field | Data Type | Description |
| :---- | :---- | :---- |
| **id** | UUID | Auto-generated unique identifier |
| **title** | TEXT | Full paper title |
| **authors** | TEXT\[\] | Array of author full names |
| **abstract** | TEXT | Full abstract — indexed for search |
| **doi** | TEXT UNIQUE | Digital Object Identifier (primary dedup key) |
| **url** | TEXT | Direct link to publisher page |
| **journal** | TEXT | Journal or conference/proceedings name |
| **year** | INTEGER | Year of publication |
| **institution** | TEXT\[\] | Author affiliations |
| **fields** | TEXT\[\] | Research disciplines and keyword tags |
| **paper\_type** | TEXT (CHECK) | Journal Article · Review · Conference · Preprint · Thesis · Book Chapter |
| **access\_type** | TEXT (CHECK) | Open Access · Free · Paywalled (clearly labelled) |
| **source** | TEXT (CHECK) | How added: OpenAlex · Crossref · Manual · Community · Institutional Feed |
| **verified** | BOOLEAN | Has a human moderator verified this record? |
| **citation\_count** | INTEGER | Pulled from OpenAlex / Semantic Scholar (updated weekly) |
| **search\_vector** | TSVECTOR | Generated column from title \+ abstract \+ authors — GIN indexed |
| **created\_at** | TIMESTAMP | When the record was first indexed |
| **updated\_at** | TIMESTAMP | Last time the record was refreshed from source API |

# **6\. Data Sources**

## **6.1 Automated API Harvesting (Primary)**

| API | Coverage | Bangladesh Filter | Cost |
| :---- | :---- | :---- | :---- |
| **OpenAlex ★** | 480M+ papers | country\_code:BD on institution | **Free — Recommended** |
| Crossref | 150M+ DOIs | Affiliation country filter | Free |
| Semantic Scholar | 200M+ papers | Keyword \+ affiliation | Free (rate limited) |
| PubMed | Medical/bio | Affiliation: Bangladesh | Free |
| arXiv | STEM preprints | Author affiliation search | Free |
| DOAJ | OA journals | Bangladesh publisher filter | Free |
| BASE | 300M+ docs | Country & institution filter | Free |

| 💡 Recommended First API Call (OpenAlex) GET https://api.openalex.org/works?filter=authorships.institutions.country\_code:BD\&per\_page=200\&cursor=\* Returns: title, abstract, authors, DOI, year, citations, open-access status. Paginate using cursor for all records. Pair with filter=concepts.display\_name:Bangladesh for topic-based papers. |
| :---- |

## **6.2 Community Submissions**

Any registered user may submit a paper. They enter the DOI; BORR auto-fetches metadata from Crossref. The submitter confirms accuracy, attests the paper is open access, and submits. Records enter a moderation queue before going live.

## **6.3 Institutional Direct Feeds (Phase 2\)**

Bangladeshi universities, journals, and research bodies (BUET, DU, SAU, BRAC University, ICDDR,B, BARI, BRRI, etc.) may submit bulk CSV or JSON metadata exports. A dedicated institutional onboarding guide will be provided.

# **7\. Core Features**

## **Phase 1 — BORR Archive (Launch)**

* Live full-text search: title, abstract, authors, institution, journal, fields

* Filters: Research Field · Year · Paper Type · Institution · Access Type

* Sort: Most Cited · Newest · Oldest · A–Z

* Keyword highlighting in search results

* Bangla script search support (Unicode-safe) *— requires pgroonga extension; PostgreSQL tsvector does not natively support Bengali script*

* Paper cards: title link, authors, institution, journal, year, abstract toggle, badges, citation count

* Community submission form (DOI → auto-fill → moderation)

* Admin moderation panel (approve / reject / flag submissions)

* About page, GitHub link, contributor guide

* SEO: schema.org metadata, sitemap, Open Graph tags for every paper

## **Phase 2 — BORR Profiles & API**

* Auto-generated author profile pages: all papers, total citations, h-index, active fields *(ORCID integration planned to resolve same-name author collisions)*

* Auto-generated institution pages: output charts, top authors, top fields

* Open REST API: GET /papers?q=arsenic\&field=public-health (free, no key required, rate limited to 100 req/min per IP)

* Bangla-language UI option

* Email digest: subscribe to new papers in a field

## **Phase 3 — BORR Academy (Future)**

* Free structured learning paths built on top of real BORR research papers

* Course modules: How to Read a Paper · How to Write a Literature Review · Research Methods in Bangladesh Context

* Mentorship directory: connect junior researchers with senior Bangladeshi academics

* Research grant directory: curated list of funding opportunities for Bangladeshi researchers

* Collaboration board: researchers post project ideas and find co-authors through BORR

# **8\. Recommended Tech Stack**

| Layer | Technology | Reason |
| :---- | :---- | :---- |
| **Frontend** | **Next.js 14 (TypeScript)** | SSR for SEO, App Router, fast page loads for paper detail pages |
| **Styling** | **Tailwind CSS** | Rapid, consistent UI; great AI tool support |
| **Database** | **PostgreSQL via Supabase** | Free tier, native full-text search (tsvector \+ GIN), Row Level Security |
| **Search Engine** | **tsvector \+ pgvector** | Keyword search now; semantic/AI search later via embeddings |
| **Backend API** | **Next.js API Routes** | Same codebase; no separate server needed for MVP |
| **Data Harvester** | **Python (scheduled script)** | Calls OpenAlex, Crossref; runs daily via GitHub Actions |
| **Auth** | **Supabase Auth** | Handles community submissions, admin panel, future Academy accounts |
| **Frontend Host** | **Vercel** | Free tier, auto-deploy from GitHub, edge CDN globally |
| **DB Host** | **Supabase** | Free tier: 500MB, 2 projects, REST \+ realtime \+ storage |
| **CI/CD** | **GitHub Actions** | Daily harvest cron \+ auto-deploy on push to main |
| **Repo** | **GitHub (public, MIT)** | Open-source from day one; community contributions via PR |

# **9\. Build Roadmap**

| Phase | Title | Key Tasks | Timeline |
| ----- | :---- | :---- | ----- |
| **Phase 1** | **BORR Archive** | Set up Next.js 14 \+ Supabase project on GitHub Create papers table with tsvector full-text search index Build OpenAlex harvester (Python) — seed 1,000+ papers *Note: Phase 1 launches with OpenAlex-only harvesting. Crossref, Semantic Scholar, and other sources are added in Phase 2.* Build search UI with filters, sort, keyword highlighting Deploy to Vercel; public GitHub repo with MIT license \+ README | **Weeks 1–3** |
| **Phase 2** | **Full Experience** | Paper detail pages (/paper/\[doi\]) with full metadata Community submission form (DOI → Crossref auto-fill → moderation) Admin panel (approve/reject submissions) SEO: schema.org, sitemap, Open Graph for every paper Bangla search support (*requires pgroonga extension or custom Bengali tokenizer — PostgreSQL tsvector does not natively support Bengali script*); mobile-responsive UI | **Weeks 4–7** |
| **Phase 3** | **Profiles & API** | Author profile pages (auto-generated from papers table) *Include ORCID integration for author disambiguation — same-name researchers will otherwise create duplicate profiles.* Institution pages with output charts Open REST API with documentation (*rate limit: 100 req/min per IP*) Citation count updates (weekly via OpenAlex) Email digest for new papers by field | **Weeks 8–12** |
| **Phase 4** | **BORR Academy** | Design Academy learning path schema Build course module viewer linked to BORR papers Mentorship directory and collaboration board Research grant directory for Bangladeshi researchers Community governance: BORR Foundation setup | **Months 4–6+** |

# **10\. AI Build Prompt**

Copy the following prompt and paste it into Claude Code, Cursor, or any AI coding tool to begin building BORR immediately:

| AI CODING TOOL PROMPT Build BORR (Bangladesh Open Research Repository) — an open-source metadata repository of research papers by Bangladeshi authors, institutions, or about Bangladesh. It is like Google Scholar scoped to Bangladesh. Metadata only — no PDFs hosted. All papers link out to original publishers. Tech Stack: Next.js 14 (App Router, TypeScript) · Tailwind CSS · Supabase (PostgreSQL \+ Auth) · Vercel hosting · Python harvester script Database table (papers): id UUID, title TEXT, authors TEXT\[\], abstract TEXT, doi TEXT UNIQUE, url TEXT, journal TEXT, year INTEGER, institution TEXT\[\], fields TEXT\[\], paper\_type TEXT, access\_type TEXT, source TEXT, verified BOOLEAN DEFAULT false, citation\_count INTEGER, search\_vector TSVECTOR generated from (title || ' ' || abstract || ' ' || array\_to\_string(authors,' ')), created\_at TIMESTAMP — add GIN index on search\_vector Pages: / (homepage: hero, search bar, stats) · /search (results \+ filters: field/year/type/institution \+ sort: cited/newest/AZ \+ keyword highlighting) · /paper/\[doi\] (full metadata \+ 'Read at Publisher' button) · /submit (DOI → Crossref auto-fill → moderation queue) · /admin (approve/reject submissions — protected) · /about (mission, BORR Academy vision, data sources, GitHub link) Harvester (scripts/harvest.py): Call https://api.openalex.org/works?filter=authorships.institutions.country\_code:BD\&per\_page=200\&cursor=\* — paginate all results — upsert into Supabase on doi conflict — also call ?filter=concepts.display\_name:Bangladesh — schedule via GitHub Actions daily cron BORR branding: Project name is BORR — Bangladesh Open Research Repository. Tagline: ' Research for a Better Bangladesh.' Navy blue (\#1E3A5F) \+ blue (\#2563EB) color palette. Mention future BORR Academy on About page. Key requirements: MIT license in repo · README with setup instructions · CONTRIBUTING.md · Bangla script search support · mobile-responsive · SEO (schema.org Article markup on paper pages) · no PDFs ever stored |
| :---- |

# **11\. Open-Source Repository Structure**

| GitHub Repository: github.com/BORR-archive/BORR  (suggested) BORR/   ├── app/                     — Next.js App Router   │   ├── page.tsx             — Homepage (hero \+ search)   │   ├── search/page.tsx      — Search results page   │   ├── paper/\[doi\]/page.tsx — Paper detail page   │   ├── submit/page.tsx      — Community submission form   │   ├── admin/page.tsx       — Moderation panel (protected)   │   └── about/page.tsx       — Mission \+ BORR Academy vision   ├── components/              — Reusable UI components   │   ├── PaperCard.tsx        — Search result card   │   ├── SearchBar.tsx        — Main search input   │   ├── FilterPanel.tsx      — Filter dropdowns   │   └── Badge.tsx            — Field / access type badges   ├── lib/                     — Shared utilities   │   ├── supabase.ts          — Supabase client   │   ├── search.ts            — Full-text search query builder   │   └── openalex.ts          — OpenAlex API client   ├── scripts/                 — Data pipeline   │   ├── harvest.py           — OpenAlex \+ Crossref harvester   │   └── clean.py             — Data cleaning utilities   ├── supabase/                — Database   │   └── migrations/          — SQL migration files   ├── .github/workflows/       — GitHub Actions   │   ├── harvest.yml          — Daily cron harvester   │   └── deploy.yml           — Auto-deploy on push   ├── README.md                — Setup, architecture, contributing   ├── CONTRIBUTING.md          — Contribution guidelines   ├── CODE\_OF\_CONDUCT.md       — Community standards   ├── LICENSE                  — MIT License   └── .env.example             — Required environment variables |
| :---- |

# **12\. Terms and Conditions**

**BORR — Bangladesh Open Research Repository**

Effective Date: To be set on public launch  ·  Last Updated: Version 1.0

By accessing or using the BORR platform ("the Service"), you agree to be bound by these Terms and Conditions. If you do not agree, you must not use the Service.

## **12.1 Nature of the Service**

BORR is a free, open-source, metadata-only research discovery platform. BORR does not host, distribute, or make available any copyrighted research papers or PDFs. All paper content remains on the servers of the original publishers. BORR provides links (URLs and DOIs) to those original sources only.

## **12.2 Eligibility**

BORR is open to all users worldwide. There is no registration required to search or browse. Registration (via email or institutional account) is required to submit papers for indexing or to contribute to the platform.

## **12.3 User Conduct**

By using BORR you agree that you will not:

* Attempt to scrape, crawl, or bulk-download BORR data in a manner that disrupts service for other users

* Submit false, misleading, or fabricated paper metadata

* Submit papers you do not have the right to submit (e.g. claiming open access for a paywalled paper)

* Use BORR to harass, defame, or misrepresent any researcher or institution

* Attempt to gain unauthorized access to BORR's systems, admin panels, or database

* Use BORR data to train commercial AI models without attribution (see Section 14 — CC-BY 4.0 license requires attribution)

## **12.4 Community Submissions**

Users who submit paper metadata to BORR represent and warrant that:

* The paper exists and the metadata submitted is accurate to the best of their knowledge

* The paper is genuinely open access or freely available to read at the linked URL

* The submission is relevant to BORR's scope (Bangladeshi author, institution, or subject)

BORR reserves the right to reject, edit, or remove any submission that does not meet these criteria. Repeat submitters of inaccurate data may have their submission access revoked.

### **Rejection Criteria**

Submissions are automatically rejected or flagged for manual review if:

* The DOI does not resolve in Crossref or OpenAlex
* The paper has no Bangladeshi author, institution, or subject relevance
* The paper is paywalled but submitted as Open Access
* The metadata appears fabricated (e.g., mismatched title/DOI, impossible publication dates)

### **Moderation SLA**

* All submissions are reviewed within **48 hours** of submission
* Moderators approve, reject, or request corrections with written feedback
* Submitters are notified via email of the decision

### **Moderator Onboarding**

* Moderators are trusted community members nominated by existing moderators and approved by the BORR steering committee
* New moderators complete a brief training guide on BORR's scope and quality standards
* Moderators may appeal decisions to the steering committee; repeat poor moderation quality results in review

## **12.5 Intellectual Property**

BORR's software is licensed under the MIT License and is free to use, modify, and redistribute. The BORR metadata database (titles, abstracts, author names, DOIs, etc.) is released under the Creative Commons CC-BY 4.0 International License — it is freely usable by anyone for any purpose, provided proper attribution is given to BORR and the original sources.

BORR does not claim ownership of any research paper, author name, institutional name, or journal name indexed in its database. All such intellectual property remains with the original authors, institutions, and publishers.

## **12.6 Disclaimer of Warranties**

BORR is provided "as is" and "as available" without any warranty of any kind, express or implied. BORR makes no warranty that:

* The service will be uninterrupted, error-free, or secure

* The metadata in the database is complete, accurate, or up to date

* Any linked publisher URL will remain active or accessible

Users are responsible for independently verifying information found on BORR before using it for academic, medical, legal, or policy purposes.

## **12.7 Limitation of Liability**

To the maximum extent permitted by law, BORR, its contributors, and maintainers shall not be liable for any indirect, incidental, special, consequential, or punitive damages arising from use of the Service, including but not limited to reliance on inaccurate metadata, broken publisher links, or service downtime.

## **12.8 Takedown & Removal Requests**

Authors, institutions, or publishers who wish to have a metadata record removed from BORR may submit a removal request to the contact address published on the BORR website. BORR will process valid removal requests within 14 business days. A request is considered valid when submitted by a verified author of the paper or an authorized representative of the publisher.

## **12.9 Changes to Terms**

BORR reserves the right to modify these Terms at any time. Changes will be posted on the website with a revised effective date. Continued use of the Service after the effective date constitutes acceptance of the revised Terms.

## **12.10 Governing Jurisdiction**

These Terms are governed by the laws of Bangladesh. Any disputes arising under these Terms shall be subject to the exclusive jurisdiction of the courts of Dhaka, Bangladesh.

## **12.11 Contact**

For questions about these Terms, to report misuse, or to submit a takedown request: contact@BORR.org.bd (placeholder — update before launch)

# **13\. Privacy Policy**

**BORR — Bangladesh Open Research Repository**

Effective Date: To be set on public launch  ·  Last Updated: Version 1.0

This Privacy Policy explains what data BORR collects, how it is used, and your rights regarding that data. BORR is committed to handling all personal data responsibly and transparently.

## **13.1 What Data BORR Collects**

### **A. Visitors (no account required)**

* BORR does not require an account to search or browse.

* BORR does not use tracking cookies, advertising pixels, or third-party analytics.

* Anonymous usage data (page views, search query counts — not the query text) may be collected in aggregate only, using privacy-respecting tools such as Plausible Analytics.

* No personally identifiable information (PII) is collected from visitors who do not register.

### **B. Registered Users (submission & contribution)**

* Email address — used for account verification and moderation communications

* Display name — shown on community submission activity

* Submission history — list of papers submitted by the user (stored in database)

* Login timestamps — for security audit purposes only

BORR does not collect: phone numbers, physical addresses, payment information, national ID numbers, or any sensitive personal data.

### **C. Paper Metadata**

Author names, institutional affiliations, and contact emails that appear in submitted paper metadata are considered bibliographic public information (they appear in published, publicly accessible papers). BORR stores these as part of the public research record, consistent with practices of Google Scholar, Semantic Scholar, and all academic indexing services.

## **13.2 How BORR Uses Your Data**

* Email addresses are used only for account-related communications (verification, submission status updates). They are never sold, rented, or shared with third parties.

* Submission history is used to attribute community contributions publicly (e.g. "Submitted by \[username\]") and to identify misuse patterns.

* Aggregate analytics (if any) are used only to understand platform usage and improve the service. They contain no PII.

## **13.3 Data Sharing**

BORR does not sell your personal data. BORR may share data only in the following circumstances:

* With service providers (e.g. Supabase for database hosting, Vercel for web hosting) who are bound by their own privacy policies and process data only as needed to operate the service

* With law enforcement or regulatory authorities if required by the laws of Bangladesh or a valid legal order

* In anonymized, aggregated form for research or transparency reports about platform usage

## **13.4 Data Retention**

* Account data is retained for as long as the account is active. If you delete your account, your email address and display name are deleted within 30 days. Submissions attributed to your account will remain but will be listed as "anonymous contributor".

* Paper metadata is retained indefinitely as part of the open public record, unless a valid takedown request is received (see Terms, Section 12.8).

## **13.5 Your Rights**

You have the right to:

* Access — request a copy of all personal data BORR holds about you

* Correction — request correction of inaccurate personal data

* Deletion — request deletion of your account and associated personal data

* Portability — receive your personal data in a machine-readable format

* Objection — object to processing of your personal data in certain circumstances

To exercise any of these rights, email: privacy@borr.org.bd (placeholder — update before launch).

## **13.6 Security**

BORR implements industry-standard security measures: HTTPS everywhere, database access restricted by Row Level Security (Supabase RLS), hashed passwords (never stored in plain text), rate limiting on submission endpoints. However, no system is 100% secure. Users should not submit any sensitive personal data beyond what is required to create an account.

## **13.7 Children**

BORR is not directed at children under the age of 13\. BORR does not knowingly collect personal data from children. If we become aware that a child under 13 has provided personal data, we will delete it promptly.

## **13.8 Changes to This Policy**

BORR may update this Privacy Policy as the platform evolves. Changes will be communicated via the website with a revised effective date. Material changes will also be communicated via email to registered users.

## **13.9 Contact**

For privacy inquiries or to exercise your rights: privacy@borr.org.bd (placeholder — update before launch)

# **14\. Open-Source License**

| MIT License Copyright (c) 2024 BORR — Bangladesh Open Research Repository Contributors Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. |
| ----- |

The BORR metadata database is separately released under CC-BY 4.0 International (Attribution License) — meaning anyone may freely copy, modify, distribute, and use the metadata, provided they give appropriate credit to BORR and the original sources.

# **15\. BORR Academy — The Future**

BORR Archive is Phase 1\. BORR Academy is the long-term vision: a free, open, Bangladesh-rooted learning ecosystem built on top of the research it aggregates.

| 📚 Learn Free structured learning paths built on real Bangladeshi research papers. How to read a paper. How to write a review. Research methods in context. | 🤝 Connect Mentorship directory linking junior researchers with senior Bangladeshi academics globally. Collaboration board for co-authorship. | 🚀 Grow Research grant directory curated for Bangladeshi researchers. Institutional capacity-building resources. Open peer review training. |
| :---- | :---- | :---- |

| Why this matters for Bangladesh Bangladesh has one of the world's youngest populations and a rapidly growing research community. What it lacks is infrastructure — a way to connect knowledge producers, make that knowledge discoverable, and train the next generation on how to contribute to it. BORR Archive builds the knowledge layer. BORR Academy builds the human layer. Together, they are a platform for Bangladesh to lead — not just participate in — the global knowledge economy. |
| :---- |

# **16\. Branding & Identity**

| Full Name | BORR — Bangladesh Open Research Repository |
| :---- | :---- |
| **Short Name** | BORR |
| **Tagline** | Research for a Better Bangladesh. |
| **Logo Concept** | The letters B-O-R-R in bold navy, with the 'O' stylized as an open book or an archive circle. Optional: small 🇧🇩 flag mark. |
| **Primary Color** | Navy Blue — \#1E3A5F (trust, depth, academia) |
| **Accent Color** | Bright Blue — \#2563EB (modernity, openness, technology) |
| **Supporting Colors** | Emerald Green \#065F46 (growth) · Amber \#92400E (warmth) · White \#FFFFFF |
| **Suggested Domain** | borr.org.bd  or  borr-archive.org  or  borr.bd |
| **GitHub Org** | github.com/borr-archive |
| **Future Academy URL** | academy.borr.org.bd |
| **Email Placeholder** | contact@borr.org.bd  ·  privacy@borr.org.bd  ·  submit@borr.org.bd |
| **Tagline (Bangla)** | " গবেষণা বাংলাদেশের সুন্দর ভবিষ্যতের জন্য" |

# **17\. Data Quality & Deduplication**

## **17.1 Deduplication Strategy**

BORR ingests data from multiple sources (OpenAlex, Crossref, Semantic Scholar, community submissions), which will produce overlapping records. The deduplication strategy:

| Priority | Method | Description |
| :---- | :---- | :---- |
| **Primary** | DOI match | Exact DOI match is the strongest dedup key. Upsert on conflict. |
| **Fallback** | Title + first author + year hash | For papers without DOIs (~30% of records), compute a SHA-256 hash of normalized (lowercased, trimmed) title + first author surname + publication year. Flag potential matches for manual review. |
| **Manual** | Moderator merge | Admin panel provides a "merge duplicate records" tool for edge cases the algorithm misses. |

## **17.2 Source Conflict Resolution**

When multiple sources provide conflicting metadata for the same paper, use this priority order:

1. **OpenAlex** (primary — richest metadata, consistent structure)
2. **Crossref** (secondary — authoritative for DOI registration)
3. **Semantic Scholar** (tertiary — good citation data)
4. **Community/Manual** (lowest — requires moderator verification)

## **17.3 Quality Checks**

Automated validation flags on ingest:

- Missing abstract (record marked incomplete)
- Publication year in the future or before 1800 (suspicious)
- Author count > 500 (likely parsing error)
- DOI format invalid (flagged for review)
- URL returns HTTP 404/410 (broken link alert)

Records failing quality checks are stored but marked `verified: false` and excluded from search results until a moderator reviews them.

# **18\. Operational Readiness**

## **18.1 Monitoring & Alerting**

| Component | Monitoring | Alert Channel |
| :---- | :---- | :---- |
| **Website uptime** | UptimeRobot or similar (5-min check) | Email + GitHub Issue |
| **Harvester cron** | GitHub Actions workflow status | GitHub Actions email on failure |
| **Database health** | Supabase built-in monitoring | Supabase dashboard alerts |
| **Search latency** | `/api/health` endpoint (target < 500ms) | Manual review weekly |

## **18.2 Health Check Endpoint**

`GET /api/health` returns JSON:
```json
{
  "status": "ok",
  "database": "connected",
  "harvester_last_run": "2026-06-09T03:00:00Z",
  "harvester_status": "success",
  "total_papers": 125000,
  "search_latency_ms": 45
}
```

## **18.3 Backup Strategy**

- **Supabase daily automated backups** (built-in, retained 7 days on free tier, 30 days on Pro)
- **Weekly full export** to encrypted S3-compatible storage (via GitHub Actions cron)
- **RPO**: 24 hours (maximum data loss window)
- **RTO**: 4 hours (time to restore from backup)

## **18.4 Storage Tier Migration Plan**

| Tier | Capacity | Cost | Trigger |
| :---- | :---- | :---- | :---- |
| **Free** | 500 MB | $0/mo | Initial launch |
| **Pro** | 8 GB | $25/mo | 80% of free tier capacity reached (~400 MB) |
| **Team** | 50 GB | $50/mo | 80% of Pro tier capacity reached |

At ~2 KB per paper record (including abstract), 500 MB holds approximately 250,000 papers. Monitor weekly and upgrade proactively.

## **18.5 Rate Limiting (Phase 2+)**

Public REST API: **100 requests/minute per IP**. Exceeded limits return `429 Too Many Requests` with `Retry-After` header. Rate limits are enforced via Supabase Edge Functions or Vercel middleware.

# **19\. Risk Register**

| # | Risk | Likelihood | Impact | Mitigation |
| :---- | :---- | :---- | :---- | :---- |
| R1 | OpenAlex API schema/endpoint changes break harvester | Medium | High | Abstract harvester behind adapter layer with type contracts; integration tests on CI before each deploy |
| R2 | Database exceeds free tier storage limit | High | Medium | Tiered migration plan (Section 18.4); compress abstracts; archive low-value records; consider abstract truncation for search-only mode |
| R3 | Single maintainer burnout / bus factor of 1 | Medium | High | Document runbooks; recruit 2+ co-maintainers within first 6 months; use GitHub Issues for transparent task tracking |
| R4 | Bangladesh jurisdiction unenforceable for international users | Medium | Low | Add international arbitration clause; keep Terms minimal and focused on conduct, not legal threats |
| R5 | Author name collisions create duplicate/merged profiles in Phase 3 | High | Medium | ORCID integration (Section 7, Phase 3); manual merge/dedup tool in admin panel; display institution alongside name |
| R6 | Scope creep from BORR Academy distracts from Archive MVP | High | Medium | Keep Academy in separate repository with separate codebase; no shared code with Archive until MVP is stable and launched |
| R7 | Community submissions include fabricated or inaccurate metadata | Medium | Medium | Moderation queue with 48-hour SLA; DOI auto-verification against Crossref; user reputation scoring; repeat offender bans |
| R8 | PostgreSQL tsvector doesn't support Bengali search natively | High | Medium | Use pgroonga extension (Supabase supports it) or implement custom Bengali tokenizer; test with realistic Bangla queries before launch |

**BORR — Bangladesh Open Research Repository**

*Open-source · Free forever · Built for Bangladesh*

MIT License · CC-BY 4.0 Metadata · github.com/borr-archive