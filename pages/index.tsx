import Head from 'next/head'
import { useState } from 'react'
import { SectionHeading } from '@/components/layout/section-heading'
import { ProjectGrid } from '@/components/project/project-grid'
import { SubmitProjectDialog } from '@/components/project/submit-project-form'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { trpc } from '@/lib/trpc'

export default function HomePage() {
  const [showCompletedOnly, setShowCompletedOnly] = useState(false)
  const projectsQuery = trpc.listProjects.useQuery(undefined, {
    refetchInterval: (query) => {
      if (
        query.state.data?.every(
          (p) => p.status === 'completed' || p.status === 'failed',
        )
      ) {
        return false
      }
      return 10_000
    },
  })

  const projects = projectsQuery.data ?? []
  const filteredProjects = showCompletedOnly
    ? projects.filter((p) => p.status === 'completed')
    : projects

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
                  checked={showCompletedOnly}
                  id="show-completed"
                  onCheckedChange={(checked: boolean | 'indeterminate') =>
                    setShowCompletedOnly(checked === true)
                  }
                />
                <Label
                  className="font-medium text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  htmlFor="show-completed"
                >
                  Show Completed Only
                </Label>
              </div>
              <SubmitProjectDialog />
            </div>
          }
          title="All Videos"
        />

        {projectsQuery.isLoading ? (
          <p className="text-sm text-zinc-500">Loading...</p>
        ) : (
          <ProjectGrid
            emptyText="No videos yet. Click '+ New Video' to start."
            projects={filteredProjects}
          />
        )}
      </div>
    </>
  )
}
