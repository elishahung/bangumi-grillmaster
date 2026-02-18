CREATE TABLE `projects` (
	`id` text PRIMARY KEY NOT NULL,
	`project_id` text NOT NULL,
	`source` text NOT NULL,
	`source_video_id` text NOT NULL,
	`original_input` text NOT NULL,
	`translation_hint` text,
	`status` text NOT NULL,
	`title` text,
	`thumbnail_url` text,
	`source_url` text,
	`media_path` text,
	`subtitle_path` text,
	`llm_cost_twd` real DEFAULT 0 NOT NULL,
	`llm_provider` text,
	`llm_model` text,
	`input_tokens` integer,
	`output_tokens` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `projects_project_id_unique` ON `projects` (`project_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `projects_source_pair_uq` ON `projects` (`source`,`source_video_id`);--> statement-breakpoint
CREATE INDEX `projects_created_at_idx` ON `projects` (`created_at`);--> statement-breakpoint
CREATE TABLE `task_events` (
	`id` text PRIMARY KEY NOT NULL,
	`task_id` text NOT NULL,
	`project_id` text NOT NULL,
	`message` text NOT NULL,
	`percent` integer NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `task_events_task_id_idx` ON `task_events` (`task_id`);--> statement-breakpoint
CREATE INDEX `task_events_project_id_idx` ON `task_events` (`project_id`);--> statement-breakpoint
CREATE TABLE `tasks` (
	`id` text PRIMARY KEY NOT NULL,
	`task_id` text NOT NULL,
	`project_id` text NOT NULL,
	`type` text NOT NULL,
	`status` text NOT NULL,
	`current_step` text NOT NULL,
	`progress_percent` integer NOT NULL,
	`message` text NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL,
	`started_at` integer,
	`finished_at` integer,
	`error_message` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `tasks_task_id_unique` ON `tasks` (`task_id`);--> statement-breakpoint
CREATE INDEX `tasks_project_id_idx` ON `tasks` (`project_id`);--> statement-breakpoint
CREATE INDEX `tasks_updated_at_idx` ON `tasks` (`updated_at`);--> statement-breakpoint
CREATE TABLE `watch_progress` (
	`id` text PRIMARY KEY NOT NULL,
	`project_id` text NOT NULL,
	`viewer_id` text NOT NULL,
	`position_sec` real NOT NULL,
	`duration_sec` real NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `watch_progress_project_viewer_uq` ON `watch_progress` (`project_id`,`viewer_id`);--> statement-breakpoint
CREATE INDEX `watch_progress_project_id_idx` ON `watch_progress` (`project_id`);