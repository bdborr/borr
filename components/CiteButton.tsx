"use client";

import { useState } from "react";
import { Quote, Copy, Check, Download, X } from "lucide-react";
import { toBibtex, toRis, toApa, citationKey, type CitablePaper } from "@/lib/citation";

const FORMATS = [
  { id: "bibtex", label: "BibTeX", ext: "bib", mime: "application/x-bibtex" },
  { id: "ris", label: "RIS", ext: "ris", mime: "application/x-research-info-systems" },
  { id: "apa", label: "APA", ext: "txt", mime: "text/plain" },
] as const;

type FormatId = (typeof FORMATS)[number]["id"];

export default function CiteButton({
  paper,
  compact = false,
  align = "left",
}: {
  paper: CitablePaper;
  compact?: boolean;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<FormatId>("bibtex");
  const [copied, setCopied] = useState(false);

  const text = format === "bibtex" ? toBibtex(paper) : format === "ris" ? toRis(paper) : toApa(paper);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (insecure context); user can select the text manually.
    }
  }

  function download() {
    const meta = FORMATS.find((f) => f.id === format)!;
    const blob = new Blob([text], { type: meta.mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${citationKey(paper)}.${meta.ext}`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={
          compact
            ? "inline-flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 px-2 py-1 rounded-md transition-colors focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none"
            : "inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-borr-navy dark:text-blue-200 bg-blue-50 dark:bg-blue-950 hover:bg-blue-100 dark:hover:bg-blue-900 rounded-md transition-colors focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none"
        }
        aria-expanded={open}
      >
        <Quote className={compact ? "w-3 h-3" : "w-4 h-4"} /> Cite
      </button>

      {open && (
        <>
          <button
            type="button"
            aria-label="Close citation panel"
            className="fixed inset-0 z-30 cursor-default"
            onClick={() => setOpen(false)}
          />
          <div className={`absolute z-40 mt-2 ${align === "right" ? "right-0" : "left-0"} w-[min(28rem,calc(100vw-2rem))] bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-4`}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex gap-1" role="tablist">
                {FORMATS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    role="tab"
                    aria-selected={format === f.id}
                    onClick={() => setFormat(f.id)}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                      format === f.id
                        ? "bg-borr-blue text-white"
                        : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <pre className="text-xs bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-700 rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-words max-h-56 overflow-y-auto">
              {text}
            </pre>

            <div className="flex gap-2 mt-3">
              <button
                type="button"
                onClick={copy}
                className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-borr-blue hover:bg-blue-700 rounded-md transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? "Copied" : "Copy"}
              </button>
              <button
                type="button"
                onClick={download}
                className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-md transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Download
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
