import { expect, test, type Page } from "@playwright/test";

const era = {
  id: "second_generation",
  name: "黄金世代",
  years: "1991 至 1998",
  eyebrow: "霍格沃兹人生模拟器 · 黄金世代",
  title: "命运的猫头鹰，正在寻找你的窗台。",
  description: "城堡的灯火越过黑湖，在夜色中等待一位新的学生。",
  mainline: "密室与古老预言",
  atmosphere: "烛火、羊皮纸与尚未写下的名字",
  available: true,
};

async function mockLandingApi(page: Page) {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const bodies: Record<string, unknown> = {
      "/api/health": {
        status: "ok",
        app_name: "HP Life Simulator",
        database: "sqlite",
        llm_configured: true,
      },
      "/api/config/llm": {
        configured: true,
        base_url: "https://example.invalid",
        model: "arcane-narrator",
        api_key_present: true,
      },
      "/api/sessions": [],
      "/api/content/eras": [era],
    };
    const body = bodies[path];
    if (body === undefined) {
      await route.fulfill({ status: 404, json: { detail: `Unhandled test route: ${path}` } });
      return;
    }
    await route.fulfill({ status: 200, json: body });
  });
}

test.beforeEach(async ({ page }) => {
  await mockLandingApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("霍格沃兹人生模拟器");
});

test("exposes the archive as a named navigation landmark", async ({ page }) => {
  await expect(page.getByRole("navigation", { name: "魔法档案导航" })).toBeVisible();
});

test("opens model settings as a named dialog with an accessible close control", async ({ page }) => {
  await page.getByRole("button", { name: "修改 / 测试" }).click();

  const dialog = page.getByRole("dialog", { name: "模型服务配置" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "关闭模型服务配置" })).toBeVisible();
});

