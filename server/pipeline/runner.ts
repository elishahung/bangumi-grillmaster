import fs from "node:fs/promises";
import path from "node:path";
import { PipelineError } from "@server/core/errors";
import { retryBackoff, toPipelineError } from "@server/core/retry";
import { repository } from "@server/db/repository";
import { ensureLivePipelineEnv, env } from "@server/env";
import { runCommand } from "@server/pipeline/exec";
import { runFunAsr } from "@server/pipeline/providers/funAsr";
import { runGeminiTranslate } from "@server/pipeline/providers/gemini";
import {
  runMockAsr,
  runMockTranslation,
  type TranslationResult,
} from "@server/pipeline/providers/mock";
import { srtToVtt } from "@server/pipeline/subtitle";
import { errAsync, ResultAsync } from "neverthrow";

interface QueueItem {
  taskId: string;
  projectId: string;
}

interface DownloadMeta {
  title: string;
  thumbnailUrl?: string;
}

class TaskPipelineRunner {
  private readonly queue: QueueItem[] = [];
  private readonly queued = new Set<string>();
  private running = false;

  enqueue(item: QueueItem) {
    if (this.queued.has(item.taskId)) {
      return;
    }

    this.queue.push(item);
    this.queued.add(item.taskId);
    void this.consume();
  }

  private async consume() {
    if (this.running) {
      return;
    }

    this.running = true;

    while (this.queue.length > 0) {
      const item = this.queue.shift();
      if (!item) {
        break;
      }

      await this.runOne(item).match(
        () => undefined,
        () => undefined,
      );
      this.queued.delete(item.taskId);
    }

    this.running = false;
  }

  private updateProgress(
    item: QueueItem,
    input: {
      status: string;
      projectStatus: string;
      step: string;
      percent: number;
      message: string;
      errorMessage?: string;
    },
  ) {
    return retryBackoff(
      () =>
        ResultAsync.fromPromise(
          Promise.all([
            repository.updateProjectFromPipeline({
              projectId: item.projectId,
              status: input.projectStatus,
            }),
            repository.updateTaskProgress({
              taskId: item.taskId,
              status: input.status,
              step: input.step,
              percent: input.percent,
              message: input.message,
              errorMessage: input.errorMessage,
            }),
          ]).then(() => undefined),
          (error) => toPipelineError("task-progress", error, true),
        ),
      { maxRetries: 3, baseDelayMs: 300 },
    );
  }

  private runOne(item: QueueItem): ResultAsync<void, PipelineError> {
    if (env.PIPELINE_MODE === "live") {
      try {
        ensureLivePipelineEnv();
      } catch (error) {
        return errAsync(toPipelineError("env", error, false));
      }
    }

    return retryBackoff(
      () =>
        ResultAsync.fromPromise(
          repository.getProjectRuntime(item.projectId),
          (error) => toPipelineError("project-read", error, true),
        ),
      { maxRetries: 3, baseDelayMs: 400 },
    ).andThen((project) => {
      if (!project) {
        return errAsync(
          new PipelineError("project", "Project not found for task", false),
        );
      }

      const projectDir = path.resolve(
        process.cwd(),
        "projects",
        item.projectId,
      );
      const videoPath = path.join(projectDir, "video.mp4");
      const audioPath = path.join(projectDir, "audio.opus");
      const asrJsonPath = path.join(projectDir, "asr.json");
      const asrSrtPath = path.join(projectDir, "asr.srt");
      const translatedSrtPath = path.join(projectDir, "video.srt");
      const translatedVttPath = path.join(projectDir, "video.vtt");
      const sourceUrl = this.normalizeSourceUrl(
        project.source,
        project.sourceVideoId,
        project.originalInput,
      );

      return this.updateProgress(item, {
        status: "running",
        projectStatus: "downloading",
        step: "download",
        percent: 10,
        message: "Downloading source video",
      })
        .andThen(() =>
          ResultAsync.fromPromise(
            fs.mkdir(projectDir, { recursive: true }),
            (error) => toPipelineError("mkdir", error, false),
          ),
        )
        .andThen(() =>
          this.downloadAndPrepareVideo(
            sourceUrl,
            projectDir,
            item.projectId,
            videoPath,
          ),
        )
        .andThen((downloadMeta) =>
          this.updateProgress(item, {
            status: "running",
            projectStatus: "asr",
            step: "audio",
            percent: 35,
            message: "Extracting audio",
          }).andThen(() =>
            retryBackoff(
              () =>
                ResultAsync.fromPromise(
                  runCommand(env.FFMPEG_BIN, [
                    "-y",
                    "-i",
                    videoPath,
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-b:a",
                    "24k",
                    audioPath,
                  ]),
                  (error) => toPipelineError("audio", error, true),
                ),
              { maxRetries: 2, baseDelayMs: 800 },
            ).map(() => downloadMeta),
          ),
        )
        .andThen((downloadMeta) =>
          this.updateProgress(item, {
            status: "running",
            projectStatus: "asr",
            step: "asr",
            percent: 55,
            message: "Running ASR",
          }).andThen(() =>
            this.runAsr(item.projectId, audioPath, asrSrtPath, asrJsonPath).map(
              () => downloadMeta,
            ),
          ),
        )
        .andThen((downloadMeta) =>
          this.updateProgress(item, {
            status: "running",
            projectStatus: "translating",
            step: "translate",
            percent: 75,
            message: "Translating subtitles",
          }).andThen(() =>
            this.runTranslation(
              item.projectId,
              asrSrtPath,
              audioPath,
              translatedSrtPath,
              project.translationHint ?? "",
            ).map((translation) => ({ downloadMeta, translation })),
          ),
        )
        .andThen(({ downloadMeta, translation }) =>
          ResultAsync.fromPromise(
            fs
              .readFile(translatedSrtPath, "utf8")
              .then((srt) =>
                fs.writeFile(translatedVttPath, srtToVtt(srt), "utf8"),
              ),
            (error) => toPipelineError("vtt", error, false),
          ).map(() => ({ downloadMeta, translation })),
        )
        .andThen(({ downloadMeta, translation }) =>
          retryBackoff(
            () =>
              ResultAsync.fromPromise(
                repository.updateProjectFromPipeline({
                  projectId: item.projectId,
                  status: "completed",
                  title: downloadMeta.title,
                  thumbnailUrl: downloadMeta.thumbnailUrl,
                  sourceUrl,
                  mediaPath: `${item.projectId}/video.mp4`,
                  subtitlePath: `${item.projectId}/video.vtt`,
                  llmCostTwd: translation.totalCostTwd,
                  llmProvider: translation.llmProvider,
                  llmModel: translation.llmModel,
                  inputTokens: translation.inputTokens,
                  outputTokens: translation.outputTokens,
                }),
                (error) => toPipelineError("project-finalize", error, true),
              ),
            { maxRetries: 3, baseDelayMs: 400 },
          ),
        )
        .andThen(() =>
          this.updateProgress(item, {
            status: "completed",
            projectStatus: "completed",
            step: "done",
            percent: 100,
            message: "Pipeline completed",
          }),
        )
        .map(() => undefined)
        .orElse((error) =>
          this.updateProgress(item, {
            status: "failed",
            projectStatus: "failed",
            step: "failed",
            percent: 100,
            message: "Pipeline failed",
            errorMessage: error.message,
          }).andThen(() => errAsync(error)),
        );
    });
  }

  private normalizeSourceUrl(
    source: string,
    sourceVideoId: string,
    originalInput: string,
  ) {
    if (
      originalInput.startsWith("http://") ||
      originalInput.startsWith("https://")
    ) {
      return originalInput;
    }

    if (source === "bilibili") {
      return `https://www.bilibili.com/video/${sourceVideoId}`;
    }

    if (source === "youtube") {
      return `https://www.youtube.com/watch?v=${sourceVideoId}`;
    }

    return originalInput;
  }

  private downloadAndPrepareVideo(
    sourceUrl: string,
    projectDir: string,
    projectId: string,
    outputVideo: string,
  ): ResultAsync<DownloadMeta, PipelineError> {
    return retryBackoff(
      () =>
        ResultAsync.fromPromise(
          runCommand(env.YT_DLP_BIN, [
            "--write-thumbnail",
            "--write-info-json",
            "--convert-thumbnails",
            "jpg",
            "--merge-output-format",
            "mp4",
            "-f",
            "bestvideo+bestaudio/best",
            "-o",
            path.join(projectDir, "%(playlist_index|0)s.%(ext)s"),
            sourceUrl,
          ]),
          (error) => toPipelineError("download", error, true),
        ),
      { maxRetries: 2, baseDelayMs: 1000 },
    ).andThen(() =>
      ResultAsync.fromPromise(
        (async () => {
          const entries = await fs.readdir(projectDir);
          const videos = entries
            .filter((name) => name.endsWith(".mp4"))
            .sort()
            .map((name) => path.join(projectDir, name));

          if (videos.length === 0) {
            throw new Error("yt-dlp produced no mp4 files");
          }

          if (videos.length === 1) {
            const first = videos[0];
            if (!first) {
              throw new Error("Missing downloaded video file");
            }
            if (first !== outputVideo) {
              await fs.rename(first, outputVideo);
            }
          } else {
            const concatFile = path.join(projectDir, "concat.txt");
            await fs.writeFile(
              concatFile,
              videos
                .map((file) => `file '${file.replaceAll("'", "''")}'`)
                .join("\n"),
              "utf8",
            );

            await runCommand(env.FFMPEG_BIN, [
              "-y",
              "-f",
              "concat",
              "-safe",
              "0",
              "-i",
              concatFile,
              "-c",
              "copy",
              "-movflags",
              "faststart",
              outputVideo,
            ]);

            await Promise.all(
              videos.map((file) => fs.rm(file, { force: true })),
            );
            await fs.rm(concatFile, { force: true });
          }

          let title = path.basename(outputVideo, ".mp4");
          try {
            const metadataRaw = await fs.readFile(
              path.join(projectDir, "metadata.info.json"),
              "utf8",
            );
            const metadata = JSON.parse(metadataRaw) as { title?: string };
            title = metadata.title ?? title;
          } catch {
            title = path.basename(outputVideo, ".mp4");
          }

          const posterName = (await fs.readdir(projectDir)).find((name) =>
            name.startsWith("poster."),
          );

          return {
            title,
            thumbnailUrl: posterName
              ? `/api/projects/${projectId}/${posterName}`
              : undefined,
          };
        })(),
        (error) => toPipelineError("download-post", error, false),
      ),
    );
  }

  private runAsr(
    projectId: string,
    audioPath: string,
    outputSrt: string,
    outputJson: string,
  ): ResultAsync<void, PipelineError> {
    if (env.PIPELINE_MODE === "live") {
      return runFunAsr({
        projectId,
        audioPath,
        outputJsonPath: outputJson,
        outputSrtPath: outputSrt,
      });
    }

    return ResultAsync.fromPromise(runMockAsr(audioPath, outputSrt), (error) =>
      toPipelineError("asr", error, false),
    );
  }

  private runTranslation(
    projectId: string,
    inputSrt: string,
    audioPath: string,
    outputSrt: string,
    hint: string,
  ): ResultAsync<TranslationResult, PipelineError> {
    if (env.PIPELINE_MODE === "live") {
      return runGeminiTranslate({
        projectId,
        asrSrtPath: inputSrt,
        audioPath,
        outputSrtPath: outputSrt,
        translationHint: hint,
      });
    }

    return ResultAsync.fromPromise(
      runMockTranslation(inputSrt, outputSrt),
      (error) => toPipelineError("translate", error, false),
    );
  }
}

let singleton: TaskPipelineRunner | null = null;

export const getTaskPipelineRunner = () => {
  if (!singleton) {
    singleton = new TaskPipelineRunner();
  }

  return singleton;
};
