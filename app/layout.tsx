import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import SearchHotkey from "@/components/SearchHotkey";
import { escapeJsonForHtml } from "@/lib/metadata";
import { getSiteUrl } from "@/lib/site-url";

// Applies the saved (or system) theme before paint to avoid a light-mode flash.
const themeInitScript = `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||(!t&&window.matchMedia("(prefers-color-scheme: dark)").matches)){document.documentElement.classList.add("dark")}}catch(e){}})();`;

const inter = Inter({ subsets: ["latin"], display: "swap" });
// Set siteUrl with production default fallback
const siteUrl = getSiteUrl();

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "BORR — Bangladesh Open Research Repository",
    template: "%s | BORR",
  },
  description:
    "Research for a Better Bangladesh. The largest open-source repository of over 450,000 research papers by Bangladeshi authors, institutions, and about Bangladesh.",
  alternates: {
    canonical: "./",
  },
  openGraph: {
    title: "BORR — Bangladesh Open Research Repository",
    description:
      "Research for a Better Bangladesh. Discover over 450,000 research papers by Bangladeshi authors, institutions, or about Bangladesh.",
    url: siteUrl,
    type: "website",
    locale: "en_US",
    siteName: "BORR",
    images: [
      {
        url: "/opengraph-image",
        width: 1200,
        height: 630,
        alt: "BORR — Bangladesh Open Research Repository",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "BORR — Bangladesh Open Research Repository",
    description:
      "Research for a Better Bangladesh. Discover over 450,000 research papers by Bangladeshi authors, institutions, or about Bangladesh.",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

const rootStructuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": "https://borrbd.org/#website",
      "url": "https://borrbd.org",
      "name": "BORR — Bangladesh Open Research Repository",
      "alternateName": "BORR",
      "description":
        "The largest open-source repository of research papers by Bangladeshi authors, institutions, and about Bangladesh.",
      "potentialAction": {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": "https://borrbd.org/search?q={search_term_string}",
        },
        "query-input": "required name=search_term_string",
      },
      "inLanguage": "en-US",
    },
    {
      "@type": "Organization",
      "@id": "https://borrbd.org/#organization",
      "name": "Bangladesh Open Research Repository",
      "alternateName": "BORR",
      "url": "https://borrbd.org",
      "logo": "https://borrbd.org/icon",
      "sameAs": ["https://github.com/bdborr/borr"],
      "founder": [
        { "@type": "Person", "name": "Nehal Hasnain" },
        { "@type": "Person", "name": "Rehan Hasnain" },
      ],
      "slogan": "Research for a Better Bangladesh",
      "description":
        "An open-access academic index aggregating scientific literature by Bangladeshi researchers, institutions, or about Bangladesh.",
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: escapeJsonForHtml(rootStructuredData) }}
        />
      </head>
      <body suppressHydrationWarning className={`${inter.className} bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen flex flex-col`}>
        <SearchHotkey />
        <Navbar />
        <main className="flex-1">{children}</main>
        <Footer />
        <Analytics />
      </body>
    </html>
  );
}
