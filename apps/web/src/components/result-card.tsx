import Link from 'next/link';
import { sanitizeSnippet } from '@/lib/safeHtml';
import { Badge } from '@/components/ui/badge';

export interface ResultCardProps {
  id: string | number;
  documentId: string | number;
  title: string;
  page?: number;
  snippet?: string; // raw HTML from API
  preview?: string;
  score?: number;
  similarity?: number;
}

export function ResultCard({ documentId, title, page, snippet, preview, score, similarity }: ResultCardProps) {
  return (
    <div className="rounded-2xl border p-4 shadow-sm bg-background">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <Link href={`/documents/${documentId}`} className="font-medium hover:underline">
            {title}
          </Link>
          {typeof page === 'number' && (
            <div className="text-xs text-muted-foreground">Page {page}</div>
          )}
        </div>
        <div className="flex gap-2">
          {typeof similarity === 'number' && (
            <Badge variant="secondary">sim {similarity.toFixed(3)}</Badge>
          )}
          {typeof score === 'number' && <Badge variant="outline">score {score.toFixed(3)}</Badge>}
        </div>
      </div>
      {snippet && (
        <div
          className="prose prose-sm mt-3 max-w-none"
          dangerouslySetInnerHTML={{ __html: sanitizeSnippet(snippet) }}
        />
      )}
      {preview && !snippet && (
        <p className="mt-3 text-sm text-muted-foreground line-clamp-3">{preview}</p>
      )}
      <div className="mt-3">
        <Link
          href={`/documents/${documentId}${typeof page === 'number' ? `#page-${page}` : ''}`}
          className="text-sm text-primary underline"
        >
          Open document{typeof page === 'number' ? ` at page ${page}` : ''}
        </Link>
      </div>
    </div>
  );
}

