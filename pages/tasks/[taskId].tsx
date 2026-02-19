import Head from 'next/head';
import { useRouter } from 'next/router';
import { SectionHeading } from '@/components/layout/section-heading';
import { TaskDetailPanel } from '@/components/task/task-detail-panel';
import { TaskEventsList } from '@/components/task/task-events-list';
import { Card, CardContent } from '@/components/ui/card';
import { trpc } from '@/lib/trpc';

export default function TaskDetailPage() {
  const router = useRouter();
  const taskId =
    typeof router.query.taskId === 'string' ? router.query.taskId : '';

  const taskQuery = trpc.taskById.useQuery(
    { taskId },
    { enabled: Boolean(taskId), refetchInterval: 2500 },
  );
  const retryMutation = trpc.retryTask.useMutation({
    onSuccess: () => {
      return taskQuery.refetch();
    },
  });
  const cancelMutation = trpc.cancelTask.useMutation({
    onSuccess: () => {
      return taskQuery.refetch();
    },
  });

  const task = taskQuery.data;
  let content = <></>;

  if (taskQuery.isLoading) {
    content = (
      <Card>
        <CardContent className="p-6 text-sm text-zinc-600">
          Loading task...
        </CardContent>
      </Card>
    );
  } else if (taskQuery.error) {
    content = (
      <Card>
        <CardContent className="p-6 text-rose-700 text-sm">
          Failed to load task: {taskQuery.error.message}
        </CardContent>
      </Card>
    );
  } else if (task) {
    content = (
      <div className="space-y-6">
        <TaskDetailPanel
          canceling={cancelMutation.isPending}
          onCancel={() => cancelMutation.mutate({ taskId: task.taskId })}
          onRetry={() => retryMutation.mutate({ taskId: task.taskId })}
          retrying={retryMutation.isPending}
          task={task}
        />
        <TaskEventsList events={task.events} />
      </div>
    );
  } else {
    content = (
      <Card>
        <CardContent className="p-6 text-sm text-zinc-600">
          Task not found.
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Head>
        <title>Task Detail | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-4">
        <SectionHeading
          description="任務狀態、錯誤與事件歷程。"
          title="Task Detail"
        />
        {content}
      </section>
    </>
  );
}
