import Link from "next/link";
import { useRouter } from "next/router";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Submit" },
  { href: "/projects", label: "Projects" },
  { href: "/tasks", label: "Tasks" },
];

export const AppLayout = ({ children }: { children: ReactNode }) => {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#f7f7f5,_#eef2f7_60%,_#e8ecf3)] text-zinc-900">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <h1 className="text-lg font-semibold tracking-tight">
          Bangumi GrillMaster Platform
        </h1>
        <nav className="flex gap-1 rounded-full border border-zinc-300 bg-white/80 p-1 backdrop-blur">
          {navItems.map((item) => (
            <Link
              className={cn(
                "rounded-full px-4 py-1.5 text-sm transition",
                router.pathname === item.href ||
                  router.pathname.startsWith(`${item.href}/`)
                  ? "bg-zinc-900 text-zinc-50"
                  : "text-zinc-600 hover:bg-zinc-100",
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
