import Head from "next/head";
import { useRouter } from "next/router";
import { SectionHeading } from "@/components/layout/section-heading";
import { TaskDetailPanel } from "@/components/task/task-detail-panel";
import { TaskEventsList } from "@/components/task/task-events-list";
import { Card, CardContent } from "@/components/ui/card";
import { trpc } from "@/lib/trpc";

export default function TaskDetailPage() {
  const router = useRouter();
  const taskId =
    typeof router.query.taskId === "string" ? router.query.taskId : "";

  const taskQuery = trpc.taskById.useQuery(
    { taskId },
    { enabled: Boolean(taskId), refetchInterval: 2500 },
  );
  const retryMutation = trpc.retryTask.useMutation({
    onSuccess: () => {
      void taskQuery.refetch();
    },
  });

  const task = taskQuery.data;

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
        {taskQuery.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Loading task...
            </CardContent>
          </Card>
        ) : taskQuery.error ? (
          <Card>
            <CardContent className="p-6 text-sm text-rose-700">
              Failed to load task: {taskQuery.error.message}
            </CardContent>
          </Card>
        ) : task ? (
          <div className="space-y-6">
            <TaskDetailPanel
              onRetry={() => retryMutation.mutate({ taskId: task.taskId })}
              retrying={retryMutation.isPending}
              task={task}
            />
            <TaskEventsList events={task.events} />
          </div>
        ) : (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Task not found.
            </CardContent>
          </Card>
        )}
      </section>
    </>
  );
}
