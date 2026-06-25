import Link from "next/link";
import { Search } from "lucide-react";
import { isTursoDatabaseConfigured, getLocalTypeCounts } from "@/lib/turso-papers";

// Stats are recomputed at most once an hour.
export const revalidate = 3600;

export default async function Home() {
  let typeCounts: Record<string, number> = {};
  if (isTursoDatabaseConfigured) {
    try {
      typeCounts = await getLocalTypeCounts();
    } catch {
      // DB unreachable; cards render zeros rather than failing the page.
    }
  }
  const fmt = (n: number | undefined) => (n ?? 0).toLocaleString();

  return (
    <div className="flex flex-col min-h-screen">
      <section className="bg-borr-navy text-white pt-20 pb-28 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-borr-blue via-borr-navy to-borr-navy"></div>
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight mb-6">
            Research for a Better Bangladesh
          </h1>
          <p className="text-lg md:text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
            The largest open source repository of research papers by Bangladeshi authors, institutions, and about Bangladesh.
          </p>

          <form action="/search" className="max-w-2xl mx-auto relative shadow-2xl">
            <div className="flex items-center bg-white rounded-lg overflow-hidden p-1 focus-within:ring-2 focus-within:ring-borr-blue transition-all">
              <Search className="h-6 w-6 text-gray-400 ml-3" />
              <input
                type="text"
                name="q"
                placeholder="Search by title, author, institution, keyword (e.g. arsenic, BUET)..."
                className="flex-1 w-full py-4 px-4 text-gray-900 focus:outline-none text-lg placeholder:text-gray-400"
              />
              <button
                type="submit"
                className="bg-borr-blue hover:bg-blue-700 text-white font-semibold py-3 px-8 rounded-md transition-colors"
              >
                Search
              </button>
            </div>
          </form>
          <div className="mt-4 text-sm text-gray-400">
            Try: <Link href="/search?q=climate+change" className="text-borr-blue hover:underline">climate change</Link>, <Link href="/search?q=public+health" className="text-borr-blue hover:underline">public health</Link>, <Link href="/search?q=agriculture" className="text-borr-blue hover:underline">agriculture</Link>
          </div>
        </div>
      </section>

      <section className="py-16 bg-white dark:bg-gray-950 border-b border-gray-100 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
            <Link href="/search?type=Journal+Article" className="block p-6 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md hover:border-borr-blue/40 transition-all">
              <h3 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{fmt(typeCounts["Journal Article"])}</h3>
              <p className="text-gray-600 dark:text-gray-400 font-medium text-sm">Articles</p>
            </Link>
            <Link href="/search?type=Book+Chapter" className="block p-6 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md hover:border-borr-blue/40 transition-all">
              <h3 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{fmt(typeCounts["Book Chapter"])}</h3>
              <p className="text-gray-600 dark:text-gray-400 font-medium text-sm">Book Chapters</p>
            </Link>
            <Link href="/search?type=Review" className="block p-6 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md hover:border-borr-blue/40 transition-all">
              <h3 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{fmt(typeCounts["Review"])}</h3>
              <p className="text-gray-600 dark:text-gray-400 font-medium text-sm">Reviews</p>
            </Link>
            <Link href="/search?type=Thesis" className="block p-6 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md hover:border-borr-blue/40 transition-all">
              <h3 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{fmt(typeCounts["Thesis"])}</h3>
              <p className="text-gray-600 dark:text-gray-400 font-medium text-sm">Dissertations</p>
            </Link>
            <Link href="/search?type=Other" className="block col-span-2 md:col-span-1 p-6 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800 shadow-sm hover:shadow-md hover:border-borr-blue/40 transition-all">
              <h3 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{fmt(typeCounts["Other"])}</h3>
              <p className="text-gray-600 dark:text-gray-400 font-medium text-sm">Other</p>
            </Link>
          </div>
        </div>
      </section>

      {!isTursoDatabaseConfigured && (
        <div className="mx-auto mt-4 max-w-2xl rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-200">
          No database is configured in this local environment. Add TURSO_DATABASE_URL to connect to the database.
        </div>
      )}

      <section className="py-20 bg-gray-50 dark:bg-gray-950 flex-1">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-6">Our Mission</h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 leading-relaxed mb-8">
            BORR exists to make all research from Bangladesh — and about Bangladesh — discoverable, accessible, and free for anyone in the world to find. We aggregate all research metadata from global publishers into a single, searchable, open platform maintained by and for the people of Bangladesh.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/about" className="inline-flex items-center justify-center px-6 py-3 border border-gray-300 dark:border-gray-700 shadow-sm text-base font-medium rounded-md text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
              Read Our Vision
            </Link>
            <Link href="/submit" className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-borr-navy dark:text-blue-200 bg-blue-100 dark:bg-blue-950 hover:bg-blue-200 dark:hover:bg-blue-900 transition-colors">
              Submit a Paper
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
