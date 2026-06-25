import { getLocalPaperByKey, isTursoDatabaseConfigured } from "@/lib/turso-papers";
import { escapeJsonForHtml, safeExternalUrl } from "@/lib/metadata";
import { ExternalLink, ArrowLeft, Building, Calendar, BookOpen, Database, BarChart3 } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import ExpandableTextList from "@/components/ExpandableTextList";
import AuthorList from "@/components/AuthorList";
import AbstractSection from "@/components/AbstractSection";
import CiteButton from "@/components/CiteButton";
import CopyDoiButton from "@/components/CopyDoiButton";

export const dynamic = "force-dynamic";

const PAPER_SELECT = "id, title, authors, abstract, doi, url, journal, year, institution, fields, paper_type, access_type, citation_count, verified";

type PaperPageRow = {
  id: string;
  openalex_id?: string | null;
  title: string;
  authors: string[] | null;
  abstract: string | null;
  doi: string | null;
  url: string | null;
  journal: string | null;
  year: number | null;
  institution: string[] | null;
  fields: string[] | null;
  paper_type: string | null;
  access_type: string | null;
  citation_count: number | null;
  verified: boolean;
};

async function loadPaper(key: string): Promise<PaperPageRow | null> {
  if (!isTursoDatabaseConfigured) {
    return null;
  }
  return getLocalPaperByKey(key);
}

// The back param carries the search page's query string so "Back to Search"
// restores the user's query, filters, and page. Re-serialize it so only safe
// key/value pairs survive.
function sanitizeBackQs(back: string | undefined): string {
  if (!back) return "";
  try {
    return new URLSearchParams(back).toString();
  } catch {
    return "";
  }
}

export async function generateMetadata({ params }: { params: Promise<{ doi: string }> }) {
  const resolvedParams = await params;
  const paper = await loadPaper(resolvedParams.doi);

  if (!paper) return { title: "Paper Not Found | BORR" };

  return {
    title: `${paper.title} | BORR`,
    description: paper.abstract || `Research paper by ${paper.authors?.[0] || "Bangladeshi researchers"} and others.`,
  };
}

export default async function PaperPage({
  params,
  searchParams,
}: {
  params: Promise<{ doi: string }>;
  searchParams: Promise<{ back?: string }>;
}) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const paper = await loadPaper(resolvedParams.doi);

  if (!paper) {
    notFound();
  }

  const backQs = sanitizeBackQs(resolvedSearchParams.back);
  const backHref = backQs ? `/search?${backQs}` : "/search";

  const safeUrl = safeExternalUrl(paper.url, paper.doi);
  const publisherUrl = safeUrl || (paper.doi ? `https://doi.org/${paper.doi}` : null);
  const identifier = paper.doi || paper.openalex_id || paper.id;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    "headline": paper.title,
    "abstract": paper.abstract,
    "author": (paper.authors || []).map((author: string) => ({ "@type": "Person", "name": author })),
    "datePublished": paper.year?.toString(),
    "url": safeUrl,
    "identifier": identifier,
    "publisher": { "@type": "Organization", "name": paper.journal || "Unknown" }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: escapeJsonForHtml(jsonLd) }} />

      <Link href={backHref} className="inline-flex items-center text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Search
      </Link>

      <article className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="p-8">
          <div className="flex flex-wrap gap-2 mb-4">
            {paper.paper_type && <span className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 text-xs px-3 py-1 rounded-full font-medium">{paper.paper_type}</span>}
            {paper.access_type && <span className={`text-xs px-3 py-1 rounded-full font-medium ${paper.access_type === 'Open Access' ? 'bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300'}`}>{paper.access_type}</span>}
          </div>

          <h1 className="text-3xl sm:text-4xl font-extrabold text-gray-900 dark:text-gray-100 leading-tight mb-6">{paper.title}</h1>

          <div className="mb-6">
            <h2 className="text-lg font-medium text-gray-800 dark:text-gray-200 mb-2">Authors</h2>
            <div className="text-gray-600 dark:text-gray-400 leading-relaxed">
              <AuthorList authors={paper.authors || []} limit={4} />
            </div>
          </div>

          <div className="mb-8">
            <CiteButton
              paper={{
                title: paper.title,
                authors: paper.authors || [],
                journal: paper.journal,
                year: paper.year,
                doi: paper.doi,
                url: paper.url,
                paper_type: paper.paper_type,
              }}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 py-6 border-y border-gray-100 dark:border-gray-800">
            {paper.institution && paper.institution.length > 0 && (
              <div className="flex items-start"><Building className="w-5 h-5 text-gray-400 mr-3 mt-0.5" /><div><span className="block text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Author Affiliations</span><div className="text-sm text-gray-600 dark:text-gray-400"><ExpandableTextList items={paper.institution} limit={4} /></div></div></div>
            )}
            {paper.journal && (
              <div className="flex items-start"><BookOpen className="w-5 h-5 text-gray-400 mr-3 mt-0.5" /><div><span className="block text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Published In</span><span className="text-sm text-gray-600 dark:text-gray-400">{paper.journal}</span></div></div>
            )}
            {paper.year && (
              <div className="flex items-start"><Calendar className="w-5 h-5 text-gray-400 mr-3 mt-0.5" /><div><span className="block text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Year</span><span className="text-sm text-gray-600 dark:text-gray-400">{paper.year}</span></div></div>
            )}
            {paper.citation_count != null && (
              <div className="flex items-start"><BarChart3 className="w-5 h-5 text-gray-400 mr-3 mt-0.5" /><div><span className="block text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Citations</span><span className="text-sm text-gray-600 dark:text-gray-400">{paper.citation_count.toLocaleString()}</span></div></div>
            )}
            {paper.doi && (
              <div className="flex items-start"><Database className="w-5 h-5 text-gray-400 mr-3 mt-0.5" /><div><span className="block text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">DOI</span><span className="text-sm"><a href={`https://doi.org/${paper.doi}`} target="_blank" rel="noopener noreferrer" className="text-borr-blue hover:underline break-all">{paper.doi}</a><CopyDoiButton doi={paper.doi} /></span></div></div>
            )}
          </div>

          <div className="mb-8">
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-4">Abstract</h2>
            {paper.abstract ? (
              <AbstractSection abstract={paper.abstract} />
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400 italic">
                No abstract is available for this paper from the publisher. Use the link below to view the full record at the source.
              </p>
            )}
          </div>

          {publisherUrl && (
            <div className="mb-8">
              <a href={publisherUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center px-5 py-2.5 text-sm font-medium text-white bg-borr-blue hover:bg-blue-700 rounded-md transition-colors shadow-sm">
                View at Publisher <ExternalLink className="w-4 h-4 ml-2" />
              </a>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">BORR does not host full-text PDFs. The button above takes you to the original publisher.</p>
            </div>
          )}

          {paper.fields && paper.fields.length > 0 && (
            <div className="mb-8">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Fields & Keywords</h2>
              <div className="flex flex-wrap gap-2">
                {paper.fields.map((field: string) => (
                  <Link key={field} href={`/search?field=${encodeURIComponent(field)}`} className="bg-blue-50 dark:bg-blue-950 text-borr-blue dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900 hover:underline text-xs px-3 py-1.5 rounded-md transition-colors">
                    {field}
                  </Link>
                ))}
              </div>
            </div>
          )}

        </div>
      </article>
    </div>
  );
}
