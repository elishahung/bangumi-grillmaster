import type { TaskRow } from '@shared/view-models';
import Link from 'next/link';
import { toTaskBadgeVariant } from '@/components/task/status';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { formatDate } from '@/lib/format-date';

export const TaskList = ({ tasks }: { tasks: TaskRow[] }) => {
  if (tasks.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          尚無任務。
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <Link
          className="block rounded-lg border border-border bg-card p-4 transition hover:border-ring hover:shadow-sm"
          href={`/tasks/${task.taskId}`}
          key={task._id}
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="line-clamp-1 font-semibold text-sm">{task.message}</p>
            <Badge variant={toTaskBadgeVariant(task.status)}>
              {task.status}
            </Badge>
          </div>
          <Progress value={task.progressPercent} />
          {task.currentStep && task.currentStep !== task.status ? (
            <p className="mt-2 text-xs text-muted-foreground">{task.currentStep}</p>
          ) : null}
          {task.errorMessage ? (
            <p className="mt-1 text-destructive text-xs">{task.errorMessage}</p>
          ) : null}
          <p className="mt-1 text-xs text-muted-foreground">
            {formatDate(task.createdAt)}
          </p>
        </Link>
      ))}
    </div>
  );
};
