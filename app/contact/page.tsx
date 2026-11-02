import type { Metadata } from "next";
import ContactForm from "@/components/ContactForm";
import { escapeJsonForHtml } from "@/lib/metadata";
import { CONTACT_EMAIL } from "@/lib/contact";

export const metadata: Metadata = {
  title: "Contact Us",
  description:
    "Contact the BORR team for metadata corrections, paper additions, takedown requests, author inquiries, or research collaboration.",
  alternates: {
    canonical: "/contact",
  },
  openGraph: {
    title: "Contact Us — BORR",
    description:
      "Contact the Bangladesh Open Research Repository team for paper updates, metadata corrections, or partnership inquiries.",
    url: "/contact",
    type: "website",
  },
};

const contactJsonLd = {
  "@context": "https://schema.org",
  "@type": "ContactPage",
  "name": "Contact BORR",
  "url": "https://borrbd.org/contact",
  "description":
    "Get in touch with the Bangladesh Open Research Repository team for metadata corrections, research partnerships, or takedown requests.",
  "mainEntity": {
    "@type": "Organization",
    "name": "Bangladesh Open Research Repository",
    "url": "https://borrbd.org",
    "email": CONTACT_EMAIL,
    "contactPoint": {
      "@type": "ContactPoint",
      "email": CONTACT_EMAIL,
      "contactType": "customer service",
      "availableLanguage": ["English", "Bengali"],
    },
  },
};

export default function ContactPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: escapeJsonForHtml(contactJsonLd) }}
      />
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-4">Contact BORR</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-8 leading-relaxed">
        Questions, corrections, takedown requests, or partnership ideas — we&apos;d love to hear from
        you. Reach us directly by email, or fill in the form below and it will open in your mail app
        ready to send.
      </p>

      <ContactForm />
    </div>
  );
}
