import { cn } from '@/lib/utils'

export const Progress = ({
  value,
  className,
}: {
  value: number
  className?: string
}) => {
  const width = Math.max(0, Math.min(100, value))

  return (
    <div
      className={cn(
        'h-2 w-full overflow-hidden rounded-full bg-secondary',
        className,
      )}
    >
      <div
        className="h-full bg-primary transition-all"
        style={{ width: `${width}%` }}
      />
    </div>
  )
}
