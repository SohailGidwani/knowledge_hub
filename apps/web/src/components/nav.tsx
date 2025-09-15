import Link from 'next/link';
import { clsx } from 'clsx';
import { ThemeToggle } from '@/components/theme-toggle';

const navItems = [
  { href: '/upload' as const, label: 'Upload' },
  { href: '/search' as const, label: 'Search' },
  { href: '/embeddings' as const, label: 'Embeddings' },
  { href: '/answer' as const, label: 'Answer' },
  { href: '/how-it-works' as const, label: 'How It Works' },
];

export function Nav() {
  return (
    <header className="border-b">
      <div className="container h-14 flex items-center justify-between">
        <Link href="/" className="font-semibold">
          Knowledge Hub
        </Link>
        <nav className="flex items-center gap-4">
          {navItems.map((i) => (
            <Link
              key={i.href}
              href={i.href}
              className={clsx(
                'text-sm text-muted-foreground hover:text-foreground transition-colors',
              )}
            >
              {i.label}
            </Link>
          ))}
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
