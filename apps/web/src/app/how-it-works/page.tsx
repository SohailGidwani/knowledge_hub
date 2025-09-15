"use client";
import {
  Upload,
  FileText,
  Scissors,
  Database,
  Search,
  MessageSquare,
  Brain,
  Timer,
  Hash,
  HardDrive,
  ShieldCheck,
  Code2,
  Scan,
} from 'lucide-react';
import { SketchCard, SketchArrow } from '@/components/sketch';

export default function HowItWorksPage() {
  return (
    <div className="space-y-10">
      <Hero />
      <TechSummary />
      <Architecture />
      <IngestionFlow />
      <SearchAnswerFlow />
      <DeepDive />
      <ApiCatalog />
      <ConfigDefaults />
      <FAQ />
    </div>
  );
}

function Hero() {
  return (
    <section className="rounded-2xl border bg-background p-6">
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Hub — Architecture Overview</h1>
        <p className="text-sm text-muted-foreground">
          A document intelligence stack: upload → chunk → embed → index → retrieve → on-device LLM answer with citations.
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge icon={ShieldCheck}>On-device LLM</Badge>
          <Badge icon={Brain}>MiniLM Embeddings (384‑d)</Badge>
          <Badge icon={HardDrive}>pgvector IVFFlat</Badge>
          <Badge icon={Hash}>Postgres FTS</Badge>
          <Badge icon={Code2}>Next.js 14 (App Router)</Badge>
        </div>
      </div>
    </section>
  );
}

function Badge({ children, icon: Icon }: { children: React.ReactNode; icon?: any }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 bg-muted/60">
      {Icon && <Icon className="h-3.5 w-3.5" />} {children}
    </span>
  );
}

function TechSummary() {
  const items = [
    { icon: Database, title: 'Database', desc: 'PostgreSQL + pgvector' },
    { icon: HardDrive, title: 'Vector Index', desc: 'IVFFlat (lists=100)' },
    { icon: Brain, title: 'Embeddings', desc: 'all‑MiniLM‑L6‑v2 (384‑d, normalized)' },
    { icon: Scan, title: 'OCR', desc: 'Optional OCR for scanned PDFs' },
    { icon: Hash, title: 'FTS', desc: 'Postgres full‑text search' },
    { icon: Timer, title: 'LLM', desc: 'gemma3:1b via Ollama (on‑device)' },
    { icon: MessageSquare, title: 'Frontend', desc: 'Next.js 14, Tailwind, shadcn, React Query, Zod' },
  ];
  return (
    <section className="rounded-2xl border p-5 bg-background">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((it, i) => (
          <SketchCard key={i} seed={i}>
            <div className="flex items-start gap-3">
              <it.icon className="h-5 w-5" />
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

function IngestionFlow() {
  const steps = [
    { icon: Upload, title: 'Upload', desc: 'POST /api/documents/upload\nFormData(file, title) → 202' },
    { icon: FileText, title: 'Extract', desc: 'Parse text per page + metadata' },
    { icon: Scan, title: 'OCR (optional)', desc: 'If scanned PDFs → OCR to text' },
    { icon: Scissors, title: 'Chunk', desc: 'Segments: (document_id, page_no, chunk_index, text)' },
    { icon: Brain, title: 'Embed', desc: 'SentenceTransformer all‑MiniLM‑L6‑v2 → vector(384), normalized' },
    { icon: Database, title: 'Store & Index', desc: 'Postgres tables + FTS; pgvector IVFFlat (lists=100)' },
  ];
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Ingestion Flow</h2>
      <FlowRow steps={steps} widthClass="w-[360px]" />
      <DetailsCard title="Stored Data Shapes">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>documents: id, title, bytes, mime_type, source_path, status, pages, created_at</li>
          <li>chunks: id, document_id, page_no, chunk_index, text</li>
          <li>embeddings: id, chunk_id, model, vector(384)</li>
        </ul>
      </DetailsCard>
    </section>
  );
}

function Architecture() {
  const steps = [
    { icon: MessageSquare, title: 'Web App', desc: 'Next.js 14 + Tailwind + shadcn\nReact Query + Zod' },
    { icon: Database, title: 'API & Data', desc: 'Flask API + SQLAlchemy\nPostgres + pgvector' },
    { icon: Search, title: 'Retrieval', desc: 'FTS + Vector ANN (IVFFlat)' },
    { icon: Brain, title: 'LLM', desc: 'Ollama (gemma3:1b) on-device' },
  ];
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Architecture</h2>
      <FlowRow steps={steps} widthClass="w-[400px]" />
    </section>
  );
}

function SearchAnswerFlow() {
  const steps = [
    { icon: Search, title: 'Query', desc: 'POST /api/search | /semantic | /hybrid' },
    { icon: Database, title: 'Hybrid Retrieve', desc: 'Embed q → vector ANN + FTS\nWeighted merge, dedupe by (doc,page)' },
    { icon: FileText, title: 'Pack Context', desc: 'Trim to token budget; CONTEXT with [CIT-#]' },
    { icon: MessageSquare, title: 'Prompt', desc: 'System: cite claims, avoid fabrication' },
    { icon: Brain, title: 'LLM', desc: 'POST /api/answer → gemma3:1b (on‑device)' },
  ];
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Search & Answer Flow</h2>
      <FlowRow steps={steps} widthClass="w-[340px]" />
      <DetailsCard title="Signals & Output">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>Answer includes citations [{'{'}CIT‑#{'}'}] mapped to (document_id, page_no, title)</li>
          <li>Timings: retrieve_ms, llm_ms, total_ms</li>
          <li>Used chunk ids reported for auditability</li>
        </ul>
      </DetailsCard>
    </section>
  );
}

function DeepDive() {
  return (
    <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <DetailsCard title="Indexes">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>pgvector IVFFlat on embeddings.vector (lists=100)</li>
          <li>ANALYZE after bulk inserts to refresh stats</li>
          <li>FTS (to_tsvector) on document text for keyword retrieval</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Retrieval Scoring">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>Semantic score + FTS score, tunable alpha/beta weights</li>
          <li>Deduplicate by (document_id, page_no) keeping top score</li>
          <li>Sentence trimming with token rough-count to fit budget</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Prompting & Safety">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>System prompt enforces citations and “no invention” policy</li>
          <li>Retry once with stricter instruction if no citations detected</li>
          <li>Sanitize snippets; render only allowed tags in UI</li>
        </ul>
      </DetailsCard>
    </section>
  );
}

function ApiCatalog() {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">API Catalog</h2>
      <DetailsCard title="Documents">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>POST /api/documents/upload → 202 + {'{'} id, title, mime_type, bytes, source_path, status {'}'}</li>
          <li>GET /api/documents/:id → metadata (status transitions to ready)</li>
          <li>GET /api/documents/:id/chunks?limit=50 → {'{'} items: [chunk] {'}'}</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Search">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>POST /api/search {'{'} q, document_id?, limit? {'}'}</li>
          <li>POST /api/search/semantic {'{'} q, document_id?, limit? {'}'}</li>
          <li>POST /api/search/hybrid {'{'} q, document_id?, limit? {'}'}</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Embeddings">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>POST /api/embeddings/reindex {'{'} document_id? {'}'} → {'{'} indexed, skipped?, message? {'}'}</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Answer">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>POST /api/answer {'{'} q, filters:{'{'}document_id?{'}'}, k?, max_context_tokens? {'}'} → {'{'} answer, citations[], timings {'}'}</li>
        </ul>
      </DetailsCard>
    </section>
  );
}

function ConfigDefaults() {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Configuration & Defaults</h2>
      <DetailsCard title="Server">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>LLM_MODEL: gemma3:1b</li>
          <li>LLM_TIMEOUT_MS: 120000</li>
          <li>EMBEDDINGS_BATCH_SIZE: 128</li>
          <li>pgvector index: IVFFlat (lists=100), vector dim 384</li>
        </ul>
      </DetailsCard>
      <DetailsCard title="Client">
        <ul className="list-disc pl-6 text-sm space-y-1">
          <li>NEXT_PUBLIC_API_BASE (default http://localhost:8000)</li>
          <li>React Query for caching; URL state on search</li>
          <li>Accessibility: labels, aria-live for polling/LLM status</li>
        </ul>
      </DetailsCard>
    </section>
  );
}

function FAQ() {
  return (
    <section className="rounded-2xl border p-5 bg-background">
      <h2 className="text-lg font-semibold">FAQ</h2>
      <div className="mt-3 grid gap-3 text-sm">
        <div>
          <div className="font-medium">Why on-device LLM?</div>
          <div className="text-muted-foreground">Privacy, reliability, and predictable cost. Answers cite exact sources.</div>
        </div>
        <div>
          <div className="font-medium">How is retrieval combined?</div>
          <div className="text-muted-foreground">Weighted hybrid of vector similarity and FTS score, deduped by page.</div>
        </div>
        <div>
          <div className="font-medium">Can I reindex a single document?</div>
          <div className="text-muted-foreground">Yes — POST /api/embeddings/reindex with document_id.</div>
        </div>
      </div>
    </section>
  );
}

function FlowRow({ steps, widthClass, orientation = 'vertical' }: { steps: { icon: any; title: string; desc: string }[]; widthClass?: string; orientation?: 'horizontal' | 'vertical' }) {
  return (
    <div className="rounded-2xl border p-4 bg-background">
      <div className="relative">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_1px_1px,#e5e7eb_1px,transparent_0)] [background-size:16px_16px] rounded-2xl" />
        {orientation === 'vertical' ? (
          <div className="flex flex-col items-center gap-4">
            {steps.map((s, i) => (
              <div key={i} className="flex flex-col items-center gap-2">
                <SketchCard seed={i}>
                  <div className={widthClass ?? 'w-[360px]'}>
                    <div className="flex items-center gap-2">
                      <s.icon className="h-4 w-4" />
                      <div className="text-sm font-medium">{s.title}</div>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 whitespace-pre-wrap">{s.desc}</div>
                  </div>
                </SketchCard>
                {i < steps.length - 1 && (
                  <div className="flex items-center">
                    <SketchArrow direction="down" />
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            {steps.map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <SketchCard seed={i}>
                  <div className={widthClass ?? 'w-[300px]'}>
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
        )}
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
