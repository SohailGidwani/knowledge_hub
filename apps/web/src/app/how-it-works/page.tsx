"use client";
import { Upload, FileText, Scissors, Database, Search, MessageSquare, Brain, Timer, Hash, HardDrive } from 'lucide-react';
import { SketchCard, SketchArrow } from '@/components/sketch';

export default function HowItWorksPage() {
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-xl font-semibold">How It Works</h1>
        <p className="text-sm text-muted-foreground">From upload → chunking → indexing → retrieval → on-device LLM answers.</p>
      </header>

      <TechSummary />

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Ingestion Pipeline</h2>
        <FlowRow
          steps={[
            { icon: Upload, title: 'Upload', desc: 'POST /api/documents/upload\nFormData(file,title)' },
            { icon: FileText, title: 'Extract', desc: 'Text + metadata per page' },
            { icon: Scissors, title: 'Chunk', desc: 'Segments with (document_id, page_no, chunk_index)' },
            { icon: Brain, title: 'Embed', desc: 'all-MiniLM-L6-v2 → vector(384) normalized' },
            { icon: Database, title: 'Store & Index', desc: 'Postgres + pgvector + FTS\nIVFFlat (lists=100)' },
          ]}
        />
        <DetailsCard title="Stored Data Shapes">
          <ul className="list-disc pl-6 text-sm space-y-1">
            <li>documents: id, title, bytes, mime_type, source_path, status, pages, created_at</li>
            <li>chunks: id, document_id, page_no, chunk_index, text</li>
            <li>embeddings: id, chunk_id, model, vector(384)</li>
          </ul>
        </DetailsCard>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Search & Answer Pipeline</h2>
        <FlowRow
          steps={[
            { icon: Search, title: 'Query', desc: 'POST /api/search | /semantic | /hybrid' },
            { icon: Database, title: 'Hybrid Retrieve', desc: 'Embed q + vector ANN + FTS\nweighted merge, dedupe by page' },
            { icon: FileText, title: 'Pack Context', desc: 'Trim by tokens; CONTEXT with [CIT-#]' },
            { icon: MessageSquare, title: 'Prompt', desc: 'System: cite claims, no fabrication' },
            { icon: Brain, title: 'LLM', desc: 'POST /api/answer → gemma3:1b' },
          ]}
        />
        <DetailsCard title="API Map">
          <ul className="list-disc pl-6 text-sm space-y-1">
            <li>POST /api/documents/upload → 202 + document meta</li>
            <li>GET /api/documents/:id → metadata (status: processing → ready)</li>
            <li>GET /api/documents/:id/chunks?limit=50 → chunk list</li>
            <li>POST /api/search | /api/search/semantic | /api/search/hybrid → results with snippet, preview</li>
            <li>POST /api/embeddings/reindex {`{ document_id? }`} → counts</li>
            <li>POST /api/answer {`{ q, filters:{document_id?}, k?, max_context_tokens? }`} → answer + citations + timings</li>
          </ul>
        </DetailsCard>
      </section>
    </div>
  );
}

function TechSummary() {
  const items = [
    { icon: Database, title: 'Database', desc: 'PostgreSQL + pgvector' },
    { icon: HardDrive, title: 'Vector Index', desc: 'IVFFlat (lists=100)' },
    { icon: Brain, title: 'Embeddings', desc: 'all-MiniLM-L6-v2 (384-d)' },
    { icon: Hash, title: 'FTS', desc: 'Postgres full-text search' },
    { icon: Timer, title: 'On-device LLM', desc: 'gemma3:1b with Ollama' },
    { icon: MessageSquare, title: 'Frontend', desc: 'Next.js 14, Tailwind, shadcn, React Query, Zod' },
  ];
  return (
    <section className="rounded-2xl border p-4 bg-background">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((it, i) => (
          <SketchCard key={i} seed={i}>
            <div className="flex items-start gap-3">
              <it.icon className="h-5 w-5 text-foreground" />
              <div>
                <div className="text-sm font-medium">{it.title}</div>
                <div className="text-xs text-muted-foreground">{it.desc}</div>
              </div>
            </div>
          </SketchCard>
        ))}
      </div>
    </section>
  );
}

function FlowRow({ steps }: { steps: { icon: any; title: string; desc: string }[] }) {
  return (
    <div className="rounded-2xl border p-4 bg-background">
      <div className="relative">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_1px_1px,#e5e7eb_1px,transparent_0)] [background-size:16px_16px] rounded-2xl" />
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <SketchCard seed={i}>
                <div className="w-[280px]">
                  <div className="flex items-center gap-2">
                    <s.icon className="h-4 w-4" />
                    <div className="text-sm font-medium">{s.title}</div>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{s.desc}</div>
                </div>
              </SketchCard>
              {i < steps.length - 1 && (
                <div className="hidden md:flex items-center">
                  <SketchArrow direction="right" />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DetailsCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border p-4 bg-background">
      <div className="text-sm font-medium mb-2">{title}</div>
      {children}
    </section>
  );
}
