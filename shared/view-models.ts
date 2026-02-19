export type ProjectRow = {
  _id: string;
  createdAt: number;
  inputTokens?: number;
  llmCostTwd: number;
  llmModel?: string;
  llmProvider?: string;
  mediaPath?: string;
  originalInput: string;
  outputTokens?: number;
  projectId: string;
  source: string;
  sourceUrl?: string;
  sourceVideoId: string;
  status: string;
  subtitlePath?: string;
  thumbnailUrl?: string;
  title?: string;
  translationHint?: string;
  updatedAt: number;
  task?: TaskRow | null; // Latest task
};

export type TaskRow = {
  _id: string;
  canceledAt?: number;
  cancelRequestedAt?: number;
  createdAt: number;
  currentStep: string;
  errorMessage?: string;
  finishedAt?: number;
  message: string;
  progressPercent: number;
  projectId: string;
  startedAt?: number;
  status: string;
  taskId: string;
  type: string;
  updatedAt: number;
};

export type TaskEventRow = {
  _id: string;
  createdAt: number;
  durationMs?: number;
  errorMessage?: string;
  eventType: 'step_start' | 'step_end' | 'log' | 'error' | 'system';
  level: 'trace' | 'debug' | 'info' | 'warn' | 'error';
  message: string;
  percent: number;
  projectId: string;
  step: string;
  taskId: string;
};

export type TaskStepStateRow = {
  _id: string;
  attempt: number;
  createdAt: number;
  durationMs?: number;
  errorMessage?: string;
  finishedAt?: number;
  outputJson?: string;
  projectId: string;
  startedAt?: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'canceled';
  step: string;
  taskId: string;
  updatedAt: number;
};

export type WatchProgressRow = {
  _id: string;
  durationSec: number;
  positionSec: number;
  projectId: string;
  updatedAt: number;
  viewerId: string;
};

export type ProjectDetail = ProjectRow & {
  tasks: TaskRow[];
  watchProgress: WatchProgressRow[];
};

export type TaskDetail = TaskRow & {
  events: TaskEventRow[];
};
