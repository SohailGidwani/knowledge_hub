"use client";

export function ThinkingLoader({ label = 'Thinking…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2" role="status" aria-live="polite">
      <div className="flex items-center gap-1">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
      <span className="text-xs text-muted-foreground">{label}</span>
      <style jsx>{`
        .dot { width: 6px; height: 6px; border-radius: 9999px; background: #111827; opacity: .35; animation: blink 1.4s infinite; }
        .dot:nth-child(2) { animation-delay: .2s; }
        .dot:nth-child(3) { animation-delay: .4s; }
        @keyframes blink { 0%, 80%, 100% { opacity: .2 } 40% { opacity: .8 } }
        :global(.dark) .dot { background: #e5e7eb; opacity: .6; }
      `}</style>
    </div>
  );
}
