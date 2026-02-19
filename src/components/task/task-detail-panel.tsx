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
      <p className="text-sm text-muted-foreground">{task.message}</p>
      <p className="text-xs text-muted-foreground">projectId: {task.projectId}</p>
      {task.errorMessage ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-destructive sm:text-destructive-foreground text-sm">
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
