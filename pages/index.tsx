import Head from 'next/head';
import Link from 'next/link';
import { useState } from 'react';
import { SectionHeading } from '@/components/layout/section-heading';
import { ProjectGrid } from '@/components/project/project-grid';
import { SubmitProjectDialog } from '@/components/project/submit-project-form';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { trpc } from '@/lib/trpc';

export default function HomePage() {
  const [showCompletedOnly, setShowCompletedOnly] = useState(false);
  const projectsQuery = trpc.listProjects.useQuery(undefined, {
    refetchInterval: 5000,
  });

  const projects = projectsQuery.data ?? [];
  const filteredProjects = showCompletedOnly
    ? projects.filter((p) => p.status === 'completed')
    : projects;

  return (
    <>
      <Head>
        <title>Home | Bangumi GrillMaster</title>
      </Head>
      <div className="space-y-8">
        <SectionHeading
          actions={
            <div className="flex items-center gap-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="show-completed"
                  checked={showCompletedOnly}
                  onCheckedChange={(checked: boolean | 'indeterminate') =>
                    setShowCompletedOnly(checked === true)
                  }
                />
                <Label
                  htmlFor="show-completed"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Show Completed Only
                </Label>
              </div>
              <SubmitProjectDialog />
            </div>
          }
          title="All Projects"
        />

        {projectsQuery.isLoading ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : (
          <ProjectGrid
            emptyText="No projects yet. Click '+ New Project' to start."
            projects={filteredProjects}
          />
        )}
      </div>
    </>
  );
}
