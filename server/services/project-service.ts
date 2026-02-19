import fs from 'node:fs/promises';
import path from 'node:path';
import { ConflictError, InfrastructureError } from '@server/core/errors';
import { repository } from '@server/db/repository';
import { parseSourceInput } from '@server/services/parse-source';
import { SubmitProjectInputSchema } from '@shared/domain';
import type {
  ProjectDetail,
  ProjectRow,
  TaskDetail,
  TaskRow,
} from '@shared/view-models';
import { errAsync, fromPromise, type ResultAsync } from 'neverthrow';

type ServiceError = ConflictError | InfrastructureError;
const infra = (message: string) => new InfrastructureError(message);

export const makeProjectService = () => ({
  submitProject: (
    input: unknown,
  ): ResultAsync<
    { projectId: string; taskId: string; status: 'queued' },
    ServiceError
  > => {
    const data = SubmitProjectInputSchema.parse(input);
    const source = parseSourceInput(data.sourceOrUrl);

    if (source.isErr()) {
      return errAsync(infra(source.error.message));
    }

    return fromPromise(
      repository.submitProject({
        source: source.value.source,
        sourceVideoId: source.value.sourceVideoId,
        originalInput: data.sourceOrUrl,
        translationHint: data.translationHint,
      }),
      (error) => {
        if (
          error instanceof Error &&
          error.message.includes('already exists')
        ) {
          return new ConflictError(error.message);
        }

        return infra(`submitProject failed: ${String(error)}`);
      },
    );
  },

  listProjects: (): ResultAsync<ProjectRow[], ServiceError> =>
    fromPromise(repository.listProjects(), (error) =>
      infra(`listProjects failed: ${String(error)}`),
    ),

  getProjectById: (
    projectId: string,
  ): ResultAsync<ProjectDetail | null, ServiceError> =>
    fromPromise(repository.getProjectById(projectId), (error) =>
      infra(`getProjectById failed: ${String(error)}`),
    ),

  listTasks: (limit?: number): ResultAsync<TaskRow[], ServiceError> =>
    fromPromise(repository.listTasks(limit), (error) =>
      infra(`listTasks failed: ${String(error)}`),
    ),

  getTaskById: (taskId: string): ResultAsync<TaskDetail | null, ServiceError> =>
    fromPromise(repository.getTaskById(taskId), (error) =>
      infra(`getTaskById failed: ${String(error)}`),
    ),

  retryTask: (
    taskId: string,
  ): ResultAsync<{ taskId: string; projectId: string }, ServiceError> =>
    fromPromise(repository.retryTask(taskId), (error) =>
      infra(`retryTask failed: ${String(error)}`),
    ),

  cancelTask: (
    taskId: string,
  ): ResultAsync<
    { taskId: string; projectId: string; status: string },
    ServiceError
  > =>
    fromPromise(repository.requestTaskCancel(taskId), (error) =>
      infra(`cancelTask failed: ${String(error)}`),
    ),

  upsertWatchProgress: (input: {
    projectId: string;
    viewerId: string;
    positionSec: number;
    durationSec: number;
  }) =>
    fromPromise(repository.upsertWatchProgress(input), (error) =>
      infra(`upsertWatchProgress failed: ${String(error)}`),
    ),

  deleteProject: (
    projectId: string,
  ): ResultAsync<{ ok: true }, ServiceError> =>
    fromPromise(
      (async () => {
        // 1. Get project to confirm existence (and potentially get info for logging)
        const project = await repository.getProjectById(projectId);
        if (!project) {
          // If project doesn't exist in DB, we still might want to try cleaning up folder, 
          // but for now let's just return success or error. 
          // If it's already gone, "delete" is technically successful or a no-op.
          // Let's treat it as a no-op success to be idempotent, or error if strict.
          // Given the requirement "project can be removed", if it's missing it's removed.
          return { ok: true as const };
        }

        // 2. Rename project folder
        const projectDir = path.resolve(process.cwd(), 'projects', projectId);
        try {
          await fs.access(projectDir);
          // Folder exists, rename it
          const deletedDir = path.resolve(
            process.cwd(),
            'projects',
            `_deleted_${projectId}`,
          );
          // If _deleted_ folder already exists, we might overwrite or error. 
          // Rename will likely fail if target exists and is non-empty or we might want to append ts.
          // For simplicity, let's assume simple rename.
          await fs.rename(projectDir, deletedDir);
        } catch (e) {
          // If folder doesn't exist, ignore (maybe it was manually deleted)
          // If rename fails, we might want to throw or log. 
          // But strict requirement: "if project folder exists, add _deleted_"
          if ((e as NodeJS.ErrnoException).code !== 'ENOENT') {
             throw new InfrastructureError(`Failed to rename project folder: ${String(e)}`);
          }
        }

        // 3. Delete from DB
        await repository.deleteProject(projectId);

        return { ok: true as const };
      })(),
      (error) => {
         if (error instanceof InfrastructureError) return error;
         return infra(`deleteProject failed: ${String(error)}`);
      }
    ),
});

