import fs from "node:fs/promises";
import path from "node:path";

export interface TranslationResult {
  llmProvider: string;
  llmModel: string;
  inputTokens: number;
  outputTokens: number;
  totalCostTwd: number;
}

export const runMockAsr = async (audioPath: string, outputSrt: string) => {
  const line = path.basename(audioPath, path.extname(audioPath));
  const content = [
    "1",
    "00:00:00,000 --> 00:00:03,000",
    `${line} transcription placeholder`,
    "",
    "2",
    "00:00:03,000 --> 00:00:08,000",
    "This is a mock ASR output. Configure real providers in .env.local.",
    "",
  ].join("\n");

  await fs.writeFile(outputSrt, content, "utf8");
};

export const runMockTranslation = async (
  asrSrt: string,
  translatedSrt: string,
): Promise<TranslationResult> => {
  const raw = await fs.readFile(asrSrt, "utf8");
  const translated = raw.replace(
    "transcription placeholder",
    "轉錄內容（mock）",
  );
  await fs.writeFile(translatedSrt, translated, "utf8");

  return {
    llmProvider: "mock",
    llmModel: "mock-translator",
    inputTokens: 0,
    outputTokens: 0,
    totalCostTwd: 0,
  };
};
