# Workflow Checks

## Network paths

- Treat mapped drive letters as user-interface conveniences; Codex tools may need the equivalent UNC path.
- If a mapped path fails, ask for or infer `\\server\share\path\project` and retry with `Set-Location -LiteralPath`.
- Use `Set-Location -LiteralPath '<project>'` before running ffmpeg so subtitle filters can stay relative.
- Escalate network-share file operations when sandboxing denies access.
## Subtitle refinement

- Confirm `video.ja.srt` and `video.cht.srt` have the same block count before editing.
- Keep a replacement map keyed by block index when chunking review work.
- Rebuild from the original `video.cht.srt` skeleton so timecodes cannot drift.
- Run `scripts/validate_srt_structure.py` after writing `video.cht.refined.srt`.

## Image generation

- Inspect `poster.jpg` first.
- Use the user's exact style request and text replacement requirements.
- Copy the newest generated PNG from `C:\Users\eli\.codex\generated_images` if the image tool does not place it directly in the project folder.

## Export

- Run export from the project folder or use `scripts/export_media.py`.
- Output folder is `~/Downloads/<project id>`.
- Final video filename is `<project.json name>.mp4`, sanitized only for Windows-invalid filename characters.


