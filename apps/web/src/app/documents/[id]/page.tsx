"use client";
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { getDocument, getChunks, DocumentMeta as Doc, ChunkItem } from '@/lib/api';
import { DocumentMeta } from '@/components/document-meta';
import { Button } from '@/components/ui/button';

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: doc, isLoading, isError, error, refetch } = useQuery<Doc>({
    queryKey: ['document', id],
    queryFn: () => getDocument(id),
    // TanStack v5 passes the Query object here, not the data directly
    refetchInterval: (q) => (q.state.data?.status === 'processing' ? 2000 : false),
  });

  const { data: chunks } = useQuery<{ items: ChunkItem[] }>({
    queryKey: ['chunks', id, 50],
    queryFn: () => getChunks(id, 50),
    enabled: !!doc && doc.status === 'ready',
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Document</h1>
          <p className="text-sm text-muted-foreground">ID: {id}</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => router.push(`/search?document_id=${encodeURIComponent(id)}`)}
        >
          Search in this document
        </Button>
      </div>

      {isLoading && (
        <div className="space-y-3">
          <div className="h-24 rounded-2xl bg-muted animate-pulse" />
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
        </div>
      )}

      {isError && (
        <div role="alert" className="text-sm text-destructive">
          {(error as any)?.message || 'Failed to load document'}
        </div>
      )}

      {doc && <DocumentMeta doc={doc} />}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Chunks</h2>
          <Button variant="ghost" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>
        {!chunks && (
          <div className="text-sm text-muted-foreground">
            {doc?.status === 'processing' ? 'Processing… chunks will appear when ready.' : 'No chunks.'}
          </div>
        )}
        {chunks && chunks.items.length === 0 && (
          <div className="text-sm text-muted-foreground">No chunks found.</div>
        )}
        {chunks && chunks.items.length > 0 && (
          <div className="grid gap-3">
            {chunks.items.map((c) => (
              <div key={c.id} className="rounded-2xl border p-3 text-sm bg-background">
                <div className="text-xs text-muted-foreground">Page {c.page ?? '-'}</div>
                <div className="mt-1 whitespace-pre-wrap">{c.text}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
