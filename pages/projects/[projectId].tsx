import Head from "next/head";
import { useRouter } from "next/router";
import { SectionHeading } from "@/components/layout/section-heading";
import { ProjectDetailHeader } from "@/components/project/project-detail-header";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectPlayerCard } from "@/components/video/project-player-card";
import { trpc } from "@/lib/trpc";

export default function ProjectDetailPage() {
  const router = useRouter();
  const projectId =
    typeof router.query.projectId === "string" ? router.query.projectId : "";

  const projectQuery = trpc.projectById.useQuery(
    { projectId },
    { enabled: Boolean(projectId), refetchInterval: 2500 },
  );

  return (
    <>
      <Head>
        <title>Project Detail | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-4">
        <SectionHeading title="影片詳情" />
        {projectQuery.isLoading ? (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Loading project...
            </CardContent>
          </Card>
        ) : projectQuery.error ? (
          <Card>
            <CardContent className="p-6 text-sm text-rose-700">
              Failed to load project: {projectQuery.error.message}
            </CardContent>
          </Card>
        ) : projectQuery.data ? (
          <div className="space-y-6">
            <ProjectDetailHeader project={projectQuery.data} />
            <ProjectPlayerCard project={projectQuery.data} />
          </div>
        ) : (
          <Card>
            <CardContent className="p-6 text-sm text-zinc-600">
              Project not found.
            </CardContent>
          </Card>
        )}
      </section>
    </>
  );
}
