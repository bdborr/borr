import { isTursoDatabaseConfigured, searchLocalPapers, type LocalPaperRow } from "@/lib/turso-papers";
import { Search as SearchIcon, X } from "lucide-react";
import PaperCard from "@/components/PaperCard";
import MobileFilterToggle from "@/components/MobileFilterToggle";
import { TOP_FIELDS } from "@/lib/fields";

// Rendered per-request (reads searchParams), but NOT force-dynamic: that emitted
// `no-store` and defeated the CDN cache configured in vercel.json. Without it, the
// edge caches each search URL (s-maxage=60), so repeat/crawler hits to the same
// query are served from the CDN instead of re-scanning Turso.
export const revalidate = 60;

const PAPER_SELECT = "id, title, authors, abstract, doi, url, journal, year, fields, access_type, citation_count, paper_type, verified, created_at";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    sort?: string;
    page?: string;
    field?: string;
    year?: string;
    yearFrom?: string;
    yearTo?: string;
    type?: string;
    access?: string;
    institution?: string;
  }>;
}) {
  const resolvedSearchParams = await searchParams;
  const query = (resolvedSearchParams.q || "").trim();
  const defaultSort = query ? "relevance" : "cited";
  const sort = resolvedSearchParams.sort || defaultSort;
  const requestedPage = Math.max(parseInt(resolvedSearchParams.page || "1", 10) || 1, 1);
  const page = Math.min(requestedPage, 20);
  const filterField = resolvedSearchParams.field || "";
  const filterYear = resolvedSearchParams.year || "";
  const filterYearFrom = resolvedSearchParams.yearFrom || "";
  const filterYearTo = resolvedSearchParams.yearTo || "";
  const filterType = resolvedSearchParams.type || "";
  const filterAccess = resolvedSearchParams.access || "";
  const filterInstitution = resolvedSearchParams.institution || "";
  const limit = 15;  // reduced from 20 — faster page loads
  const offset = (page - 1) * limit;

  let papers: LocalPaperRow[] | null = [];
  let count: number | null = 0;
  let countMode: "exact" | "estimated" | "lower-bound" = "exact";
  let hasNextPage = false;
  let error: { message: string } | null = null;
  const hasAnyFilter = Boolean(filterField || filterYear || filterYearFrom || filterYearTo || filterType || filterAccess || filterInstitution);
  const searchEnabled = process.env.BORR_SEARCH_ENABLED === "1";
  const canQueryDatabase = searchEnabled && query.length >= 2;

  if (isTursoDatabaseConfigured && canQueryDatabase) {
    try {
      const result = await searchLocalPapers({
        query,
        sort,
        page,
        field: filterField,
        year: filterYear,
        yearFrom: filterYearFrom,
        yearTo: filterYearTo,
        type: filterType,
        access: filterAccess,
        institution: filterInstitution,
        limit,
      });
      papers = result.papers;
      count = result.count;
      countMode = result.countMode;
      hasNextPage = result.hasNextPage;
    } catch (err) {
      error = { message: err instanceof Error ? err.message : "Turso database query failed" };
    }
  } else if (!isTursoDatabaseConfigured) {
    error = { message: "No database is configured. Add TURSO_DATABASE_URL to connect to the database." };
  }

  function buildQs(overrides: Record<string, string>) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (sort !== defaultSort) params.set("sort", sort);
    if (filterField) params.set("field", filterField);
    if (filterYear) params.set("year", filterYear);
    if (filterYearFrom) params.set("yearFrom", filterYearFrom);
    if (filterYearTo) params.set("yearTo", filterYearTo);
    if (filterType) params.set("type", filterType);
    if (filterAccess) params.set("access", filterAccess);
    if (filterInstitution) params.set("institution", filterInstitution);
    for (const [k, v] of Object.entries(overrides)) {
      if (v) params.set(k, v);
      else params.delete(k);
    }
    return params.toString();
  }

  function buildUrl(overrides: Record<string, string>) {
    return `/search?${buildQs(overrides)}`;
  }

  const currentQs = buildQs({});

  const sortOptions = [
    ...(query ? [{ value: "relevance", label: "Sort by relevance" }] : []),
    { value: "newest", label: "Sort by date" },
    { value: "cited", label: "Sort by citations" },
  ];

  const activeFilters: { label: string; clear: Record<string, string> }[] = [];
  if (filterField) activeFilters.push({ label: `Field: ${filterField}`, clear: { field: "", page: "1" } });
  if (filterInstitution) activeFilters.push({ label: `Affiliation: ${filterInstitution}`, clear: { institution: "", page: "1" } });
  if (filterYearFrom || filterYearTo) activeFilters.push({ label: `Year: ${filterYearFrom || "…"}–${filterYearTo || "…"}`, clear: { yearFrom: "", yearTo: "", page: "1" } });
  if (filterYear && !filterYearFrom && !filterYearTo) activeFilters.push({ label: `Year: ${filterYear}`, clear: { year: "", page: "1" } });
  if (filterType) activeFilters.push({ label: `Type: ${filterType}`, clear: { type: "", page: "1" } });
  if (filterAccess) activeFilters.push({ label: filterAccess, clear: { access: "", page: "1" } });

  function formatResultCount(n: number | null): string {
    const value = (n ?? 0).toLocaleString();
    if (countMode === "estimated") return `~${value}`;
    if (countMode === "lower-bound") return `${value}+`;
    return value;
  }

  const totalPages = Math.max(1, Math.ceil((count ?? 0) / limit));
  const totalPagesLabel = countMode === "exact" ? totalPages.toLocaleString() : countMode === "estimated" ? `~${totalPages.toLocaleString()}` : `${totalPages.toLocaleString()}+`;
  const hasPrevPage = page > 1;

  const inputClasses = "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-borr-blue";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col md:flex-row gap-4 md:gap-8">
      <aside className="w-full md:w-64 shrink-0">
        <MobileFilterToggle>
          <div className="bg-white dark:bg-gray-900 p-6 rounded-lg border border-gray-200 dark:border-gray-800 md:sticky md:top-4 md:max-h-[calc(100vh-2rem)] md:overflow-y-auto space-y-6">
            <h2 className="font-bold text-gray-900 dark:text-gray-100">Filters</h2>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Sort By</h3>
              <div className="space-y-1">
                {sortOptions.map((opt) => (
                  <a
                    key={opt.value}
                    href={buildUrl({ sort: opt.value === defaultSort ? "" : opt.value, page: "1" })}
                    className={`block text-sm px-3 py-1.5 rounded-md transition-colors ${
                      sort === opt.value ? "bg-borr-blue text-white" : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                    }`}
                  >
                    {opt.label}
                  </a>
                ))}
              </div>
            </div>

            <form action="/search" method="get" className="space-y-5">
              <input type="hidden" name="q" value={query} />
              {sort !== defaultSort && <input type="hidden" name="sort" value={sort} />}
              {filterType && <input type="hidden" name="type" value={filterType} />}

              <div>
                <label htmlFor="filter-field" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Field</label>
                <select id="filter-field" name="field" defaultValue={filterField} className={inputClasses}>
                  <option value="">All fields</option>
                  {TOP_FIELDS.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="filter-institution" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Author Affiliation</label>
                <input id="filter-institution" type="text" name="institution" placeholder="e.g. University of Dhaka, BRAC University" defaultValue={filterInstitution} className={inputClasses} />
              </div>

              <div>
                <span className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Year Range</span>
                <div className="flex items-center gap-2">
                  <input type="number" name="yearFrom" aria-label="Year from" placeholder="From" defaultValue={filterYearFrom} className={inputClasses} />
                  <span className="text-sm text-gray-500 dark:text-gray-400 shrink-0">to</span>
                  <input type="number" name="yearTo" aria-label="Year to" placeholder="To" defaultValue={filterYearTo} className={inputClasses} />
                </div>
              </div>

              <div>
                <label htmlFor="filter-access" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Access</label>
                <select id="filter-access" name="access" defaultValue={filterAccess} className={inputClasses}>
                  <option value="">Any access</option>
                  <option value="Open Access">Open Access</option>
                </select>
              </div>

              <button type="submit" className="w-full bg-borr-blue hover:bg-blue-700 text-white font-medium py-2 rounded-md transition-colors text-sm">
                Apply Filters
              </button>
              {activeFilters.length > 0 && (
                <a href={buildUrl({ field: "", institution: "", year: "", yearFrom: "", yearTo: "", type: "", access: "", page: "1" })} className="block text-xs text-red-500 hover:underline text-center">
                  Clear all filters
                </a>
              )}
            </form>
          </div>
        </MobileFilterToggle>
      </aside>

      <main className="flex-1 min-w-0">
        <form action="/search" className="mb-8">
          {sort !== defaultSort && <input type="hidden" name="sort" value={sort} />}
          {filterType && <input type="hidden" name="type" value={filterType} />}
          <div className="flex shadow-sm rounded-md overflow-hidden border border-gray-300 dark:border-gray-700">
            <input type="text" name="q" defaultValue={query} placeholder="Search papers… (press / to focus)" className="flex-1 min-w-0 px-4 py-3 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-borr-blue" />
            <button type="submit" className="bg-borr-navy hover:bg-opacity-90 text-white px-6 flex items-center transition-colors"><SearchIcon className="w-5 h-5 mr-2" /> Search</button>
          </div>
        </form>

        <div className="mb-4 flex justify-between items-end border-b border-gray-200 dark:border-gray-800 pb-4">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{query ? <>Results for &ldquo;{query}&rdquo;</> : "All Papers"}</h1>
          <span className="text-gray-500 dark:text-gray-400 text-sm shrink-0 ml-4">{formatResultCount(count)} {count === 1 ? "result" : "results"}</span>
        </div>

        {activeFilters.length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2">
            {activeFilters.map((filter) => (
              <a
                key={filter.label}
                href={buildUrl(filter.clear)}
                className="inline-flex items-center gap-1.5 text-xs font-medium bg-blue-50 dark:bg-blue-950 text-borr-navy dark:text-blue-200 hover:bg-blue-100 dark:hover:bg-blue-900 px-3 py-1.5 rounded-full transition-colors"
                title={`Remove filter: ${filter.label}`}
              >
                {filter.label}
                <X className="w-3 h-3" />
              </a>
            ))}
          </div>
        )}

        {error ? (
          <div className="bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300 p-4 rounded-md border border-red-200 dark:border-red-900"><p>Error loading results: {error.message}</p></div>
        ) : !canQueryDatabase ? (
          <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800"><SearchIcon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" /><h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">Search temporarily protected</h3><p className="text-gray-500 dark:text-gray-400">BORR public search is paused while database-read quota recovers. This prevents crawler traffic from consuming more Turso reads. Set BORR_SEARCH_ENABLED=1 in production when you are ready to re-enable it.</p>{(query || hasAnyFilter) && <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">No database query was run for this request.</p>}</div>
        ) : !papers || papers.length === 0 ? (
          <div className="text-center py-16 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800"><SearchIcon className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600 mb-4" /><h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">No papers found</h3><p className="text-gray-500 dark:text-gray-400">Try adjusting your search terms or filters.</p></div>
        ) : (
          <div className="space-y-4">
            {papers.map((paper) => (
              <PaperCard key={paper.id} paper={paper} query={query} backQs={currentQs} />
            ))}

            <nav className="mt-8 flex justify-between items-center py-4" aria-label="Pagination">
              <a
                href={hasPrevPage ? buildUrl({ page: String(page - 1) }) : undefined}
                aria-disabled={!hasPrevPage}
                className={`px-4 py-2 border rounded-md text-sm font-medium transition-colors ${hasPrevPage ? "text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800" : "text-gray-400 dark:text-gray-600 border-gray-200 dark:border-gray-800 opacity-50 pointer-events-none"}`}
              >
                Previous
              </a>
              <span className="text-sm text-gray-600 dark:text-gray-400">Page {page.toLocaleString()} of {totalPagesLabel}</span>
              <a
                href={hasNextPage ? buildUrl({ page: String(page + 1) }) : undefined}
                aria-disabled={!hasNextPage}
                className={`px-4 py-2 border rounded-md text-sm font-medium transition-colors ${hasNextPage ? "text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800" : "text-gray-400 dark:text-gray-600 border-gray-200 dark:border-gray-800 opacity-50 pointer-events-none"}`}
              >
                Next
              </a>
            </nav>
          </div>
        )}
      </main>
    </div>
  );
}
