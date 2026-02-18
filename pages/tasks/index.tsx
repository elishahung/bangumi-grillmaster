import Head from "next/head";
import { SectionHeading } from "@/components/layout/section-heading";
import { TaskList } from "@/components/task/task-list";
import { Card, CardContent } from "@/components/ui/card";
import { trpc } from "@/lib/trpc";

export default function TasksPage() {
  const tasksQuery = trpc.listTasks.useQuery(
    { limit: 100 },
    { refetchInterval: 2500 },
  );
  const tasks = tasksQuery.data;

  return (
    <>
      <Head>
        <title>Tasks | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-4">
        <SectionHeading
          description="包含目前進行中與歷史任務。"
          title="Task History"
        />
        {tasksQuery.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Loading tasks...
            </CardContent>
          </Card>
        ) : tasksQuery.error ? (
          <Card>
            <CardContent className="p-6 text-sm text-rose-700">
              Failed to load tasks: {tasksQuery.error.message}
            </CardContent>
          </Card>
        ) : (
          <TaskList tasks={tasks ?? []} />
        )}
      </section>
    </>
  );
}
