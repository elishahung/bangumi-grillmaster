import type { ProjectDetail } from '@shared/view-models';
import Link from 'next/link';
import { toProjectBadgeVariant } from '@/components/project/status';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const ProjectDetailHeader = ({
  project,
}: {
  project: ProjectDetail;
}) => (
  <Card>
    <CardHeader>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CardTitle>
          {project.title ?? `${project.source}:${project.sourceVideoId}`}
        </CardTitle>
        <Badge variant={toProjectBadgeVariant(project.status)}>
          {project.status}
        </Badge>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="grid gap-2 text-sm text-zinc-600 sm:grid-cols-2">
        <p>Project ID: {project.projectId}</p>
        <p>Source: {project.source}</p>
        <p>Video ID: {project.sourceVideoId}</p>
        <p>LLM Cost: NT$ {project.llmCostTwd.toFixed(2)}</p>
      </div>
      {project.sourceUrl ? (
        <Link
          className="text-blue-700 text-sm underline"
          href={project.sourceUrl}
          target="_blank"
        >
          Open Source Link
        </Link>
      ) : null}
    </CardContent>
  </Card>
);
