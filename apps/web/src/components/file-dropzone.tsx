"use client";
import { useCallback, useState } from 'react';
import { cn } from '@/components/utils';

export interface FileDropzoneProps {
  onFile: (file: File) => void;
  accept?: string;
  maxSize?: number; // bytes
}

export function FileDropzone({ onFile, accept, maxSize = 20 * 1024 * 1024 }: FileDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      if (accept && !f.type.match(accept)) {
        setError('Unsupported file type');
        return;
      }
      if (f.size > maxSize) {
        setError(`File too large (max ${Math.round(maxSize / (1024 * 1024))} MB)`);
        return;
      }
      setError(null);
      onFile(f);
    },
    [accept, maxSize, onFile],
  );

  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          onFiles(e.dataTransfer.files);
        }}
        className={cn(
          'flex w-full cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors focus:outline-none focus:ring-2 focus:ring-ring',
          dragOver ? 'bg-accent' : 'bg-background',
        )}
      >
        <input
          type="file"
          className="hidden"
          onChange={(e) => onFiles(e.target.files)}
          aria-label="Upload file"
        />
        <div className="text-sm text-muted-foreground">Drag and drop a file here, or click to browse</div>
        <div className="mt-1 text-xs text-muted-foreground">PDFs recommended</div>
      </label>
      {error && (
        <div className="mt-2 text-sm text-destructive" role="alert" aria-live="polite">
          {error}
        </div>
      )}
    </div>
  );
}

