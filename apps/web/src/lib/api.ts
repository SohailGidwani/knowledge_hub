export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  info?: any;
  constructor(message: string, status: number, info?: any) {
    super(message);
    this.status = status;
    this.info = info;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const headers = new Headers(init.headers || {});
  if (!headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('Accept', 'application/json');
  const res = await fetch(url, { ...init, headers });
  const isJson = res.headers.get('content-type')?.includes('application/json');
  const data = isJson ? await res.json().catch(() => undefined) : undefined;
  if (!res.ok) {
    const msg = (data && (data.message || data.detail)) || `Request failed: ${res.status}`;
    throw new ApiError(msg, res.status, data);
  }
  return data as T;
}

// Types (based on provided contracts)
export type DocumentStatus = 'ready' | 'processing' | 'error';
export interface DocumentMeta {
  id: number | string;
  title: string;
  mime_type: string;
  bytes: number;
  hash_sha256?: string;
  source_path?: string;
  status: DocumentStatus;
  created_at?: string;
  updated_at?: string;
  pages?: number;
}

export interface SearchParams {
  q: string;
  document_id?: number | string;
  limit?: number;
}

export interface SearchResultItem {
  document_id: number | string;
  title: string;
  page?: number;
  snippet?: string; // HTML with <b>
  preview?: string;
  score?: number;
  similarity?: number;
}

export interface ChunkItem {
  id: string | number;
  document_id: string | number;
  page?: number;
  text: string;
  score?: number;
}

export interface AnswerRequest {
  q: string;
  document_id?: string | number;
  k?: number;
  max_context_tokens?: number;
}

export interface AnswerResponse {
  answer: string;
  citations: Array<{ cit: string; document_id: number | string; page_no?: number; title: string }>;
  used_chunks: Array<string | number>;
  timings: { retrieve_ms: number; llm_ms: number; total_ms: number };
  error?: string;
  detail?: string;
}

// Specialized helpers
export async function uploadDocument(form: FormData) {
  return apiFetch<DocumentMeta>('/api/documents/upload', {
    method: 'POST',
    body: form,
  });
}

export async function getDocument(id: string | number) {
  return apiFetch<DocumentMeta>(`/api/documents/${id}`);
}

export async function getChunks(id: string | number, limit = 50) {
  return apiFetch<{ items: ChunkItem[] }>(`/api/documents/${id}/chunks?limit=${limit}`);
}

export async function searchFts(params: SearchParams) {
  return apiFetch<{ items: SearchResultItem[] }>(`/api/search`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function searchSemantic(params: SearchParams) {
  return apiFetch<{ items: SearchResultItem[] }>(`/api/search/semantic`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function searchHybrid(params: SearchParams) {
  return apiFetch<{ items: SearchResultItem[] }>(`/api/search/hybrid`, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function reindexEmbeddings(params: { document_id?: string | number }) {
  return apiFetch<{ indexed: number; skipped?: number; message?: string }>(
    `/api/embeddings/reindex`,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
  );
}

export async function askAnswer(req: AnswerRequest, signal?: AbortSignal) {
  const payload: any = { q: req.q };
  if (req.document_id) payload.filters = { document_id: req.document_id };
  if (req.k) payload.k = req.k;
  if (req.max_context_tokens) payload.max_context_tokens = req.max_context_tokens;
  return apiFetch<AnswerResponse>('/api/answer', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}
