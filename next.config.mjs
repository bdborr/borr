/** @type {import('next').NextConfig} */

// Content-Security-Policy.
// Next.js (App Router) injects inline bootstrap/hydration scripts and next/font
// injects an inline <style>, so without per-request nonce middleware we must
// allow 'unsafe-inline' here. This still blocks the high-value vectors:
// external/injected <script> and <object> sources, clickjacking (frame-ancestors),
// <base> hijacking, off-site form posts, and it forces sub-resources onto HTTPS.
// 'unsafe-eval' is only needed by the dev/Turbopack runtime, so it is dev-only.
const isProd = process.env.NODE_ENV === "production";
const isDeploy = Boolean(process.env.VERCEL || (process.env.NEXT_PUBLIC_SITE_URL && process.env.NEXT_PUBLIC_SITE_URL.startsWith("https://")));

const cspDirectives = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${!isProd ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
];

if (isDeploy) {
  cspDirectives.push("upgrade-insecure-requests");
}

const contentSecurityPolicy = cspDirectives.join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

if (isDeploy) {
  securityHeaders.push({
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  });
}

const nextConfig = {
  poweredByHeader: false,
  compress: true,
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
      {
        source: "/search",
        headers: [
          { key: "Cache-Control", value: "public, s-maxage=600, stale-while-revalidate=86400" },
        ],
      },
    ];
  },
};

export default nextConfig;
