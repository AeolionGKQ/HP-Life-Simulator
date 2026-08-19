import { expect, test } from "@playwright/test";

test("@integration reads health and LLM status from the real backend", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("本地服务已连接")).toBeVisible();
  await expect(page.locator(".error-banner")).toHaveCount(0);

  await page.getByRole("button", { name: "修改 / 测试" }).click();
  const dialog = page.getByRole("dialog", { name: "模型服务配置" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Base URL" })).toHaveValue(/.+/);
  await expect(dialog.getByRole("textbox", { name: "模型名" })).toHaveValue(/.+/);
  await expect(dialog.getByLabel("API Key")).toHaveAttribute("type", "password");
  await expect(dialog.getByLabel("API Key")).toHaveValue("");
});
