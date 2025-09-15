import Link from 'next/link';
import { Button } from '@/components/ui/button';

export default function Page() {
  return (
    <div className="container-narrow space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge Hub</h1>
        <p className="text-muted-foreground">Upload, search, and analyze your documents.</p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button asChild>
          <Link href="/upload">Upload</Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/search">Search</Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/embeddings">Embeddings</Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/answer">Answer</Link>
        </Button>
      </div>
    </div>
  );
}

