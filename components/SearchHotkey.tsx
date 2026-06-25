"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Pressing "/" anywhere focuses the nearest search box (Scholar/GitHub convention),
// or jumps to /search when the page has none.
export default function SearchHotkey() {
  const router = useRouter();

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
        router.push("/search");
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);

  return null;
}
