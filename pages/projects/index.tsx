import Head from "next/head";
import { SectionHeading } from "@/components/layout/section-heading";
import { ProjectGrid } from "@/components/project/project-grid";
import { Card, CardContent } from "@/components/ui/card";
import { trpc } from "@/lib/trpc";

export default function ProjectsPage() {
  const projectsQuery = trpc.listProjects.useQuery(undefined, {
    refetchInterval: 5000,
  });

  return (
    <>
      <Head>
        <title>Projects | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-4">
        <SectionHeading
          description="Collection of all videos and translation progress"
          title="Video Library"
        />
        {projectsQuery.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Loading projects...
            </CardContent>
          </Card>
        ) : projectsQuery.error ? (
          <Card>
            <CardContent className="p-6 text-sm text-rose-700">
              Failed to load projects: {projectsQuery.error.message}
            </CardContent>
          </Card>
        ) : (
          <ProjectGrid projects={projectsQuery.data ?? []} />
        )}
      </section>
    </>
  );
}
