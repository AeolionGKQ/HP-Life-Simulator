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
  current_step: 6,
  completed: false,
  steps_total: 18,
  era_id: "golden_era",
  current: {
    step: 6,
    title: "你的家族来自何处？",
    description: "血统不会决定你的选择，但它会改变世界最初看待你的方式。",
    selection_mode: "single",
    options: [
      { id: "pure_blood", label: "纯血家族", description: "父母双方都是巫师。你从小熟悉会动的照片、猫头鹰邮递和魔法社会礼仪，也可能背负古老家族的声誉与偏见。", value: "pure_blood", category: "", appendable: false, available: true },
      { id: "half_blood", label: "混血家庭", description: "家庭同时连接魔法界与麻瓜世界。你对两边都不完全陌生，也常常要在两套生活方式之间寻找自己的位置。", value: "half_blood", category: "", appendable: false, available: true },
      { id: "muggle_born", label: "麻瓜出身", description: "父母都是麻瓜。魔法曾以无法解释的意外出现在童年里，而霍格沃茨来信将第一次为这些怪事给出答案。", value: "muggle_born", category: "", appendable: false, available: true },
      { id: "hidden", label: "被隐去的身世", description: "一段暂时无法读取的家族记录。", value: "hidden", category: "特殊身世", appendable: false, available: false },
    ],
  },
  answers: {
    "1": "golden_era",
    "2": "艾琳·格雷",
    "3": "女",
    "4": "1980-03-12",
    "5": "黑发灰眼，身形清瘦",
    "6": "half_blood",
  },
};

const birthdaySetupView = {
  ...setupView,
  current_step: 4,
  current: {
    step: 4,
    title: "生日",
    description: "请以 YYYY-MM-DD 格式写下生日。",
    selection_mode: "text" as const,
    options: [],
  },
};

const startingPointSetupView = {
  ...setupView,
  current_step: 14,
  answers: {
    ...setupView.answers,
    "6": "火龙化成人",
  },
  current: {
    step: 14,
    title: "剧情起点",
    description: "从已经编排好的剧情节点中选择故事真正开始的时刻。",
    selection_mode: "single" as const,
    options: [
      { id: "before_first_letter", label: "收到霍格沃茨来信之前", description: "从 1991 年 7 月 1 日窗台、翅膀声和那封改变人生的霍格沃茨来信开始。", value: "before_first_letter", category: "", appendable: false, available: true },
      { id: "diagon_alley", label: "第一次踏入对角巷", description: "从采购魔杖、长袍、课本和坩埚开始。", value: "diagon_alley", category: "", appendable: false, available: true },
      { id: "platform_nine_three_quarters", label: "九又四分之三站台", description: "从 1991 年 9 月 1 日的蒸汽、猫头鹰叫声和即将启程的列车开始。", value: "platform_nine_three_quarters", category: "", appendable: false, available: true },
      { id: "sorting_ceremony", label: "分院时", description: "从礼堂烛光、长桌和分院帽落到头顶的那一刻开始。", value: "sorting_ceremony", category: "", appendable: false, available: true },
    ],
  },
};

const initialFriendsSetupView = {
  ...setupView,
  current_step: 13,
  current: {
    step: 13,
    title: "初始好友",
    description: "可选择预设好友，也可以不选择任何预设好友，独自开始故事。",
    selection_mode: "append" as const,
    options: [
      { id: "harry_potter", label: "哈利·波特", description: "勇敢而珍惜友谊。", value: "哈利·波特", category: "", appendable: true, available: true },
      { id: "hermione_granger", label: "赫敏·格兰杰", description: "认真聪明。", value: "赫敏·格兰杰", category: "", appendable: true, available: true },
    ],
  },
  answers: {
    ...setupView.answers,
    "7": "童年经历",
    "8": "性格",
    "9": "价值观",
    "10": "魔杖",
    "11": "魔法天赋",
    "12": "猫头鹰",
  },
};

const completedSetup = {
  current_step: 18,
  completed: true,
  steps_total: 18,
  era_id: "golden_era",
  current: { step: 18, title: "命运已经成形", description: "", selection_mode: "confirm", options: [] },
  answers: {},
  attribute_initialization: { status: "ready", calibration_summary: "初始属性已完成校准。" },
};

const finalSetupView = {
  current_step: 18,
  completed: false,
  steps_total: 18,
  era_id: "golden_era",
  current: {
    step: 18,
    title: "命运已经成形",
    description: "最后确认你的设定，随后魔法世界将为你校准初始属性。",
    selection_mode: "confirm",
    options: [],
  },
  answers: {
    "1": "golden_era",
    "2": "艾琳·格雷",
    "3": "女",
    "4": "1980-03-12",
    "5": "黑发灰眼，身形清瘦",
    "6": "half_blood",
    "7": "在旧宅阁楼阅读禁书",
    "8": "安静而好奇",
    "9": "知识应当被谨慎地分享",
    "10": "榆木，龙心弦",
    "11": "古代魔文直觉",
    "12": "猫头鹰",
    "13": "卢娜·洛夫古德",
    "14": "sorting_ceremony",
    "15": "ravenclaw",
  },
  attribute_initialization: { status: "pending" },
};

const emptyChanges = {
  inventory_add: [], inventory_remove: [], status_add: [], status_remove: [],
  skill_add: [], skill_remove: [], skill_deltas: {}, skill_experience_deltas: {},
  course_skill_deltas: {}, trait_add: [], trait_remove: [],
  resource_deltas: [], dimension_deltas: [], resource_cap_deltas: [], dimension_cap_deltas: [],
  reputation_deltas: {}, relationship_deltas: [],
};

const storyChanges = {
  ...emptyChanges,
  inventory_add: [
    {
      item_id: "ancient_bookmark",
      name: "古老书签",
      description: "刻有未知家族徽记",
      quantity: 1,
    },
    {
      item_id: "sealed_box",
      description: "没有留下名称的旧盒子",
      quantity: 1,
    },
  ],
};

const turnResponse = {
  turn: {
    title: "午夜后的图书馆",
    scene_type: "exploration",
    narrative: "禁书区的最后一盏灯忽然熄灭。你听见书架深处传来羽毛笔划过羊皮纸的声音，而那张桌子前分明没有任何人。\n\n一册没有书名的旧书自行翻开，墨迹在纸上缓慢聚成你的名字。",
    current_date: "1991-09-03",
    location_id: "library",
    location_name: "图书馆",
  },
  choices: [
    { id: "approach", label: "举起魔杖，走近那本自行书写的旧书", kind: "choice", risk: "medium", effects_hint: "可能发现秘密", effects: { gains: [{ id: "clue", name: "古老线索", type: "memory", direction: "gain", description: "与城堡旧誓言有关" }], losses: [], note: "需要保持警觉" } },
    { id: "observe", label: "留在阴影中，先观察墨迹的变化", kind: "choice", risk: "low", effects_hint: "更加谨慎", effects: { gains: [], losses: [], note: "可能错过短暂的机会" } },
    { id: "free", label: "写下自己的行动", kind: "free_text", risk: "low", effects_hint: "", effects: { gains: [], losses: [], note: "" } },
  ],
  worldline: { offset_rate: 7.4, delta: 1.2, reason: "你触碰了原本无人发现的档案", affected_nodes: ["禁书区的旧誓言"] },
  player_changes: storyChanges,
  applied_changes: storyChanges,
  memory_update: { summary: "在图书馆发现会写下自己名字的无名旧书。" },
};

const previousTurnResponse = {
  ...turnResponse,
  turn: {
    ...turnResponse.turn,
    title: "猫头鹰带来的第一封信",
    narrative: "窗台上的猫头鹰刚刚离开，厚重的信封安静地躺在你的书桌上。",
    current_date: "1991-09-02",
    location_id: "ollivanders",
    location_name: "",
  },
  choices: [
    { id: "open_letter", label: "拆开信封，看看里面写了什么", kind: "choice", risk: "low", effects_hint: "", effects: { gains: [], losses: [], note: "" } },
    { id: "ask_mother", label: "先去询问母亲是否知道这封信的来历", kind: "choice", risk: "medium", effects_hint: "", effects: { gains: [], losses: [], note: "" } },
    { id: "free", label: "写下自己的行动", kind: "free_text", risk: "low", effects_hint: "", effects: { gains: [], losses: [], note: "" } },
  ],
};

const playerState = {
  attribute_initialization: {
    status: "ready",
    calibration_summary: "角色初始属性已根据设定完成校准。",
  },
  identity: { name: "艾琳·格雷", gender: "女", birthday: "1980-03-12", age: 11 },
  resources: {
    health: { value: 92, max: 100 },
    mana: { value: 78, max: 100 },
    sanity: { value: 88, max: 100 },
    energy: { value: 71, max: 100 },
    satiety: { value: 86, max: 100 },
  },
  dimensions: {
    constitution: { value: 11, max: 20 },
    intelligence: { value: 12, max: 20 },
    willpower: { value: 10, max: 20 },
    charisma: { value: 9, max: 20 },
    magical_power: { value: 13, max: 20 },
  },
  current_context: { datetime: "1991-09-03 00:18", current_date: "1991-09-03", location_id: "library", location_name: "图书馆" },
  worldline: { offset_rate: 7.4, reason: "一段被遗忘的誓言重新出现", affected_nodes: ["first_letter_and_enrollment", "禁书区的旧誓言"] },
  school: { year_level: 1, house: "ravenclaw", courses: ["魔咒学", "变形术"] },
  family: { bloodline: "half_blood", home: "约克郡的一座旧宅" },
  personality: { temperament: "安静而好奇" },
  values: { belief: "知识应当被谨慎地分享" },
  magic_talents: [{ name: "古代魔文直觉", rank: "初现" }],
  skills: {
    charms: {
      id: "charms",
      name: "咒语",
      description: "学习施放、控制和组合各种实用咒语。",
      level: 2,
      experience: 0,
      source: "course",
      course_id: "charms",
      course_skill: true,
    },
    transfiguration: {
      id: "transfiguration",
      name: "变形术",
      description: "研究改变物体形态与性质的魔法。",
      level: 1,
      experience: 0,
      source: "course",
      course_id: "transfiguration",
      course_skill: true,
    },
  },
  statuses: [],
  traits: [{ id: "careful_reader", name: "谨慎的阅读者", polarity: "positive", source: "童年", description: "面对未知文字时更容易察觉异常。" }],
  inventory: [
    { name: "榆木魔杖" },
    { name: "黄铜书签" },
    { item_id: "ancient_bookmark", name: "古老书签", quantity: 1 },
    { item_id: "sealed_box", quantity: 1 },
  ],
  pet: { name: "墨点", species: "猫头鹰" },
  reputation: {
    score: 24,
    level_id: "kindly",
    level_name: "友善倾向",
    alignment: "轻微正面",
    last_delta: 4,
    last_reason: "保护低年级学生并公开作证",
  },
  letters: [],
};

const expelledPlayerState = {
  ...playerState,
  school: {
    grade: "left_school",
    house: "ravenclaw",
    departure_reason: "expelled",
    active_courses: [],
    elective_courses: [],
    newt_courses: [],
    course_selection: null,
    departure_notice: {
      status: "pending",
      notice_id: "expulsion:year_1:-61",
      reason: "expelled",
      title: "霍格沃兹开除通知",
      message: "由于你的声望已低至【黑巫师】级别，你已被霍格沃兹开除。当前学籍已经终止，课程已清空，请尽快离开学校。",
    },
  },
  reputation: {
    score: -61,
    level_id: "black_wizard",
    level_name: "黑巫师",
    alignment: "偏向黑巫师",
    last_delta: -8,
    last_reason: "持续伤害无辜者并破坏学校安全",
  },
};

type Scenario = "landing" | "setup" | "setup-birthday" | "setup-confirm" | "setup-starting-point" | "setup-friends" | "story" | "expulsion";

async function installApi(page: Page, scenario: Scenario) {
  const sessions = scenario === "setup" || scenario === "setup-birthday" || scenario === "setup-confirm" || scenario === "setup-starting-point" || scenario === "setup-friends"
    ? [setupSession]
    : scenario === "story" || scenario === "expulsion"
      ? [activeSession]
      : [];
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const bodies: Record<string, unknown> = {
      "/api/health": { status: "ok", app_name: "HP Life Simulator", database: "sqlite", llm_configured: true },
      "/api/config/llm": { configured: true, base_url: "https://example.invalid", model: "arcane-narrator", api_key_present: true },
      "/api/sessions": sessions,
      "/api/content/eras": [era],
      "/api/sessions/session-setup/setup": scenario === "setup-birthday"
        ? birthdaySetupView
        : scenario === "setup-confirm"
        ? finalSetupView
        : scenario === "setup-starting-point"
          ? startingPointSetupView
          : scenario === "setup-friends"
            ? initialFriendsSetupView
          : setupView,
      "/api/sessions/session-active/setup": completedSetup,
      "/api/sessions/session-active/state": {
        session_id: "session-active",
        state_version: scenario === "expulsion" ? 8 : 7,
        state: scenario === "expulsion" ? expelledPlayerState : playerState,
      },
      "/api/sessions/session-active/courses": {
        session_id: "session-active",
        state_version: 7,
        grade: "year_1",
        school_year: "1991-1992",
        term: "autumn",
        active_courses: [
          { id: "charms", name: "咒语", description: "学习施放、控制和组合各种实用咒语。", category: "core", available: true, unavailable_reason: null, skill_id: "charms", skill_level: 2 },
          { id: "transfiguration", name: "变形术", description: "研究改变物体形态与性质的魔法。", category: "core", available: true, unavailable_reason: null, skill_id: "transfiguration", skill_level: 1 },
        ],
        selection_options: [],
        editable_phase: null,
        elective_courses: [],
        newt_courses: [],
        skills: [],
        owl_results: [],
        newt_results: [],
        course_selection: null,
        course_history: [],
      },
      "/api/sessions/session-active/journal": [{ id: "journal-1", turn_id: "turn-7", entry_type: "story", title: "午夜后的图书馆", summary: "无名旧书写下了你的名字。", data: { sequence: 7 }, created_at: "1991-09-03T00:18:00Z" }],
      "/api/sessions/session-active/relationships": [{
        source_id: "player",
        target_id: "luna_lovegood",
        state: {
          stage: "acquaintance",
          bond_type: "friendship",
          romance_stage: "none",
          affinity: 18,
          trust: 12,
          last_change: { reason: "一起整理了图书馆的旧书架" },
        },
      }],
      "/api/sessions/session-active/npcs": [{ npc_id: "luna_lovegood", is_original_character: false, state: { name: "卢娜·洛夫古德" } }],
      "/api/sessions/session-active/turns": [
        { id: "turn-6", sequence: 6, action: { kind: "choice" }, narrative: previousTurnResponse.turn.narrative, response: previousTurnResponse, state_version_after: 6, created_at: "1991-09-02T00:18:00Z" },
        { id: "turn-7", sequence: 7, action: { kind: "choice" }, narrative: turnResponse.turn.narrative, response: turnResponse, state_version_after: 7, created_at: "1991-09-03T00:18:00Z" },
      ],
    };
    if (path === "/api/sessions/session-active/departure-notice/acknowledge") {
      await route.fulfill({
        status: 200,
        json: {
          session_id: "session-active",
          state_version: 9,
          state: {
            ...expelledPlayerState,
            school: {
              ...expelledPlayerState.school,
              departure_notice: {
                ...expelledPlayerState.school.departure_notice,
                status: "acknowledged",
              },
            },
          },
        },
      });
      return;
    }
    if (path === "/api/sessions/session-setup/setup/answer" && request.method() === "POST") {
      const requestBody = request.postDataJSON() as { step?: number; answer?: string };
      if (requestBody.step === 13 && requestBody.answer === "") {
        await route.fulfill({ status: 200, json: startingPointSetupView });
        return;
      }
    }
    if (path === "/api/sessions/session-setup/setup/confirm") {
      await new Promise((resolve) => setTimeout(resolve, 450));
      await route.fulfill({
        status: 502,
        json: { detail: "模型属性校准失败，请稍后重试" },
      });
      return;
    }
    const body = bodies[path];
    if (path === "/api/sessions/session-active/actions") {
      await new Promise((resolve) => setTimeout(resolve, 800));
      await route.fulfill({
        status: 200,
        json: {
          turn_id: "turn-8",
          sequence: 8,
          state_version: 8,
          recalled_memory_ids: [],
          response: turnResponse,
        },
      });
      return;
    }
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
      const originInput = page.getByRole("textbox", { name: setupView.current.title });
      await expect(originInput).toHaveValue("混血家庭");
      await page.getByRole("button", { name: "纯血家族" }).click();
      await expect(originInput).toHaveValue("纯血家族");
      await expect(page.getByText("父母双方都是巫师。你从小熟悉会动的照片、猫头鹰邮递和魔法社会礼仪，也可能背负古老家族的声誉与偏见。")).toBeVisible();
      await expect(page.getByText("家庭同时连接魔法界与麻瓜世界。你对两边都不完全陌生，也常常要在两套生活方式之间寻找自己的位置。")).toBeVisible();
      await expect(page.getByText("父母都是麻瓜。魔法曾以无法解释的意外出现在童年里，而霍格沃茨来信将第一次为这些怪事给出答案。")).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-setup.png` });
    });

    test("uses a native date input for the birthday", async ({ page }) => {
      await installApi(page, "setup-birthday");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();

      const birthdayInput = page.locator('input[type="date"][aria-label="生日"]');
      await expect(birthdayInput).toBeVisible();
      await expect(birthdayInput).toHaveValue("1980-03-12");
      await expect(birthdayInput).toHaveAttribute("autocomplete", "bday");
    });

    test("opens the new-save flow from the save manager", async ({ page }) => {
      await installApi(page, "setup");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();
      await expect(page.getByRole("heading", { name: setupView.current.title })).toBeVisible();

      await page.getByRole("button", { name: "创建新存档" }).click();

      await expect(page.getByRole("heading", { name: "从档案柜中取出一卷羊皮纸" })).toBeVisible();
      await expect(page.getByPlaceholder("为这段命运题名（可选）")).toBeVisible();
      await expect(page.getByRole("button", { name: "开始新的游戏" })).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("restricts the story starting point to predefined options", async ({ page }) => {
      await installApi(page, "setup-starting-point");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();

      await expect(page.getByRole("heading", { name: "剧情起点" })).toBeVisible();
      await expect(page.getByRole("button", { name: "收到霍格沃茨来信之前" })).toBeVisible();
      await expect(page.getByRole("button", { name: "第一次踏入对角巷" })).toBeVisible();
      await expect(page.getByRole("button", { name: "九又四分之三站台" })).toBeVisible();
      await expect(page.getByRole("button", { name: "分院时" })).toBeVisible();
      await expect(page.locator(".setup-option")).toHaveCount(4);
      await expect(page.getByRole("textbox", { name: "剧情起点" })).toHaveCount(0);
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("allows starting without a preset initial friend", async ({ page }) => {
      await installApi(page, "setup-friends");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();

      await expect(page.getByRole("heading", { name: "初始好友" })).toBeVisible();
      const next = page.getByRole("button", { name: "不选择预设好友，继续" });
      await expect(next).toBeEnabled();
      await next.click();
      await expect(page.getByRole("heading", { name: "剧情起点" })).toBeVisible();
    });

    test("shows attribute calibration progress and keeps retry available after failure", async ({ page }) => {
      await installApi(page, "setup-confirm");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${setupSession.name}` }).click();
      await expect(page.getByRole("heading", { name: finalSetupView.current.title })).toBeVisible();
      await expect(page.getByText("分院时", { exact: true })).toBeVisible();
      await expect(page.getByText("sorting_ceremony", { exact: true })).toHaveCount(0);

      await page.getByRole("button", { name: "确认角色并开始" }).click();
      await expect(page.getByRole("status")).toContainText("命运正在校准你的魔法回响");
      await expect(page.getByText("学院、出身与天赋的星轨正在交汇")).toBeVisible();
      await expect(page.getByRole("button", { name: "确认中…" })).toBeDisabled();

      await expect(page.getByText("模型属性校准失败，请稍后重试")).toBeVisible();
      const retry = page.getByRole("button", { name: "确认角色并开始" });
      await expect(retry).toBeEnabled();
      await retry.click();
      await expect(page.getByRole("status")).toContainText("命运正在校准你的魔法回响");
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("captures the active story archive", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await expect(page.getByRole("heading", { name: turnResponse.turn.title })).toBeVisible();
      await expect(page.getByText("日期：1991-09-03")).toBeVisible();
      await expect(page.getByText("地点：图书馆")).toBeVisible();
      await expect(page.getByText("ollivanders", { exact: true })).toHaveCount(0);
      await expect(page.getByText("物品：古老书签", { exact: true })).toBeVisible();
      await expect(page.getByText("物品：sealed_box", { exact: true })).toBeVisible();
      await expect(page.getByText("风险：中")).toBeVisible();
      await expect(page.getByText("风险：低")).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
      await page.screenshot({ path: `test-results/visual-review/${viewport.name}-story.png` });
      await page.getByRole("button", { name: "角色" }).click();
      await expect(page.getByText("古老书签", { exact: true })).toBeVisible();
      await expect(page.getByText("sealed_box", { exact: true })).toHaveCount(2);
    });

  test("shows reputation score and level in the reputation archive", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await page.getByRole("button", { name: "声望" }).click();

      await expect(page.getByRole("heading", { name: "友善倾向" })).toBeVisible();
      await expect(page.getByText("+24", { exact: true })).toBeVisible();
      await expect(page.getByText("轻微正面", { exact: true })).toBeVisible();
      await expect(page.getByText("本回合声望上升 +4", { exact: true })).toBeVisible();
      await expect(page.getByText("保护低年级学生并公开作证", { exact: true })).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("shows a blocking expulsion notice after automatic reputation expulsion", async ({ page }) => {
      await installApi(page, "expulsion");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();

      await expect(page.getByRole("heading", { name: "霍格沃兹开除通知" })).toBeVisible();
      await expect(page.getByText("声望已低至【黑巫师】级别", { exact: false })).toBeVisible();
      await expect(page.getByRole("button", { name: "确认并离开学校" })).toBeEnabled();
      await expect(page.getByRole("button", { name: "举起魔杖，走近那本自行书写的旧书" })).toHaveCount(0);

      await page.getByRole("button", { name: "确认并离开学校" }).click();
      await expect(page.getByRole("heading", { name: "霍格沃兹开除通知" })).toBeHidden();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("translates course skill fields in the character archive", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await page.getByRole("button", { name: "角色" }).click();

      const skillsSection = page.locator(".data-section").filter({
        has: page.getByRole("heading", { name: "技能与熟练度" }),
      });
      await expect(skillsSection.getByText("课程", { exact: true })).toHaveCount(2);
      await expect(skillsSection.getByText("课程技能", { exact: true })).toHaveCount(2);
      await expect(skillsSection.getByText("记录编号", { exact: true })).toHaveCount(2);
      await expect(skillsSection.getByText("变形术", { exact: true })).toHaveCount(4);
      await expect(skillsSection.getByText("Course Id", { exact: true })).toHaveCount(0);
      await expect(skillsSection.getByText("Course Skill", { exact: true })).toHaveCount(0);
      await expect(skillsSection.getByText("Transfiguration", { exact: true })).toHaveCount(0);
      await expect(skillsSection.getByText("transfiguration", { exact: true })).toHaveCount(0);
    });

    test("translates course term and affected worldline nodes", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();

      await page.getByRole("button", { name: "课程" }).click();
      await expect(page.getByText("学期", { exact: true })).toBeVisible();
      await expect(page.getByText("秋季", { exact: true })).toBeVisible();
      await expect(page.getByText("autumn", { exact: true })).toHaveCount(0);

      await page.getByRole("button", { name: "世界线" }).click();
      await expect(page.getByText("霍格沃茨来信与入学", { exact: true })).toBeVisible();
      await expect(page.getByText("first_letter_and_enrollment", { exact: true })).toHaveCount(0);
    });

    test("browses previous story nodes without allowing historical choices", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();

      const previous = page.getByRole("button", { name: "上一节点" });
      const next = page.getByRole("button", { name: "下一节点" });
      await expect(previous).toBeEnabled();
      await expect(next).toBeDisabled();

      await previous.click();
      await expect(page.getByRole("heading", { name: previousTurnResponse.turn.title })).toBeVisible();
      await expect(page.getByText("地点：奥利凡德魔杖店")).toBeVisible();
      await expect(page.getByText("正在浏览历史剧情节点，选项仅供查看")).toBeVisible();
      await expect(page.getByRole("button", { name: "拆开信封，看看里面写了什么" })).toBeDisabled();
      await expect(next).toBeEnabled();

      await next.click();
      await expect(page.getByRole("heading", { name: turnResponse.turn.title })).toBeVisible();
      await expect(page.getByText("正在浏览历史剧情节点，选项仅供查看")).toBeHidden();
      await expect(page.getByRole("button", { name: "举起魔杖，走近那本自行书写的旧书" })).toBeEnabled();
      await expect(next).toBeDisabled();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("opens fate intervention and submits a direct story target", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();

      await page.getByRole("button", { name: /干涉命运/ }).click();
      const instruction = page.getByRole("textbox", { name: "你希望接下来发生什么" });
      await expect(instruction).toBeVisible();
      await instruction.fill("下一幕让我在禁书区发现一本会写下我名字的无名书。");
      await expect(page.getByText(/\/2000$/)).toBeVisible();

      const actionRequest = page.waitForRequest((request) =>
        request.url().endsWith("/api/sessions/session-active/actions")
        && request.method() === "POST",
      );
      await page.getByRole("button", { name: "干涉命运并结束当前节点" }).click();
      const requestBody = JSON.parse((await actionRequest).postData() ?? "{}");
      expect(requestBody.kind).toBe("fate_intervention");
      expect(requestBody.fate_instruction).toContain("禁书区");
      await expect(page.getByRole("status")).toContainText("命运的墨迹正在改道");
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("reshapes the latest story node without adding history", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();

      const freeTextInput = page.getByPlaceholder("写下一个不在预言之中的行动…");
      const reshapeTrigger = page.getByRole("button", { name: /重新生成/ });
      await expect(reshapeTrigger).toBeVisible();
      await expect(reshapeTrigger).toContainText("重塑命运");
      await expect(reshapeTrigger).toContainText("重新生成：让羽毛笔重新写下你的故事");
      const freeTextBox = await freeTextInput.boundingBox();
      const reshapeBox = await reshapeTrigger.boundingBox();
      expect(freeTextBox).not.toBeNull();
      expect(reshapeBox).not.toBeNull();
      expect(reshapeBox?.y ?? 0).toBeGreaterThan(freeTextBox?.y ?? 0);

      await reshapeTrigger.click();
      const instruction = page.getByRole("textbox", { name: "你希望这一幕如何重写" });
      await expect(instruction).toBeVisible();
      await instruction.fill("保留无名书出现的事实，但让人物入场更自然，不要重复结算物品。");

      const actionRequest = page.waitForRequest((request) =>
        request.url().endsWith("/api/sessions/session-active/actions")
        && request.method() === "POST",
      );
      await page.getByRole("button", { name: "重塑这一节点" }).click();
      const requestBody = JSON.parse((await actionRequest).postData() ?? "{}");
      expect(requestBody.kind).toBe("reshape_fate");
      expect(requestBody.reshape_instruction).toContain("不要重复结算物品");
      const reshapeStatus = page.getByRole("status");
      await expect(reshapeStatus).toContainText("命运正在重新书写");
      await expect(reshapeStatus).toBeHidden();
      await expect(page.getByText("第 2 / 2 个剧情节点", { exact: true })).toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });

    test("keeps archive panels available while the quill writes", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await page.getByRole("button", { name: "举起魔杖，走近那本自行书写的旧书" }).click();
      await expect(page.getByRole("status")).toContainText("羽毛笔正在书写命运");

      await page.getByRole("button", { name: "角色" }).click();
      await expect(page.getByText("姓名", { exact: true })).toBeVisible();
      await expect(page.getByText("生日", { exact: true })).toBeVisible();

      await page.getByRole("button", { name: "剧情" }).click();
      await expect(page.getByRole("status")).toContainText("羽毛笔正在书写命运");
    });

    test("shows canonical bond details in the bond archive", async ({ page }) => {
      await installApi(page, "story");
      await page.goto("/");
      await page.getByRole("button", { name: `打开存档：${activeSession.name}` }).click();
      await page.getByRole("button", { name: "羁绊" }).click();
      await expect(page.getByText("卢娜·洛夫古德")).toBeVisible();
      await expect(page.getByText("相识")).toBeVisible();
      await expect(page.getByText("友情")).toBeVisible();
      await expect(page.getByText("好感 18/100 · 信任 12/100")).toBeVisible();
      await expect(page.getByText("最近变化：一起整理了图书馆的旧书架")).toBeVisible();
      await expect(page.getByText("romance_state")).not.toBeVisible();
      if (viewport.name === "mobile") await assertMinimumTouchTargets(page);
      await assertNoHorizontalOverflow(page);
    });
  });
}
