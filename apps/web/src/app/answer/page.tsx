"use client";
import { useEffect, useRef, useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useMutation } from '@tanstack/react-query';
import { searchHybrid, SearchResultItem, askAnswer, AnswerResponse } from '@/lib/api';
import { ResultCard } from '@/components/result-card';
import Link from 'next/link';
import { ThinkingLoader } from '@/components/loader';
import { answerTextToHtml } from '@/lib/safeHtml';

export default function AnswerPage() {
  const [q, setQ] = useState('');
  const [docId, setDocId] = useState('');
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  type Msg = {
    role: 'user' | 'assistant';
    content: string;
    pending?: boolean;
    meta?: AnswerResponse | { error: string };
  };
  const [messages, setMessages] = useState<Msg[]>([]);

  const hybrid = useMutation({
    mutationFn: searchHybrid,
    onSuccess: (d) => setResults(d.items || []),
  });

  async function onSubmit() {
    if (!q.trim()) return;
    setError(null);
    setAnswer(null);
    await hybrid.mutateAsync({ q, document_id: docId || undefined, limit: 10 });
  }

  const [ctrl, setCtrl] = useState<AbortController | null>(null);
  const ask = useMutation({
    mutationFn: async (vars: { q: string; document_id?: string }) => {
      const controller = new AbortController();
      setCtrl(controller);
      try {
        return await askAnswer(vars, controller.signal);
      } finally {
        // controller cleared in onSettled
      }
    },
    onMutate: (vars: { q: string }) => {
      setError(null);
      setAnswer(null);
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: vars.q },
        { role: 'assistant', content: '', pending: true },
      ]);
    },
    onSuccess: (res) => {
      if ((res as any).error) {
        const msg = (res as any).detail || (res as any).error || 'LLM error';
        setError(msg);
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'assistant' && next[i].pending) {
              next[i] = { role: 'assistant', content: 'Error: ' + msg, pending: false, meta: { error: msg } };
              break;
            }
          }
          return next;
        });
      } else {
        setAnswer(res);
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'assistant' && next[i].pending) {
              next[i] = { role: 'assistant', content: res.answer, pending: false, meta: res };
              break;
            }
          }
          return next;
        });
      }
    },
    onError: (e: any) => {
      const msg = e?.name === 'AbortError' ? 'Canceled' : e?.message || 'Failed to get answer';
      setError(e?.name === 'AbortError' ? null : msg);
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === 'assistant' && next[i].pending) {
            next[i] = { role: 'assistant', content: msg, pending: false, meta: { error: msg } };
            break;
          }
        }
        return next;
      });
    },
    onSettled: () => setCtrl(null),
  });

  async function onAsk() {
    if (!q.trim()) return;
    const query = q;
    setQ('');
    await ask.mutateAsync({ q: query, document_id: docId || undefined });
  }

  function onCancel() {
    if (ctrl) {
      ctrl.abort();
    }
  }

  const listEndRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Answer</h1>
        <p className="text-sm text-muted-foreground">Get answers exactly related to how your specific course and lecture notes.</p>
      </div>

      <div className="space-y-4 rounded-2xl border p-4">
        <div className="space-y-3 max-h-[50vh] overflow-auto pr-2" aria-live="polite">
          {messages.length === 0 && (
            <div className="text-sm text-muted-foreground">Ask a question to start the chat.</div>
          )}
          {messages.map((m, i) => (
            <ChatBubble key={i} role={m.role} pending={m.pending}>
              {m.pending ? (
                <ThinkingLoader label="Thinking…" />
              ) : (
                m.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: answerTextToHtml(m.content) }} />
                ) : (
                  <div className="whitespace-pre-wrap leading-relaxed text-sm">{m.content}</div>
                )
              )}
              {!m.pending && m.meta && !('error' in m.meta) && (
                <div className="mt-2 text-[11px] text-muted-foreground">
                  Timings: retrieve {(m.meta as AnswerResponse).timings.retrieve_ms}ms · LLM {(m.meta as AnswerResponse).timings.llm_ms}ms · total {(m.meta as AnswerResponse).timings.total_ms}ms
                </div>
              )}
            </ChatBubble>
          ))}
          <div ref={listEndRef} />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Textarea
            id="question"
            placeholder="Ask a question... (Shift+Enter for newline)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onAsk();
              }
            }}
          />
          <div className="flex flex-col gap-2 sm:w-64">
            <Input
              placeholder="Optional document_id"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
            />
            <div className="flex gap-2">
              <Button onClick={onAsk} disabled={ask.isPending || !q.trim()}>
                {ask.isPending ? 'Thinking…' : 'Ask LLM'}
              </Button>
              <Button variant="outline" onClick={onCancel} disabled={!ask.isPending}>
                Cancel
              </Button>
              {/* <Button variant="secondary" onClick={onSubmit} disabled={hybrid.isPending}>
                {hybrid.isPending ? 'Retrieving…' : 'Fetch top chunks'}
              </Button> */}
            </div>
          </div>
        </div>
        {error && (
          <div className="text-sm text-destructive" role="alert">
            {error}
          </div>
        )}
      </div>

      {hybrid.isPending && (
        <div className="space-y-3">
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
          <div className="h-20 rounded-2xl bg-muted animate-pulse" />
        </div>
      )}

      {results && results.length > 0 && (
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

      {answer && (
        <section className="space-y-3">
          {answer.citations.length > 0 && (
            <div className="rounded-2xl border p-4">
              <div className="text-sm font-medium mb-2">Citations</div>
              <ul className="text-sm list-disc pl-5">
                {answer.citations.map((c, i) => (
                  <li key={i}>
                    <span className="text-muted-foreground">[{c.cit}]</span>{' '}
                    <Link className="underline" href={`/documents/${c.document_id}${c.page_no ? `#page-${c.page_no}` : ''}`}>
                      {c.title}
                    </Link>
                    {typeof c.page_no === 'number' ? ` · Page ${c.page_no}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ChatBubble({
  role,
  children,
  pending,
}: {
  role: 'user' | 'assistant';
  children: React.ReactNode;
  pending?: boolean;
}) {
  const isUser = role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm ${
          isUser ? 'bg-primary text-primary-foreground rounded-br-sm' : 'bg-background border rounded-bl-sm'
        } ${pending ? 'opacity-90' : ''}`}
      >
        {children}
      </div>
    </div>
  );
}
