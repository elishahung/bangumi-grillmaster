import { z } from 'zod';

const EnvSchema = z.object({
  PIPELINE_MODE: z.enum(['mock', 'live']).default('mock'),
  YT_DLP_BIN: z.string().default('yt-dlp'),
  FFMPEG_BIN: z.string().default('ffmpeg'),
  DASHSCOPE_API_URL: z
    .string()
    .default('https://dashscope.aliyuncs.com/api/v1'),
  DASHSCOPE_API_KEY: z.string().optional(),
  FUN_ASR_MODEL: z.string().default('fun-asr'),
  OSS_REGION: z.string().optional(),
  OSS_BUCKET: z.string().optional(),
  OSS_ACCESS_KEY_ID: z.string().optional(),
  OSS_ACCESS_KEY_SECRET: z.string().optional(),
  GEMINI_API_KEY: z.string().optional(),
  GEMINI_MODEL: z.string().default('gemini-3.1-pro-preview'),
  SQLITE_DB_PATH: z.string().default('data/grillmaster.db'),
});

export const env = EnvSchema.parse({
  PIPELINE_MODE: process.env.PIPELINE_MODE,
  YT_DLP_BIN: process.env.YT_DLP_BIN,
  FFMPEG_BIN: process.env.FFMPEG_BIN,
  DASHSCOPE_API_URL: process.env.DASHSCOPE_API_URL,
  DASHSCOPE_API_KEY: process.env.DASHSCOPE_API_KEY,
  FUN_ASR_MODEL: process.env.FUN_ASR_MODEL,
  OSS_REGION: process.env.OSS_REGION,
  OSS_BUCKET: process.env.OSS_BUCKET,
  OSS_ACCESS_KEY_ID: process.env.OSS_ACCESS_KEY_ID,
  OSS_ACCESS_KEY_SECRET: process.env.OSS_ACCESS_KEY_SECRET,
  GEMINI_API_KEY: process.env.GEMINI_API_KEY,
  GEMINI_MODEL: process.env.GEMINI_MODEL,
  SQLITE_DB_PATH: process.env.SQLITE_DB_PATH,
});

export const ensureLivePipelineEnv = () => {
  if (env.PIPELINE_MODE !== 'live') {
    return;
  }

  const required: [string, string | undefined][] = [
    ['DASHSCOPE_API_KEY', env.DASHSCOPE_API_KEY],
    ['OSS_REGION', env.OSS_REGION],
    ['OSS_BUCKET', env.OSS_BUCKET],
    ['OSS_ACCESS_KEY_ID', env.OSS_ACCESS_KEY_ID],
    ['OSS_ACCESS_KEY_SECRET', env.OSS_ACCESS_KEY_SECRET],
    ['GEMINI_API_KEY', env.GEMINI_API_KEY],
  ];

  const missing = required.filter(([, value]) => !value).map(([key]) => key);

  if (missing.length > 0) {
    throw new Error(`Missing live pipeline env: ${missing.join(', ')}`);
  }
};
