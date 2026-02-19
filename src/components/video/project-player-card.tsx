import { DEFAULT_VIEWER_ID } from '@shared/constants'
import type { ProjectDetail } from '@shared/view-models'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { trpc } from '@/lib/trpc'

const SYNC_INTERVAL = 5000

export const ProjectPlayerCard = ({ project }: { project: ProjectDetail }) => {
  const [viewerId, setViewerId] = useState<string>('')
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const upsertMutation = trpc.upsertWatchProgress.useMutation()

  useEffect(() => {
    setViewerId(DEFAULT_VIEWER_ID)
  }, [])

  const mineProgress = useMemo(() => {
    if (!viewerId) {
      return null
    }
    return (
      project.watchProgress.find((row) => row.viewerId === viewerId) ?? null
    )
  }, [project.watchProgress, viewerId])

  const [hasInitialSeek, setHasInitialSeek] = useState(false)

  useEffect(() => {
    const video = videoRef.current
    if (!(video && mineProgress) || hasInitialSeek) {
      return
    }

    if (mineProgress.positionSec > 0) {
      video.currentTime = mineProgress.positionSec
    }
    setHasInitialSeek(true)
  }, [mineProgress, hasInitialSeek])

  useEffect(() => {
    const videoElement = videoRef.current
    if (!(viewerId && videoElement)) {
      return
    }

    if (!hasInitialSeek) {
      return
    }

    const timer = window.setInterval(() => {
      const { currentTime, duration } = videoElement
      if (
        !(Number.isFinite(currentTime) && Number.isFinite(duration)) ||
        duration <= 0
      ) {
        return
      }

      upsertMutation.mutate({
        projectId: project.projectId,
        viewerId,
        positionSec: currentTime,
        durationSec: duration,
      })
    }, SYNC_INTERVAL)

    return () => window.clearInterval(timer)
  }, [project.projectId, upsertMutation, viewerId, hasInitialSeek])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Player</CardTitle>
      </CardHeader>
      <CardContent>
        <video
          className="w-full rounded-lg border border-border bg-black"
          controls
          poster={project.thumbnailUrl}
          ref={videoRef}
        >
          {project.mediaPath ? (
            <source
              src={`/api/projects/${project.mediaPath}`}
              type="video/mp4"
            />
          ) : null}
          {project.subtitlePath && (
            <track
              default={!!project.subtitlePath}
              kind="subtitles"
              label="中文"
              src={`/api/projects/${project.subtitlePath}`}
              srcLang="zh-TW"
            />
          )}
          {project.asrVttPath && (
            <track
              default={!project.subtitlePath}
              kind="subtitles"
              label="Japanese"
              src={`/api/projects/${project.asrVttPath}`}
              srcLang="ja"
            />
          )}
        </video>
      </CardContent>
    </Card>
  )
}
