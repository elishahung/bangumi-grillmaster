import { z } from "zod";

export const SourceSchema = z.enum(["bilibili", "tver", "youtube", "unknown"]);
export type Source = z.infer<typeof SourceSchema>;

export const ProjectStatusSchema = z.enum([
  "queued",
  "downloading",
  "asr",
  "translating",
  "completed",
  "failed",
]);

export const TaskStatusSchema = z.enum([
  "queued",
  "running",
  "completed",
  "failed",
]);

export const SubmitProjectInputSchema = z.object({
  sourceOrUrl: z.string().min(2),
  translationHint: z.string().max(400).optional(),
});

export const TaskProgressSchema = z.object({
  step: z.string().min(1),
  percent: z.number().int().min(0).max(100),
  message: z.string().min(1),
});

export const CostBreakdownSchema = z.object({
  llmProvider: z.string(),
  llmModel: z.string(),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
  totalCostTwd: z.number().nonnegative(),
});
