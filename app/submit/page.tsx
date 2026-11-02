import type { Metadata } from "next";
import SubmitForm from "@/components/SubmitForm";
import { escapeJsonForHtml } from "@/lib/metadata";

export const metadata: Metadata = {
  title: "Submit a Paper",
  description:
    "Submit your published research paper or preprint to the Bangladesh Open Research Repository (BORR) via DOI to index and highlight your scientific contributions.",
  alternates: {
    canonical: "/submit",
  },
  openGraph: {
    title: "Submit a Paper — BORR",
    description:
      "Submit your published research paper or preprint to the Bangladesh Open Research Repository via DOI to expand its global visibility.",
    url: "/submit",
    type: "website",
  },
};

const submitJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Submit a Paper to BORR",
  "url": "https://borrbd.org/submit",
  "description":
    "Researchers can submit published scholarly articles or preprints via DOI to be indexed in the Bangladesh Open Research Repository.",
  "publisher": {
    "@type": "Organization",
    "name": "Bangladesh Open Research Repository",
    "url": "https://borrbd.org",
  },
};

export default function SubmitPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: escapeJsonForHtml(submitJsonLd) }}
      />
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-6">
        Submit a Paper to BORR
      </h1>
      <p className="text-gray-600 dark:text-gray-400 mb-8 leading-relaxed">
        Help build the largest open database of Bangladeshi research. Enter the DOI of the paper
        below, and our system will automatically fetch the metadata from Crossref. All submissions
        go through a quick human moderation queue to ensure accuracy.
      </p>

      <SubmitForm />
    </div>
  );
}
