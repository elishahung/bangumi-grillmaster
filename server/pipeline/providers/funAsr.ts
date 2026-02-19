import fs from 'node:fs/promises';
import path from 'node:path';
import { PipelineError } from '@server/core/errors';
import type { TaskLogger } from '@server/core/logger';
import { retryBackoff, toPipelineError } from '@server/core/retry';
import { env } from '@server/env';
import OSS from 'ali-oss';
import { errAsync, okAsync, ResultAsync } from 'neverthrow';

type FunAsrWord = {
  begin_time: number;
  end_time: number;
  punctuation?: string;
  text: string;
};

type FunAsrSentence = {
  begin_time: number;
  end_time: number;
  text: string;
  words: FunAsrWord[];
};

type FunAsrTranscript = {
  channel_id: number;
  sentences: FunAsrSentence[];
};

type FunAsrResult = {
  transcripts: FunAsrTranscript[];
};

const getRequired = (name: string, value: string | undefined) => {
  if (!value) {
    throw new PipelineError('env', `${name} is required for live ASR`, false);
  }
  return value;
};

const srtTime = (ms: number) => {
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  const seconds = Math.floor((ms % 60_000) / 1000);
  const milliseconds = ms % 1000;
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')},${String(milliseconds).padStart(3, '0')}`;
};

const REGEX_ENGLISH_LETTER = /^[A-Za-z]$/;
const isEnglishLetter = (char: string) => REGEX_ENGLISH_LETTER.test(char);

const mergeDottedSentences = (sentences: FunAsrSentence[]) => {
  const merged: FunAsrSentence[] = [];
  let cursor = 0;

  while (cursor < sentences.length) {
    let current = sentences[cursor];
    if (!current) {
      break;
    }

    while (cursor + 1 < sentences.length) {
      const next = sentences[cursor + 1];
      if (!next) {
        break;
      }

      const lastWord = current.words.at(-1);
      if (!lastWord || lastWord.punctuation?.trim() !== '.') {
        break;
      }

      const lastChar = lastWord.text.trim().at(-1);
      const nextHead = next.words.at(0)?.text.trim().at(0);
      if (
        !(
          lastChar &&
          nextHead &&
          isEnglishLetter(lastChar) &&
          isEnglishLetter(nextHead)
        )
      ) {
        break;
      }

      if (next.begin_time - current.end_time > 500) {
        break;
      }

      current = {
        begin_time: current.begin_time,
        end_time: next.end_time,
        text: `${current.text.trimEnd()}${next.text}`,
        words: [...current.words, ...next.words],
      };
      cursor += 1;
    }

    merged.push(current);
    cursor += 1;
  }

  return merged;
};

const splitLongSentence = (sentence: FunAsrSentence, maxChars = 40) => {
  const fullText = sentence.words
    .map((word) => `${word.text}${word.punctuation ?? ''}`)
    .join('')
    .trim();

  if (fullText.length <= maxChars) {
    return [
      {
        begin_time: sentence.begin_time,
        end_time: sentence.end_time,
        text: fullText || sentence.text.trim(),
      },
    ];
  }

  const segments: Array<{
    begin_time: number;
    end_time: number;
    text: string;
  }> = [];
  let buffer: FunAsrWord[] = [];
  let bufferText = '';
  let splitPivot = -1;

  for (const word of sentence.words) {
    const token = `${word.text}${word.punctuation ?? ''}`;
    buffer.push(word);
    bufferText += token;

    if (
      ['、', '。', '！', '？', '!', '?', '，', ','].includes(
        (word.punctuation ?? '').trim(),
      )
    ) {
      splitPivot = buffer.length;
    }

    if (bufferText.length >= Math.floor(maxChars * 0.8)) {
      const cut = splitPivot > 0 ? splitPivot : buffer.length;
      const chunk = buffer.slice(0, cut);
      const first = chunk[0];
      const last = chunk.at(-1);
      const text = chunk
        .map((part) => `${part.text}${part.punctuation ?? ''}`)
        .join('')
        .trim();

      if (first && last && text) {
        segments.push({
          begin_time: first.begin_time,
          end_time: last.end_time,
          text,
        });
      }

      buffer = buffer.slice(cut);
      bufferText = buffer
        .map((part) => `${part.text}${part.punctuation ?? ''}`)
        .join('');
      splitPivot = -1;
    }
  }

  const first = buffer[0];
  const last = buffer.at(-1);
  const text = buffer
    .map((part) => `${part.text}${part.punctuation ?? ''}`)
    .join('')
    .trim();

  if (first && last && text) {
    segments.push({
      begin_time: first.begin_time,
      end_time: last.end_time,
      text,
    });
  }

  return segments;
};

const convertToSrt = (result: FunAsrResult) => {
  const transcript =
    result.transcripts.find((row) => row.channel_id === 0) ??
    result.transcripts[0];

  if (!transcript) {
    throw new PipelineError(
      'asr-convert',
      'No transcripts found in ASR result',
      false,
    );
  }

  const normalized = mergeDottedSentences(transcript.sentences).flatMap(
    (sentence) => splitLongSentence(sentence, 40),
  );

  return normalized
    .map(
      (sentence, index) =>
        `${index + 1}\n${srtTime(sentence.begin_time)} --> ${srtTime(sentence.end_time)}\n${sentence.text}\n`,
    )
    .join('\n');
};

const fetchJson = (step: string, url: string, init?: RequestInit) =>
  ResultAsync.fromPromise(
    (async () => {
      const response = await fetch(url, init);
      const text = await response.text();
      const body = text ? (JSON.parse(text) as Record<string, unknown>) : {};

      if (!response.ok) {
        throw new PipelineError(
          step,
          `HTTP ${response.status}: ${JSON.stringify(body)}`,
          response.status === 429 || response.status >= 500,
        );
      }

      return body;
    })(),
    (error) =>
      error instanceof PipelineError
        ? error
        : toPipelineError(step, error, true),
  );

const normalizeRegion = (region: string) =>
  region.startsWith('oss-') ? region : `oss-${region}`;

const objectPublicUrl = (bucket: string, region: string, key: string) => {
  const shortRegion = region.startsWith('oss-') ? region.slice(4) : region;
  return `https://${bucket}.oss-${shortRegion}.aliyuncs.com/${key}`;
};

const pollTask = (input: {
  apiUrl: string;
  apiKey: string;
  taskId: string;
  attempt: number;
  maxAttempts: number;
}): ResultAsync<string, PipelineError> => {
  if (input.attempt > input.maxAttempts) {
    return errAsync(
      new PipelineError('asr-poll', 'ASR task polling timeout', true),
    );
  }

  return retryBackoff(
    () =>
      fetchJson('asr-poll', `${input.apiUrl}/tasks/${input.taskId}`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${input.apiKey}`,
        },
      }),
    { maxRetries: 3, baseDelayMs: 400 },
  ).andThen((task) => {
    const output = task.output as
      | {
          task_status?: string;
          results?: Array<{
            subtask_status?: string;
            transcription_url?: string;
          }>;
        }
      | undefined;

    if (output?.task_status === 'SUCCEEDED') {
      const first = output.results?.[0];
      if (!first?.transcription_url || first.subtask_status !== 'SUCCEEDED') {
        return errAsync(
          new PipelineError(
            'asr-poll',
            `ASR subtask failed: ${JSON.stringify(first)}`,
            false,
          ),
        );
      }

      return okAsync(first.transcription_url);
    }

    if (
      output?.task_status === 'FAILED' ||
      output?.task_status === 'CANCELED'
    ) {
      return errAsync(
        new PipelineError(
          'asr-poll',
          `ASR task failed: ${JSON.stringify(task)}`,
          false,
        ),
      );
    }

    return ResultAsync.fromPromise(
      new Promise((resolve) => setTimeout(resolve, 2000)),
      () => new PipelineError('asr-poll', 'sleep failed', true),
    ).andThen(() => pollTask({ ...input, attempt: input.attempt + 1 }));
  });
};

export const runFunAsr = (input: {
  projectId: string;
  audioPath: string;
  outputJsonPath: string;
  outputSrtPath: string;
  logger?: TaskLogger;
}): ResultAsync<void, PipelineError> => {
  const ossRegion = normalizeRegion(getRequired('OSS_REGION', env.OSS_REGION));
  const ossBucket = getRequired('OSS_BUCKET', env.OSS_BUCKET);
  const ossAccessKeyId = getRequired(
    'OSS_ACCESS_KEY_ID',
    env.OSS_ACCESS_KEY_ID,
  );
  const ossAccessKeySecret = getRequired(
    'OSS_ACCESS_KEY_SECRET',
    env.OSS_ACCESS_KEY_SECRET,
  );
  const dashscopeApiKey = getRequired(
    'DASHSCOPE_API_KEY',
    env.DASHSCOPE_API_KEY,
  );

  const ossClient = new OSS({
    region: ossRegion,
    bucket: ossBucket,
    accessKeyId: ossAccessKeyId,
    accessKeySecret: ossAccessKeySecret,
  });

  const key = `${input.projectId}/${path.basename(input.audioPath)}`;

  const upload = retryBackoff(
    () =>
      ResultAsync.fromPromise(
        (async () => {
          await input.logger?.debug(`Uploading audio to OSS with key: ${key}`);
          await ossClient.put(key, input.audioPath);
          await ossClient.putACL(key, 'public-read');
        })(),
        (error) => toPipelineError('asr-upload', error, true),
      ),
    { maxRetries: 4, baseDelayMs: 500 },
  );

  const cleanup = () =>
    ResultAsync.fromPromise(
      ossClient.delete(key),
      () =>
        new PipelineError(
          'asr-cleanup',
          'Failed to cleanup OSS temp file',
          false,
        ),
    ).orElse(() => okAsync(undefined));

  return upload
    .andThen(() => {
      const fileUrl = objectPublicUrl(ossBucket, ossRegion, key);
      input.logger?.info(`ASR file uploaded: ${fileUrl}`);

      return retryBackoff(
        () =>
          fetchJson(
            'asr-submit',
            `${env.DASHSCOPE_API_URL}/services/audio/asr/transcription`,
            {
              method: 'POST',
              headers: {
                Authorization: `Bearer ${dashscopeApiKey}`,
                'Content-Type': 'application/json',
                'X-DashScope-Async': 'enable',
              },
              body: JSON.stringify({
                model: env.FUN_ASR_MODEL,
                input: { file_urls: [fileUrl] },
                parameters: {
                  language_hints: ['ja'],
                  diarization_enabled: true,
                },
              }),
            },
          ),
        { maxRetries: 4, baseDelayMs: 500 },
      );
    })
    .andThen((submit) => {
      const taskId = (submit.output as { task_id?: string } | undefined)
        ?.task_id;
      if (!taskId) {
        return errAsync(
          new PipelineError(
            'asr-submit',
            `DashScope task_id missing: ${JSON.stringify(submit)}`,
            false,
          ),
        );
      }
      input.logger?.info(`ASR task submitted: ${taskId}`);

      return pollTask({
        apiUrl: env.DASHSCOPE_API_URL,
        apiKey: dashscopeApiKey,
        taskId,
        attempt: 1,
        maxAttempts: 600,
      });
    })
    .andThen((transcriptionUrl) =>
      retryBackoff(
        () => {
          input.logger?.debug(`Fetching ASR result: ${transcriptionUrl}`);
          return fetchJson('asr-result', transcriptionUrl);
        },
        {
          maxRetries: 4,
          baseDelayMs: 500,
        },
      ),
    )
    .andThen((asrResultRaw) => {
      input.logger?.info('ASR result fetched, converting to SRT');
      const asrResult = asrResultRaw as unknown as FunAsrResult;

      let srt = '';
      try {
        srt = convertToSrt(asrResult);
      } catch (error) {
        return errAsync(toPipelineError('asr-convert', error, false));
      }

      return ResultAsync.fromPromise(
        Promise.all([
          fs.writeFile(
            input.outputJsonPath,
            JSON.stringify(asrResult, null, 2),
            'utf8',
          ),
          fs.writeFile(input.outputSrtPath, srt, 'utf8'),
        ]).then(() => undefined),
        (error) => toPipelineError('asr-write', error, false),
      );
    })
    .andThen((value) => cleanup().map(() => value))
    .andThen((value) => {
      input.logger?.info('ASR artifacts saved');
      return okAsync(value);
    })
    .orElse((error) => cleanup().andThen(() => errAsync(error)));
};
