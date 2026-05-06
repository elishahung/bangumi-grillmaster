"""Export grilled project deliverables to Downloads."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

INVALID_FILENAME_CHARS = '<>:"/\\|?*'
DEFAULT_SUBTITLE_STYLE = "Fontname=Microsoft JhengHei,Fontsize=22,Bold=1,Outline=1.5"


def sanitize_filename(value: str) -> str:
    cleaned = "".join("_" if ch in INVALID_FILENAME_CHARS or ord(ch) < 32 else ch for ch in value)
    cleaned = cleaned.strip().rstrip(".")
    if not cleaned:
        raise ValueError("project name is empty after filename sanitization")
    return cleaned


def load_project(project_dir: Path) -> dict[str, object]:
    project_path = project_dir / "project.json"
    if not project_path.exists():
        raise FileNotFoundError(f"missing {project_path}")
    return json.loads(project_path.read_text(encoding="utf-8-sig"))


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")


def build_ffmpeg_command(output_video: Path, subtitle_style: str) -> list[str]:
    filter_arg = f"subtitles=video.cht.refined.srt:force_style='{subtitle_style}'"
    return [
        "ffmpeg",
        "-i",
        "video.mp4",
        "-vf",
        filter_arg,
        "-c:a",
        "copy",
        str(output_video),
        "-y",
    ]


def resolve_output_paths(project_dir: Path, downloads_dir: Path) -> tuple[Path, Path, Path]:
    project_dir = project_dir.resolve()
    project = load_project(project_dir)
    project_id = str(project.get("id") or "").strip()
    project_name = str(project.get("name") or "").strip()
    if not project_id:
        raise ValueError("project.json is missing id")
    if not project_name:
        raise ValueError("project.json is missing name")

    output_dir = downloads_dir / project_id
    output_video = output_dir / f"{sanitize_filename(project_name)}.mp4"
    output_cover = output_dir / "poster.cover.png"
    return output_dir, output_video, output_cover


def export_video(project_dir: Path, downloads_dir: Path, subtitle_style: str, dry_run: bool) -> Path:
    project_dir = project_dir.resolve()
    require_file(project_dir / "video.mp4")
    require_file(project_dir / "video.cht.refined.srt")

    output_dir, output_video, output_cover = resolve_output_paths(project_dir, downloads_dir)
    command = build_ffmpeg_command(output_video, subtitle_style)

    print(f"output_dir={output_dir}")
    print(f"cover={output_cover}")
    print(f"video={output_video}")
    print("ffmpeg=" + " ".join(command))

    if dry_run:
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, cwd=project_dir, check=True)
    return output_dir


def export_cover(project_dir: Path, downloads_dir: Path, dry_run: bool) -> Path:
    project_dir = project_dir.resolve()
    require_file(project_dir / "poster.cover.png")

    output_dir, output_video, output_cover = resolve_output_paths(project_dir, downloads_dir)

    print(f"output_dir={output_dir}")
    print(f"cover={output_cover}")
    print(f"video={output_video}")

    if dry_run:
        return output_dir

    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_dir / "poster.cover.png", output_cover)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=["video", "cover"])
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--downloads-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--subtitle-style", default=DEFAULT_SUBTITLE_STYLE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.target == "video":
            export_video(args.project_dir, args.downloads_dir, args.subtitle_style, args.dry_run)
        else:
            export_cover(args.project_dir, args.downloads_dir, args.dry_run)
    except Exception as exc:  # noqa: BLE001 - CLI should surface concise failures.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

