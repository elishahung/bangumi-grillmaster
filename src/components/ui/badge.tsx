import { cva } from "class-variance-authority";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        queued: "bg-zinc-200 text-zinc-700",
        running: "bg-amber-100 text-amber-700",
        completed: "bg-emerald-100 text-emerald-700",
        failed: "bg-rose-100 text-rose-700",
        default: "bg-zinc-100 text-zinc-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export const Badge = ({
  className,
  variant,
  children,
}: {
  className?: string;
  variant?: "queued" | "running" | "completed" | "failed" | "default";
  children: ReactNode;
}) => (
  <span className={cn(badgeVariants({ variant }), className)}>{children}</span>
);
