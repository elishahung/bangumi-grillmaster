import Link from 'next/link';
import { useRouter } from 'next/router';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: '首頁' },
  { href: '/projects', label: 'Projects' },
  { href: '/tasks', label: 'Tasks' },
];

export const AppLayout = ({ children }: { children: ReactNode }) => {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/">
          <h1 className="font-semibold text-lg tracking-tight">GrillMaster</h1>
        </Link>
        <nav className="flex gap-1 rounded-full border border-border bg-background/80 p-1 backdrop-blur">
          {navItems.map((item) => (
            <Link
              className={cn(
                'rounded-full px-4 py-1.5 text-sm transition font-medium',
                router.pathname === item.href ||
                  router.pathname.startsWith(`${item.href}/`)
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 pb-10 sm:px-6">
        {children}
      </main>
    </div>
  );
};
