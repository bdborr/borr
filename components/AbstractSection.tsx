"use client";

import { useState } from "react";

export default function AbstractSection({ abstract }: { abstract: string }) {
  const [expanded, setExpanded] = useState(false);

  const words = abstract.trim().split(/\s+/);
  const isLong = words.length > 120;
  const visible = expanded || !isLong ? abstract : words.slice(0, 120).join(" ") + "…";

  return (
    <div>
      <div className="text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{visible}</div>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="mt-3 text-sm font-medium text-borr-blue hover:underline focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none rounded"
        >
          {expanded ? "Show less" : "Show full abstract"}
        </button>
      )}
    </div>
  );
}
