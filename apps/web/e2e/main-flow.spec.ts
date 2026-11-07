import { expect, test } from "@playwright/test";
import { CASE_ID, changedReport, mockApi, VERDICT_LABEL } from "./mock-api";

// With E2E_REAL=1 it runs against a real local API and worker, which spends
// free search and model quota: never against production. Otherwise the API is
// simulated in the browser.
const REAL = Boolean(process.env.E2E_REAL);

const PASSWORD = "Fak3sNews-e2e-Pass!";
const CLAIM = "Colombia alcanzó un récord de turismo en 2024 con más de 6 millones de visitantes.";
const ANY_VERDICT = /Respaldada por fuentes|Contradicha por fuentes|Evidencia insuficiente/;

test("register, sign in, send a case and read its report", async ({ page, context }) => {
  if (!REAL) await mockApi(page, context);
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#confirm-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.waitForURL(/\/login/);

  await page.getByLabel("Correo electrónico").fill(email);
  await page.locator("#password").fill(PASSWORD);
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.waitForURL(/\/history/);

  await page.goto("/submit");
  await page.locator("#raw-input").fill(CLAIM);
  await page.getByRole("button", { name: "Verificar", exact: true }).click();
  await page.waitForURL(/\/reports\//);

  const verdict = page.getByText(REAL ? ANY_VERDICT : VERDICT_LABEL).first();
  await expect(verdict).toBeVisible({ timeout: REAL ? 200_000 : 10_000 });

  await page.goto("/history");
  await expect(page.getByText(CLAIM).first()).toBeVisible();
  if (!REAL) {
    await page.getByRole("button", { name: "Cargar más" }).click();
    await expect(page.getByText("Un caso anterior")).toBeVisible();
    await expect(page.getByRole("button", { name: "Cargar más" })).toBeHidden();
  }
});

test("a CHANGED claim shows its sources oldest first", async ({ page, context }) => {
  test.skip(REAL, "needs a report with a known shape");
  await mockApi(page, context, changedReport());
  await context.addCookies([{ name: "access_token", value: "e2e", domain: "localhost", path: "/" }]);

  await page.goto(`/reports/${CASE_ID}`);

  await expect(page.getByText("Cambió con el tiempo").first()).toBeVisible({ timeout: 10_000 });
  const items = page.getByTestId("timeline-item");
  await expect(items).toHaveCount(2);
  await expect(items.first()).toContainText("2022");
  await expect(items.nth(1)).toContainText("2026");
  await expect(page.getByText("Sin fecha")).toBeVisible();
  await expect(page.getByText("NaN")).toHaveCount(0);
  await expect(page.getByText("con cambios en el tiempo")).toBeVisible();
});

test("a protected page sends a signed-out visitor to sign in", async ({ page }) => {
  await page.goto("/history");

  await expect(page).toHaveURL(/\/login/);
});
