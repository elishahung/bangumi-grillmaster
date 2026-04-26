# Bangumi GrillMaster

下載日本綜藝節目，生成繁體中文 SRT 字幕方便個人使用識讀

![](/doc/image2.jpg)
![](/doc/image3.png)
![](/doc/image1.png)

## 說明

- 設定偏好都是個人主觀，如需修改請自行 fork
- 目標是 one shot 即可直接觀看，不想校準 (避免被暴雷)
- 一小時左右的影片成本大概 $20 台幣 (ASR $6 + 翻譯 $14)

## 工具

經過各種嘗試，API、自架等組合後，覺得以下方式最合適

### ASR

[ElevenLabs Scribe v2](https://elevenlabs.io/docs/eleven-api/guides/cookbooks/speech-to-text) 日文辨識效果穩定，尤其在一堆人大聲喧嘩，或者裝傻吐槽之間無間隔狀況都能分析出來。

### 翻譯

測試多種模型還是 Gemini 的潤飾最能抓住日本綜藝的韻味，加上圖片音檔的理解真的很好，但 Gemini 的輸出常常會漏 Index 或弄錯時間軸，所以如果驗證錯誤，會透過 `DeepSeek V4 Flash` 做修正

使用 Gemini 進行**兩階段併發翻譯**：

1. **Pre-pass**：完整 SRT + 節目資訊 + 完整音檔 + 少量全片代表圖片，要求輸出結構化 JSON 簡報（人物對照、專有名詞/ASR 修正 dict、梗的固定譯法、整體語氣、每段局部摘要）
2. **併發翻譯**：SRT 按字元數平均切塊（block 邊界對齊），每塊配上 pre-pass 簡報 + 自己的局部摘要 + 該 chunk 的音檔切片 + 該範圍的代表圖片，平行送出翻譯
3. **組裝**：每塊輸出驗證 index/timecode 連續性，使用額外 code 專長便宜模型修正，再拼接寫檔

不只聽音訊，也會參考影片抽出的圖片，幫助辨識人物、場景、道具與畫面上的提示文字

另外，翻譯過程的 chunk / pre-pass 資源與回應會保留在專案資料夾中，方便失敗後直接 resume，不用每次都重切音訊、重抽圖、重跑整個翻譯

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
語音辨識 (ElevenLabs Scribe v2)
    ↓
產生 SRT 字幕
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
# ElevenLabs Speech to Text
ELEVENLABS_API_KEY=xxx
ELEVENLABS_STT_MODEL=scribe_v2
ELEVENLABS_STT_LANGUAGE_CODE=jpn

# 可選：ElevenLabs JSON -> SRT 格式轉換
ELEVENLABS_SRT_MAX_CHARACTERS_PER_LINE=24
ELEVENLABS_SRT_MAX_SEGMENT_CHARS=48
ELEVENLABS_SRT_MAX_SEGMENT_DURATION_S=4
ELEVENLABS_SRT_SEGMENT_ON_SILENCE_LONGER_THAN_S=0.5
ELEVENLABS_SRT_MERGE_SPEAKER_TURNS_GAP_S=0.1
ELEVENLABS_SRT_MAX_LINES_PER_BLOCK=3

# Google Gemini (翻譯)
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3-flash-preview

# DeepSeek (chunk 結構修正)
DEEPSEEK_API_KEY=xxx
LLM_CHUNK_FIX_MAX_RETRIES=3            # 修正失敗重試次數

# 可選：Gemini 翻譯調校
GEMINI_THINKING_LEVEL=HIGH             # 翻譯 thinking level: LOW/MEDIUM/HIGH
GEMINI_PRE_PASS_MAX_FRAMES=10          # pre-pass 最多附幾張全片代表圖片
GEMINI_PRE_PASS_FRAME_MAX_SIDE=768     # pre-pass 圖片最長邊尺寸
GEMINI_CHUNK_CHAR_LIMIT=6000           # 每塊目標字元數 (約 5 分鐘字幕)
GEMINI_CONCURRENCY=10                  # chunk 併發上限
GEMINI_CHUNK_MAX_RETRIES=3             # chunk 失敗重試次數
GEMINI_CHUNK_FRAME_INTERVAL_SECONDS=30 # chunk 圖片抽樣頻率（每幾秒一張）
GEMINI_CHUNK_FRAME_MAX_SIDE=768        # chunk 圖片最長邊尺寸
GEMINI_CHUNK_MISSING_BLOCK_TOLERANCE=2 # 每塊允許未對齊/缺漏字幕區塊數上限

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
├── asr.json          # ElevenLabs 原始結果
├── video.ja.srt      # 日文原文字幕
├── pre_pass.json     # Gemini pre-pass 簡報
├── pre_pass/         # pre-pass 用的圖片快取
├── chunks/           # chunk 音檔 / 圖片 / 翻譯回應快取（供 resume）
└── video.cht.srt     # 繁體中文翻譯字幕
```
