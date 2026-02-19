import { repository } from '@server/db/repository';
import type { TaskEventRow } from '@shared/view-models';
import chalk from 'chalk';

const MAX_LOG_MESSAGE = 1600;

const truncateMessage = (message: string) =>
  message.length > MAX_LOG_MESSAGE
    ? `${message.slice(0, MAX_LOG_MESSAGE)}...[truncated ${message.length - MAX_LOG_MESSAGE} chars]`
    : message;

const colorByLevel: Record<TaskEventRow['level'], (text: string) => string> = {
  trace: chalk.gray,
  debug: chalk.cyan,
  info: chalk.white,
  warn: chalk.yellow,
  error: chalk.red,
};

export type TaskLogger = {
  debug: (message: string) => Promise<void>;
  error: (message: string, errorMessage?: string) => Promise<void>;
  info: (message: string) => Promise<void>;
  trace: (message: string) => Promise<void>;
  warn: (message: string) => Promise<void>;
};

export const createTaskLogger = (input: {
  taskId: string;
  projectId: string;
  step: string;
  percent: number;
}): TaskLogger => {
  const write = async (
    level: TaskEventRow['level'],
    message: string,
    errorMessage?: string,
  ) => {
    const normalized = truncateMessage(message);
    const stamp = new Date().toISOString();
    const line = `[${stamp}] [${level.toUpperCase()}] [task:${input.taskId}] [step:${input.step}] ${normalized}`;
    const withColor = colorByLevel[level] ?? chalk.white;
    if (level === 'error') {
      console.error(withColor(line));
    } else {
      console.log(withColor(line));
    }

    await repository.appendTaskEvent({
      taskId: input.taskId,
      projectId: input.projectId,
      step: input.step,
      eventType: level === 'error' ? 'error' : 'log',
      level,
      message: normalized,
      percent: input.percent,
      errorMessage,
    });
  };

  return {
    trace: async (message) => write('trace', message),
    debug: async (message) => write('debug', message),
    info: async (message) => write('info', message),
    warn: async (message) => write('warn', message),
    error: async (message, errorMessage) =>
      write('error', message, errorMessage),
  };
};
