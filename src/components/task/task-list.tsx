import type { TaskRow } from '@shared/view-models';
import Link from 'next/link';
import { toTaskBadgeVariant } from '@/components/task/status';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

export const TaskList = ({ tasks }: { tasks: TaskRow[] }) => {
  if (tasks.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-zinc-600">
          No tasks yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <Link
          className="block rounded-lg border border-zinc-200 bg-white p-4 hover:border-zinc-400"
          href={`/tasks/${task.taskId}`}
          key={task._id}
        >
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="font-semibold text-sm">{task.currentStep}</p>
            <Badge variant={toTaskBadgeVariant(task.status)}>
              {task.status}
            </Badge>
          </div>
          <Progress value={task.progressPercent} />
          <p className="mt-2 text-xs text-zinc-600">{task.message}</p>
          {task.errorMessage ? (
            <p className="mt-1 text-rose-700 text-xs">{task.errorMessage}</p>
          ) : null}
          <p className="mt-1 text-xs text-zinc-500">taskId: {task.taskId}</p>
        </Link>
      ))}
    </div>
  );
};
