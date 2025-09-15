"use client";
import { useEffect, useRef } from 'react';

export function usePoller(fn: () => void, intervalMs: number, enabled: boolean) {
  const saved = useRef<() => void>(fn);
  useEffect(() => void (saved.current = fn), [fn]);
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => saved.current(), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}

