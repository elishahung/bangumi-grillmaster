import { db, initDb } from '@server/db/client';
import {
  projectsTable,
  taskEventsTable,
  taskStepStatesTable,
  tasksTable,
  watchProgressTable,
} from '@server/db/schema';
import type {
  ProjectDetail,
  ProjectRow,
  TaskDetail,
  TaskEventRow,
  TaskRow,
  TaskStepStateRow,
  WatchProgressRow,
} from '@shared/view-models';
import { and, desc, eq, inArray } from 'drizzle-orm';

const now = () => Date.now();

const toProjectRow = (row: typeof projectsTable.$inferSelect): ProjectRow => ({
  _id: row.id,
  projectId: row.projectId,
  source: row.source,
  sourceVideoId: row.sourceVideoId,
  originalInput: row.originalInput,
  translationHint: row.translationHint ?? undefined,
  status: row.status,
  title: row.title ?? undefined,
  thumbnailUrl: row.thumbnailUrl ?? undefined,
  sourceUrl: row.sourceUrl ?? undefined,
  mediaPath: row.mediaPath ?? undefined,
  subtitlePath: row.subtitlePath ?? undefined,
  llmCostTwd: row.llmCostTwd,
  llmProvider: row.llmProvider ?? undefined,
  llmModel: row.llmModel ?? undefined,
  inputTokens: row.inputTokens ?? undefined,
  outputTokens: row.outputTokens ?? undefined,
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
});

const toTaskRow = (row: typeof tasksTable.$inferSelect): TaskRow => ({
  _id: row.id,
  taskId: row.taskId,
  projectId: row.projectId,
  type: row.type,
  status: row.status,
  currentStep: row.currentStep,
  progressPercent: row.progressPercent,
  message: row.message,
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
  startedAt: row.startedAt ?? undefined,
  finishedAt: row.finishedAt ?? undefined,
  errorMessage: row.errorMessage ?? undefined,
  cancelRequestedAt: row.cancelRequestedAt ?? undefined,
  canceledAt: row.canceledAt ?? undefined,
});

const toTaskEventRow = (
  row: typeof taskEventsTable.$inferSelect,
): TaskEventRow => ({
  _id: row.id,
  taskId: row.taskId,
  projectId: row.projectId,
  level: (row.level as TaskEventRow['level']) ?? 'info',
  step: row.step,
  eventType: (row.eventType as TaskEventRow['eventType']) ?? 'system',
  message: row.message,
  percent: row.percent,
  durationMs: row.durationMs ?? undefined,
  errorMessage: row.errorMessage ?? undefined,
  createdAt: row.createdAt,
});

const toTaskStepStateRow = (
  row: typeof taskStepStatesTable.$inferSelect,
): TaskStepStateRow => ({
  _id: row.id,
  taskId: row.taskId,
  projectId: row.projectId,
  step: row.step,
  status: row.status as TaskStepStateRow['status'],
  attempt: row.attempt,
  startedAt: row.startedAt ?? undefined,
  finishedAt: row.finishedAt ?? undefined,
  durationMs: row.durationMs ?? undefined,
  errorMessage: row.errorMessage ?? undefined,
  outputJson: row.outputJson ?? undefined,
  createdAt: row.createdAt,
  updatedAt: row.updatedAt,
});

const toWatchProgressRow = (
  row: typeof watchProgressTable.$inferSelect,
): WatchProgressRow => ({
  _id: row.id,
  projectId: row.projectId,
  viewerId: row.viewerId,
  positionSec: row.positionSec,
  durationSec: row.durationSec,
  updatedAt: row.updatedAt,
});

export const repository = {
  init: () => initDb(),

  appendTaskEvent: async (input: {
    taskId: string;
    projectId: string;
    step?: string;
    eventType?: TaskEventRow['eventType'];
    level?: TaskEventRow['level'];
    message: string;
    percent: number;
    durationMs?: number;
    errorMessage?: string;
  }) => {
    initDb();
    await db.insert(taskEventsTable).values({
      id: crypto.randomUUID(),
      taskId: input.taskId,
      projectId: input.projectId,
      level: input.level ?? 'info',
      step: input.step ?? 'system',
      eventType: input.eventType ?? 'system',
      message: input.message,
      percent: input.percent,
      durationMs: input.durationMs,
      errorMessage: input.errorMessage,
      createdAt: now(),
    });

    return { ok: true as const };
  },

  submitProject: async (input: {
    source: string;
    sourceVideoId: string;
    originalInput: string;
    translationHint?: string;
  }) => {
    initDb();
    const duplicated = await db
      .select({ projectId: projectsTable.projectId })
      .from(projectsTable)
      .where(
        and(
          eq(projectsTable.source, input.source),
          eq(projectsTable.sourceVideoId, input.sourceVideoId),
        ),
      )
      .limit(1);

    if (duplicated.length > 0) {
      throw new Error('Project already exists for this source and videoId');
    }

    const createdAt = now();
    const projectId = crypto.randomUUID();
    const taskId = crypto.randomUUID();

    await db.insert(projectsTable).values({
      id: crypto.randomUUID(),
      projectId,
      source: input.source,
      sourceVideoId: input.sourceVideoId,
      originalInput: input.originalInput,
      translationHint: input.translationHint,
      status: 'queued',
      llmCostTwd: 0,
      createdAt,
      updatedAt: createdAt,
    });

    await db.insert(tasksTable).values({
      id: crypto.randomUUID(),
      taskId,
      projectId,
      type: 'pipeline',
      status: 'queued',
      currentStep: 'submit',
      progressPercent: 0,
      message: 'Project submitted',
      createdAt,
      updatedAt: createdAt,
    });

    await repository.appendTaskEvent({
      taskId,
      projectId,
      message: 'Project created and queued',
      percent: 0,
      eventType: 'system',
      step: 'submit',
      level: 'info',
    });

    return { projectId, taskId, status: 'queued' as const };
  },

  listProjects: async (): Promise<ProjectRow[]> => {
    initDb();
    const projects = await db
      .select()
      .from(projectsTable)
      .orderBy(desc(projectsTable.createdAt))
      .limit(200);

    if (projects.length === 0) {
      return [];
    }

    const tasks = await db
      .select()
      .from(tasksTable)
      .where(
        inArray(
          tasksTable.projectId,
          projects.map((p) => p.projectId),
        ),
      );

    // Map latest task to project
    const taskMap = new Map<string, TaskRow>();
    for (const task of tasks) {
      const existing = taskMap.get(task.projectId);
      if (!existing || task.updatedAt > existing.updatedAt) {
        taskMap.set(task.projectId, toTaskRow(task));
      }
    }

    return projects.map((p) => ({
      ...toProjectRow(p),
      task: taskMap.get(p.projectId) ?? null,
    }));
  },

  getProjectRuntime: async (projectId: string): Promise<ProjectRow | null> => {
    initDb();
    const row = await db
      .select()
      .from(projectsTable)
      .where(eq(projectsTable.projectId, projectId))
      .limit(1);

    return row[0] ? toProjectRow(row[0]) : null;
  },

  getProjectById: async (projectId: string): Promise<ProjectDetail | null> => {
    initDb();
    const projectRows = await db
      .select()
      .from(projectsTable)
      .where(eq(projectsTable.projectId, projectId))
      .limit(1);

    const project = projectRows[0];
    if (!project) {
      return null;
    }

    const taskRows = await db
      .select()
      .from(tasksTable)
      .where(eq(tasksTable.projectId, projectId))
      .orderBy(desc(tasksTable.updatedAt))
      .limit(20);

    const progressRows = await db
      .select()
      .from(watchProgressTable)
      .where(eq(watchProgressTable.projectId, projectId));

    return {
      ...toProjectRow(project),
      tasks: taskRows.map(toTaskRow),
      watchProgress: progressRows.map(toWatchProgressRow),
    };
  },

  updateProjectFromPipeline: async (input: {
    projectId: string;
    status: string;
    title?: string;
    thumbnailUrl?: string;
    sourceUrl?: string;
    mediaPath?: string;
    subtitlePath?: string;
    llmCostTwd?: number;
    llmProvider?: string;
    llmModel?: string;
    inputTokens?: number;
    outputTokens?: number;
  }) => {
    initDb();
    const updatedAt = now();

    await db
      .update(projectsTable)
      .set({
        status: input.status,
        title: input.title,
        thumbnailUrl: input.thumbnailUrl,
        sourceUrl: input.sourceUrl,
        mediaPath: input.mediaPath,
        subtitlePath: input.subtitlePath,
        llmCostTwd: input.llmCostTwd,
        llmProvider: input.llmProvider,
        llmModel: input.llmModel,
        inputTokens: input.inputTokens,
        outputTokens: input.outputTokens,
        updatedAt,
      })
      .where(eq(projectsTable.projectId, input.projectId));

    return { ok: true };
  },

  listTasks: async (limit = 100): Promise<TaskRow[]> => {
    initDb();
    const rows = await db
      .select()
      .from(tasksTable)
      .orderBy(desc(tasksTable.updatedAt))
      .limit(limit);
    return rows.map(toTaskRow);
  },

  getTaskRuntime: async (taskId: string): Promise<TaskRow | null> => {
    initDb();
    const rows = await db
      .select()
      .from(tasksTable)
      .where(eq(tasksTable.taskId, taskId))
      .limit(1);

    return rows[0] ? toTaskRow(rows[0]) : null;
  },

  getTaskById: async (taskId: string): Promise<TaskDetail | null> => {
    initDb();
    const rows = await db
      .select()
      .from(tasksTable)
      .where(eq(tasksTable.taskId, taskId))
      .limit(1);

    const task = rows[0];
    if (!task) {
      return null;
    }

    const eventRows = await db
      .select()
      .from(taskEventsTable)
      .where(eq(taskEventsTable.taskId, taskId))
      .orderBy(desc(taskEventsTable.createdAt))
      .limit(400);

    return {
      ...toTaskRow(task),
      events: eventRows.map(toTaskEventRow),
    };
  },

  updateTaskProgress: async (input: {
    taskId: string;
    status: string;
    step: string;
    percent: number;
    message: string;
    errorMessage?: string;
    eventType?: TaskEventRow['eventType'];
    level?: TaskEventRow['level'];
    durationMs?: number;
  }) => {
    initDb();
    const rows = await db
      .select()
      .from(tasksTable)
      .where(eq(tasksTable.taskId, input.taskId))
      .limit(1);

    const task = rows[0];
    if (!task) {
      throw new Error('Task not found');
    }

    const updatedAt = now();
    const isTerminal = ['completed', 'failed', 'canceled'].includes(
      input.status,
    );

    await db
      .update(tasksTable)
      .set({
        status: input.status,
        currentStep: input.step,
        progressPercent: input.percent,
        message: input.message,
        updatedAt,
        startedAt: task.startedAt ?? updatedAt,
        finishedAt: isTerminal ? updatedAt : null,
        errorMessage: input.errorMessage ?? null,
      })
      .where(eq(tasksTable.id, task.id));

    await repository.appendTaskEvent({
      taskId: task.taskId,
      projectId: task.projectId,
      step: input.step,
      eventType: input.eventType ?? 'system',
      level: input.level ?? (input.errorMessage ? 'error' : 'info'),
      message: input.message,
      percent: input.percent,
      durationMs: input.durationMs,
      errorMessage: input.errorMessage,
    });

    return { ok: true };
  },

  getTaskStepStates: async (taskId: string): Promise<TaskStepStateRow[]> => {
    initDb();
    const rows = await db
      .select()
      .from(taskStepStatesTable)
      .where(eq(taskStepStatesTable.taskId, taskId))
      .orderBy(desc(taskStepStatesTable.updatedAt));

    return rows.map(toTaskStepStateRow);
  },

  upsertTaskStepState: async (input: {
    taskId: string;
    projectId: string;
    step: string;
    status: TaskStepStateRow['status'];
    attempt?: number;
    startedAt?: number;
    finishedAt?: number;
    durationMs?: number;
    errorMessage?: string;
    outputJson?: string;
  }) => {
    initDb();
    const rows = await db
      .select()
      .from(taskStepStatesTable)
      .where(
        and(
          eq(taskStepStatesTable.taskId, input.taskId),
          eq(taskStepStatesTable.step, input.step),
        ),
      )
      .limit(1);

    const existing = rows[0];
    const updatedAt = now();

    if (existing) {
      await db
        .update(taskStepStatesTable)
        .set({
          status: input.status,
          attempt: input.attempt ?? existing.attempt,
          startedAt: input.startedAt ?? existing.startedAt,
          finishedAt: input.finishedAt,
          durationMs: input.durationMs,
          errorMessage: input.errorMessage,
          outputJson: input.outputJson ?? existing.outputJson,
          updatedAt,
        })
        .where(eq(taskStepStatesTable.id, existing.id));

      return { ok: true as const };
    }

    await db.insert(taskStepStatesTable).values({
      id: crypto.randomUUID(),
      taskId: input.taskId,
      projectId: input.projectId,
      step: input.step,
      status: input.status,
      attempt: input.attempt ?? 0,
      startedAt: input.startedAt,
      finishedAt: input.finishedAt,
      durationMs: input.durationMs,
      errorMessage: input.errorMessage,
      outputJson: input.outputJson,
      createdAt: updatedAt,
      updatedAt,
    });

    return { ok: true as const };
  },

  markStepStart: async (input: {
    taskId: string;
    projectId: string;
    step: string;
  }) => {
    initDb();
    const rows = await db
      .select()
      .from(taskStepStatesTable)
      .where(
        and(
          eq(taskStepStatesTable.taskId, input.taskId),
          eq(taskStepStatesTable.step, input.step),
        ),
      )
      .limit(1);

    const existing = rows[0];
    const startedAt = now();

    await repository.upsertTaskStepState({
      taskId: input.taskId,
      projectId: input.projectId,
      step: input.step,
      status: 'running',
      attempt: (existing?.attempt ?? 0) + 1,
      startedAt,
      finishedAt: undefined,
      durationMs: undefined,
      errorMessage: undefined,
    });

    return { startedAt };
  },

  markStepEnd: async (input: {
    taskId: string;
    projectId: string;
    step: string;
    status: 'completed' | 'failed' | 'canceled';
    errorMessage?: string;
    outputJson?: string;
  }) => {
    initDb();
    const rows = await db
      .select()
      .from(taskStepStatesTable)
      .where(
        and(
          eq(taskStepStatesTable.taskId, input.taskId),
          eq(taskStepStatesTable.step, input.step),
        ),
      )
      .limit(1);

    const existing = rows[0];
    const finishedAt = now();
    const startedAt = existing?.startedAt ?? finishedAt;
    const durationMs = Math.max(0, finishedAt - startedAt);

    await repository.upsertTaskStepState({
      taskId: input.taskId,
      projectId: input.projectId,
      step: input.step,
      status: input.status,
      attempt: existing?.attempt ?? 1,
      startedAt,
      finishedAt,
      durationMs,
      errorMessage: input.errorMessage,
      outputJson: input.outputJson,
    });

    return { finishedAt, durationMs };
  },

  requestTaskCancel: async (taskId: string) => {
    initDb();
    const task = await repository.getTaskRuntime(taskId);
    if (!task) {
      throw new Error('Task not found');
    }

    const updatedAt = now();

    if (['completed', 'failed', 'canceled'].includes(task.status)) {
      return {
        taskId: task.taskId,
        projectId: task.projectId,
        status: task.status,
      };
    }

    if (task.status === 'queued') {
      await db
        .update(tasksTable)
        .set({
          status: 'canceled',
          currentStep: 'canceled',
          message: 'Task canceled before execution',
          finishedAt: updatedAt,
          canceledAt: updatedAt,
          cancelRequestedAt: updatedAt,
          errorMessage: 'Canceled by user',
          updatedAt,
        })
        .where(eq(tasksTable.taskId, taskId));

      await repository.updateProjectFromPipeline({
        projectId: task.projectId,
        status: 'canceled',
      });

      await repository.appendTaskEvent({
        taskId,
        projectId: task.projectId,
        step: 'canceled',
        eventType: 'system',
        level: 'warn',
        message: 'Task canceled before execution',
        percent: task.progressPercent,
        errorMessage: 'Canceled by user',
      });

      return {
        taskId: task.taskId,
        projectId: task.projectId,
        status: 'canceled' as const,
      };
    }

    await db
      .update(tasksTable)
      .set({
        status: 'canceling',
        message: 'Cancel requested; stopping at next safe point',
        cancelRequestedAt: updatedAt,
        updatedAt,
      })
      .where(eq(tasksTable.taskId, taskId));

    await repository.updateProjectFromPipeline({
      projectId: task.projectId,
      status: 'canceling',
    });

    await repository.appendTaskEvent({
      taskId,
      projectId: task.projectId,
      step: task.currentStep,
      eventType: 'system',
      level: 'warn',
      message: 'Cancel requested; waiting for current step to finish',
      percent: task.progressPercent,
    });

    return {
      taskId: task.taskId,
      projectId: task.projectId,
      status: 'canceling' as const,
    };
  },

  isTaskCancelRequested: async (taskId: string) => {
    initDb();
    const rows = await db
      .select({
        cancelRequestedAt: tasksTable.cancelRequestedAt,
        status: tasksTable.status,
      })
      .from(tasksTable)
      .where(eq(tasksTable.taskId, taskId))
      .limit(1);

    const row = rows[0];
    if (!row) {
      throw new Error('Task not found');
    }

    return Boolean(row.cancelRequestedAt) || row.status === 'canceling';
  },

  markTaskCanceled: async (input: {
    taskId: string;
    reason: string;
    step: string;
    percent: number;
  }) => {
    initDb();
    const task = await repository.getTaskRuntime(input.taskId);
    if (!task) {
      throw new Error('Task not found');
    }

    const updatedAt = now();

    await db
      .update(tasksTable)
      .set({
        status: 'canceled',
        currentStep: input.step,
        message: input.reason,
        errorMessage: input.reason,
        canceledAt: updatedAt,
        finishedAt: updatedAt,
        cancelRequestedAt: task.cancelRequestedAt ?? updatedAt,
        updatedAt,
      })
      .where(eq(tasksTable.taskId, input.taskId));

    await repository.updateProjectFromPipeline({
      projectId: task.projectId,
      status: 'canceled',
    });

    await repository.appendTaskEvent({
      taskId: input.taskId,
      projectId: task.projectId,
      step: input.step,
      eventType: 'error',
      level: 'warn',
      message: input.reason,
      percent: input.percent,
      errorMessage: input.reason,
    });

    return { ok: true as const };
  },

  retryTask: async (taskId: string) => {
    initDb();
    const task = await repository.getTaskById(taskId);
    if (!task) {
      throw new Error('Task not found');
    }

    const updatedAt = now();

    await db
      .update(tasksTable)
      .set({
        status: 'queued',
        currentStep: 'retry',
        message: 'Task retried and queued',
        progressPercent: 0,
        errorMessage: null,
        cancelRequestedAt: null,
        canceledAt: null,
        finishedAt: null,
        updatedAt,
      })
      .where(eq(tasksTable.taskId, taskId));

    await repository.updateProjectFromPipeline({
      projectId: task.projectId,
      status: 'queued',
    });

    const stepRows = await db
      .select()
      .from(taskStepStatesTable)
      .where(eq(taskStepStatesTable.taskId, taskId));

    await Promise.all(
      stepRows
        .filter((row) => row.status !== 'completed')
        .map((row) =>
          db
            .update(taskStepStatesTable)
            .set({
              status: 'pending',
              startedAt: null,
              finishedAt: null,
              durationMs: null,
              errorMessage: null,
              updatedAt,
            })
            .where(eq(taskStepStatesTable.id, row.id)),
        ),
    );

    await repository.appendTaskEvent({
      taskId: task.taskId,
      projectId: task.projectId,
      step: 'retry',
      eventType: 'system',
      level: 'info',
      message: 'Task retried and queued',
      percent: 0,
    });

    return { taskId: task.taskId, projectId: task.projectId };
  },

  upsertWatchProgress: async (input: {
    projectId: string;
    viewerId: string;
    positionSec: number;
    durationSec: number;
  }) => {
    initDb();
    const updatedAt = now();

    const existing = await db
      .select()
      .from(watchProgressTable)
      .where(
        and(
          eq(watchProgressTable.projectId, input.projectId),
          eq(watchProgressTable.viewerId, input.viewerId),
        ),
      )
      .limit(1);

    if (existing.length > 0) {
      await db
        .update(watchProgressTable)
        .set({
          positionSec: input.positionSec,
          durationSec: input.durationSec,
          updatedAt,
        })
        .where(eq(watchProgressTable.id, existing[0]!.id));
    } else {
      await db.insert(watchProgressTable).values({
        id: crypto.randomUUID(),
        projectId: input.projectId,
        viewerId: input.viewerId,
        positionSec: input.positionSec,
        durationSec: input.durationSec,
        updatedAt,
      });
    }

    return { ok: true as const };
  },

  deleteProject: async (projectId: string) => {
    initDb();

    // Delete tasks associated with the project
    await db.delete(tasksTable).where(eq(tasksTable.projectId, projectId));

    // Delete task events associated with the project
    await db
      .delete(taskEventsTable)
      .where(eq(taskEventsTable.projectId, projectId));

    // Delete task step states associated with the project
    await db
      .delete(taskStepStatesTable)
      .where(eq(taskStepStatesTable.projectId, projectId));

    // Delete watch progress associated with the project
    await db
      .delete(watchProgressTable)
      .where(eq(watchProgressTable.projectId, projectId));

    // Delete the project itself
    await db.delete(projectsTable).where(eq(projectsTable.projectId, projectId));

    return { ok: true as const };
  },
};

