"use client";
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = (mounted ? resolvedTheme : theme) === 'dark';
  return (
    <button
      aria-label="Toggle theme"
      className="rounded-xl border px-3 py-1.5 text-sm hover:bg-accent"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      title="Toggle theme"
    >
      {isDark ? 'Light' : 'Dark'}
    </button>
  );
}

