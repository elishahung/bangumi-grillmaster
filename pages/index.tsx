import Head from 'next/head';
import Link from 'next/link';
import { SectionHeading } from '@/components/layout/section-heading';
import { ProjectGrid } from '@/components/project/project-grid';
import { SubmitProjectDialog } from '@/components/project/submit-project-form';
import { TaskList } from '@/components/task/task-list';
import { Button } from '@/components/ui/button';
import { trpc } from '@/lib/trpc';

export default function HomePage() {
  const projectsQuery = trpc.listProjects.useQuery(undefined, {
    refetchInterval: 5000,
  });
  const tasksQuery = trpc.listTasks.useQuery(
    { limit: 6 },
    { refetchInterval: 2500 },
  );

  return (
    <>
      <Head>
        <title>Home | Bangumi GrillMaster</title>
      </Head>
      <div className="space-y-8">
        <SectionHeading
          actions={
            <div className="flex gap-2">
              <SubmitProjectDialog />
            </div>
          }
          title="My Projects"
        />

        {projectsQuery.isLoading ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : (
          <ProjectGrid
            emptyText="No projects yet. Click '+ New Project' to start."
            projects={projectsQuery.data ?? []}
          />
        )}

        <section className="space-y-3">
          <SectionHeading
            actions={
              <Link href="/tasks">
                <Button size="sm" variant="ghost">
                  View All
                </Button>
              </Link>
            }
            title="Recent Tasks"
          />
          <TaskList tasks={tasksQuery.data ?? []} />
        </section>
      </div>
    </>
  );
}
