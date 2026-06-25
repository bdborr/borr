import Link from "next/link";
import { ExternalLink, CheckCircle } from "lucide-react";
import type { Paper } from "@/lib/supabase";
import { safeExternalUrl } from "@/lib/metadata";
import { highlightText } from "@/components/highlight";
import CiteButton from "@/components/CiteButton";

export default function PaperCard({
  paper,
  query = "",
  backQs = "",
}: {
  paper: Paper;
  query?: string;
  backQs?: string;
}) {
  const safeUrl = paper.url ? safeExternalUrl(paper.url, paper.doi) : null;
  const paperHref = `/paper/${encodeURIComponent(paper.id)}${backQs ? `?back=${encodeURIComponent(backQs)}` : ""}`;

  return (
    <div className="bg-white dark:bg-gray-900 p-6 rounded-lg border border-gray-200 dark:border-gray-800 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-xl font-bold text-borr-navy dark:text-blue-300 hover:text-borr-blue dark:hover:text-blue-200 transition-colors">
          <Link href={paperHref}>{highlightText(paper.title, query)}</Link>
        </h3>
        {paper.verified && <span className="flex items-center text-xs text-borr-green dark:text-green-400 bg-green-50 dark:bg-green-950 px-2 py-1 rounded-full font-medium ml-4 shrink-0"><CheckCircle className="w-3 h-3 mr-1" /> Verified</span>}
      </div>
      <p className="text-gray-600 dark:text-gray-400 mb-3 text-sm">
        {highlightText(
          (paper.authors ?? []).length > 4
            ? `${(paper.authors ?? []).slice(0, 4).join(", ")} et al.`
            : (paper.authors ?? []).join(", "),
          query
        )}
      </p>
      <div className="text-sm text-gray-500 dark:text-gray-400 mb-4 flex flex-wrap gap-x-4 gap-y-1">
        {paper.journal && <span><span className="font-semibold text-gray-700 dark:text-gray-300">Journal:</span> {paper.journal}</span>}
        {paper.year && <span><span className="font-semibold text-gray-700 dark:text-gray-300">Year:</span> {paper.year}</span>}
        {paper.citation_count !== null && <span><span className="font-semibold text-gray-700 dark:text-gray-300">Citations:</span> {paper.citation_count}</span>}
      </div>
      {paper.abstract && <p className="text-gray-700 dark:text-gray-300 text-sm mb-4 line-clamp-3">{highlightText(paper.abstract, query)}</p>}
      <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
        <div className="flex flex-wrap items-center gap-2">
          {paper.fields?.slice(0, 3).map((field) => <Link key={field} href={`/search?field=${encodeURIComponent(field)}`} className="text-xs bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 px-2 py-1 rounded-md transition-colors">{field}</Link>)}
          {paper.access_type === "Open Access" && <span className="text-xs bg-blue-50 dark:bg-blue-950 text-borr-blue dark:text-blue-300 px-2 py-1 rounded-md font-medium">Open Access</span>}
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <CiteButton
            compact
            align="right"
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
          {safeUrl && <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="flex items-center text-sm font-medium text-borr-blue dark:text-blue-300 hover:text-blue-800 dark:hover:text-blue-200 transition-colors">Read Source <ExternalLink className="w-4 h-4 ml-1" /></a>}
        </div>
      </div>
    </div>
  );
}
