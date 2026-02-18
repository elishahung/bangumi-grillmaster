export interface ProjectRow {
  _id: string;
  projectId: string;
  source: string;
  sourceVideoId: string;
  originalInput: string;
  translationHint?: string;
  status: string;
  title?: string;
  thumbnailUrl?: string;
  sourceUrl?: string;
  mediaPath?: string;
  subtitlePath?: string;
  llmCostTwd: number;
  llmProvider?: string;
  llmModel?: string;
  inputTokens?: number;
  outputTokens?: number;
  createdAt: number;
  updatedAt: number;
}

export interface TaskRow {
  _id: string;
  taskId: string;
  projectId: string;
  type: string;
  status: string;
  currentStep: string;
  progressPercent: number;
  message: string;
  createdAt: number;
  updatedAt: number;
  startedAt?: number;
  finishedAt?: number;
  errorMessage?: string;
}

export interface TaskEventRow {
  _id: string;
  taskId: string;
  projectId: string;
  message: string;
  percent: number;
  createdAt: number;
}

export interface WatchProgressRow {
  _id: string;
  projectId: string;
  viewerId: string;
  positionSec: number;
  durationSec: number;
  updatedAt: number;
}

export interface ProjectDetail extends ProjectRow {
  tasks: TaskRow[];
  watchProgress: WatchProgressRow[];
}

export interface TaskDetail extends TaskRow {
  events: TaskEventRow[];
}
