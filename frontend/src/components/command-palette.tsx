"use client";
import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { navigation } from "@/lib/navigation";
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const router = useRouter();
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  return (
    <>
      {
        <button className="search-trigger" onClick={() => setOpen(true)}>
          <Search />
          Search anything <kbd>⌘ K</kbd>
        </button>
      }
      {open && (
        <div className="modal-backdrop" onMouseDown={() => setOpen(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            className="command"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <div className="command-input">
              <Search />
              <input
                autoFocus
                placeholder="Search pages and actions…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <button aria-label="Close" onClick={() => setOpen(false)}>
                <X />
              </button>
            </div>
            <div className="command-results">
              {navigation
                .filter((i) => i.label.toLowerCase().includes(q.toLowerCase()))
                .map((item) => (
                  <button
                    key={item.href}
                    onClick={() => {
                      router.push(item.href);
                      setOpen(false);
                    }}
                  >
                    <item.icon />
                    {item.label}
                    <span>{item.href}</span>
                  </button>
                ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
