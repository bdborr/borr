import { NextRequest, NextResponse } from "next/server";

const BLOCKED_UA_RE = /(?:GPTBot|ChatGPT-User|OAI-SearchBot|ClaudeBot|Claude-Web|anthropic-ai|CCBot|Bytespider|PerplexityBot|Amazonbot|Applebot-Extended|Google-Extended|cohere-ai|Diffbot|ImagesiftBot|Omgilibot|meta-externalagent|FacebookBot|DataForSeoBot|SemrushBot|AhrefsBot|MJ12bot|DotBot|BLEXBot|PetalBot|YandexBot|Baiduspider|python-requests|curl|wget|Go-http-client|Java\/|HttpClient|Scrapy|HeadlessChrome|bot\b|crawler|spider|scraper)/i;

const buckets = new Map<string, { count: number; resetAt: number }>();
const WINDOW_MS = 60_000;

function clientIp(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

function limitForPath(pathname: string): number {
  if (pathname.startsWith("/search")) return 12;
  if (pathname.startsWith("/paper")) return 60;
  return 30;
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

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const ua = request.headers.get("user-agent") || "";

  // Hard block known AI/scraper/crawler traffic before it can invoke SSR/Turso.
  if (!ua || BLOCKED_UA_RE.test(ua)) {
    return plain(403, "BORR blocks automated crawler traffic on database-backed routes.\n");
  }

  // Deep pagination is almost always crawler behavior and makes OFFSET queries expensive.
  if (pathname.startsWith("/search")) {
    const page = Number.parseInt(searchParams.get("page") || "1", 10) || 1;
    if (page > 20) return plain(410, "Deep search pagination is disabled. Refine your search query.\n");
  }

  const ip = clientIp(request);
  const key = `${ip}:${pathname.startsWith("/paper") ? "/paper" : pathname}`;
  if (isRateLimited(key, limitForPath(pathname))) {
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
