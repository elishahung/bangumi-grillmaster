import fs from "node:fs";
import path from "node:path";
import type { NextApiRequest, NextApiResponse } from "next";

const projectsRoot = path.resolve(process.cwd(), "projects");

const mimeType = (filePath: string) => {
  if (filePath.endsWith(".mp4")) return "video/mp4";
  if (filePath.endsWith(".srt")) return "application/x-subrip";
  if (filePath.endsWith(".vtt")) return "text/vtt";
  if (filePath.endsWith(".json")) return "application/json";
  return "application/octet-stream";
};

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const raw = req.query.path;
  const segments = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const requested = path.resolve(projectsRoot, ...segments);

  if (!requested.startsWith(projectsRoot)) {
    res.status(400).json({ message: "Invalid path" });
    return;
  }

  if (!fs.existsSync(requested) || fs.statSync(requested).isDirectory()) {
    res.status(404).json({ message: "File not found" });
    return;
  }

  const stat = fs.statSync(requested);
  const range = req.headers.range;
  res.setHeader("Content-Type", mimeType(requested));
  res.setHeader("Accept-Ranges", "bytes");

  if (!range) {
    res.setHeader("Content-Length", stat.size);
    fs.createReadStream(requested).pipe(res);
    return;
  }

  const [startText, endText] = range.replace("bytes=", "").split("-");
  const start = Number.parseInt(startText ?? "0", 10);
  const end = endText ? Number.parseInt(endText, 10) : stat.size - 1;

  if (
    Number.isNaN(start) ||
    Number.isNaN(end) ||
    start > end ||
    end >= stat.size
  ) {
    res.status(416).end();
    return;
  }

  res.status(206);
  res.setHeader("Content-Range", `bytes ${start}-${end}/${stat.size}`);
  res.setHeader("Content-Length", end - start + 1);

  fs.createReadStream(requested, { start, end }).pipe(res);
}
