# Bangumi GrillMaster

下載日本綜藝節目，生成繁體中文 SRT 字幕。

## 說明

- 設定偏好都是個人主觀，如需修改請自行 fork
- 目標是 one shot 即可直接觀看，不想校準 (避免被暴雷)
- 一小時左右的影片成本大概 30 台幣 (基本就是 gemini 的成本，ASR 很少)

## 工具

經過各種嘗試，API、自架等組合後，覺得以下方式最合適

### ASR

[豆包語音](https://www.volcengine.com/docs/6561/80909)效果最好，但還沒開放海外，走 API 需要認證無法。所以改採 FunASR (`fun-asr-2025-11-07`)，會有英文標點奇怪切割的狀況

### 翻譯

使用 Gemini 進行**兩階段併發翻譯**：

1. **Pre-pass**：完整 SRT + 節目資訊 + 音檔，要求輸出結構化 JSON 簡報（人物對照、專有名詞/ASR 修正 dict、梗的固定譯法、整體語氣、每段局部摘要）
2. **併發翻譯**：SRT 按字元數平均切塊（block 邊界對齊），每塊配上 pre-pass 簡報 + 自己的局部摘要 + 音檔，平行送出翻譯
3. **組裝**：每塊輸出驗證 index/timecode 連續性，再拼接寫檔

**新增**：`services/gemini/storage.py`（音檔上傳至 Gemini File API；有同名遠端檔則略過上傳）。pre-pass 與每段 chunk 皆帶音檔與文字。

**更動**：翻譯只保留 `GEMINI_MODEL` 一項（併用於 pre-pass 與 chunk；舊的 pre-pass／chunk 分開模型已移除）。預設 `GEMINI_CONCURRENCY` 改為 10。

`pre_pass.json` 可沿用；只重跑 chunk 時不會重跑 pre-pass。

## 流程

```
Video ID
    ↓
下載影片 (yt-dlp)
    ↓
合併影片 (FFmpeg)
    ↓
提取音檔 (FFmpeg, mono 16kHz opus)
    ↓
語音辨識 (FunASR)
    ↓
生成 SRT 字幕
    ↓
翻譯字幕 (Gemini: pre-pass → 併發 chunk 翻譯 → 組裝驗證)
    ↓
歸檔 (可選)
```

## 安裝

### 前置需求

- Python 3.13+
- FFmpeg (自行安裝並加入 PATH)
- uv (推薦) 或 pip

### 安裝步驟

```bash
# 使用 uv
uv sync

# 或使用 pip
pip install -e .
```

## 使用方式

### 方式一：加入 PATH

將 `scripts/` 資料夾加到系統 PATH，然後執行：

```bash
grill <SOURCE> [TRANSLATION_HINT]
```

### 方式二：直接執行

```bash
python main.py <SOURCE> [TRANSLATION_HINT]
```

- `SOURCE`: 影片 ID 或完整 URL
- `TRANSLATION_HINT`: 可選，提供給翻譯用的提示，通常是 bilibili 只有隱晦標題的需要

### 範例

```bash
# 使用影片標題作為翻譯提示
grill BV18KBJBeEmV

# 自訂翻譯提示
grill BV1CakEBaEJp "華大千鳥 - 全力100萬 - 間諜 1/7"

# 使用完整 URL
grill "https://www.bilibili.com/video/BV18KBJBeEmV"
```

## 環境變數

建立 `.env` 檔案：

```env
# Alibaba DashScope (FunASR)
DASHSCOPE_API_KEY=sk-xxx
FUN_ASR_MODEL=fun-asr

# Alibaba OSS (暫存音檔)
OSS_REGION=cn-beijing
OSS_BUCKET=your-bucket-name
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx

# Google Gemini (翻譯)
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-flash-preview

# 可選：Gemini 翻譯調校
GEMINI_CHUNK_CHAR_LIMIT=12000          # 每塊目標字元數 (約 10 分鐘字幕)
GEMINI_CONCURRENCY=10                  # chunk 併發上限
GEMINI_THINKING_LEVEL=HIGH             # 翻譯 thinking level: LOW/MEDIUM/HIGH
GEMINI_CHUNK_MAX_RETRIES=3             # 單塊失敗重試次數 (pre-pass 也共用)

# 可選
COOKIES_TXT_PATH=cookies.txt   # 影片來源網站 cookies (供 yt-dlp 使用)
ARCHIVED_PATH=NAS:\bangumi\ai\  # 歸檔路徑 - 處理完直接移至指定資料夾並將資料夾名稱改為影片名稱
```

## 專案結構

```
projects/{video_id}/
├── project.json      # 專案狀態
├── video.mp4         # 合併後的影片
├── audio.opus        # 提取的音檔
├── asr.json          # FunASR 原始結果
├── video.ja.srt      # 日文原文字幕
├── pre_pass.json     # Gemini pre-pass 簡報 (快取，供重跑翻譯用)
└── video.cht.srt     # 繁體中文翻譯字幕
```
