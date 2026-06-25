"use client";

import { useState } from "react";
import Link from "next/link";

export default function AuthorList({ authors, limit = 4 }: { authors: string[]; limit?: number }) {
  const [expanded, setExpanded] = useState(false);

  if (!authors || authors.length === 0) return <span>Unknown</span>;

  const showMore = authors.length > limit;
  const visible = expanded ? authors : authors.slice(0, limit);

  return (
    <span>
      {visible.map((author, i) => (
        <span key={`${author}-${i}`}>
          <Link
            href={`/search?q=${encodeURIComponent(`"${author}"`)}`}
            className="text-borr-blue hover:underline"
          >
            {author}
          </Link>
          {i < visible.length - 1 && ", "}
        </span>
      ))}
      {!expanded && showMore && ", …"}
      {showMore && (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="ml-2 text-borr-blue hover:underline text-sm font-medium focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none rounded"
        >
          {expanded ? "See Less" : `+${authors.length - limit} More`}
        </button>
      )}
    </span>
  );
}
