"use client";
import { useState, Suspense } from 'react';
import { SearchForm, SearchFormState } from '@/components/search-form';
import { useMutation } from '@tanstack/react-query';
import { searchFts, searchHybrid, searchSemantic, SearchResultItem } from '@/lib/api';
import { ResultCard } from '@/components/result-card';

export default function SearchPage() {
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fts = useMutation({
    mutationFn: searchFts,
    onSuccess: (d) => setResults(d.items || []),
    onError: (e: any) => setError(e?.message || 'Search failed'),
  });
  const semantic = useMutation({
    mutationFn: searchSemantic,
    onSuccess: (d) => setResults(d.items || []),
    onError: (e: any) => setError(e?.message || 'Search failed'),
  });
  const hybrid = useMutation({
    mutationFn: searchHybrid,
    onSuccess: (d) => setResults(d.items || []),
    onError: (e: any) => setError(e?.message || 'Search failed'),
  });

  async function onSubmit(s: SearchFormState) {
    setError(null);
    setResults(null);
    const payload = { q: s.q, document_id: s.document_id || undefined, limit: s.limit };
    if (s.tab === 'fts') await fts.mutateAsync(payload);
    else if (s.tab === 'semantic') await semantic.mutateAsync(payload);
    else await hybrid.mutateAsync(payload);
  }

  const loading = fts.isPending || semantic.isPending || hybrid.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Search</h1>
        <p className="text-sm text-muted-foreground">Run FTS, Semantic, or Hybrid searches.</p>
      </div>

      <Suspense fallback={<div className="h-20 rounded-2xl bg-muted animate-pulse" />}>
        <SearchForm onSubmit={onSubmit} />
      </Suspense>

      {loading && (
        <div className="space-y-3" aria-live="polite">
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
        </div>
      )}

      {error && (
        <div className="text-sm text-destructive" role="alert">
          {error}
        </div>
      )}

      {!loading && results && results.length === 0 && (
        <div className="text-sm text-muted-foreground">No results. Try another query.</div>
      )}

      {!loading && results && results.length > 0 && (
        <div className="grid gap-3">
          {results.map((r, idx) => (
            <ResultCard
              key={idx}
              id={idx}
              documentId={r.document_id}
              title={r.title}
              page={r.page}
              snippet={r.snippet}
              preview={r.preview}
              score={r.score}
              similarity={r.similarity}
            />
          ))}
        </div>
      )}
    </div>
  );
}

