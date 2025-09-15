"use client";
import { useEffect, useMemo, useRef, useState } from 'react';
import rough from 'roughjs';

export function SketchCard({ children, seed }: { children: React.ReactNode; seed?: number }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const s = useMemo(() => seed ?? 42, [seed]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    function measure() {
      if (!el) return;
      const r = el.getBoundingClientRect();
      setSize({ w: r.width, h: r.height });
    }
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} className="relative rounded-2xl bg-background px-4 py-3 shadow-sm">
      <div className="relative z-10">{children}</div>
      <SketchBorder width={size.w} height={size.h} seed={s} />
    </div>
  );
}

function SketchBorder({ width, height, seed }: { width: number; height: number; seed: number }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    if (!svgRef.current || width <= 0 || height <= 0) return;
    const rc = rough.svg(svgRef.current);
    svgRef.current.innerHTML = '';
    const padding = 6;
    const node = rc.rectangle(padding, padding, Math.max(0, width - padding * 2), Math.max(0, height - padding * 2), {
      roughness: 1.5,
      bowing: 1.3,
      seed,
      stroke: '#111827',
      strokeWidth: 1.5,
      fill: 'transparent',
    });
    svgRef.current.appendChild(node);
  }, [width, height, seed]);
  return (
    <svg ref={svgRef} className="pointer-events-none absolute inset-0" width={width} height={height} aria-hidden />
  );
}

export function SketchArrow({ direction = 'right' as 'right' | 'down' }) {
  // Simple hand-drawn arrow
  const svgRef = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    if (!svgRef.current) return;
    const rc = rough.svg(svgRef.current);
    svgRef.current.innerHTML = '';
    if (direction === 'right') {
      const line = rc.line(0, 10, 40, 10, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      const head1 = rc.line(40, 10, 30, 4, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      const head2 = rc.line(40, 10, 30, 16, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      svgRef.current.appendChild(line);
      svgRef.current.appendChild(head1);
      svgRef.current.appendChild(head2);
    } else {
      const line = rc.line(10, 0, 10, 40, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      const head1 = rc.line(10, 40, 4, 30, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      const head2 = rc.line(10, 40, 16, 30, { stroke: '#111827', strokeWidth: 1.5, roughness: 1.5 });
      svgRef.current.appendChild(line);
      svgRef.current.appendChild(head1);
      svgRef.current.appendChild(head2);
    }
  }, [direction]);
  return (
    <svg ref={svgRef} className="h-6 w-10 md:w-12 text-foreground" aria-hidden />
  );
}

