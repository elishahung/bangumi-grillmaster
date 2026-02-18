import type { ProjectDetail } from "@shared/view-models";
import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { trpc } from "@/lib/trpc";

const EMPTY_VTT_TRACK =
  "data:text/vtt;charset=utf-8,WEBVTT%0A%0A00:00:00.000%20--%3E%2000:00:00.500%0A";

export const ProjectPlayerCard = ({ project }: { project: ProjectDetail }) => {
  const [viewerId, setViewerId] = useState<string>("");
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const upsertMutation = trpc.upsertWatchProgress.useMutation();

  useEffect(() => {
    const key = "bgm_viewer_id";
    const existing = window.localStorage.getItem(key);
    if (existing) {
      setViewerId(existing);
      return;
    }

    const created = crypto.randomUUID();
    window.localStorage.setItem(key, created);
    setViewerId(created);
  }, []);

  const mineProgress = useMemo(() => {
    if (!viewerId) {
      return null;
    }
    return (
      project.watchProgress.find((row) => row.viewerId === viewerId) ?? null
    );
  }, [project.watchProgress, viewerId]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !mineProgress || mineProgress.positionSec < 3) {
      return;
    }
    video.currentTime = mineProgress.positionSec;
  }, [mineProgress]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (!viewerId || !videoRef.current) {
        return;
      }

      const { currentTime, duration } = videoRef.current;
      if (
        !Number.isFinite(currentTime) ||
        !Number.isFinite(duration) ||
        duration <= 0
      ) {
        return;
      }

      upsertMutation.mutate({
        projectId: project.projectId,
        viewerId,
        positionSec: currentTime,
        durationSec: duration,
      });
    }, 5000);

    return () => window.clearInterval(timer);
  }, [project.projectId, upsertMutation, viewerId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Video Player</CardTitle>
      </CardHeader>
      <CardContent>
        <video
          className="w-full rounded-lg border border-zinc-300 bg-black"
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
          <track
            default
            kind="captions"
            label={
              project.subtitlePath
                ? "Traditional Chinese"
                : "Captions unavailable"
            }
            src={
              project.subtitlePath
                ? `/api/projects/${project.subtitlePath}`
                : EMPTY_VTT_TRACK
            }
            srcLang={project.subtitlePath ? "zh-TW" : "en"}
          />
        </video>
        <p className="mt-2 text-xs text-zinc-500">
          播放進度每 5 秒同步到 SQLite watch_progress。
        </p>
      </CardContent>
    </Card>
  );
};
