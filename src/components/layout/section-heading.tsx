import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export const SectionHeading = ({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) => (
  <div
    className={cn(
      "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
      className,
    )}
  >
    <div className="space-y-1">
      <h2 className="text-xl font-semibold tracking-tight sm:text-2xl">
        {title}
      </h2>
      {description ? (
        <p className="text-sm text-zinc-600">{description}</p>
      ) : null}
    </div>
    {actions ? <div>{actions}</div> : null}
  </div>
);
