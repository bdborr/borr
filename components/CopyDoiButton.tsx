"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function CopyDoiButton({ doi }: { doi: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(doi);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable; the DOI is visible as text anyway.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label="Copy DOI"
      className="inline-flex items-center gap-1 ml-2 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none rounded px-1 py-0.5"
    >
      {copied ? <Check className="w-3 h-3 text-borr-green" /> : <Copy className="w-3 h-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
