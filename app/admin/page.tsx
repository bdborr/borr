"use client";

import { useState } from "react";
import { CheckCircle, XCircle, ShieldAlert, Loader2 } from "lucide-react";

interface AdminPaper {
  id: string;
  title: string;
  authors: string[];
  doi: string;
  source: string | null;
  abstract: string | null;
}

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [papers, setPapers] = useState<AdminPaper[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function fetchQueue(key = adminKey) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/admin", {
        method: "GET",
        headers: { "x-admin-key": key },
        cache: "no-store",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to load queue.");
      }
      setPapers(data.papers || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load queue.");
      setPapers([]);
    }
    setLoading(false);
  }

  async function handleAction(id: string, action: "approve" | "reject") {
    setActionLoading(id);
    try {
      const res = await fetch("/api/admin", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "x-admin-key": adminKey,
        },
        body: JSON.stringify({ id, action }),
      });

      if (res.ok) {
        setPapers((prev) => prev.filter((p) => p.id !== id));
      } else {
        const data = await res.json();
        alert(data.error || "Action failed.");
      }
    } catch {
      alert("Network error.");
    }
    setActionLoading(null);
  }

  function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    const key = adminKey.trim();
    if (key) {
      setAdminKey(key);
      setAuthenticated(true);
      fetchQueue(key);
    }
  }

  if (!authenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20">
        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 text-center">
          <ShieldAlert className="mx-auto h-12 w-12 text-borr-navy mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Admin Access</h1>
          <p className="text-gray-500 mb-6 text-sm">Enter the admin secret key to access the moderation queue.</p>
          <form onSubmit={handleLogin} className="space-y-4">
            <input type="password" value={adminKey} onChange={(e) => setAdminKey(e.target.value)} placeholder="Admin Secret Key" className="w-full px-4 py-3 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-borr-blue" required />
            <button type="submit" className="w-full bg-borr-navy text-white font-semibold py-3 px-4 rounded-md hover:bg-opacity-90 transition-colors">Access Queue</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-12">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Admin Moderation Queue</h1>
        <div className="flex items-center gap-3">
          <button onClick={() => fetchQueue()} className="text-sm px-3 py-1 rounded-md border border-gray-300 hover:bg-gray-50">Refresh</button>
          <span className="bg-amber-100 text-amber-800 text-sm px-3 py-1 rounded-full font-medium">{papers.length} Pending</span>
        </div>
      </div>

      {error && <div className="mb-6 bg-red-50 text-red-700 p-4 rounded-md border border-red-200">{error}</div>}

      {loading ? (
        <div className="text-center py-16"><Loader2 className="mx-auto h-8 w-8 text-gray-400 animate-spin" /></div>
      ) : papers.length > 0 ? (
        <div className="bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
          <ul className="divide-y divide-gray-200">
            {papers.map((paper) => (
              <li key={paper.id} className="p-6 hover:bg-gray-50 transition-colors">
                <div className="flex flex-col lg:flex-row justify-between gap-6">
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-gray-900 mb-1">{paper.title}</h3>
                    <p className="text-sm text-gray-600 mb-2">{paper.authors.join(", ")}</p>
                    <div className="text-xs text-gray-500 mb-2"><span className="font-semibold text-gray-700 mr-1">DOI:</span> {paper.doi}<span className="mx-2">&bull;</span><span className="font-semibold text-gray-700 mr-1">Source:</span> {paper.source || "Manual"}</div>
                    {paper.abstract && <p className="text-sm text-gray-700 line-clamp-2 mt-2">{paper.abstract}</p>}
                  </div>
                  <div className="flex lg:flex-col justify-end gap-3 shrink-0">
                    <button onClick={() => handleAction(paper.id, "approve")} disabled={actionLoading === paper.id} className="flex items-center justify-center bg-green-50 hover:bg-green-100 text-green-700 border border-green-200 px-4 py-2 rounded-md font-medium text-sm transition-colors disabled:opacity-50"><CheckCircle className="w-4 h-4 mr-2" /> Approve</button>
                    <button onClick={() => handleAction(paper.id, "reject")} disabled={actionLoading === paper.id} className="flex items-center justify-center bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 px-4 py-2 rounded-md font-medium text-sm transition-colors disabled:opacity-50"><XCircle className="w-4 h-4 mr-2" /> Reject</button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="bg-white p-12 text-center rounded-xl border border-gray-200 shadow-sm"><CheckCircle className="mx-auto h-12 w-12 text-green-500 mb-4" /><h3 className="text-xl font-medium text-gray-900 mb-2">Queue is empty!</h3><p className="text-gray-500">All submissions have been moderated.</p></div>
      )}
    </div>
  );
}
