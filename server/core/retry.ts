import { PipelineError } from '@server/core/errors';
import {
  errAsync,
  okAsync,
  type ResultAsync as RA,
  ResultAsync,
} from 'neverthrow';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type RetryOptions = {
  baseDelayMs: number;
  jitter?: boolean;
  maxDelayMs?: number;
  maxRetries: number;
};

const withJitter = (delay: number) => delay * (0.75 + Math.random() * 0.5);

export const retryBackoff = <T>(
  factory: () => RA<T, PipelineError>,
  options: RetryOptions,
): RA<T, PipelineError> => {
  const run = (attempt: number): RA<T, PipelineError> =>
    factory().orElse((error) => {
      if (!error.retryable || attempt >= options.maxRetries) {
        return errAsync(error);
      }

      const rawDelay = Math.min(
        options.baseDelayMs * 2 ** attempt,
        options.maxDelayMs ?? Number.MAX_SAFE_INTEGER,
      );
      const delay = Math.max(
        1,
        Math.floor(options.jitter === false ? rawDelay : withJitter(rawDelay)),
      );

      return ResultAsync.fromPromise(sleep(delay), () => error).andThen(() =>
        run(attempt + 1),
      );
    });

  return run(0);
};

export const toPipelineError = (
  step: string,
  error: unknown,
  retryable: boolean,
) =>
  new PipelineError(
    step,
    error instanceof Error ? error.message : String(error),
    retryable,
  );

export const okUnit = () => okAsync<void, never>(undefined);
