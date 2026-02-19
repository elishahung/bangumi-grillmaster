import Head from 'next/head';
import Link from 'next/link';
import { useMemo } from 'react';
import { SectionHeading } from '@/components/layout/section-heading';
import { ProjectGrid } from '@/components/project/project-grid';
import { SubmitProjectForm } from '@/components/project/submit-project-form';
import { TaskList } from '@/components/task/task-list';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { trpc } from '@/lib/trpc';

export default function SubmitPage() {
  const projectsQuery = trpc.listProjects.useQuery(undefined, {
    refetchInterval: 5000,
  });
  const tasksQuery = trpc.listTasks.useQuery(
    { limit: 8 },
    { refetchInterval: 2500 },
  );
  const recentProjects = useMemo(
    () => (projectsQuery.data ?? []).slice(0, 3),
    [projectsQuery.data],
  );

  return (
    <>
      <Head>
        <title>Submit | Bangumi GrillMaster</title>
      </Head>
      <div className="space-y-6">
        <SectionHeading
          actions={
            <div className="flex gap-2">
              <Link href="/projects">
                <Button size="sm" variant="secondary">
                  Browse Projects
                </Button>
              </Link>
              <Link href="/tasks">
                <Button size="sm">Open Tasks</Button>
              </Link>
            </div>
          }
          description="提交新影片，並追蹤轉換狀態與處理任務。"
          title="Bangumi GrillMaster Dashboard"
        />

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <SubmitProjectForm />
          <Card>
            <CardHeader>
              <CardTitle>Platform Notes</CardTitle>
              <CardDescription>
                Drizzle + SQLite 提供資料層，tRPC 負責 submit 與查詢。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-zinc-600">
              <p>- projectId 改為 UUID</p>
              <p>- source + sourceVideoId 做重複檢查</p>
              <p>- 保存 LLM 成本與 token 使用量</p>
              <p>- 任務頁以 polling 顯示近即時進度</p>
            </CardContent>
          </Card>
        </div>

        <section className="space-y-3">
          <SectionHeading
            actions={
              <Link href="/projects">
                <Button size="sm" variant="ghost">
                  View all
                </Button>
              </Link>
            }
            title="Recent Projects"
          />
          <ProjectGrid
            emptyText="尚未有專案，先提交第一支影片。"
            projects={recentProjects}
          />
        </section>

        <section className="space-y-3">
          <SectionHeading
            actions={
              <Link href="/tasks">
                <Button size="sm" variant="ghost">
                  View all
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
