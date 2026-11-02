"use client";

import { useEffect } from "react";

// Pressing "/" anywhere focuses the nearest search box (Scholar/GitHub convention),
// or jumps to /search when the page has none.
export default function SearchHotkey() {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      const input = document.querySelector<HTMLInputElement>('input[name="q"]');
      if (input) {
        input.focus();
        input.select();
      } else {
        window.location.assign("/search");
      }
    }

    const cancelIdle =
      typeof window !== "undefined" && "requestIdleCallback" in window
        ? window.requestIdleCallback(() => window.addEventListener("keydown", onKeyDown))
        : (setTimeout(() => window.addEventListener("keydown", onKeyDown), 50) as unknown as number);

    return () => {
      if (typeof window !== "undefined") {
        if ("cancelIdleCallback" in window) {
          window.cancelIdleCallback(cancelIdle);
        } else {
          clearTimeout(cancelIdle);
        }
        window.removeEventListener("keydown", onKeyDown);
      }
    };
  }, []);

  return null;
}
