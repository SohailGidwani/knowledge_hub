import { DocumentMeta as Doc } from '@/lib/api';
import { formatBytes, formatDate } from '@/lib/format';
import { StatusPill } from '@/components/status-pill';

function Copy({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <button
      onClick={() => navigator.clipboard.writeText(text)}
      className="text-xs text-primary underline"
      aria-label="Copy to clipboard"
    >
      Copy
    </button>
  );
}

export function DocumentMeta({ doc }: { doc: Doc }) {
  const items = [
    { label: 'Title', value: doc.title },
    { label: 'Status', value: <StatusPill status={doc.status} /> },
    { label: 'Pages', value: doc.pages ?? '-' },
    { label: 'Bytes', value: formatBytes(doc.bytes) },
    { label: 'MIME', value: doc.mime_type },
    { label: 'SHA256', value: doc.hash_sha256 },
    { label: 'Source Path', value: doc.source_path },
    { label: 'Created', value: formatDate(doc.created_at) },
    { label: 'Updated', value: formatDate(doc.updated_at) },
  ];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {items.map((it) => (
        <div key={it.label} className="rounded-2xl border bg-background p-3">
          <div className="text-xs text-muted-foreground">{it.label}</div>
          <div className="mt-1 text-sm flex items-center gap-2">
            <span>{typeof it.value === 'string' || typeof it.value === 'number' ? it.value : it.value}</span>
            {typeof it.value === 'string' && <Copy text={it.value} />}
          </div>
        </div>
      ))}
    </div>
  );
}

