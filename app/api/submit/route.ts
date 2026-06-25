import { NextRequest, NextResponse } from "next/server";
import { isTursoDatabaseConfigured, localDoiExists, insertLocalPaper } from "@/lib/turso-papers";
import { normalizeDoi, safeExternalUrl, stripMarkup } from "@/lib/metadata";

const WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 10;
const rateLimit = new Map<string, { count: number; resetAt: number }>();

function getClientIp(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const bucket = rateLimit.get(ip);

  if (!bucket || bucket.resetAt <= now) {
    // Evict expired buckets so the map can't grow unbounded on a long-lived
    // instance. (Note: this limiter is per-instance; for distributed/serverless
    // deployments back it with a shared store like Redis/Upstash.)
    if (rateLimit.size > 5000) {
      for (const [key, b] of rateLimit) {
        if (b.resetAt <= now) rateLimit.delete(key);
      }
    }
    rateLimit.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return true;
  }

  if (bucket.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }

  bucket.count += 1;
  return true;
}

async function fetchCrossrefWork(doi: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);

  try {
    const crossrefRes = await fetch(
      `https://api.crossref.org/works/${encodeURIComponent(doi)}`,
      {
        headers: { "User-Agent": "BORR/1.0 (mailto:contact@borr.org.bd)" },
        signal: controller.signal,
      }
    );

    if (!crossrefRes.ok) {
      return null;
    }

    const crossrefData = await crossrefRes.json();
    return crossrefData.message;
  } finally {
    clearTimeout(timeout);
  }
}

export async function POST(request: NextRequest) {
  try {
    if (!request.headers.get("content-type")?.includes("application/json")) {
      return NextResponse.json({ error: "Content-Type must be application/json." }, { status: 415 });
    }

    const ip = getClientIp(request);
    if (!checkRateLimit(ip)) {
      return NextResponse.json({ error: "Too many submissions. Please wait and try again." }, { status: 429 });
    }

    const { doi } = await request.json();
    const cleanDoi = normalizeDoi(doi);

    if (!cleanDoi) {
      return NextResponse.json({ error: "A valid DOI is required." }, { status: 400 });
    }

    if (isTursoDatabaseConfigured) {
      if (await localDoiExists(cleanDoi)) {
        return NextResponse.json({ error: "This paper is already in the BORR database." }, { status: 409 });
      }
    } else {
      return NextResponse.json({ error: "No database configured." }, { status: 500 });
    }

    const work = await fetchCrossrefWork(cleanDoi);
    if (!work) {
      return NextResponse.json(
        { error: "Could not find this DOI on Crossref. Please check the DOI and try again." },
        { status: 404 }
      );
    }

    const authors = (work.author || [])
      .map((a: { given?: string; family?: string }) => [a.given, a.family].filter(Boolean).join(" ").trim())
      .filter(Boolean);

    const title = stripMarkup(Array.isArray(work.title) ? work.title[0] : work.title) || "Untitled";
    const abstract = stripMarkup(work.abstract);
    const journal = stripMarkup(work["container-title"]?.[0]);
    const year = Number.isInteger(work.published?.["date-parts"]?.[0]?.[0])
      ? work.published["date-parts"][0][0]
      : null;
    const url = safeExternalUrl(work.URL, cleanDoi);

    const paperRecord = {
      title,
      authors,
      abstract,
      doi: cleanDoi,
      url,
      journal,
      year,
      institution: [] as string[],
      fields: Array.isArray(work.subject) ? work.subject.slice(0, 10).map(String) : [],
      paper_type: "Other",
      access_type: "Unknown",
      source: "Community",
      verified: false,
      citation_count: Number.isInteger(work["is-referenced-by-count"]) ? work["is-referenced-by-count"] : 0,
    };

    if (isTursoDatabaseConfigured) {
      try {
        await insertLocalPaper(paperRecord);
      } catch (insertError: unknown) {
        // SQLite unique constraint error code varies, but usually contains "UNIQUE constraint failed"
        const errMsg = insertError instanceof Error ? insertError.message : String(insertError);
        if (errMsg.includes("UNIQUE constraint failed")) {
          return NextResponse.json({ error: "This paper is already in the BORR database." }, { status: 409 });
        }
        console.error("Database insert error:", insertError);
        return NextResponse.json(
          { error: "Failed to submit the paper. Please try again later." },
          { status: 500 }
        );
      }
    } else {
      return NextResponse.json({ error: "No database configured." }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      message: "Paper submitted successfully! It will appear after moderation review.",
      paper: { title, authors, journal, year, doi: cleanDoi },
    });
  } catch (err) {
    console.error("Submit error:", err);
    return NextResponse.json(
      { error: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}
