"use client";
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { uploadDocument, getDocument, DocumentMeta as Doc } from '@/lib/api';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { FileDropzone } from '@/components/file-dropzone';
import { StatusPill } from '@/components/status-pill';
import { formatBytes } from '@/lib/format';
import { usePoller } from '@/hooks/usePoller';
import Link from 'next/link';
import { Progress } from '@/components/ui/progress';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [docId, setDocId] = useState<string | number | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: async ({ file, title }: { file: File; title: string }) => {
      const form = new FormData();
      form.append('file', file);
      form.append('title', title);
      return uploadDocument(form);
    },
    onSuccess: (doc) => setDocId(doc.id),
    onError: (e: any) => setClientError(e?.message || 'Upload failed'),
  });

  const { data: doc, refetch } = useQuery<Doc | undefined>({
    queryKey: ['document', docId],
    queryFn: async () => (docId ? await getDocument(docId) : undefined),
    enabled: !!docId,
    refetchOnWindowFocus: false,
  });

  const processing = useMemo(() => doc && doc.status === 'processing', [doc]);
  usePoller(() => refetch(), 2000, !!docId && processing === true);

  const canSubmit = !!file && title.trim().length > 0 && !upload.isPending;

  return (
    <div className="container-narrow space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Upload</h1>
        <p className="text-sm text-muted-foreground">Upload a document for processing.</p>
      </div>

      <div className="space-y-4 rounded-2xl border p-4 bg-background">
        <FileDropzone onFile={setFile} accept={".*"} />
        {file && (
          <div className="text-sm text-muted-foreground">
            Selected: <span className="font-medium">{file.name}</span> ({formatBytes(file.size)})
          </div>
        )}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button disabled={!canSubmit} onClick={() => file && upload.mutate({ file, title })}>
            {upload.isPending ? 'Uploading…' : 'Upload'}
          </Button>
        </div>
        {clientError && (
          <div role="alert" className="text-sm text-destructive">
            {clientError}
          </div>
        )}
      </div>

      {docId && (
        <div className="space-y-3 rounded-2xl border p-4">
          <div className="flex items-center justify-between">
            <div className="font-medium">Processing Status</div>
            <StatusPill status={doc?.status || 'processing'} />
          </div>
          {(!doc || doc.status === 'processing') && (
            <div>
              <Progress value={66} />
              <div className="mt-2 text-sm text-muted-foreground" aria-live="polite">
                Processing… This may take a moment.
              </div>
            </div>
          )}
          {doc && doc.status !== 'processing' && (
            <div className="space-y-2 text-sm">
              <div>
                Title: <span className="font-medium">{doc.title}</span>
              </div>
              <div>
                MIME: <span className="font-medium">{doc.mime_type}</span>
              </div>
              <div>
                Size: <span className="font-medium">{formatBytes(doc.bytes)}</span>
              </div>
              {doc.source_path && (
                <div>
                  Path: <span className="font-medium break-all">{doc.source_path}</span>
                </div>
              )}
              <div className="pt-2">
                <Link className="text-primary underline" href={`/documents/${doc.id}`}>
                  Go to Document Detail
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

