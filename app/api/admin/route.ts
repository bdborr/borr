import { timingSafeEqual } from "crypto";
import { NextRequest, NextResponse } from "next/server";
import {
  isTursoDatabaseConfigured,
  getUnverifiedLocalPapers,
  setLocalPaperVerified,
  deleteLocalPaper,
} from "@/lib/turso-papers";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 30;
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

  if (bucket.count >= MAX_REQUESTS_PER_WINDOW) return false;
  bucket.count += 1;
  return true;
}

function isAuthorized(request: NextRequest): boolean {
  const expected = process.env.ADMIN_SECRET_KEY;
  const provided = request.headers.get("x-admin-key") || "";

  if (!expected || !provided) return false;

  const expectedBuffer = Buffer.from(expected);
  const providedBuffer = Buffer.from(provided);

  if (expectedBuffer.length !== providedBuffer.length) return false;
  return timingSafeEqual(expectedBuffer, providedBuffer);
}

function unauthorized() {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

export async function GET(request: NextRequest) {
  try {
    if (!checkRateLimit(getClientIp(request))) {
      return NextResponse.json({ error: "Too many requests." }, { status: 429 });
    }

    if (!isAuthorized(request)) return unauthorized();

    if (isTursoDatabaseConfigured) {
      const papers = await getUnverifiedLocalPapers();
      return NextResponse.json({ papers }, { headers: { "Cache-Control": "no-store" } });
    }

    return NextResponse.json({ error: "No database configured." }, { status: 500 });
  } catch (err) {
    console.error("Admin queue error:", err);
    return NextResponse.json({ error: "Failed to load admin queue." }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  try {
    if (!checkRateLimit(getClientIp(request))) {
      return NextResponse.json({ error: "Too many requests." }, { status: 429 });
    }

    if (!isAuthorized(request)) return unauthorized();

    const { id, action } = await request.json();

    if (typeof id !== "string" || !UUID_RE.test(id) || !["approve", "reject"].includes(action)) {
      return NextResponse.json(
        { error: "Invalid request. Provide a valid id and action (approve/reject)." },
        { status: 400 }
      );
    }

    if (isTursoDatabaseConfigured) {
      if (action === "approve") {
        await setLocalPaperVerified(id);
        return NextResponse.json({ success: true, message: "Paper approved." });
      }

      await deleteLocalPaper(id);
      return NextResponse.json({ success: true, message: "Paper rejected and removed." });
    }

    return NextResponse.json({ error: "No database configured." }, { status: 500 });
  } catch (err) {
    console.error("Admin action error:", err);
    return NextResponse.json(
      { error: "Failed to process admin action." },
      { status: 500 }
    );
  }
}
