import Head from 'next/head';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { SectionHeading } from '@/components/layout/section-heading';
import { ProjectDetailHeader } from '@/components/project/project-detail-header';
import { TaskDetailPanel } from '@/components/task/task-detail-panel';
import { TaskEventsList } from '@/components/task/task-events-list';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { ProjectPlayerCard } from '@/components/video/project-player-card';
import { trpc } from '@/lib/trpc';
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function ProjectDetailPage() {
  const router = useRouter();
  const projectId =
    typeof router.query.projectId === 'string' ? router.query.projectId : '';

  const [isTaskExpanded, setIsTaskExpanded] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const projectQuery = trpc.projectById.useQuery(
    { projectId },
    { enabled: Boolean(projectId), refetchInterval: 2500 },
  );

  const retryMutation = trpc.retryTask.useMutation({
    onSuccess: () => {
      return projectQuery.refetch();
    },
  });
  const cancelMutation = trpc.cancelTask.useMutation({
    onSuccess: () => {
      return projectQuery.refetch();
    },
  });

  const deleteMutation = trpc.deleteProject.useMutation({
    onSuccess: () => {
      router.push('/');
    },
  });

  const project = projectQuery.data;
  // Use the first task (which is the latest one due to ordering in backend)
  const task = project?.tasks[0];

  const isCompleted = project?.status === 'completed';
  const showVideo = isCompleted;

  return (
    <>
      <Head>
        <title>Project Detail | Bangumi GrillMaster</title>
      </Head>
      <section className="space-y-6">
        <div className="flex items-center justify-between">
            <SectionHeading title="Project Details" />
            
            {project && (
            <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                <DialogTrigger asChild>
                <Button variant="destructive" size="sm">
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Project
                </Button>
                </DialogTrigger>
                <DialogContent>
                <DialogHeader>
                    <DialogTitle>Are you absolutely sure?</DialogTitle>
                    <DialogDescription>
                    This action cannot be undone. This will permanently delete the project
                    record from the database and rename the project data folder.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <DialogClose asChild>
                    <Button variant="outline">Cancel</Button>
                    </DialogClose>
                    <Button 
                    variant="destructive" 
                    onClick={() => deleteMutation.mutate({ projectId })}
                    disabled={deleteMutation.isPending}
                    >
                    {deleteMutation.isPending ? 'Deleting...' : 'Delete Project'}
                    </Button>
                </DialogFooter>
                </DialogContent>
            </Dialog>
            )}
        </div>
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
        ) : project ? (
          <div className="space-y-8">
            <ProjectDetailHeader project={project} />

            {showVideo ? <ProjectPlayerCard project={project} /> : null}

            {task && (
              <Collapsible
                open={!isCompleted || isTaskExpanded}
                onOpenChange={setIsTaskExpanded}
                className="space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold tracking-tight">
                    Task Status
                  </h3>
                  <CollapsibleTrigger asChild>
                    <Button variant="ghost" size="sm" className={cn("w-9 p-0", !isCompleted && 'opacity-0 pointer-events-none')}>
                      {!isCompleted || isTaskExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      <span className="sr-only">Toggle Task Details</span>
                    </Button>
                  </CollapsibleTrigger>
                </div>
                <CollapsibleContent className="space-y-6">
                  <ActiveTaskViewer taskId={task.taskId} isCompleted={isCompleted} isTaskExpanded={isTaskExpanded} setIsTaskExpanded={setIsTaskExpanded} />
                </CollapsibleContent>
              </Collapsible>
            )}
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

function ActiveTaskViewer({ taskId, isCompleted, isTaskExpanded, setIsTaskExpanded }: { taskId: string, isCompleted: boolean, isTaskExpanded: boolean, setIsTaskExpanded: (v: boolean) => void }) {
  const taskQuery = trpc.taskById.useQuery(
    { taskId },
    { refetchInterval: 2500 },
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

  if (!taskQuery.data) return <div className="p-4 text-sm text-muted-foreground">Loading task details...</div>;

  const task = taskQuery.data;

  return (
    <div className="space-y-6">
        <TaskDetailPanel
        canceling={cancelMutation.isPending}
        onCancel={() =>
            cancelMutation.mutate({ taskId: task.taskId })
        }
        onRetry={() => retryMutation.mutate({ taskId: task.taskId })}
        retrying={retryMutation.isPending}
        task={task}
        />
        <TaskEventsList events={task.events} />
    </div>
  );
}
