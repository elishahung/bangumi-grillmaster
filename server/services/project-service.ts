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
});
