import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "BORR — Bangladesh Open Research Repository";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #16293F 0%, #1E3A5F 55%, #24466E 100%)",
          color: "white",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <svg width="96" height="96" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 7v14" />
            <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
          </svg>
          <div style={{ fontSize: 110, fontWeight: 800, letterSpacing: -3 }}>BORR</div>
        </div>
        <div style={{ fontSize: 36, marginTop: 18, color: "#E5E7EB", fontWeight: 600 }}>
          Bangladesh Open Research Repository
        </div>
        <div style={{ fontSize: 26, marginTop: 28, color: "#9CA3AF" }}>
          An open index of 440,000+ research papers — Research for a Better Bangladesh
        </div>
      </div>
    ),
    size
  );
}
