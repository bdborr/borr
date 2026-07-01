import type { MetadataRoute } from "next";

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
  return {
    rules: [
      // Disallow scrapers entirely.
      { userAgent: BLOCKED_BOTS, disallow: "/" },
      // Everyone else (Googlebot, Bingbot, humans' feed readers, etc.):
      // block /search — its faceted filter links are an effectively infinite
      // URL space and each one is an uncached DB query — but allow the paper
      // pages, which are the content worth indexing.
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/search", "/api/", "/admin"],
        crawlDelay: 10,
      },
    ],
  };
}
