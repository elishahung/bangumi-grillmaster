import type { TaskDetail } from '@shared/view-models';
import { toTaskBadgeVariant } from '@/components/task/status';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

export const TaskDetailPanel = ({
  task,
  onRetry,
  onCancel,
  retrying,
  canceling,
}: {
  task: TaskDetail;
  onRetry: () => void;
  onCancel: () => void;
  retrying: boolean;
  canceling: boolean;
}) => (
  <Card>
    <CardHeader>
      <div className="flex items-center justify-between gap-3">
        <CardTitle>Task {task.taskId}</CardTitle>
        <Badge variant={toTaskBadgeVariant(task.status)}>{task.status}</Badge>
      </div>
    </CardHeader>
    <CardContent className="space-y-3">
      <Progress value={task.progressPercent} />
      <p className="text-sm text-zinc-600">{task.message}</p>
      <p className="text-xs text-zinc-500">projectId: {task.projectId}</p>
      {task.errorMessage ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-rose-800 text-sm">
          {task.errorMessage}
        </div>
      ) : null}
      {['queued', 'running', 'canceling'].includes(task.status) ? (
        <Button
          disabled={canceling || task.status === 'canceling'}
          onClick={onCancel}
          size="sm"
          variant="secondary"
        >
          {canceling || task.status === 'canceling'
            ? 'Canceling...'
            : 'Cancel Task'}
        </Button>
      ) : null}
      {['failed', 'canceled'].includes(task.status) ? (
        <Button
          disabled={retrying}
          onClick={onRetry}
          size="sm"
          variant="secondary"
        >
          {retrying ? 'Retrying...' : 'Retry Task'}
        </Button>
      ) : null}
    </CardContent>
  </Card>
);
