import { cva } from 'class-variance-authority'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 font-medium text-xs',
  {
    variants: {
      variant: {
        queued: 'bg-secondary text-secondary-foreground',
        running: 'bg-amber-500 text-white dark:bg-amber-600 dark:text-white',
        completed:
          'bg-emerald-500 text-white dark:bg-emerald-600 dark:text-white',
        failed:
          'bg-destructive text-destructive dark:text-destructive-foreground',
        default: 'bg-secondary text-secondary-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export const Badge = ({
  className,
  variant,
  children,
}: {
  className?: string
  variant?: 'queued' | 'running' | 'completed' | 'failed' | 'default'
  children: ReactNode
}) => (
  <span className={cn(badgeVariants({ variant }), className)}>{children}</span>
)
