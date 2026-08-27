export const TEMPORAL_TIMELINE_LABELS: Record<string, string> = {
  original_2020: "原始2020时间线",
  altered_2020: "改变后的2020时间线",
};

export const MEMORY_STATUS_LABELS: Record<string, string> = {
  original: "原始记忆",
  blurred: "模糊记忆",
  conflicted: "记忆冲突",
  fractured: "记忆碎裂",
};

export function translateTimelineId(value: unknown): string {
  const text = String(value);
  return TEMPORAL_TIMELINE_LABELS[text] ?? text;
}

export function translateMemoryStatus(value: unknown): string {
  const text = String(value);
  return MEMORY_STATUS_LABELS[text] ?? text;
}
