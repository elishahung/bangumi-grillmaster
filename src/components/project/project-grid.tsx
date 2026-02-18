import type { ProjectRow } from "@shared/view-models";
import Link from "next/link";
import { toProjectBadgeVariant } from "@/components/project/status";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export const ProjectGrid = ({
  projects,
  emptyText,
}: {
  projects: ProjectRow[];
  emptyText?: string;
}) => {
  if (projects.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-zinc-600">
          {emptyText ?? "No projects yet."}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {projects.map((project) => (
        <Link
          className="rounded-lg border border-zinc-200 bg-white p-4 transition hover:border-zinc-400"
          href={`/projects/${project.projectId}`}
          key={project._id}
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="line-clamp-1 text-sm font-semibold">
              {project.title ?? `${project.source}:${project.sourceVideoId}`}
            </p>
            <Badge variant={toProjectBadgeVariant(project.status)}>
              {project.status}
            </Badge>
          </div>
          <p className="text-xs text-zinc-500">{project.projectId}</p>
          <p className="mt-2 text-xs text-zinc-600">
            Cost: NT$ {project.llmCostTwd.toFixed(2)}
          </p>
        </Link>
      ))}
    </div>
  );
};
