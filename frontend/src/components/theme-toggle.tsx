"use client";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);
  return (
    <button
      className="icon-button"
      aria-label="Toggle color theme"
      onClick={() => {
        document.documentElement.classList.toggle("dark");
        setDark((v) => !v);
      }}
    >
      {dark ? <Sun /> : <Moon />}
    </button>
  );
}
