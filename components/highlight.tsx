import type { ReactNode } from "react";

export function highlightText(text: string, query: string): ReactNode {
  if (!query || !text) return text;
  const words = query.split(/\s+/).filter(Boolean);
  if (words.length === 0) return text;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "gi");
  const matcher = new RegExp(`^(${escaped.join("|")})$`, "i");
  return text.split(regex).map((part, i) =>
    matcher.test(part) ? (
      <mark key={i} className="bg-yellow-200 dark:bg-yellow-700/60 text-gray-900 dark:text-gray-100 rounded px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  );
}
