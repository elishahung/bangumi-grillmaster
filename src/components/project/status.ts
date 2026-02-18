export const toProjectBadgeVariant = (
  status: string,
): "queued" | "running" | "completed" | "failed" | "default" => {
  if (status === "queued") return "queued";
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (["downloading", "asr", "translating", "running"].includes(status)) {
    return "running";
  }
  return "default";
};
