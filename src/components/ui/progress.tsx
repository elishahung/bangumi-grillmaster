import { cn } from '@/lib/utils';

export const Progress = ({
  value,
  className,
}: {
  value: number;
  className?: string;
}) => {
  const width = Math.max(0, Math.min(100, value));

  return (
    <div
      className={cn(
        'h-2 w-full overflow-hidden rounded-full bg-zinc-200',
        className,
      )}
    >
      <div
        className="h-full bg-zinc-900 transition-all"
        style={{ width: `${width}%` }}
      />
    </div>
  );
};
