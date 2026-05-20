import { chromium } from "playwright";

const baseUrl = process.env.DASHBOARD_URL || "http://127.0.0.1:8000";

const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

await page.goto(`${baseUrl}/login`, { waitUntil: "networkidle" });
await page.fill('input[type="email"]', "admin@crickenzen.com");
await page.fill('input[type="password"]', "admin123");
await Promise.all([
  page.waitForURL("**/dashboard", { timeout: 15000 }),
  page.click('button[type="submit"]'),
]);

await page.waitForSelector("text=Match Centre", { timeout: 15000 });
await page.waitForTimeout(2500);

const proof = await page.evaluate(() => {
  const text = document.body.innerText;
  const buttons = [...document.querySelectorAll("button")].map((button) => button.innerText.trim()).filter(Boolean);
  return {
    title: document.title,
    hasMatchCentre: text.includes("Match Centre"),
    hasLiveTab: buttons.includes("Live"),
    hasUpcomingTab: buttons.includes("Upcoming"),
    hasDetailWorkspace: text.includes("Win Probability Timeline") && text.includes("Match Detail"),
    hasManualDrawer: text.includes("Manual CREX start"),
    bodyTextSample: text.slice(0, 700),
  };
});

await page.screenshot({ path: "artifacts/match-centre-dashboard.png", fullPage: true });
console.log(JSON.stringify(proof, null, 2));

await browser.close();
