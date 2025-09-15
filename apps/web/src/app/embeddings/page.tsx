import { EmbeddingsPanel } from '@/components/embeddings-panel';

export default function EmbeddingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Embeddings</h1>
        <p className="text-sm text-muted-foreground">Reindex embeddings for documents.</p>
      </div>
      <EmbeddingsPanel />
    </div>
  );
}

