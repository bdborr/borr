import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Use — BORR",
  description:
    "BORR is a metadata index and research-discovery service. Full-text rights remain with the original publishers, repositories, and authors.",
};

export default function TermsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="bg-white dark:bg-gray-900 p-8 md:p-12 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
        <h1 className="text-4xl font-extrabold text-borr-navy dark:text-blue-300 mb-2">Terms of Use</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: 13 June 2026.</p>

        <div className="prose prose-lg prose-blue max-w-none text-gray-700 dark:text-gray-300">
          <p className="mb-4 leading-relaxed">
            BORR (Bangladesh Open Research Repository) is a free{" "}
            <strong>metadata index and research-discovery service</strong>. It helps you <em>find</em>{" "}
            scholarly works by Bangladeshi authors, by Bangladeshi institutions, or about Bangladesh. It is
            a finding tool, not a substitute for the original source.
          </p>

          <ul className="list-disc pl-6 mb-6 space-y-3">
            <li>
              <strong>We index, we don&apos;t host.</strong> BORR stores only bibliographic metadata
              (titles, authors, affiliations, abstracts, DOIs, and similar descriptive information). We do
              not host, store, or distribute full-text PDFs or the published version of record.
            </li>
            <li>
              <strong>All rights stay with the source.</strong> Copyright and all full-text rights in each
              work remain with the original authors, publishers, journals, or repositories. Each record
              links back to that authoritative source, and any use of the full text is governed by that
              source&apos;s own licence and terms.
            </li>
            <li>
              <strong>Always cite the original.</strong> Citations, abstracts, and links provided here are
              for discovery and attribution. Verify details against, and cite, the publisher&apos;s version
              of record — not BORR.
            </li>
            <li>
              <strong>Acceptable use.</strong> You may search, link to, and cite records freely. You may not
              scrape the service in a way that disrupts it, misrepresent BORR as the publisher of a work, or
              use the service for any unlawful purpose.
            </li>
          </ul>

          <p className="leading-relaxed">
            See also our{" "}
            <Link href="/policy" className="text-borr-blue dark:text-blue-300 font-medium hover:underline">
              Disclaimer, Takedown &amp; Corrections Policy
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
