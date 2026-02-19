import { spawn } from 'node:child_process';
import { PipelineError } from '@server/core/errors';

const REGEX_LINE_BREAK = /\r?\n/;
const splitLines = (buffer: string, onLine: (line: string) => void): string => {
  const parts = buffer.split(REGEX_LINE_BREAK);
  const pending = parts.pop() ?? '';
  for (const part of parts) {
    onLine(part);
  }
  return pending;
};

export const runCommand = (
  command: string,
  args: string[],
  cwd?: string,
  options?: {
    onStdoutLine?: (line: string) => void;
    onStderrLine?: (line: string) => void;
    shouldCancel?: () => Promise<boolean> | boolean;
  },
): Promise<{ stdout: string; stderr: string }> =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      shell: false,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let stdoutPending = '';
    let stderrPending = '';

    child.stdout.on('data', (chunk) => {
      const text = String(chunk);
      stdout += text;
      stdoutPending = splitLines(stdoutPending + text, (line) => {
        options?.onStdoutLine?.(line);
      });
      Promise.resolve(options?.shouldCancel?.())
        .then((shouldCancel) => {
          if (shouldCancel) {
            child.kill();
          }
        })
        .catch(() => undefined);
    });

    child.stderr.on('data', (chunk) => {
      const text = String(chunk);
      stderr += text;
      stderrPending = splitLines(stderrPending + text, (line) => {
        options?.onStderrLine?.(line);
      });
      Promise.resolve(options?.shouldCancel?.())
        .then((shouldCancel) => {
          if (shouldCancel) {
            child.kill();
          }
        })
        .catch(() => undefined);
    });

    child.on('error', reject);

    child.on('close', (code) => {
      if (stdoutPending) {
        options?.onStdoutLine?.(stdoutPending);
      }
      if (stderrPending) {
        options?.onStderrLine?.(stderrPending);
      }

      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }

      if (code === null) {
        reject(
          new PipelineError('command', `Command canceled: ${command}`, false),
        );
        return;
      }

      reject(
        new Error(
          `Command failed (${command} ${args.join(' ')}): ${stderr || stdout}`,
        ),
      );
    });
  });
