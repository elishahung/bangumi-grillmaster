# Bangumi GrillMaster Platform

網頁全端平台：可提交影片任務、追蹤任務進度、播放影片與字幕並同步觀看進度。

## Tech Stack

- Runtime / Package: `pnpm`
- Frontend: `Next.js 16` (`pages` router), `React 19`
- API: `tRPC v11`
- Database: `Drizzle ORM` + local `SQLite` (`better-sqlite3`)
- Backend error/result flow: `neverthrow`
- Validation: `zod v4` + `React Hook Form`
- UI: `Tailwind CSS v4` + shadcn-style components
- Code quality: `Biome` + `Ultracite`

## Core Architecture

- `Drizzle + SQLite` 儲存專案、任務、任務事件、觀看進度
- `tRPC` 負責 submit project、查詢與更新 watch progress
- Backend service / pipeline 使用 `neverthrow`（Result / ResultAsync）做錯誤流與重試控制
- ASR / 翻譯由 TypeScript provider 實作（`FunASR + Gemini`）
- 以 `source + sourceVideoId` 做重複提交檢查
- 創建新元件請優先考慮使用 `pnpm dlx shadcn@latest add [component]`

## Features

- Submit 頁：貼 `videoId` 或 URL 建立新專案
- Projects 頁：列出已轉換影片，可進入詳情頁
- Project 詳情頁：播放影片、載入字幕、同步 watch progress
- Tasks 頁：polling 顯示任務歷史與目前進度
- Task 詳情頁：查看 task event timeline
- Task 支援手動取消（safe-point），並顯示取消/失敗錯誤細節
- Task pipeline 採 step checkpoint，可從失敗步驟續跑
- Task events 會記錄 step start/end、log level、duration 與 error message
- Mobile-friendly responsive layout

## Local Development

### 1. Install

```bash
pnpm install
```

### 2. Environment

建立 `.env.local`：

```env
PIPELINE_MODE=mock
YT_DLP_BIN=yt-dlp
FFMPEG_BIN=ffmpeg
SQLITE_DB_PATH=data/grillmaster.db

# 若要跑真實 ASR + 翻譯，改成 PIPELINE_MODE=live 並填以下
DASHSCOPE_API_URL=https://dashscope.aliyuncs.com/api/v1
DASHSCOPE_API_KEY=sk-xxx
FUN_ASR_MODEL=fun-asr
OSS_REGION=cn-beijing
OSS_BUCKET=your-bucket
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-pro-preview
```

### 3. Start Next.js

```bash
pnpm dev
```

### 4. Database Migration

```bash
pnpm db:generate
pnpm db:migrate
```

## Scripts

- `pnpm dev` - Next.js dev server
- `pnpm build` - production build
- `pnpm start` - run production server
- `pnpm lint` - ultracite check
- `pnpm format` - ultracite fix
- `pnpm check` - biome + TypeScript check
- `pnpm db:generate` - generate SQL migrations from schema
- `pnpm db:migrate` - apply migrations to local SQLite
- `pnpm db:studio` - open Drizzle Studio

## Data Model Summary

- `projects`: 專案主資料、來源資訊、成本與媒體路徑
- `tasks`: 任務狀態與進度
- `taskEvents`: 任務歷程事件（含 level、step、duration、error）
- `taskStepStates`: 每個步驟的 checkpoint 狀態與輸出（resumable 依據）
- `watchProgress`: 每個 viewer 在各 project 的觀看進度

## Static Media Route

影片與字幕由 `projects/` 目錄直接 host：

- API route: `GET /api/projects/[...path]`
- 支援 `mp4/srt/vtt/json`
- 支援影片 range request

## Project Structure

```txt
pages/
  api/
  projects/
  tasks/
server/
  db/
  core/
  services/
  trpc/
drizzle/
shared/
src/
  components/
  lib/
styles/
projects/
```
