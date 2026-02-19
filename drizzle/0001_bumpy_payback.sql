CREATE TABLE `task_step_states` (
	`id` text PRIMARY KEY NOT NULL,
	`task_id` text NOT NULL,
	`project_id` text NOT NULL,
	`step` text NOT NULL,
	`status` text NOT NULL,
	`attempt` integer DEFAULT 0 NOT NULL,
	`started_at` integer,
	`finished_at` integer,
	`duration_ms` integer,
	`error_message` text,
	`output_json` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `task_step_states_task_step_uq` ON `task_step_states` (`task_id`,`step`);--> statement-breakpoint
CREATE INDEX `task_step_states_task_id_idx` ON `task_step_states` (`task_id`);--> statement-breakpoint
CREATE INDEX `task_step_states_project_id_idx` ON `task_step_states` (`project_id`);--> statement-breakpoint
ALTER TABLE `task_events` ADD `level` text DEFAULT 'info' NOT NULL;--> statement-breakpoint
ALTER TABLE `task_events` ADD `step` text DEFAULT 'system' NOT NULL;--> statement-breakpoint
ALTER TABLE `task_events` ADD `event_type` text DEFAULT 'system' NOT NULL;--> statement-breakpoint
ALTER TABLE `task_events` ADD `duration_ms` integer;--> statement-breakpoint
ALTER TABLE `task_events` ADD `error_message` text;--> statement-breakpoint
ALTER TABLE `tasks` ADD `cancel_requested_at` integer;--> statement-breakpoint
ALTER TABLE `tasks` ADD `canceled_at` integer;