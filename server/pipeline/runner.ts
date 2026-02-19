import fs from 'node:fs/promises'
import path from 'node:path'
import { PipelineError } from '@server/core/errors'
import { createTaskLogger, type TaskLogger } from '@server/core/logger'
import { retryBackoff, toPipelineError } from '@server/core/retry'
import { repository } from '@server/db/repository'
import { ensureLivePipelineEnv, env } from '@server/env'
import { runCommand } from '@server/pipeline/exec'
import { runFunAsr } from '@server/pipeline/providers/fun-asr'
import { runGeminiTranslate } from '@server/pipeline/providers/gemini'
import {
  runMockAsr,
  runMockTranslation,
  type TranslationResult,
} from '@server/pipeline/providers/mock'
import { srtToVtt } from '@server/pipeline/subtitle'
import type { TaskStepStateRow } from '@shared/view-models'
import { ResultAsync } from 'neverthrow'

type QueueItem = {
  taskId: string
  projectId: string
}

type PipelineStepId =
  | 'fetch_metadata'
  | 'download_video'
  | 'extract_audio'
  | 'run_asr'
  | 'translate_subtitles'
  | 'build_vtt'
  | 'finalize_project'

type StepOutput = Record<string, unknown>

type StepContext = {
  item: QueueItem
  projectDir: string
  sourceUrl: string
  videoPath: string
  audioPath: string
  asrJsonPath: string
  asrSrtPath: string
  translatedSrtPath: string
  translatedVttPath: string
  states: Map<PipelineStepId, TaskStepStateRow>
}

type StepDefinition = {
  id: PipelineStepId
  message: string
  percent: number
  projectStatus: string
}

const steps: StepDefinition[] = [
  {
    id: 'fetch_metadata',
    message: 'Fetching video metadata',
    percent: 10,
    projectStatus: 'downloading',
  },
  {
    id: 'download_video',
    message: 'Downloading source video',
    percent: 25,
    projectStatus: 'downloading',
  },
  {
    id: 'extract_audio',
    message: 'Extracting audio',
    percent: 40,
    projectStatus: 'asr',
  },
  {
    id: 'run_asr',
    message: 'Running ASR',
    percent: 55,
    projectStatus: 'asr',
  },
  {
    id: 'translate_subtitles',
    message: 'Translating subtitles',
    percent: 75,
    projectStatus: 'translating',
  },
  {
    id: 'build_vtt',
    message: 'Building VTT subtitles',
    percent: 88,
    projectStatus: 'translating',
  },
  {
    id: 'finalize_project',
    message: 'Finalizing project output',
    percent: 95,
    projectStatus: 'translating',
  },
]

const asStepMap = (rows: TaskStepStateRow[]) => {
  const map = new Map<PipelineStepId, TaskStepStateRow>()
  for (const row of rows) {
    map.set(row.step as PipelineStepId, row)
  }
  return map
}

const normalizeSourceUrl = (
  source: string,
  sourceVideoId: string,
  originalInput: string,
) => {
  if (
    originalInput.startsWith('http://') ||
    originalInput.startsWith('https://')
  ) {
    return originalInput
  }

  if (source === 'bilibili') {
    return `https://www.bilibili.com/video/${sourceVideoId}`
  }

  if (source === 'youtube') {
    return `https://www.youtube.com/watch?v=${sourceVideoId}`
  }

  return originalInput
}

const REGEX_LINE_BREAK = /\r?\n/
const parseMetadataJson = (stdout: string) => {
  const lines = stdout
    .split(REGEX_LINE_BREAK)
    .map((line) => line.trim())
    .filter(Boolean)

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]
    if (!line) {
      continue
    }
    try {
      return JSON.parse(line) as Record<string, unknown>
    } catch {
      // ignore
    }
  }

  throw new Error('yt-dlp metadata JSON not found in stdout')
}

const parseStepOutput = <T>(
  states: Map<PipelineStepId, TaskStepStateRow>,
  step: PipelineStepId,
): T | null => {
  const value = states.get(step)?.outputJson
  if (!value) {
    return null
  }

  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

class TaskPipelineRunner {
  private readonly queue: QueueItem[] = []
  private readonly queued = new Set<string>()
  private running = false

  enqueue(item: QueueItem) {
    if (this.queued.has(item.taskId)) {
      return
    }

    this.queue.push(item)
    this.queued.add(item.taskId)
    this.consume()
  }

  private async consume() {
    if (this.running) {
      return
    }

    this.running = true

    while (this.queue.length > 0) {
      const item = this.queue.shift()
      if (!item) {
        break
      }

      await this.runOne(item).match(
        () => undefined,
        () => undefined,
      )
      this.queued.delete(item.taskId)
    }

    this.running = false
  }

  private runOne(item: QueueItem): ResultAsync<void, PipelineError> {
    return ResultAsync.fromPromise(this.runOneInternal(item), (error) =>
      error instanceof PipelineError
        ? error
        : toPipelineError('pipeline', error, false),
    )
  }

  private async runOneInternal(item: QueueItem) {
    if (env.PIPELINE_MODE === 'live') {
      try {
        ensureLivePipelineEnv()
      } catch (error) {
        throw toPipelineError('env', error, false)
      }
    }

    const taskRuntime = await repository.getTaskRuntime(item.taskId)
    if (!taskRuntime) {
      throw new PipelineError('task', 'Task not found', false)
    }

    if (taskRuntime.status === 'canceled') {
      return
    }

    const project = await repository.getProjectRuntime(item.projectId)
    if (!project) {
      throw new PipelineError('project', 'Project not found for task', false)
    }

    const projectDir = path.resolve(process.cwd(), 'projects', item.projectId)
    const videoPath = path.join(projectDir, 'video.mp4')
    const audioPath = path.join(projectDir, 'audio.opus')
    const asrJsonPath = path.join(projectDir, 'asr.json')
    const asrSrtPath = path.join(projectDir, 'asr.srt')
    const translatedSrtPath = path.join(projectDir, 'video.srt')
    const translatedVttPath = path.join(projectDir, 'video.vtt')
    const sourceUrl = normalizeSourceUrl(
      project.source,
      project.sourceVideoId,
      project.originalInput,
    )

    await fs.mkdir(projectDir, { recursive: true })

    const states = asStepMap(await repository.getTaskStepStates(item.taskId))
    const context: StepContext = {
      item,
      projectDir,
      sourceUrl,
      videoPath,
      audioPath,
      asrJsonPath,
      asrSrtPath,
      translatedSrtPath,
      translatedVttPath,
      states,
    }

    for (const step of steps) {
      if (await repository.isTaskCancelRequested(item.taskId)) {
        await repository.markTaskCanceled({
          taskId: item.taskId,
          reason: 'Task canceled by user',
          step: step.id,
          percent: step.percent,
        })
        return
      }

      const checkpoint = context.states.get(step.id)
      if (checkpoint?.status === 'completed') {
        const logger = createTaskLogger({
          taskId: item.taskId,
          projectId: item.projectId,
          step: step.id,
          percent: step.percent,
        })
        await logger.debug('Step skipped because checkpoint is completed')
        continue
      }

      await repository.updateProjectFromPipeline({
        projectId: item.projectId,
        status: step.projectStatus,
        sourceUrl,
      })

      await repository.updateTaskProgress({
        taskId: item.taskId,
        status: 'running',
        step: step.id,
        percent: step.percent,
        message: step.message,
        eventType: 'system',
        level: 'info',
      })

      await repository.markStepStart({
        taskId: item.taskId,
        projectId: item.projectId,
        step: step.id,
      })

      await repository.appendTaskEvent({
        taskId: item.taskId,
        projectId: item.projectId,
        step: step.id,
        eventType: 'step_start',
        level: 'info',
        message: `Step started: ${step.id}`,
        percent: step.percent,
      })

      const logger = createTaskLogger({
        taskId: item.taskId,
        projectId: item.projectId,
        step: step.id,
        percent: step.percent,
      })

      try {
        let output: StepOutput | undefined

        if (step.id === 'fetch_metadata') {
          output = await this.fetchMetadata(context, logger)
        } else if (step.id === 'download_video') {
          output = await this.downloadVideo(context, logger)
        } else if (step.id === 'extract_audio') {
          output = await this.extractAudio(context, logger)
        } else if (step.id === 'run_asr') {
          output = await this.runAsr(context, logger)
        } else if (step.id === 'translate_subtitles') {
          output = await this.runTranslation(context, logger)
        } else if (step.id === 'build_vtt') {
          output = await this.buildVtt(context, logger)
        } else if (step.id === 'finalize_project') {
          output = await this.finalizeProject(context, logger)
        }

        const ended = await repository.markStepEnd({
          taskId: item.taskId,
          projectId: item.projectId,
          step: step.id,
          status: 'completed',
          outputJson: output ? JSON.stringify(output) : undefined,
        })

        await repository.appendTaskEvent({
          taskId: item.taskId,
          projectId: item.projectId,
          step: step.id,
          eventType: 'step_end',
          level: 'info',
          message: `Step completed: ${step.id}`,
          percent: step.percent,
          durationMs: ended.durationMs,
        })

        context.states = asStepMap(
          await repository.getTaskStepStates(item.taskId),
        )

        if (await repository.isTaskCancelRequested(item.taskId)) {
          await repository.markTaskCanceled({
            taskId: item.taskId,
            reason: 'Task canceled by user',
            step: step.id,
            percent: step.percent,
          })
          return
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Pipeline step failed'

        const ended = await repository.markStepEnd({
          taskId: item.taskId,
          projectId: item.projectId,
          step: step.id,
          status: 'failed',
          errorMessage: message,
        })

        await repository.updateProjectFromPipeline({
          projectId: item.projectId,
          status: 'failed',
        })

        await repository.updateTaskProgress({
          taskId: item.taskId,
          status: 'failed',
          step: step.id,
          percent: step.percent,
          message: `Pipeline failed at step: ${step.id}`,
          errorMessage: message,
          eventType: 'error',
          level: 'error',
          durationMs: ended.durationMs,
        })

        await logger.error(`Step failed: ${message}`, message)
        throw error instanceof PipelineError
          ? error
          : toPipelineError(step.id, error, false)
      }
    }

    await repository.updateProjectFromPipeline({
      projectId: item.projectId,
      status: 'completed',
    })

    await repository.updateTaskProgress({
      taskId: item.taskId,
      status: 'completed',
      step: 'done',
      percent: 100,
      message: 'Pipeline completed',
      eventType: 'system',
      level: 'info',
    })
  }

  private async fetchMetadata(context: StepContext, logger: TaskLogger) {
    await logger.info('Fetching metadata via yt-dlp --dump-single-json')

    const result = await retryBackoff(
      () =>
        ResultAsync.fromPromise(
          runCommand(
            env.YT_DLP_BIN,
            ['--dump-single-json', '--skip-download', context.sourceUrl],
            context.projectDir,
            {
              onStdoutLine: (line) => {
                logger.trace(`[yt-dlp:stdout] ${line}`)
              },
              onStderrLine: (line) => {
                logger.debug(`[yt-dlp:stderr] ${line}`)
              },
            },
          ),
          (error) => toPipelineError('fetch_metadata', error, true),
        ),
      { maxRetries: 2, baseDelayMs: 500 },
    ).match(
      (value) => value,
      (error) => {
        throw error
      },
    )

    const metadata = parseMetadataJson(result.stdout)
    const title =
      typeof metadata.title === 'string'
        ? metadata.title
        : path.basename(context.videoPath, '.mp4')
    const thumbnailUrl =
      typeof metadata.thumbnail === 'string' ? metadata.thumbnail : undefined

    await fs.writeFile(
      path.join(context.projectDir, 'metadata.info.json'),
      JSON.stringify(metadata, null, 2),
      'utf8',
    )

    await repository.updateProjectFromPipeline({
      projectId: context.item.projectId,
      status: 'downloading',
      sourceUrl: context.sourceUrl,
      title,
      thumbnailUrl,
    })

    await logger.info('Metadata fetched and project updated')

    return {
      title,
      thumbnailUrl,
      sourceUrl: context.sourceUrl,
    }
  }

  private async downloadVideo(context: StepContext, logger: TaskLogger) {
    await logger.info('Downloading video and preparing merged mp4 output')

    const defaultOut = path.join(
      context.projectDir,
      '%(playlist_index|0)s.%(ext)s',
    )
    const infoJsonOut = path.join(context.projectDir, 'metadata')
    const thumbnailOut = path.join(context.projectDir, 'poster')

    await retryBackoff(
      () =>
        ResultAsync.fromPromise(
          runCommand(
            env.YT_DLP_BIN,
            [
              '--write-thumbnail',
              '--write-info-json',
              '-o',
              `${defaultOut}`,
              '-o',
              `infojson:${infoJsonOut}`,
              '-o',
              `thumbnail:${thumbnailOut}`,
              '--merge-output-format',
              'mp4',
              '-f',
              'bestvideo+bestaudio/best',
              '--convert-thumbnails',
              'jpg',
              '--embed-thumbnail',
              '--embed-metadata',
              '--embed-chapters',
              context.sourceUrl,
            ],
            context.projectDir,
            {
              onStdoutLine: (line) => {
                logger.trace(`[yt-dlp:stdout] ${line}`)
              },
              onStderrLine: (line) => {
                logger.debug(`[yt-dlp:stderr] ${line}`)
              },
            },
          ),
          (error) => toPipelineError('download_video', error, true),
        ),
      { maxRetries: 2, baseDelayMs: 1000 },
    ).match(
      () => undefined,
      (error) => {
        throw error
      },
    )

    const entries = await fs.readdir(context.projectDir)
    const videos = entries
      .filter((name) => name.endsWith('.mp4'))
      .sort()
      .map((name) => path.join(context.projectDir, name))

    if (videos.length === 0) {
      throw new PipelineError(
        'download_video',
        'yt-dlp produced no mp4 files',
        false,
      )
    }

    if (videos.length === 1) {
      const first = videos[0]
      if (!first) {
        throw new PipelineError(
          'download_video',
          'Downloaded mp4 missing',
          false,
        )
      }
      if (first !== context.videoPath) {
        await fs.rename(first, context.videoPath)
      }
    } else {
      const concatFile = path.join(context.projectDir, 'concat.txt')
      await fs.writeFile(
        concatFile,
        videos.map((file) => `file '${file.replaceAll("'", "''")}'`).join('\n'),
        'utf8',
      )

      await runCommand(
        env.FFMPEG_BIN,
        [
          '-y',
          '-f',
          'concat',
          '-safe',
          '0',
          '-i',
          concatFile,
          '-c',
          'copy',
          '-movflags',
          'faststart',
          context.videoPath,
        ],
        context.projectDir,
        {
          onStderrLine: (line) => {
            logger.debug(`[ffmpeg:stderr] ${line}`)
          },
        },
      )

      await Promise.all(videos.map((file) => fs.rm(file, { force: true })))
      await fs.rm(concatFile, { force: true })
    }

    const posterName = (await fs.readdir(context.projectDir)).find((name) =>
      name.startsWith('poster.'),
    )

    const localThumb = posterName
      ? `/api/projects/${context.item.projectId}/${posterName}`
      : undefined

    await repository.updateProjectFromPipeline({
      projectId: context.item.projectId,
      status: 'downloading',
      mediaPath: `${context.item.projectId}/video.mp4`,
      thumbnailUrl: localThumb,
    })

    await logger.info('Video download step completed')

    return {
      mediaPath: `${context.item.projectId}/video.mp4`,
      thumbnailUrl: localThumb,
    }
  }

  private async extractAudio(context: StepContext, logger: TaskLogger) {
    await logger.info('Extracting mono 16k opus audio')

    await retryBackoff(
      () =>
        ResultAsync.fromPromise(
          runCommand(
            env.FFMPEG_BIN,
            [
              '-y',
              '-i',
              context.videoPath,
              '-ac',
              '1',
              '-ar',
              '16000',
              '-b:a',
              '24k',
              context.audioPath,
            ],
            context.projectDir,
            {
              onStderrLine: (line) => {
                logger.debug(`[ffmpeg:stderr] ${line}`)
              },
            },
          ),
          (error) => toPipelineError('extract_audio', error, true),
        ),
      { maxRetries: 2, baseDelayMs: 800 },
    ).match(
      () => undefined,
      (error) => {
        throw error
      },
    )

    await logger.info('Audio extracted successfully')

    return {
      audioPath: context.audioPath,
    }
  }

  private async runAsr(context: StepContext, logger: TaskLogger) {
    await logger.info('Starting ASR provider')

    if (env.PIPELINE_MODE === 'live') {
      await runFunAsr({
        projectId: context.item.projectId,
        audioPath: context.audioPath,
        outputJsonPath: context.asrJsonPath,
        outputSrtPath: context.asrSrtPath,
        logger,
      }).match(
        () => undefined,
        (error) => {
          throw error
        },
      )
    } else {
      await runMockAsr(context.audioPath, context.asrSrtPath)
    }

    try {
      const srtContent = await fs.readFile(context.asrSrtPath, 'utf8')
      const vttContent = srtToVtt(srtContent)
      const asrVttPath = path.join(context.projectDir, 'asr.vtt')
      await fs.writeFile(asrVttPath, vttContent, 'utf8')
      await logger.info('Generated asr.vtt')

      await repository.updateProjectFromPipeline({
        projectId: context.item.projectId,
        status: 'asr',
        asrVttPath: `${context.item.projectId}/asr.vtt`,
      })
    } catch (error) {
      await logger.warn(
        `Failed to generate asr.vtt: ${error instanceof Error ? error.message : String(error)}`,
      )
    }

    await logger.info('ASR step completed')

    return {
      asrJsonPath: context.asrJsonPath,
      asrSrtPath: context.asrSrtPath,
    }
  }

  private async runTranslation(context: StepContext, logger: TaskLogger) {
    await logger.info('Starting subtitle translation')

    let translation: TranslationResult

    if (env.PIPELINE_MODE === 'live') {
      translation = await runGeminiTranslate({
        projectId: context.item.projectId,
        asrSrtPath: context.asrSrtPath,
        audioPath: context.audioPath,
        outputSrtPath: context.translatedSrtPath,
        translationHint:
          (await repository.getProjectRuntime(context.item.projectId))
            ?.translationHint ?? '',
        logger,
      }).match(
        (value) => value,
        (error) => {
          throw error
        },
      )
    } else {
      translation = await runMockTranslation(
        context.asrSrtPath,
        context.translatedSrtPath,
      )
    }

    await repository.updateProjectFromPipeline({
      projectId: context.item.projectId,
      status: 'translating',
      llmCostTwd: translation.totalCostTwd,
      llmProvider: translation.llmProvider,
      llmModel: translation.llmModel,
      inputTokens: translation.inputTokens,
      outputTokens: translation.outputTokens,
    })

    await logger.info('Translation step completed')

    return {
      translation,
    }
  }

  private async buildVtt(context: StepContext, logger: TaskLogger) {
    const srt = await fs.readFile(context.translatedSrtPath, 'utf8')
    await fs.writeFile(context.translatedVttPath, srtToVtt(srt), 'utf8')
    await logger.info('VTT subtitle built')

    return {
      subtitlePath: `${context.item.projectId}/video.vtt`,
    }
  }

  private async finalizeProject(context: StepContext, logger: TaskLogger) {
    const metadataOutput = parseStepOutput<{
      title?: string
      thumbnailUrl?: string
      sourceUrl?: string
    }>(context.states, 'fetch_metadata')
    const downloadOutput = parseStepOutput<{
      thumbnailUrl?: string
      mediaPath?: string
    }>(context.states, 'download_video')
    const translationOutput = parseStepOutput<{
      translation?: TranslationResult
    }>(context.states, 'translate_subtitles')

    const translation = translationOutput?.translation

    await repository.updateProjectFromPipeline({
      projectId: context.item.projectId,
      status: 'completed',
      title: metadataOutput?.title,
      sourceUrl: metadataOutput?.sourceUrl ?? context.sourceUrl,
      thumbnailUrl:
        downloadOutput?.thumbnailUrl ?? metadataOutput?.thumbnailUrl,
      mediaPath:
        downloadOutput?.mediaPath ?? `${context.item.projectId}/video.mp4`,
      subtitlePath: `${context.item.projectId}/video.vtt`,
      llmCostTwd: translation?.totalCostTwd,
      llmProvider: translation?.llmProvider,
      llmModel: translation?.llmModel,
      inputTokens: translation?.inputTokens,
      outputTokens: translation?.outputTokens,
    })

    await logger.info('Project finalized')

    return {
      mediaPath: `${context.item.projectId}/video.mp4`,
      subtitlePath: `${context.item.projectId}/video.vtt`,
    }
  }

  constructor() {
    this.cleanupInterruptedTasks().catch((error) => {
      console.error('Failed to cleanup interrupted tasks', error)
    })
  }

  private async cleanupInterruptedTasks() {
    const tasks = await repository.getInterruptedTasks()
    if (tasks.length === 0) {
      return
    }

    console.log(`Found ${tasks.length} interrupted tasks, cleaning up...`)

    for (const task of tasks) {
      try {
        if (task.status === 'running') {
          await repository.updateTaskProgress({
            taskId: task.taskId,
            status: 'failed',
            step: task.currentStep,
            percent: task.progressPercent,
            message: 'Task execution interrupted by server restart',
            errorMessage: 'Server restart detected while task was running',
            eventType: 'error',
            level: 'error',
          })

          await repository.updateProjectFromPipeline({
            projectId: task.projectId,
            status: 'failed',
          })

          await repository.appendTaskEvent({
            taskId: task.taskId,
            projectId: task.projectId,
            step: task.currentStep,
            eventType: 'error',
            level: 'error',
            message: 'Task execution interrupted by server restart',
            errorMessage: 'Server restart detected while task was running',
            percent: task.progressPercent,
          })
        } else if (task.status === 'canceling') {
          await repository.markTaskCanceled({
            taskId: task.taskId,
            reason: 'Task canceled by user (processed after restart)',
            step: task.currentStep,
            percent: task.progressPercent,
          })
        }
      } catch (error) {
        console.error(`Failed to cleanup task ${task.taskId}`, error)
      }
    }
  }
}

let singleton: TaskPipelineRunner | null = null

export const getTaskPipelineRunner = () => {
  if (!singleton) {
    singleton = new TaskPipelineRunner()
  }

  return singleton
}
