"use client";

import { useState } from "react";

export default function ExpandableTextList({ items, limit = 4 }: { items: string[], limit?: number }) {
  const [expanded, setExpanded] = useState(false);
  
  if (!items || items.length === 0) return <span>Unknown</span>;

  const showMore = items.length > limit;
  const visibleItems = expanded ? items : items.slice(0, limit);

  return (
    <span>
      {visibleItems.join(", ")}
      {!expanded && showMore && ", ..."}
      {showMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="ml-2 text-borr-blue hover:underline text-sm font-medium focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none rounded"
        >
          {expanded ? "See Less" : `+${items.length - limit} More`}
        </button>
      )}
    </span>
  );
}
