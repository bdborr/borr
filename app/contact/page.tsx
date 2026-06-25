"use client";

import { useState } from "react";
import { Mail, Copy, Check, Send } from "lucide-react";
import { CONTACT_EMAIL } from "@/lib/contact";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);

  const mailtoSubject = subject.trim() || "BORR — Message from website";
  const mailtoBody = `${message}\n\n— ${name || "A BORR visitor"}${email ? ` (${email})` : ""}`;
  const mailtoHref = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(mailtoSubject)}&body=${encodeURIComponent(mailtoBody)}`;

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(CONTACT_EMAIL);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (insecure context); the address is visible anyway.
    }
  }

  const inputClasses =
    "w-full px-4 py-3 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 rounded-md focus:outline-none focus:ring-2 focus:ring-borr-blue";

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-4">Contact BORR</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-8 leading-relaxed">
        Questions, corrections, takedown requests, or partnership ideas — we&apos;d love to hear from
        you. Reach us directly by email, or fill in the form below and it will open in your mail app
        ready to send.
      </p>

      <div className="mb-8 flex flex-col sm:flex-row sm:items-center gap-3 bg-blue-50 dark:bg-blue-950 border border-blue-100 dark:border-blue-900 rounded-lg p-5">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <Mail className="w-5 h-5 text-borr-blue dark:text-blue-300 shrink-0 mt-0.5" />
          <div className="min-w-0">
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-borr-blue dark:text-blue-300 font-medium hover:underline break-all">
              {CONTACT_EMAIL}
            </a>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Nehal Hasnain
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={copyEmail}
          className="inline-flex items-center justify-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 px-3 py-2 rounded-md transition-colors shrink-0 focus-visible:ring-2 focus-visible:ring-borr-blue focus-visible:outline-none"
        >
          {copied ? <Check className="w-4 h-4 text-borr-green" /> : <Copy className="w-4 h-4" />}
          {copied ? "Copied" : "Copy email"}
        </button>
      </div>

      <div className="bg-white dark:bg-gray-900 p-8 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            window.location.href = mailtoHref;
          }}
          className="space-y-6"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Your name
              </label>
              <input id="name" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Researcher" className={inputClasses} />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Your email
              </label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@university.edu" className={inputClasses} />
            </div>
          </div>

          <div>
            <label htmlFor="subject" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Subject
            </label>
            <input id="subject" type="text" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Metadata correction for a paper" className={inputClasses} />
          </div>

          <div>
            <label htmlFor="message" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Message
            </label>
            <textarea id="message" value={message} onChange={(e) => setMessage(e.target.value)} required rows={6} placeholder="Write your message here…" className={`${inputClasses} resize-y`} />
          </div>

          <button
            type="submit"
            className="w-full inline-flex items-center justify-center gap-2 bg-borr-navy hover:bg-opacity-90 text-white font-semibold py-3 px-4 rounded-md transition-colors disabled:opacity-50"
            disabled={!message.trim()}
          >
            <Send className="w-5 h-5" /> Open in Mail App
          </button>
          <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
            This opens your email program with the message ready to send. Prefer to write it yourself?
            Just email{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-borr-blue dark:text-blue-300 hover:underline">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </form>
      </div>
    </div>
  );
}
