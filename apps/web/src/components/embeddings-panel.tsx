"use client";
import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { reindexEmbeddings } from '@/lib/api';

export function EmbeddingsPanel() {
  const [documentId, setDocumentId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit() {
    setLoading(true);
    setError(null);
    setLog((l) => [...l, 'Submitting reindex request...']);
    try {
      const res = await reindexEmbeddings({ document_id: documentId || undefined });
      setResult(res);
      setLog((l) => [...l, 'Reindex completed.']);
    } catch (e: any) {
      setError(e?.message || 'Failed to reindex');
      setLog((l) => [...l, `Error: ${e?.message}`]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          placeholder="Optional document_id"
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
        />
        <Button onClick={onSubmit} disabled={loading}>
          {loading ? 'Reindexing…' : 'Reindex embeddings'}
        </Button>
      </div>
      {error && (
        <div role="alert" className="text-sm text-destructive">
          {error}
        </div>
      )}
      {result && (
        <div className="rounded-2xl border p-3 text-sm">
          <div>Indexed: {result.indexed}</div>
          {result.skipped != null && <div>Skipped: {result.skipped}</div>}
          {result.message && <div>Message: {result.message}</div>}
        </div>
      )}
      <div className="rounded-2xl border p-3 text-xs h-32 overflow-auto bg-muted/50">
        {log.map((l, i) => (
          <div key={i}>{l}</div>
        ))}
      </div>
    </div>
  );
}

