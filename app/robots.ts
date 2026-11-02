import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site-url";

// Aggressive AI/scraper crawlers: no SEO value, and the likeliest source of the
// ~700M-row read spike. Block them from the whole site.
const BLOCKED_BOTS = [
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "ClaudeBot",
  "Claude-Web",
  "anthropic-ai",
  "CCBot",
  "Bytespider",
  "PerplexityBot",
  "Amazonbot",
  "Applebot-Extended",
  "Google-Extended",
  "cohere-ai",
  "Diffbot",
  "ImagesiftBot",
  "Omgilibot",
  "meta-externalagent",
  "FacebookBot",
  "DataForSeoBot",
  "SemrushBot",
  "AhrefsBot",
  "MJ12bot",
  "DotBot",
];

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();

  return {
    rules: [
      // Disallow abusive AI scrapers entirely.
      { userAgent: BLOCKED_BOTS, disallow: "/" },
      // Search engines (Googlebot, Bingbot, etc.):
      // Explicitly allow core content pages and paper records.
      // Disallow /search and /api/ to prevent crawler loops and unindexed DB queries.
      {
        userAgent: ["Googlebot", "Bingbot", "DuckDuckBot", "Applebot"],
        allow: ["/", "/about", "/contact", "/submit", "/terms", "/policy", "/paper/"],
        disallow: ["/search", "/api/", "/admin"],
      },
      // General crawlers fallback
      {
        userAgent: "*",
        allow: ["/", "/about", "/contact", "/submit", "/terms", "/policy", "/paper/"],
        disallow: ["/search", "/api/", "/admin"],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
