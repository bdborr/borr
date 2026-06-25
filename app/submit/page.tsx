"use client";

import { useState } from "react";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";

export default function SubmitPage() {
  const [doi, setDoi] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [paperPreview, setPaperPreview] = useState<{
    title?: string;
    authors?: string[];
    journal?: string;
    year?: number;
  } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus("loading");
    setMessage("");
    setPaperPreview(null);

    try {
      const res = await fetch("/api/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi }),
      });

      const data = await res.json();

      if (!res.ok) {
        setStatus("error");
        setMessage(data.error || "Something went wrong.");
        return;
      }

      setStatus("success");
      setMessage(data.message);
      setPaperPreview(data.paper);
      setDoi("");
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-6">Submit a Paper to BORR</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-8 leading-relaxed">
        Help build the largest open database of Bangladeshi research. Enter the DOI of the paper
        below, and our system will automatically fetch the metadata from Crossref. All submissions
        go through a quick human moderation queue to ensure accuracy.
      </p>

      <div className="bg-white dark:bg-gray-900 p-8 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="doi" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Digital Object Identifier (DOI)
            </label>
            <input
              type="text"
              id="doi"
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              placeholder="e.g. 10.1038/s41586-020-2649-2"
              className="w-full px-4 py-3 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 rounded-md focus:outline-none focus:ring-2 focus:ring-borr-blue"
              required
              disabled={status === "loading"}
            />
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Must be a valid DOI. We do not accept raw PDF uploads.
            </p>
          </div>

          <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-md border border-blue-100 dark:border-blue-900">
            <h3 className="text-sm font-medium text-borr-navy dark:text-blue-200 mb-2">Before you submit:</h3>
            <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 list-disc list-inside">
              <li>Ensure at least one author is Bangladeshi, or the paper is about Bangladesh.</li>
              <li>Verify that the DOI links to the official publisher&apos;s version of record.</li>
              <li>We accept all globally published papers regardless of their access type.</li>
              <li>Submissions must be officially accepted, published, or hosted on a recognized preprint server.</li>
              <li>The submitted title, abstract, and author list must perfectly match the official publication record.</li>
            </ul>
          </div>

          {status === "error" && (
            <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-900 text-red-700 dark:text-red-300 px-4 py-3 rounded-md flex items-start gap-3">
              <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
              <p className="text-sm">{message}</p>
            </div>
          )}

          {status === "success" && (
            <div className="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-900 text-green-700 dark:text-green-300 px-4 py-3 rounded-md">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium">{message}</p>
                  {paperPreview && (
                    <div className="mt-3 text-xs text-green-600 dark:text-green-400 space-y-1">
                      <p><span className="font-semibold">Title:</span> {paperPreview.title}</p>
                      <p><span className="font-semibold">Authors:</span> {paperPreview.authors?.join(", ")}</p>
                      {paperPreview.journal && <p><span className="font-semibold">Journal:</span> {paperPreview.journal}</p>}
                      {paperPreview.year && <p><span className="font-semibold">Year:</span> {paperPreview.year}</p>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={status === "loading"}
            className="w-full bg-borr-navy hover:bg-opacity-90 text-white font-semibold py-3 px-4 rounded-md transition-colors disabled:opacity-50 flex items-center justify-center"
          >
            {status === "loading" ? (
              <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Fetching Metadata...</>
            ) : (
              "Fetch Metadata & Submit"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
