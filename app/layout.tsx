import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import SearchHotkey from "@/components/SearchHotkey";

// Applies the saved (or system) theme before paint to avoid a light-mode flash.
const themeInitScript = `(function(){try{var t=localStorage.getItem("theme");if(t==="dark"||(!t&&window.matchMedia("(prefers-color-scheme: dark)").matches)){document.documentElement.classList.add("dark")}}catch(e){}})();`;

const inter = Inter({ subsets: ["latin"] });
// Set NEXT_PUBLIC_SITE_URL to the real domain at deploy time.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "BORR — Bangladesh Open Research Repository",
  description: "Research for a Better Bangladesh. The largest open source repository of research papers by Bangladeshi authors, institutions, and about Bangladesh.",
  openGraph: {
    title: "BORR — Bangladesh Open Research Repository",
    description: "Research for a Better Bangladesh. Discover research papers by Bangladeshi authors, institutions, or about Bangladesh.",
    type: "website",
    locale: "en_US",
    siteName: "BORR",
  },
  twitter: {
    card: "summary_large_image",
    title: "BORR — Bangladesh Open Research Repository",
    description: "Research for a Better Bangladesh. Discover research papers by Bangladeshi authors, institutions, or about Bangladesh.",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body suppressHydrationWarning className={`${inter.className} bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen flex flex-col`}>
        <SearchHotkey />
        <Navbar />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
