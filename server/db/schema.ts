import {
  index,
  integer,
  real,
  sqliteTable,
  text,
  uniqueIndex,
} from "drizzle-orm/sqlite-core";

export const projectsTable = sqliteTable(
  "projects",
  {
    id: text("id").primaryKey(),
    projectId: text("project_id").notNull().unique(),
    source: text("source").notNull(),
    sourceVideoId: text("source_video_id").notNull(),
    originalInput: text("original_input").notNull(),
    translationHint: text("translation_hint"),
    status: text("status").notNull(),
    title: text("title"),
    thumbnailUrl: text("thumbnail_url"),
    sourceUrl: text("source_url"),
    mediaPath: text("media_path"),
    subtitlePath: text("subtitle_path"),
    llmCostTwd: real("llm_cost_twd").notNull().default(0),
    llmProvider: text("llm_provider"),
    llmModel: text("llm_model"),
    inputTokens: integer("input_tokens"),
    outputTokens: integer("output_tokens"),
    createdAt: integer("created_at").notNull(),
    updatedAt: integer("updated_at").notNull(),
  },
  (table) => [
    uniqueIndex("projects_source_pair_uq").on(
      table.source,
      table.sourceVideoId,
    ),
    index("projects_created_at_idx").on(table.createdAt),
  ],
);

export const tasksTable = sqliteTable(
  "tasks",
  {
    id: text("id").primaryKey(),
    taskId: text("task_id").notNull().unique(),
    projectId: text("project_id").notNull(),
    type: text("type").notNull(),
    status: text("status").notNull(),
    currentStep: text("current_step").notNull(),
    progressPercent: integer("progress_percent").notNull(),
    message: text("message").notNull(),
    createdAt: integer("created_at").notNull(),
    updatedAt: integer("updated_at").notNull(),
    startedAt: integer("started_at"),
    finishedAt: integer("finished_at"),
    errorMessage: text("error_message"),
  },
  (table) => [
    index("tasks_project_id_idx").on(table.projectId),
    index("tasks_updated_at_idx").on(table.updatedAt),
  ],
);

export const taskEventsTable = sqliteTable(
  "task_events",
  {
    id: text("id").primaryKey(),
    taskId: text("task_id").notNull(),
    projectId: text("project_id").notNull(),
    message: text("message").notNull(),
    percent: integer("percent").notNull(),
    createdAt: integer("created_at").notNull(),
  },
  (table) => [
    index("task_events_task_id_idx").on(table.taskId),
    index("task_events_project_id_idx").on(table.projectId),
  ],
);

export const watchProgressTable = sqliteTable(
  "watch_progress",
  {
    id: text("id").primaryKey(),
    projectId: text("project_id").notNull(),
    viewerId: text("viewer_id").notNull(),
    positionSec: real("position_sec").notNull(),
    durationSec: real("duration_sec").notNull(),
    updatedAt: integer("updated_at").notNull(),
  },
  (table) => [
    uniqueIndex("watch_progress_project_viewer_uq").on(
      table.projectId,
      table.viewerId,
    ),
    index("watch_progress_project_id_idx").on(table.projectId),
  ],
);
