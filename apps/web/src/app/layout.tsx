import type { Metadata } from 'next';
import './globals.css';
import { ReactQueryProvider } from '@/lib/query-client';
import { Nav } from '@/components/nav';

export const metadata: Metadata = {
  title: 'Knowledge Hub',
  description: 'Search and manage documents',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ReactQueryProvider>
          <div className="min-h-screen flex flex-col">
            <Nav />
            <main className="flex-1 container py-6 space-y-6">{children}</main>
          </div>
        </ReactQueryProvider>
      </body>
    </html>
  );
}

