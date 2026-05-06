---
name: refine-export
description: "Manual-only workflow. Use this skill only when the user explicitly invokes /refine-export or $refine-export for a grilled video project that needs subtitle refinement, cover image generation, and final ffmpeg export. Do not invoke implicitly for ordinary subtitle, image, or video tasks."
---

# Refine Export

Use this skill only after an explicit `/refine-export` or `$refine-export` request. The workflow turns one completed grilled project folder into final deliverables:

1. `video.cht.refined.srt` from `video.cht.srt`, refined as Traditional Chinese subtitles translated from Japanese.
2. `poster.cover.png` from `poster.jpg`, generated in parallel when delegation is available.
3. `~/Downloads/<project id>/poster.cover.png` and `~/Downloads/<project id>/<project name>.mp4` with burned-in subtitles.

## Network path handling

Projects may live on a network share or mapped drive. Codex shell sessions do not always inherit the same mapped drive letters that the user sees in Explorer. If a mapped drive path such as `V:\...` fails, lands in the wrong directory, or cannot be found, ask for or infer the equivalent UNC path, for example `\\server\share\path\project`.

When running PowerShell commands, prefer `Set-Location -LiteralPath '<project path>'` before reading files or invoking ffmpeg. If the sandbox blocks network-share reads or writes, request approval for the specific project folder action. Do not rewrite ffmpeg subtitle filters with a long network subtitle path; run ffmpeg from the project directory and keep `subtitles=video.cht.refined.srt` as a relative filter argument.

## Expected project layout

Run from or point to a single project folder containing:

- `project.json`
- `video.mp4`
- `poster.jpg`
- `video.ja.srt`
- `video.cht.srt`
- `.pre_pass/pre_pass.json`
- optional visual references under `.pre_pass/media` and `.chunks/media/frames`

Read `project.json` first. Use `id` for the output folder name and `name` for the final video file name.

## Step 1: Refine subtitles

Goal: medium refinement, not a rewrite. Produce natural Traditional Chinese subtitles from the Japanese source, fixing errors, awkward phrasing, missing translation, and term consistency while preserving the variety-show roast tone.

Rules:

- Do not change SRT indexes or timecodes.
- Do not merge or split blocks.
- Keep the block count identical to `video.cht.srt`.
- Use `video.ja.srt` as the Japanese source-language reference, but account for ASR mistakes.
- The refined subtitle text must be Traditional Chinese. Do not leave Japanese in the subtitle text unless it is an intentional proper noun, title, service name, or quoted term that should remain untranslated.
- Use `.pre_pass/pre_pass.json` for summary, cast, term glossary, and segment summaries.
- Use frames only when text context is insufficient.
- Prefer editing only text lines inside each block.

For large SRT files, chunk by stable index ranges and stitch text back into the original skeleton. Only delegate ranges to subagents when the active instructions and user request allow agent delegation; otherwise process ranges locally. Each range pass must return replacements keyed by block index, not a full reindexed SRT.

After writing `video.cht.refined.srt`, run:

```powershell
python <skill>/scripts/validate_srt_structure.py video.cht.srt video.cht.refined.srt
```

Fix every reported issue before export.

## Step 2: Start cover image generation

Use the image generation/editing tool on `poster.jpg`. Inspect the actual poster before writing the prompt. The cover task is a reinterpretation of the original poster as if the same people and poster concept appeared inside a Rick-and-Morty-like adult animated cartoon, not a photo-shaped filter pass.

Start this as early as possible after inspecting `poster.jpg`, ideally while subtitle refinement or ffmpeg export continues. If active instructions allow subagents, launch one cover-generation sidecar agent with the project path, the current `poster.jpg` observations, the prompt rules below, and the requirement to save/copy the final image to `poster.cover.png`. Tell the sidecar agent it is not alone in the project folder and must not edit subtitles, video files, scripts, or unrelated artifacts. Continue the main workflow locally with subtitle validation and video export while the cover sidecar runs. If delegation is not available, generate the cover locally but do not delay subtitle refinement before starting it.

Cover rules:

- Preserve the original poster concept, people count, relative positions, props, background, callout shapes, visible text meaning, and visual hierarchy.
- Reimagine each person as a native character in a Rick-and-Morty-inspired American adult animated cartoon. Do not preserve photographic head shapes, skin texture, lighting, lens effects, or cutout-photo edges when they make the result look like a filter.
- Keep recognizable identity cues such as hairstyle, glasses, facial hair, expression, pose, relative body size, and distinctive facial proportions, but simplify them into cartoon construction.
- Preserve the original meaning and layout of visible text, but convert Japanese text into concise English.
- Do not add new objects, characters, logos, story themes, food, badges, or titles that are not present in the original poster unless the user explicitly requests them.
- Do not reuse stale prompt details from previous projects. In particular, do not mention malatang, a bowl, six heads, a bottom branding strip, sci-fi additions, or other elements unless they are visible in the current `poster.jpg`.
- Apply only a Rick-and-Morty-inspired American adult animated cartoon rendering style: thick uneven black outlines, flat saturated colors, simplified shading, large uneven eyes, exaggerated mouths and teeth, rubbery facial geometry, and slightly grotesque comedy caricature.
- Do not intentionally make the people look like different people.
- Avoid the word "sci-fi" in the prompt unless the source poster already has sci-fi elements or the user asks for sci-fi.

Use this prompt shape, replacing bracketed text with what is actually visible in the poster:

```text
Reimagine the original poster as if this exact variety-show poster existed inside a Rick-and-Morty-inspired American adult animated cartoon. Keep the same poster concept, same number of people, same relative positions, same props/background/callout shapes, same visible text hierarchy, and same overall layout, but redraw the people as native cartoon characters rather than preserving photo-real head shapes or applying a filter. Keep each person's recognizable identity cues: [briefly list visible cues such as hairstyle, glasses, pose, expression, clothing, relative size]. Use thick uneven black outlines, flat saturated colors, simplified shading, large uneven eyes, exaggerated mouths and teeth, rubbery facial geometry, and slightly grotesque comedy caricature. Convert all visible Japanese text into concise English with the same meaning and similar placement: [list each visible text item and its English replacement]. Do not add new characters, objects, logos, food, badges, sci-fi elements, or extra text. Do not change the poster concept; redraw only the existing poster into this cartoon universe.
```

Save or copy the generated image to `poster.cover.png` in the project folder. If the image tool saves under `C:\Users\eli\.codex\generated_images\...`, copy the newest generated PNG to the project folder and leave the original in place. After copying, verify `poster.cover.png` exists before exporting.

## Step 3: Export deliverables

Use the bundled export script so naming and paths stay consistent. Export the video and cover as two independent operations; both operations create `~/Downloads/<project id>` before writing.

```powershell
python <skill>/scripts/export_media.py video <project-dir>
python <skill>/scripts/export_media.py cover <project-dir>
```

The video export writes `<project name>.mp4` using ffmpeg with burned-in subtitles:

```text
subtitles=video.cht.refined.srt:force_style='Fontname=Microsoft JhengHei,Fontsize=22,Bold=1,Outline=1.5'
```

The script runs ffmpeg from the project directory so the subtitle filter can use the simple relative subtitle path.

If `poster.cover.png` is still being generated by the sidecar agent after `video.cht.refined.srt` has passed validation, do not wait before starting the video encode. Run the video export:

```powershell
python <skill>/scripts/export_media.py video <project-dir>
```

After the sidecar produces `poster.cover.png`, export only the cover:

```powershell
python <skill>/scripts/export_media.py cover <project-dir>
```

## Operational notes

- Before generating a cover, check whether `poster.cover.png` already exists. If it exists and the user did not ask to regenerate it, reuse it.
- When a cover sidecar agent is running, continue the main workflow until the next step actually needs the cover. Wait for the sidecar only before the final response or before running the cover export.
- If a prior turn was interrupted, verify which artifacts already exist before repeating work.
- Prefer commands that do not print long non-ASCII paths when running under Windows console code pages. If needed, print short status fields or use JSON with UTF-8-safe output to avoid `UnicodeEncodeError`.
- Treat cover generation as one-shot. Do not regenerate automatically just because the result is imperfect. If the generated poster is missing, malformed, or visibly changes the people/elements too much, report that in the final response so the user can decide whether to revise the skill prompt or rerun the cover step.

## Final response

Report the output folder and the two generated files. Include whether SRT validation passed and whether ffmpeg completed successfully.

Also include a concise subtitle-refinement summary with representative examples. Prefer a Markdown table with these columns:

- `字幕編號`
- `原譯`
- `修改後`
- `修改原因`

If there are many edits, choose the most important examples: term consistency, Japanese-to-Traditional-Chinese translation fixes, ASR/source-reference corrections, meaning reversals, awkward phrasing cleanup, tone preservation, and recurring joke/name consistency. Do not list every small wording change.
