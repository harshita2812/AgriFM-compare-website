import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("all primary sections, help, About disclaimer, and no-upload/no-PII boundary", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.locator(".project-card .muted, .student-card .muted")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Evaluation readiness" })).toBeVisible();
  await expect(page.locator(".readiness-table tbody tr")).toHaveCount(4);

  const nav = page.locator(".nav-item");
  await nav.nth(3).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Models in the study" })).toBeVisible();
  await expect(page.getByText("Not evaluated", { exact: true }).first()).toBeVisible();

  await nav.nth(4).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Datasets & imagery" })).toBeVisible();
  await expect(page.locator(".dataset-panel tbody tr")).toHaveCount(5);
  await expect(page.locator(".dataset-panel")).toContainText("Metadata only");
  await expect(page.locator(".dataset-panel")).not.toContainText("Ready");

  await nav.nth(5).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Methodology & evaluation" })).toBeVisible();
  await expect(page.getByText("Seeded performance scores exist")).toHaveCount(0);
  await expect(page.getByText("used here as the primary ranking metric")).toHaveCount(0);
  await expect(page.getByText("ABOUT THIS PROTOTYPE")).toBeVisible();
  await expect(page.locator("footer")).toContainText("no validated performance results");
  await expect(page.locator(".credit-people")).not.toContainText("TEAM");
  await expect(page.locator(".credit-people")).not.toContainText("PROJECT GUIDE");
  await expect(page.locator('input[type="file"]')).toHaveCount(0);

  await page.getByRole("button", { name: "Help" }).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Methodology & evaluation" })).toBeVisible();
  await nav.nth(1).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
  await page.locator(".nav-item").nth(3).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await page.getByRole("button", { name: "Compare models", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
  await nav.nth(0).click();
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.getByRole("heading", { name: "Region-controlled study setup." })).toBeVisible();
});

test("farmer guide loads planning guidance and Hindi copy", async ({ page }) => {
  await page.route("**/api/farmer/advisory", (route) => route.fulfill({
    json: {
      region_id: "punjab",
      region_name: "Punjab",
      crop: "Wheat",
      language: "hi",
      source: "Open-Meteo",
      asset_id: "fixture-weather",
      fetched_at: "2026-11-19T00:00:00+00:00",
      forecast_days: 7,
      summary: { hottest_day_c: 30, total_rainfall_mm: 12 },
      advisories: ["यह एक परीक्षण पूर्वानुमान सलाह है।", "सुबह सिंचाई की योजना बनाएं।", "स्थानीय कृषि अधिकारी से सलाह लें।"],
      disclaimer: "यह सार्वजनिक मौसम पूर्वानुमान पर आधारित योजना सहायता है, प्रमाणित कृषि सलाह नहीं।",
      daily: [
        { date: "2026-11-19", temperature_max_c: 30, temperature_min_c: 18, precipitation_mm: 2, condition: "Light rain" },
      ],
    },
  }));
  await page.goto("/");
  await page.locator(".nav-item").nth(2).click();
  await expect(page.getByRole("heading", { name: "Weather-based crop planning" })).toBeVisible();
  await page.getByLabel("Language").selectOption("hi");
  await expect(page.getByRole("heading", { name: "मौसम आधारित फसल योजना" })).toBeVisible();
  await page.getByRole("button", { name: "7-दिन की सलाह देखें" }).click();
  await expect(page.locator(".farmer-advice")).toContainText("यह एक परीक्षण पूर्वानुमान सलाह है");
  await expect(page.locator(".farmer-advice")).toContainText("प्रमाणित कृषि सलाह नहीं");
});

test("overview entry points reach the comparison workspace", async ({ page }) => {
  await page.goto("/");
  for (const name of ["New comparison", "Set up a run", "Compare models", "Set up a comparison", "View all"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
    await page.locator(".nav-item").nth(0).click();
  }
});

test("model library add actions select the model in the comparison workspace", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator(".nav-item");
  await nav.nth(1).click();
  await expect(page.locator(".model-choice")).toHaveCount(4);
  for (const choice of await page.locator(".model-choice").all()) {
    if (await choice.getAttribute("aria-pressed") === "true") await choice.click();
  }
  await expect(page.locator('.model-choice[aria-pressed="true"]')).toHaveCount(0);

  await nav.nth(3).click();
  await expect(page.locator(".model-card")).toHaveCount(4);
  for (let index = 0; index < 4; index += 1) {
    await page.locator(".model-card").nth(index).getByRole("button", { name: "Add to a comparison" }).click();
    await expect(page.locator(".model-choice").nth(index)).toHaveAttribute("aria-pressed", "true");
    if (index < 3) await nav.nth(3).click();
  }
});

test("comparison controls save context only, show Phase-II placeholders, and export a truthful CSV", async ({ page }) => {
  await page.goto("/");
  await page.locator(".nav-item").nth(1).click();
  await expect(page.locator(".model-choice")).toHaveCount(4);
  await page.getByLabel("Study region").selectOption("maharashtra");
  await page.getByLabel("Target crop").selectOption("Rice");
  await page.getByLabel("Growing season").selectOption("Kharif 2025");
  await page.getByLabel("Imagery / dataset").selectOption("s1s2");

  for (let index = 1; index < 4; index += 1) await page.locator(".model-choice").nth(index).click();
  await expect(page.getByRole("button", { name: "Save comparison setup" })).toBeDisabled();
  await page.getByRole("button", { name: "Select all" }).click();
  await expect(page.locator('.model-choice[aria-pressed="true"]')).toHaveCount(4);
  await page.getByRole("button", { name: "Save comparison setup" }).click();

  await expect(page.getByText("Comparison setup saved — no model inference was run.")).toBeVisible();
  await expect(page.locator(".result-table tbody tr")).toHaveCount(4);
  await expect(page.locator(".result-table")).toContainText("Not yet evaluated — Phase-II");
  await expect(page.getByRole("status")).toContainText("DEMO DATA");
  await expect(page.locator(".winner-banner")).toHaveCount(0);
  await expect(page.locator(".mini-bar-chart")).toHaveCount(0);
  await expect(page.locator(".unmeasured-chart")).toContainText("Not yet evaluated — Phase-II");
  await expect(page.locator(".context-panel")).toContainText("Maharashtra");
  await expect(page.locator(".context-panel")).toContainText("Evaluation blocked");
  await expect(page.locator(".context-panel")).toContainText("No authorized model checkpoints");
  await expect(page.locator(".provenance-panel")).toContainText("No provenance was recorded because inference was not run");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download results as CSV" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^agrifm-.+\.csv$/);
  const contents = await readFile(await download.path(), "utf8");
  expect(contents).toContain('"Not yet evaluated — Phase-II"');
  expect(contents).toContain('"is_demo"');
  expect(contents).toContain('"true"');
  expect(contents).toContain('"evaluation_status"');
  expect(contents).toContain('"provenance_status"');

  await page.locator(".saved-select select").selectOption({ index: 1 });
  await expect(page.getByLabel("Study region")).toHaveValue("maharashtra");
  await expect(page.getByLabel("Target crop")).toHaveValue("Rice");
  await page.locator(".saved-select select").selectOption({ index: await page.locator(".saved-select option").count() - 1 });
  await expect(page.getByLabel("Study region")).toHaveValue("punjab");
  await expect(page.getByLabel("Target crop")).toHaveValue("Wheat");
  await page.getByRole("button", { name: "Dismiss" }).click();
  await expect(page.getByText("Comparison complete — the run is saved to history.")).toHaveCount(0);

  const provenanceResponse = await page.request.post("http://127.0.0.1:8000/api/runs", {
    data: {
      region_id: "punjab",
      crop: "Wheat",
      dataset_id: "sentinel2",
      model_ids: ["prithvi", "satmae"],
      provenance: {
        dataset_release: "fixture-release",
        model_revisions: { prithvi: "fixture-revision" },
      },
    },
  });
  expect(provenanceResponse.ok()).toBeTruthy();
  const provenanceRun = await provenanceResponse.json();
  await page.reload();
  await page.locator(".nav-item").nth(1).click();
  await page.locator(".saved-select select").selectOption(provenanceRun.id);
  await expect(page.locator(".provenance-panel")).toContainText("Declared values are unverified");
  await expect(page.locator(".provenance-panel")).toContainText("fixture-release");
  await expect(page.locator(".provenance-panel")).toContainText("prithvi: fixture-revision");

  const [provenanceDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Download results as CSV" }).click(),
  ]);
  const provenanceCsv = await readFile(await provenanceDownload.path(), "utf8");
  expect(provenanceCsv).toContain('"fixture-release"');
});

test("empty results state can save a context-only setup", async ({ page }) => {
  await page.route("**/api/runs", (route) => route.request().method() === "GET"
    ? route.fulfill({ json: [] })
    : route.continue());
  await page.goto("/");
  await page.locator(".nav-item").nth(1).click();
  await expect(page.getByText("Results will appear here")).toBeVisible();
  await page.getByRole("button", { name: "Save current setup" }).click();
  await expect(page.getByText("Comparison setup saved — no model inference was run.")).toBeVisible();
  await expect(page.locator(".result-table tbody tr")).toHaveCount(4);
});

test("comparison API errors are visible and do not leave the run button stuck", async ({ page }) => {
  await page.route("**/api/runs", (route) => route.request().method() === "POST"
    ? route.fulfill({ status: 503, json: { detail: "Comparison service unavailable" } })
    : route.continue());
  await page.goto("/");
  await page.locator(".nav-item").nth(1).click();
  await page.getByRole("button", { name: "Save comparison setup" }).click();
  await expect(page.locator(".notice-banner")).toContainText("Comparison service unavailable");
  await expect(page.getByRole("button", { name: "Save comparison setup" })).toBeEnabled();
  await page.getByRole("button", { name: "Dismiss" }).click();
  await expect(page.locator(".notice-banner")).toHaveCount(0);
});

test("overview history controls open the selected run and comparison view-all action", async ({ page }) => {
  await page.goto("/");
  const firstRun = page.locator(".run-link").first();
  await expect(firstRun).toBeVisible();
  await firstRun.click();
  await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
  await page.locator(".nav-item").nth(0).click();
  await page.getByRole("button", { name: "View run" }).first().click();
  await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
  await page.locator(".nav-item").nth(0).click();
  await page.getByRole("button", { name: "View all" }).click();
  await expect(page.getByRole("heading", { name: "Compare foundation models" })).toBeVisible();
});

test("responsive navigation stays off-canvas on smaller screens and remains accessible", async ({ page }) => {
  for (const width of [900, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");
    const sidebar = page.locator(".sidebar");
    await expect.poll(() => sidebar.evaluate((el) => el.getBoundingClientRect().right)).toBeLessThanOrEqual(0);
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(sidebar).toHaveClass(/sidebar-open/);
    await page.getByRole("button", { name: "Close navigation" }).click();
    await expect(sidebar).not.toHaveClass(/sidebar-open/);
    await expect.poll(() => sidebar.evaluate((el) => el.getBoundingClientRect().right)).toBeLessThanOrEqual(0);
  }
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.locator(".nav-item").nth(5).click();
  await expect(page.getByRole("heading", { name: "Methodology & evaluation" })).toBeVisible();
});

test("retry recovers after a transient dashboard API failure", async ({ page }) => {
  await page.route("**/api/dashboard", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator(".top-status")).toContainText("API unavailable");
  await page.unroute("**/api/dashboard");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await expect(page.getByText("API connected")).toBeVisible();
});
