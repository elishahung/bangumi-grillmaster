import { makeProjectService } from '@server/services/project-service';
import type { CreateNextContextOptions } from '@trpc/server/adapters/next';

export const createTrpcContext = (_opts: CreateNextContextOptions) => {
  return {
    projectService: makeProjectService(),
  };
};

export type TrpcContext = Awaited<ReturnType<typeof createTrpcContext>>;
