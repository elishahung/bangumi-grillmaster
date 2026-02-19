import Link from 'next/link';
import { useRouter } from 'next/router';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Home' },
];

export const AppLayout = ({ children }: { children: ReactNode }) => {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/">
          <h1 className="font-semibold text-lg tracking-tight">GrillMaster</h1>
        </Link>
      </header>
      <main className="mx-auto w-full max-w-6xl px-4 pb-10 sm:px-6">
        {children}
      </main>
    </div>
  );
};
