import { mkdir } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

const era = {
  id: "golden_era",
  name: "黄金世代",
  years: "1991 至 1998",
  eyebrow: "霍格沃兹人生模拟器 · 黄金世代",
  title: "命运的猫头鹰，正在寻找你的窗台。",
  description: "魔法世界的钟声在黑湖上空回荡。写下你的名字，让城堡与尚未发生的历史见证另一种可能。",
  mainline: "密室、预言与改变历史的选择",
  atmosphere: "烛火、羊皮纸与冬夜的猫头鹰",
  available: true,
};

const setupSession = {
  id: "session-setup",
  name: "夜鸦的第一学年",
  era_id: "golden_era",
  status: "setup",
  state_version: 0,
  created_at: "2026-08-19T08:00:00Z",
  updated_at: "2026-08-19T08:00:00Z",
};

const activeSession = {
  ...setupSession,
  id: "session-active",
  name: "黑湖边的旧誓言",
  status: "active",
  state_version: 7,
};

const setupView = {
  current_step: 4,
  completed: false,
  steps_total: 13,
  current: {
    step: 4,
    title: "你的家族来自何处？",
    description: "血统不会决定你的选择，但它会改变世界最初看待你的方式。",
    selection_mode: "single",
    options: [
      { id: "pure", label: "古老纯血家族", description: "姓氏被写在多本家谱中。", value: "pure_blood", category: "魔法家庭", appendable: false, available: true },
      { id: "half", label: "混血家庭", description: "同时理解魔法与麻瓜世界。", value: "half_blood", category: "魔法家庭", appendable: false, available: true },
      { id: "muggle", label: "麻瓜家庭", description: "猫头鹰带来了第一个不可思议的秘密。", value: "muggle_born", category: "非魔法家庭", appendable: false, available: true },
      { id: "hidden", label: "被隐去的身世", description: "一段暂时无法读取的家族记录。", value: "hidden", category: "特殊身世", appendable: false, available: false },
    ],
  },
  answers: { "1": "golden_era", "2": "student", "3": "黑发灰眼，身形清瘦", "4": "half_blood" },
};

const completedSetup = {
  current_step: 13,
  completed: true,
  steps_total: 13,
  current: { step: 13, title: "命运已经成形", description: "", selection_mode: "confirm", options: [] },
  answers: {},
};

const emptyChanges = {
  inventory_add: [], inventory_remove: [], status_add: [], status_remove: [],
  skill_add: [], skill_remove: [], skill_deltas: {}, trait_add: [], trait_remove: [],
  vital_deltas: {}, attribute_deltas: {}, reputation_deltas: {}, relationship_deltas: [],
};

const turnResponse = {
  turn: {
    title: "午夜后的图书馆",
    scene_type: "exploration",
    narrative: "禁书区的最后一盏灯忽然熄灭。你听见书架深处传来羽毛笔划过羊皮纸的声音，而那张桌子前分明没有任何人。\n\n一册没有书名的旧书自行翻开，墨迹在纸上缓慢聚成你的名字。",
    location_id: "library",
    time_advance_minutes: 12,
  },
  choices: [
    { id: "approach", label: "举起魔杖，走近那本自行书写的旧书", kind: "choice", risk: "medium", effects_hint: "可能发现秘密", effects: { gains: [{ id: "clue", name: "古老线索", type: "memory", direction: "gain", description: "与城堡旧誓言有关" }], losses: [], note: "需要保持警觉" } },
    { id: "observe", label: "留在阴影中，先观察墨迹的变化", kind: "choice", risk: "low", effects_hint: "更加谨慎", effects: { gains: [], losses: [], note: "可能错过短暂的机会" } },
    { id: "free", label: "写下自己的行动", kind: "free_text", risk: "unknown", effects_hint: "", effects: { gains: [], losses: [], note: "" } },
  ],
  worldline: { offset_rate: 7.4, delta: 1.2, reason: "你触碰了原本无人发现的档案", affected_nodes: ["禁书区的旧誓言"] },
  player_changes: emptyChanges,
  applied_changes: emptyChanges,
  memory_update: { summary: "在图书馆发现会写下自己名字的无名旧书。" },
};

const playerState = {
  identity: { name: "艾琳·格雷", age: 11 },
  vitals: { hp: 92, max_hp: 100, mp: 78, max_mp: 100, sp: 88, max_sp: 100, energy: 71 },
  current_context: { datetime: "1991-09-03 00:18", location_id: "library" },
  worldline: { offset_rate: 7.4, reason: "一段被遗忘的誓言重新出现", affected_nodes: ["禁书区的旧誓言"] },
  school: { year_level: 1, house: "ravenclaw", courses: ["魔咒学", "变形术"] },
  family: { bloodline: "half_blood", home: "约克郡的一座旧宅" },
  personality: { temperament: "安静而好奇" },
  values: { belief: "知识应当被谨慎地分享" },
  magic_talents: [{ name: "古代魔文直觉", rank: "初现" }],
  skills: { charms: 12, transfiguration: 9 },
  statuses: [],
  traits: [{ id: "careful_reader", name: "谨慎的阅读者", polarity: "positive", source: "童年", description: "面对未知文字时更容易察觉异常。" }],
  inventory: [{ name: "榆木魔杖" }, { name: "黄铜书签" }],
  pet: { name: "墨点", species: "猫头鹰" },
  reputation: { ravenclaw: 8 },
  letters: [],
};

type Scenario = "landing" | "setup" | "story";

async function installApi(page: Page, scenario: Scenario) {
  const sessions = scenario === "setup" ? [setupSession] : scenario === "story" ? [activeSession] : [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const bodies: Record<string, unknown> = {
      "/api/health": { status: "ok", app_name: "HP Life Simulator", database: "sqlite", llm_configured: true },
      "/api/config/llm": { configured: true, base_url: "https://example.invalid", model: "arcane-narrator", api_key_present: true },
      "/api/sessions": sessions,
      "/api/content/eras": [era],
      "/api/sessions/session-setup/setup": setupView,
      "/api/sessions/session-active/setup": completedSetup,
      "/api/sessions/session-active/state": { session_id: "session-active", state_version: 7, state: playerState },
      "/api/sessions/session-active/journal": [{ id: "journal-1", turn_id: "turn-7", entry_type: "story", title: "午夜后的图书馆", summary: "无名旧书写下了你的名字。", data: { sequence: 7 }, created_at: "1991-09-03T00:18:00Z" }],
      "/api/sessions/session-active/relationships": [{ source_id: "player", target_id: "luna_lovegood", state: { stage: "acquaintance", affinity: 18, trust: 12 } }],
      "/api/sessions/session-active/npcs": [{ npc_id: "luna_lovegood", is_original_character: false, state: { name: "卢娜·洛夫古德" } }],
      "/api/sessions/session-active/turns": [{ id: "turn-7", sequence: 7, action: { kind: "choice" }, narrative: turnResponse.turn.narrative, response: turnResponse, state_version_after: 7, created_at: "1991-09-03T00:18:00Z" }],
    };
    const body = bodies[path];
    if (body === undefined) {
      await route.fulfill({ status: 404, json: { detail: `Unhandled test route: ${request.method()} ${path}` } });
      return;
    }
    await route.fulfill({ status: 200, json: body });
  });
}

async function assertNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

function parseColor(value: string): [number, number, number] {
  const hex = value.trim().match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    return [0, 2, 4].map((offset) => Number.parseInt(hex[1].slice(offset, offset + 2), 16)) as [number, number, number];
  }
  const rgb = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!rgb) throw new Error(`Unsupported CSS color: ${value}`);
  return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
}

function contrastRatio(foreground: string, background: string): number {
  const luminance = (value: string) => {
    const channels = parseColor(value).map((channel) => {
      const normalized = channel / 255;
      return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  };
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

async function assertReadableSecondaryText(page: Page) {
  const tokens = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement);
    return {
      foreground: style.getPropertyValue("--muted-dark"),
      backgrounds: [
        style.getPropertyValue("--surface"),
        style.getPropertyValue("--surface-raised"),
        style.getPropertyValue("--surface-soft"),
      ],
    };
  });
  for (const background of tokens.backgrounds) {
    expect(contrastRatio(tokens.foreground, background)).toBeGreaterThanOrEqual(4.5);
  }

  const placeholder = await page.locator(".era-start-actions input").evaluate((element) => ({
    foreground: getComputedStyle(element, "::placeholder").color,
    background: getComputedStyle(element).backgroundColor,
  }));
  expect(contrastRatio(placeholder.foreground, placeholder.background)).toBeGreaterThanOrEqual(4.5);
}

async function assertMinimumTouchTargets(page: Page) {
  const undersized = await page.locator("button, input, textarea").evaluateAll((elements) =>
    elements
      .filter((element) => {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0 && style.visibility !== "hidden";
      })
      .map((element) => {
        const box = element.getBoundingClientRect();
        return { label: element.getAttribute("aria-label") || element.textContent?.trim() || element.getAttribute("placeholder") || element.tagName, width: box.width, height: box.height };
      })
      .filter((target) => target.width < 44 || target.height < 44),
  );
  expect(undersized).toEqual([]);
}

const viewports = [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
] as const;

for (const viewport of viewports) {
  test.describe(viewport.name, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test.beforeEach(async ({ page }) => {
      await mkdir("test-results/visual-review", { recursive: true });
      await page.emulateMedia({ reducedMotion: "reduce" });
    });

    test("captures the landing archive", async ({ page }) => {
      await installApi(page, "landing");
      await page.goto("/");
      await expect(page.getByText("本地服务已连接")).toBeVisible();
      await assertReadableSecondaryText(page);
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-landing.png` });
    });

    test("captures the model configuration dialog", async ({ page }) => {
      await installApi(page, "landing");
      await page.goto("/");
      await page.getByRole("button", { name: "修改 / 测试" }).click();
      const dialog = page.getByRole("dialog", { name: "模型服务配置" });
      await expect(dialog).toBeVisible();
      const dialogBox = await dialog.boundingBox();
      expect(dialogBox).not.toBeNull();
      if (!dialogBox) throw new Error("Model configuration dialog has no layout box");
      expect(dialogBox.y).toBeGreaterThanOrEqual(12);
      expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(viewport.height - 12);
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-config.png` });
    });

    test("captures the character setup archive", async ({ page }) => {
      await installApi(page, "setup");
      await page.goto("/");
      await expect(page.locator(".save-card")).toHaveCSS("cursor", "auto");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();
      await expect(page.getByRole("heading", { name: setupView.current.title })).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-setup.png` });
    });

    test("captures the active story archive", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await expect(page.getByRole("heading", { name: turnResponse.turn.title })).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-story.png` });
    });
  });
}
