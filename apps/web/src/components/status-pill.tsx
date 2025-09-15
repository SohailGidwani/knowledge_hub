import { Badge } from '@/components/ui/badge';
import { DocumentStatus } from '@/lib/api';

export function StatusPill({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, { label: string; variant: any }> = {
    ready: { label: 'Ready', variant: 'success' },
    processing: { label: 'Processing', variant: 'warning' },
    error: { label: 'Error', variant: 'destructive' },
  };
  const cfg = map[status] || { label: status, variant: 'secondary' };
  return <Badge variant={cfg.variant as any}>{cfg.label}</Badge>;
}

