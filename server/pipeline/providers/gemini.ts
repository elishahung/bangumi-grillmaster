import crypto from "node:crypto";
import fs from "node:fs/promises";
import { createPartFromUri, FinishReason, GoogleGenAI } from "@google/genai";
import { PipelineError } from "@server/core/errors";
import { retryBackoff, toPipelineError } from "@server/core/retry";
import { env } from "@server/env";
import type { TranslationResult } from "@server/pipeline/providers/mock";
import { errAsync, okAsync, ResultAsync } from "neverthrow";

const SYSTEM_INSTRUCTION = `You are an expert subtitle translator and localizer specializing in Japanese variety shows.
Translate input SRT into Traditional Chinese (Taiwan), keep timecodes unchanged, and output strict SRT only.`;

const modelPricingUsdPer1M: Record<
  string,
  { input: number; cacheHit: number; output: number }
> = {
  "gemini-3-flash-preview": { input: 0.5, cacheHit: 0.1, output: 3 },
  "gemini-3-pro-preview": { input: 2, cacheHit: 0.2, output: 12 },
};

const calculateCostTwd = (
  model: string,
  usage:
    | {
        promptTokenCount?: number;
        cachedContentTokenCount?: number;
        candidatesTokenCount?: number;
        thoughtsTokenCount?: number;
      }
    | undefined,
) => {
  if (!usage) {
    return { costTwd: 0, inputTokens: 0, outputTokens: 0 };
  }

  const pricing = modelPricingUsdPer1M[model];
  if (!pricing) {
    return {
      costTwd: 0,
      inputTokens: usage.promptTokenCount ?? 0,
      outputTokens:
        (usage.candidatesTokenCount ?? 0) + (usage.thoughtsTokenCount ?? 0),
    };
  }

  const totalPrompt = usage.promptTokenCount ?? 0;
  const cached = usage.cachedContentTokenCount ?? 0;
  const output = usage.candidatesTokenCount ?? 0;
  const thoughts = usage.thoughtsTokenCount ?? 0;
  const input = totalPrompt - cached;

  const usd =
    (input / 1_000_000) * pricing.input +
    (cached / 1_000_000) * pricing.cacheHit +
    ((output + thoughts) / 1_000_000) * pricing.output;

  return {
    costTwd: usd * 32,
    inputTokens: input,
    outputTokens: output + thoughts,
  };
};

const toUserMessage = (translationHint: string, srt: string) => {
  const hintBlock = translationHint.trim()
    ? `\n\n【節目標題/資訊】(請用此修正 ASR 錯誤):\n${translationHint.trim()}`
    : "";

  return `請根據所附資料，將以下 SRT 文本翻譯為繁體中文。${hintBlock}\n\n【SRT 文本】(由 ASR 自動產生，可能有辨識錯誤):\n---\n${srt}`;
};

const continueTranslation = (
  chat: ReturnType<GoogleGenAI["chats"]["create"]>,
  continuation: number,
  sections: string[],
  total: { inputTokens: number; outputTokens: number; costTwd: number },
  response: Awaited<ReturnType<typeof chat.sendMessage>>,
): ResultAsync<TranslationResult, PipelineError> => {
  sections.push(response.text ?? "");
  const usage = calculateCostTwd(env.GEMINI_MODEL, response.usageMetadata);
  total.inputTokens += usage.inputTokens;
  total.outputTokens += usage.outputTokens;
  total.costTwd += usage.costTwd;

  const finishReason = response.candidates?.[0]?.finishReason;
  if (finishReason === FinishReason.STOP || finishReason === undefined) {
    return okAsync({
      llmProvider: "google",
      llmModel: env.GEMINI_MODEL,
      inputTokens: total.inputTokens,
      outputTokens: total.outputTokens,
      totalCostTwd: total.costTwd,
    });
  }

  if (finishReason !== FinishReason.MAX_TOKENS || continuation >= 10) {
    return errAsync(
      new PipelineError(
        "translate",
        `Gemini finish reason: ${String(finishReason)}`,
        false,
      ),
    );
  }

  return retryBackoff(
    () =>
      ResultAsync.fromPromise(chat.sendMessage({ message: "繼續" }), (error) =>
        toPipelineError("translate", error, true),
      ),
    { maxRetries: 4, baseDelayMs: 800 },
  ).andThen((next) =>
    continueTranslation(chat, continuation + 1, sections, total, next),
  );
};

export const runGeminiTranslate = (input: {
  projectId: string;
  asrSrtPath: string;
  audioPath: string;
  outputSrtPath: string;
  translationHint: string;
}): ResultAsync<TranslationResult, PipelineError> => {
  if (!env.GEMINI_API_KEY) {
    return errAsync(
      new PipelineError("env", "GEMINI_API_KEY is required", false),
    );
  }

  const ai = new GoogleGenAI({ apiKey: env.GEMINI_API_KEY });
  const total = { inputTokens: 0, outputTokens: 0, costTwd: 0 };
  const sections: string[] = [];

  return ResultAsync.fromPromise(
    fs.readFile(input.asrSrtPath, "utf8"),
    (error) => toPipelineError("translate", error, false),
  ).andThen((srt) => {
    const userMessage = toUserMessage(input.translationHint, srt);

    const cachedName = crypto
      .createHash("md5")
      .update(`${input.projectId}:${env.GEMINI_MODEL}:${env.GEMINI_API_KEY}`)
      .digest("hex");

    return retryBackoff(
      () =>
        ResultAsync.fromPromise(
          ai.files.upload({
            file: input.audioPath,
            config: {
              name: cachedName,
              mimeType: "audio/ogg",
            },
          }),
          (error) => toPipelineError("translate", error, true),
        ),
      { maxRetries: 4, baseDelayMs: 1000 },
    ).andThen((uploaded) => {
      if (!uploaded.uri) {
        return errAsync(
          new PipelineError(
            "translate",
            "Gemini uploaded file uri missing",
            false,
          ),
        );
      }
      const uploadedUri = uploaded.uri;

      const chat = ai.chats.create({
        model: env.GEMINI_MODEL,
        config: {
          systemInstruction: SYSTEM_INSTRUCTION,
        },
      });

      return retryBackoff(
        () =>
          ResultAsync.fromPromise(
            chat.sendMessage({
              message: [
                createPartFromUri(
                  uploadedUri,
                  uploaded.mimeType ?? "audio/ogg",
                ),
                userMessage,
              ],
            }),
            (error) => toPipelineError("translate", error, true),
          ),
        { maxRetries: 4, baseDelayMs: 800 },
      )
        .andThen(() =>
          retryBackoff(
            () =>
              ResultAsync.fromPromise(
                chat.sendMessage({ message: userMessage }),
                (error) => toPipelineError("translate", error, true),
              ),
            { maxRetries: 4, baseDelayMs: 800 },
          ),
        )
        .andThen((firstResponse) =>
          continueTranslation(chat, 0, sections, total, firstResponse),
        )
        .andThen((result) =>
          ResultAsync.fromPromise(
            fs.writeFile(
              input.outputSrtPath,
              sections.join("\n<BREAK>\n"),
              "utf8",
            ),
            (error) => toPipelineError("translate", error, false),
          ).map(() => result),
        );
    });
  });
};
