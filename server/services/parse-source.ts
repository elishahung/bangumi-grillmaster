import { ValidationError } from '@server/core/errors';
import { type Source, SourceSchema } from '@shared/domain';
import { err, ok, type Result } from 'neverthrow';

const BILIBILI_REGEX = /(?:BV[0-9A-Za-z]{10})/i;
const TVER_REGEX = /(?:episodes\/(\w+))/i;
const YOUTUBE_REGEX = /(?:v=|youtu\.be\/)([A-Za-z0-9_-]{11})/i;
const RAW_VIDEO_ID_REGEX = /^[A-Za-z0-9_-]{6,30}$/;

const extractByPattern = (
  input: string,
): { source: Source; sourceVideoId: string } | null => {
  const trimmed = input.trim();

  const bilibiliMatch = trimmed.match(BILIBILI_REGEX);
  if (bilibiliMatch) {
    return {
      source: 'bilibili',
      sourceVideoId: bilibiliMatch[0].toUpperCase(),
    };
  }

  const tverMatch = trimmed.match(TVER_REGEX);
  if (tverMatch?.[1]) {
    return { source: 'tver', sourceVideoId: tverMatch[1] };
  }

  const youtubeMatch = trimmed.match(YOUTUBE_REGEX);
  if (youtubeMatch?.[1]) {
    return { source: 'youtube', sourceVideoId: youtubeMatch[1] };
  }

  if (RAW_VIDEO_ID_REGEX.test(trimmed)) {
    return { source: 'unknown', sourceVideoId: trimmed };
  }

  return null;
};

export const parseSourceInput = (
  input: string,
): Result<{ source: Source; sourceVideoId: string }, ValidationError> => {
  const parsed = extractByPattern(input);

  if (!parsed) {
    return err(
      new ValidationError('無法辨識來源，請提供有效的影片 URL 或 videoId'),
    );
  }

  return ok({
    source: SourceSchema.parse(parsed.source),
    sourceVideoId: parsed.sourceVideoId,
  });
};
