"use client";
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { z } from 'zod';
import { useRouter, useSearchParams } from 'next/navigation';

const schema = z.object({
  q: z.string().min(1, 'Enter a query'),
  document_id: z.string().optional(),
  limit: z.coerce.number().min(1).max(50).default(10),
  tab: z.enum(['fts', 'semantic', 'hybrid']).default('hybrid'),
});

export type SearchFormState = z.infer<typeof schema>;

const HISTORY_KEY = 'khub_recent_queries_v1';

export function SearchForm({ onSubmit }: { onSubmit: (s: SearchFormState) => void }) {
  const params = useSearchParams();
  const router = useRouter();

  // Relaxed parsing for URL params so empty q doesn't throw; enforce on submit
  const initial: SearchFormState = useMemo(() => {
    const relaxed = z.object({
      q: z.string().default(''),
      document_id: z.string().optional(),
      limit: z.coerce.number().min(1).max(50).default(10),
      tab: z.enum(['fts', 'semantic', 'hybrid']).default('hybrid'),
    });
    return relaxed.parse({
      q: params.get('q') ?? undefined,
      document_id: params.get('document_id') ?? undefined,
      limit: params.get('limit') ?? undefined,
      tab: (params.get('tab') as any) ?? undefined,
    }) as SearchFormState;
  }, [params]);

  const [state, setState] = useState<SearchFormState>(initial);
  const [onlyThisDoc, setOnlyThisDoc] = useState<boolean>(!!initial.document_id);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setState(initial), [initial]);

  const updateUrl = useCallback(
    (s: SearchFormState) => {
      const usp = new URLSearchParams();
      usp.set('q', s.q);
      usp.set('tab', s.tab);
      if (s.document_id) usp.set('document_id', s.document_id);
      usp.set('limit', String(s.limit));
      router.replace(`/search?${usp.toString()}`);
    },
    [router],
  );

  function pushHistory(q: string) {
    try {
      const arr = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') as string[];
      const next = [q, ...arr.filter((x) => x !== q)].slice(0, 10);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
    } catch {}
  }

  function getHistory(): string[] {
    try {
      return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') as string[];
    } catch {
      return [];
    }
  }

  const submit = useCallback(
    (s: SearchFormState) => {
      const parsed = schema.safeParse(s);
      if (!parsed.success) {
        setError(parsed.error.errors[0]?.message || 'Invalid input');
        return;
      }
      setError(null);
      const final = parsed.data;
      updateUrl(final);
      pushHistory(final.q);
      onSubmit(final);
    },
    [onSubmit, updateUrl],
  );

  function handleEnter(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') submit(state);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1 space-y-2">
          <label htmlFor="q" className="sr-only">
            Query
          </label>
          <Input
            id="q"
            placeholder="Search..."
            value={state.q}
            onChange={(e) => setState({ ...state, q: e.target.value })}
            onKeyDown={handleEnter}
            aria-invalid={!!error}
            aria-describedby={error ? 'q-error' : undefined}
          />
          {error && (
            <div id="q-error" className="text-sm text-destructive" role="alert">
              {error}
            </div>
          )}
          <div className="flex items-center gap-2 text-sm">
            <input
              id="only-doc"
              type="checkbox"
              checked={onlyThisDoc}
              onChange={(e) => {
                setOnlyThisDoc(e.target.checked);
                const document_id = e.target.checked ? state.document_id || '' : undefined;
                const next = { ...state, document_id } as SearchFormState;
                setState(next);
                updateUrl(next);
              }}
            />
            <label htmlFor="only-doc">Only this document</label>
          </div>
        </div>
        <div className="flex gap-2 sm:items-start">
          <select
            className="h-10 rounded-xl border border-input bg-transparent px-3 text-sm"
            value={state.limit}
            onChange={(e) => setState({ ...state, limit: Number(e.target.value) })}
            aria-label="Limit"
          >
            {[10, 20, 50].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <Button onClick={() => submit(state)}>Search</Button>
        </div>
      </div>

      <div className="text-xs text-muted-foreground flex gap-2 flex-wrap" aria-live="polite">
        Recent:
        {getHistory().map((q) => (
          <button
            key={q}
            className="underline"
            onClick={() => {
              const next = { ...state, q } as SearchFormState;
              setState(next);
              submit(next);
            }}
          >
            {q}
          </button>
        ))}
      </div>

      <Tabs value={state.tab} onValueChange={(tab) => setState({ ...state, tab: tab as any })}>
        <TabsList>
          <TabsTrigger value="fts">FTS</TabsTrigger>
          <TabsTrigger value="semantic">Semantic</TabsTrigger>
          <TabsTrigger value="hybrid">Hybrid</TabsTrigger>
        </TabsList>
        <TabsContent value={state.tab}>
          <div className="flex gap-2">
            <Button onClick={() => submit({ ...state, tab: state.tab })}>Search {state.tab}</Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
