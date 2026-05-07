Refine subtitles for this video project.

Goal: medium refinement, not a rewrite. Produce natural Traditional Chinese subtitles from the Japanese source, fixing errors, awkward phrasing, missing translation, and term consistency while preserving the variety-show roast tone.

Files in the current working directory:

- `video.cht.srt` — original Traditional Chinese subtitles to refine.
- `video.ja.srt` — Japanese source-language reference (account for ASR mistakes).
- `.pre_pass/pre_pass.json` — summary, cast, term glossary, segment summaries.
- Optional visual references under `.pre_pass/media/` and `.chunks/media/frames/`.

Write scope (strict): you may only create or modify `video.cht.refined.srt` and `.refine/report.md`. Do **not** touch any other file, in particular:

- `project.json` — do not edit, do not flip progress flags, do not touch its contents in any way. The outer Python workflow owns this file and will mark progress after validating your output.
- `video.cht.srt` and `video.ja.srt` — read-only sources.
- `.pre_pass/`, `.chunks/`, `.asr/` — read-only caches.
- `video.mp4`, `audio.opus`, `poster.jpg`, etc. — unrelated to subtitle refinement.

Do not run scripts that mutate `project.json` (e.g. don't run the project's own Python entrypoints, validators that write back, or any tool that re-saves state).

Rules:

- Do not change SRT indexes or timecodes.
- Do not merge or split blocks.
- Keep the block count identical to `video.cht.srt`.
- Use `video.ja.srt` as the Japanese source-language reference, but account for ASR mistakes.
- The refined subtitle text must be Traditional Chinese. Do not leave Japanese in the subtitle text unless it is an intentional proper noun, title, service name, or quoted term that should remain untranslated.
- Use `.pre_pass/pre_pass.json` for summary, cast, term glossary, and segment summaries.
- Use frames only when text context is insufficient.
- Prefer editing only text lines inside each block.
- Preserve intentional Japanese address register and honorifics when they are already present in the Traditional Chinese subtitles. Do not remove or flatten suffixes such as `桑`, `醬`, `君`, `大人`, `前輩`, or `後輩` just to make the line sound more localized. Keep the speaker's polite/plain register contrast through word choice, but treat this as a preservation rule, not a reason to over-edit otherwise natural lines.
- Do not force terminology, proper-noun, or name localization when the existing subtitle is not clearly wrong. For program titles, talent names, group names, segment labels, and other proper nouns, keep Japanese or established romanized forms when there is no genuinely common Traditional Chinese (Taiwan) rendering. For example, preserve `テツヤ` if the source subtitles intentionally keep it that way; do not change it to `Tetsuya` unless there is a clear project glossary or common-use reason.
- Before polishing a line, identify its variety-show function in context: setup, answer, reaction, roast, self-defense, callback, team-name reference, person-name reference, song/title reference, or scoreboard/segment flow. Preserve that function even when a literal translation sounds smoother.
- Treat recurring team names, nicknames, segment labels, challenge names, and running jokes as show-specific terms. Check nearby blocks, `.pre_pass/pre_pass.json`, and the Japanese source before turning them into generic descriptions. For example, a term like `黒帯` may be a team or performer name in context, not a literal martial-arts rank.
- Keep spoken Mandarin/Taiwan Traditional Chinese subtitle rhythm. Prefer natural conversational particles and compact phrasing when the Japanese line is a quick retort, interruption, or defense; avoid over-formal explanations that flatten the variety-show timing.
- When correcting an awkward but context-dependent line, optimize for the intended joke/interaction over word-for-word equivalence. If the line is about a prior on-screen match, quiz team, or segment action, make that relationship explicit enough for viewers to follow.
- Keep subtitle line breaks balanced for on-screen display. When changing a two-line subtitle, do not leave one line much longer than the other if a natural break can make the visual width more even. Prefer breaks at phrase boundaries, for example:

```text
但有一個人，讓我們把原本
陌生的西洋音樂聽得更親近。
```

instead of:

```text
但有一個人，讓我們把原本陌生的西洋音樂
聽得更親近。
```

For large SRT files, chunk by stable index ranges and stitch text back into the original skeleton. Each range pass must return replacements keyed by block index, not a full reindexed SRT.

After writing the refined SRT, also write a concise refinement summary to `.refine/report.md` (the `.refine/` directory already exists). The report must be a Markdown table with these exact columns:

| 字幕編號 | 原譯 | 修改後 | 修改原因 |
| --- | --- | --- | --- |

Pick at most 10 representative rows. When choosing rows, prefer the most important examples covering: term consistency, Japanese-to-Traditional-Chinese translation fixes, ASR/source-reference corrections, meaning reversals, awkward phrasing cleanup, tone preservation, and recurring joke/name consistency. Do not list every small wording change.

If your edits exceed 10 rows, append a short paragraph after the table describing in general what kinds of remaining changes were made (e.g. minor punctuation, particle smoothing, line-break rebalancing) so the reader knows what is not in the table.

Write the table headers and rows in Traditional Chinese.

Final state:

- `video.cht.refined.srt` exists in the current working directory. Block count, indexes, and timecodes must match `video.cht.srt` exactly. Every block's text must be non-empty Traditional Chinese.
- `.refine/report.md` exists with the table described above.

Reply with just the single word `done`. Do not include explanations, summaries, edit lists, file paths, or any other commentary — the report file already covers the substantive changes, the calling workflow ignores your final message, and any extra tokens are wasted.
