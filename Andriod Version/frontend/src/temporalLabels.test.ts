import { describe, expect, test } from "vitest";
import { translateMemoryStatus, translateTimelineId } from "./temporalLabels";

describe("时间扰动中文映射", () => {
  test("映射已知时间线和记忆状态", () => {
    expect(translateTimelineId("original_2020")).toBe("原始2020时间线");
    expect(translateTimelineId("altered_2020")).toBe("改变后的2020时间线");
    expect(translateMemoryStatus("original")).toBe("原始记忆");
    expect(translateMemoryStatus("blurred")).toBe("模糊记忆");
    expect(translateMemoryStatus("conflicted")).toBe("记忆冲突");
    expect(translateMemoryStatus("fractured")).toBe("记忆碎裂");
  });

  test("未知值回退为原始字段", () => {
    expect(translateTimelineId("future_2020")).toBe("future_2020");
    expect(translateMemoryStatus("unknown_status")).toBe("unknown_status");
  });
});
