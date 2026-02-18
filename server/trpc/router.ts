import { getTaskPipelineRunner } from "@server/pipeline/runner";
import { createTrpcError, publicProcedure, router } from "@server/trpc/trpc";
import { SubmitProjectInputSchema } from "@shared/domain";
import { z } from "zod";

export const appRouter = router({
  submitProject: publicProcedure
    .input(SubmitProjectInputSchema)
    .mutation(async ({ ctx, input }) => {
      const result = await ctx.projectService.submitProject(input).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );

      getTaskPipelineRunner().enqueue({
        taskId: result.taskId,
        projectId: result.projectId,
      });
      return result;
    }),

  listProjects: publicProcedure.query(async ({ ctx }) => {
    return ctx.projectService.listProjects().match(
      (value) => value,
      (error) => {
        throw createTrpcError(error);
      },
    );
  }),

  projectById: publicProcedure
    .input(z.object({ projectId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      return ctx.projectService.getProjectById(input.projectId).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );
    }),

  listTasks: publicProcedure
    .input(
      z.object({ limit: z.number().int().positive().optional() }).optional(),
    )
    .query(async ({ ctx, input }) => {
      return ctx.projectService.listTasks(input?.limit).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );
    }),

  taskById: publicProcedure
    .input(z.object({ taskId: z.string().uuid() }))
    .query(async ({ ctx, input }) => {
      return ctx.projectService.getTaskById(input.taskId).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );
    }),

  retryTask: publicProcedure
    .input(z.object({ taskId: z.string().uuid() }))
    .mutation(async ({ ctx, input }) => {
      const result = await ctx.projectService.retryTask(input.taskId).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );

      getTaskPipelineRunner().enqueue(result);
      return { ok: true };
    }),

  upsertWatchProgress: publicProcedure
    .input(
      z.object({
        projectId: z.string().uuid(),
        viewerId: z.string().uuid(),
        positionSec: z.number().nonnegative(),
        durationSec: z.number().positive(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      return ctx.projectService.upsertWatchProgress(input).match(
        (value) => value,
        (error) => {
          throw createTrpcError(error);
        },
      );
    }),
});

export type AppRouter = typeof appRouter;
