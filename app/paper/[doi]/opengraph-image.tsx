import { ImageResponse } from "next/og";
import { getLocalPaperByKey, isTursoDatabaseConfigured } from "@/lib/turso-papers";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage({
  params,
}: {
  params: Promise<{ doi: string }>;
}) {
  const resolved = await params;
  let paper = null;
  if (isTursoDatabaseConfigured) {
    try {
      paper = await getLocalPaperByKey(resolved.doi);
    } catch {}
  }

  const title = paper?.title || "Research Paper";
  const author =
    paper?.authors && paper.authors.length > 0
      ? paper.authors.slice(0, 3).join(", ")
      : "Bangladeshi Researchers";
  const journal = paper?.journal || "Scholarly Publication";
  const year = paper?.year ? String(paper.year) : "";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "linear-gradient(135deg, #0F172A 0%, #1E3A5F 50%, #0F2338 100%)",
          color: "white",
          padding: 60,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#60A5FA"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 7v14" />
              <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
            </svg>
            <span style={{ fontSize: 32, fontWeight: 800, letterSpacing: -1, color: "white" }}>
              BORR
            </span>
          </div>
          <span style={{ fontSize: 18, color: "#93C5FD", fontWeight: 600 }}>
            Bangladesh Open Research Repository
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              fontSize: title.length > 90 ? 36 : 44,
              fontWeight: 800,
              lineHeight: 1.25,
              color: "#F8FAFC",
              maxHeight: 220,
              overflow: "hidden",
            }}
          >
            {title}
          </div>
          <div style={{ fontSize: 24, color: "#94A3B8" }}>
            {author} {year ? `(${year})` : ""}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid #334155",
            paddingTop: 20,
          }}
        >
          <span style={{ fontSize: 20, color: "#38BDF8", fontWeight: 600 }}>{journal}</span>
          <span style={{ fontSize: 18, color: "#64748B" }}>borrbd.org</span>
        </div>
      </div>
    ),
    size
  );
}
