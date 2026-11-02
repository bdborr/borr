import { NextRequest, NextResponse } from "next/server";

const ALLOWED_SEARCH_BOTS_RE = /(?:Googlebot|bingbot|DuckDuckBot|Slurp|Baiduspider|YandexBot|Twitterbot|facebookexternalhit|LinkedInBot|Chrome-Lighthouse|Lighthouse)/i;

// Block aggressive AI scrapers, SEO tool crawlers, and raw script scrapers that waste DB quotas.
// Legitimate search engines (Googlebot, Bingbot, etc.) and audit tools are explicitly allowed.
const BLOCKED_UA_RE = /(?:GPTBot|ChatGPT-User|OAI-SearchBot|ClaudeBot|Claude-Web|anthropic-ai|CCBot|Bytespider|PerplexityBot|Amazonbot|Applebot-Extended|Google-Extended|cohere-ai|Diffbot|ImagesiftBot|Omgilibot|meta-externalagent|FacebookBot|DataForSeoBot|SemrushBot|AhrefsBot|MJ12bot|DotBot|BLEXBot|PetalBot|python-requests|curl|wget|Go-http-client|Java\/|HttpClient|Scrapy)/i;

const buckets = new Map<string, { count: number; resetAt: number }>();
const WINDOW_MS = 60_000;

function clientIp(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

function limitForPath(pathname: string, isSearchBot = false): number {
  // BORR expects only a handful of real users. A low limit keeps even a
  // browser-spoofing crawler far below Turso's free monthly read quota.
  if (pathname.startsWith("/search")) return 5;
  if (pathname.startsWith("/paper")) return isSearchBot ? 120 : 20;
  return 30;
}

function isPrefetch(request: NextRequest): boolean {
  // Next.js may speculatively request every visible <Link>. On a paper page
  // that used to fan out into dozens of /search requests (one per author and
  // field) without a click. Reject all known prefetch forms at the edge before
  // they can render a route or touch Turso.
  return (
    request.headers.get("purpose")?.toLowerCase() === "prefetch" ||
    request.headers.get("sec-purpose")?.toLowerCase().includes("prefetch") === true ||
    request.headers.get("next-router-prefetch") === "1" ||
    request.headers.get("x-middleware-prefetch") === "1"
  );
}

function isRateLimited(key: string, limit: number): boolean {
  const now = Date.now();
  const bucket = buckets.get(key);
  if (!bucket || bucket.resetAt <= now) {
    if (buckets.size > 5000) {
      for (const [k, v] of buckets) {
        if (v.resetAt <= now) buckets.delete(k);
      }
    }
    buckets.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return false;
  }
  bucket.count += 1;
  return bucket.count > limit;
}

function plain(status: number, message: string): NextResponse {
  return new NextResponse(message, {
    status,
    headers: {
      "content-type": "text/plain; charset=utf-8",
      "cache-control": "public, max-age=60, s-maxage=300",
      "x-robots-tag": "noindex, nofollow, noarchive",
    },
  });
}

export function proxy(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const ua = request.headers.get("user-agent") || "";

  if (isPrefetch(request)) {
    return new NextResponse(null, {
      status: 204,
      headers: {
        "cache-control": "private, no-store",
        "x-robots-tag": "noindex, nofollow, noarchive",
        "x-borr-prefetch-blocked": "1",
      },
    });
  }

  const isSearchBot = Boolean(ua && ALLOWED_SEARCH_BOTS_RE.test(ua));

  // Hard block known AI/scraper clients before they can invoke SSR/Turso.
  // Legitimate search bots (Googlebot, Bingbot, etc.) and audit tools pass through.
  if (!isSearchBot && (!ua || BLOCKED_UA_RE.test(ua))) {
    return plain(403, "BORR blocks automated crawler traffic on database-backed routes.\n");
  }

  // Deep pagination is almost always crawler behavior and makes OFFSET queries expensive.
  if (pathname.startsWith("/search")) {
    const page = Number.parseInt(searchParams.get("page") || "1", 10) || 1;
    if (page > 20) return plain(410, "Deep search pagination is disabled. Refine your search query.\n");
  }

  const ip = clientIp(request);
  const key = `${ip}:${pathname.startsWith("/paper") ? "/paper" : pathname}`;
  if (!isSearchBot && isRateLimited(key, limitForPath(pathname, isSearchBot))) {
    return plain(429, "Too many requests. Please wait and try again.\n");
  }

  const response = NextResponse.next();
  if (pathname.startsWith("/search") || pathname.startsWith("/api")) {
    response.headers.set("x-robots-tag", "noindex, nofollow, noarchive");
  }
  return response;
}

export const config = {
  matcher: ["/search/:path*", "/paper/:path*", "/api/:path*"],
};
