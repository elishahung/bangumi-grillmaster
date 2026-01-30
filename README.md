# Bangumi GrillMaster

下載 bilibili 的日本綜藝節目，生成繁體中文 SRT 字幕。

## 說明

- 僅限個人測試使用，設定偏好都是個人主觀，如需修改請自行 fork
- 目標是 one shot 即可直接觀看，不想校準 (避免被暴雷)

### ASR

各種 API 和自架測試下來，目前[豆包語音](https://www.volcengine.com/docs/6561/80909)效果最好，但這模型沒開海外，走 API 需要認證無法。所以改採 FunASR (`fun-asr-2025-11-07`)，會有英文奇怪切割的狀況

### 翻譯

將字幕跟音檔一起餵給 Gemini 3 Pro Preview 翻譯效果最好，不做切割。實測 M1 2025 第一段 1.5 小時沒問題。Gemini 3 Flash Preview 後半段會出現幻覺 (分多次對話可能可以改善？)

覺得 API 太貴這步也可以到 Gemini 平台 或 AI Studio 手動操作

其實也可以餵影片給 Gemini 3 Pro Preview 直接生成 SRT，好處是連畫面上的東西也能感知，但是時間最小單位只到秒，對於漫才之類注重精準時間點的類型觀感不好

## 流程

```
Bilibili ID
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
翻譯字幕 (Gemini)
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
grill <BILIBILI_ID> [DESCRIPTION]
```

### 方式二：直接執行

```bash
python main.py <BILIBILI_ID> [DESCRIPTION]
```

### 範例

```bash
# 使用影片標題作為描述
grill BV18KBJBeEmV

# 自訂描述(提供給翻譯用)
grill BV1CakEBaEJp "華大千鳥 - 全力100萬 - 間諜 1/7"
```

## 環境變數

建立 `.env` 檔案：

```env
# Alibaba DashScope (FunASR)
DASHSCOPE_API_KEY=sk-xxx
FUN_ASR_MODEL=fun-asr-2025-11-07

# Alibaba OSS (暫存音檔)
OSS_REGION=cn-beijing
OSS_BUCKET=your-bucket-name
OSS_ACCESS_KEY_ID=xxx
OSS_ACCESS_KEY_SECRET=xxx

# Google Gemini (翻譯)
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-pro-preview

# 可選
COOKIES_TXT_PATH=./cookies.txt   # Bilibili 會員 cookies
ARCHIVED_PATH=NAS:\bangumi\ai\  # 歸檔路徑 - 處理完直接移至指定資料夾並將資料夾名稱改為影片名稱
```

## 專案結構

```
projects/{bilibili_id}/
├── project.json   # 專案狀態
├── video.mp4      # 合併後的影片
├── audio.opus     # 提取的音檔
├── asr.json       # FunASR 原始結果
├── asr.srt        # 原文字幕
└── video.srt      # 翻譯後的字幕
```
