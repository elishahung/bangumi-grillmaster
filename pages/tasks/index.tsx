import Head from 'next/head';
import { SectionHeading } from '@/components/layout/section-heading';
import { TaskList } from '@/components/task/task-list';
import { Card, CardContent } from '@/components/ui/card';
import { trpc } from '@/lib/trpc';

export default function TasksPage() {
  const tasksQuery = trpc.listTasks.useQuery(
    { limit: 100 },
    { refetchInterval: 2500 },
  );
  const tasks = tasksQuery.data;
  let content = <></>;

  if (tasksQuery.isLoading) {
    content = (
      <Card>
        <CardContent className="p-6 text-sm text-zinc-600">
          Loading tasks...
        </CardContent>
      </Card>
    );
  } else if (tasksQuery.error) {
    content = (
      <Card>
        <CardContent className="p-6 text-rose-700 text-sm">
          Failed to load tasks: {tasksQuery.error.message}
        </CardContent>
      </Card>
    );
  } else {
    content = <TaskList tasks={tasks ?? []} />;
  }

  return (
    <>
      <Head>
        <title>Tasks | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-4">
        <SectionHeading description="所有處理任務的即時狀態" title="任務歷史" />
        {content}
      </section>
    </>
  );
}
