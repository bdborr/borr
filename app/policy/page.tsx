import type { Metadata } from "next";
import Link from "next/link";
import { CONTACT_EMAIL } from "@/lib/contact";

export const metadata: Metadata = {
  title: "Disclaimer, Takedown & Corrections — BORR",
  description:
    "BORR's metadata disclaimer and the process for correcting metadata, merging duplicates, and handling takedown requests or source complaints.",
};

export default function PolicyPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <div className="bg-white dark:bg-gray-900 p-8 md:p-12 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
        <h1 className="text-4xl font-extrabold text-borr-navy dark:text-blue-300 mb-2">
          Disclaimer, Takedown &amp; Corrections
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-10">Last updated: 13 June 2026.</p>

        <div className="prose prose-lg prose-blue max-w-none text-gray-700 dark:text-gray-300">
          <h2 id="disclaimer" className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-0 mb-4 scroll-mt-24">
            Disclaimer
          </h2>
          <p className="mb-8 leading-relaxed">
            BORR&apos;s metadata is aggregated automatically from public sources such as Crossref, OpenAlex,
            and community submissions. It is provided <strong>&quot;as is,&quot; without warranty of any
            kind</strong>, express or implied. Records may be incomplete, out of date, duplicated, or
            contain errors, and an entry&apos;s presence here does not imply endorsement by, or affiliation
            with, BORR. To the fullest extent permitted by law, BORR and its maintainers are not liable for
            any loss or damage arising from use of, or reliance on, the information provided. For anything
            authoritative, consult the original source linked from each record.
          </p>

          <h2 id="takedown" className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-8 mb-4 scroll-mt-24">
            Takedown &amp; Corrections Policy
          </h2>
          <p className="mb-4 leading-relaxed">
            We want the index to be accurate and to respect the rights of authors, publishers, and
            repositories. If you are an author, rights holder, or reader and you find a problem, contact us
            and we will review it promptly. Please use this process for:
          </p>
          <ul className="list-disc pl-6 mb-6 space-y-2">
            <li><strong>Incorrect metadata</strong> — wrong title, authors, affiliations, year, abstract, or DOI.</li>
            <li><strong>Duplicate records</strong> — the same work indexed more than once.</li>
            <li><strong>Takedown requests</strong> — a rights holder or source asking that a record be removed or amended.</li>
            <li><strong>Source complaints</strong> — any concern raised by the original publisher or repository.</li>
          </ul>
          <p className="mb-4 leading-relaxed">
            Email{" "}
            <a
              href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("BORR — Takedown / Correction request")}`}
              className="text-borr-blue dark:text-blue-300 font-medium hover:underline"
            >
              {CONTACT_EMAIL}
            </a>{" "}
            with the record&apos;s DOI or link and a short description of the issue. For takedown requests,
            please include enough detail for us to identify the record and the basis for the request. We aim
            to acknowledge requests within a few business days and, where a change is warranted, to correct
            or remove the affected record. You can also reach us through our{" "}
            <Link href="/contact" className="text-borr-blue dark:text-blue-300 font-medium hover:underline">
              contact page
            </Link>
            .
          </p>

          <p className="leading-relaxed">
            See also our{" "}
            <Link href="/terms" className="text-borr-blue dark:text-blue-300 font-medium hover:underline">
              Terms of Use
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
