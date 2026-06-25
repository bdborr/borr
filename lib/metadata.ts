export function normalizeDoi(input: unknown): string | null {
  if (typeof input !== "string") return null;

  const doi = input
    .trim()
    .replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")
    .replace(/^doi:\s*/i, "")
    .trim()
    .toLowerCase();

  if (!doi || doi.length > 255) return null;
  if (!/^10\.\d{4,9}\/\S+$/.test(doi)) return null;

  return doi;
}

export function safeExternalUrl(input: unknown, doi?: string | null): string {
  const fallback = doi ? `https://doi.org/${doi}` : "https://doi.org/";

  if (typeof input !== "string" || !input.trim()) {
    return fallback;
  }

  try {
    const parsed = new URL(input);
    if (!["https:", "http:"].includes(parsed.protocol)) {
      return fallback;
    }
    return parsed.toString();
  } catch {
    return fallback;
  }
}

// Escape a value for safe embedding inside an inline <script> tag (e.g. JSON-LD).
// Neutralizes the `</script>`/`<!--` breakout (<, >, &) and the U+2028/U+2029
// line separators that are valid in JSON but break inline-script parsing.
export function escapeJsonForHtml(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

export function stripMarkup(input: unknown): string | null {
  if (typeof input !== "string") return null;
  const stripped = input.replace(/<[^>]*>/g, "").trim();
  return stripped || null;
}
