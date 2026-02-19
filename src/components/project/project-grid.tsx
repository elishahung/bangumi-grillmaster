import { DEFAULT_VIEWER_ID } from '@shared/constants'
import type { ProjectRow } from '@shared/view-models'
import { PlayCircle } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import { toProjectBadgeVariant } from '@/components/project/status'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { formatDate } from '@/lib/format-date'

export const ProjectGrid = ({
  projects,
  emptyText,
}: {
  projects: ProjectRow[]
  emptyText?: string
}) => {
  if (projects.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground text-sm">
          {emptyText ?? 'No projects yet.'}
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {projects.map((project) => {
        const isCompleted = project.status === 'completed'
        const task = project.task
        const mineProgress = isCompleted
          ? project.watchProgress?.find((p) => p.viewerId === DEFAULT_VIEWER_ID)
          : null

        return (
          <Link
            className="group block overflow-hidden rounded-xl border border-border bg-card transition hover:border-ring hover:shadow-md"
            href={`/videos/${project.projectId}`}
            key={project._id}
          >
            <div className="relative aspect-video w-full overflow-hidden bg-gradient-to-br from-muted to-muted/80">
              {project.thumbnailUrl ? (
                <Image
                  alt={project.title ?? project.sourceVideoId}
                  className="h-full w-full object-cover transition group-hover:scale-105"
                  height={180}
                  src={project.thumbnailUrl}
                  width={320}
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-muted-foreground/50">
                  <svg
                    aria-hidden="true"
                    className="size-10"
                    fill="none"
                    role="img"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <title>Video Placeholder</title>
                    <path
                      d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}

              {isCompleted ? (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity group-hover:opacity-100">
                  <PlayCircle className="h-12 w-12 text-white drop-shadow-md" />
                </div>
              ) : null}

              <div className="absolute top-2 right-2">
                <Badge variant={toProjectBadgeVariant(project.status)}>
                  {project.status}
                </Badge>
              </div>
            </div>

            <div className="space-y-3 p-3">
              <div className="space-y-1">
                <p className="line-clamp-2 font-semibold text-sm leading-snug">
                  {project.title ??
                    `${project.source}:${project.sourceVideoId}`}
                </p>
                <p className="text-muted-foreground text-xs">
                  {formatDate(project.createdAt)}
                </p>
              </div>

              {!isCompleted && task && (
                <div className="mt-auto space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-muted-foreground">
                      {task.currentStep}
                    </span>
                    <span className="text-muted-foreground">
                      {task.progressPercent}%
                    </span>
                  </div>
                  <Progress className="h-1.5" value={task.progressPercent} />
                </div>
              )}

              {isCompleted && mineProgress && mineProgress.durationSec > 0 && (
                <div className="mt-auto space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-muted-foreground">
                      Watched
                    </span>
                    <span className="text-muted-foreground">
                      {Math.round(
                        (mineProgress.positionSec / mineProgress.durationSec) *
                          100,
                      )}
                      %
                    </span>
                  </div>
                  <Progress
                    className="h-1.5"
                    value={
                      (mineProgress.positionSec / mineProgress.durationSec) *
                      100
                    }
                  />
                </div>
              )}
            </div>
          </Link>
        )
      })}
    </div>
  )
}
