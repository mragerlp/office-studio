// Run against a disposable local Studio instance, with the same Playwright installation as hosted/tests/browser.mjs.
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

function luminance(rgb) {
  const channels = rgb.match(/[\d.]+/g).slice(0, 3).map(n => Number(n) / 255)
    .map(n => n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

async function main() {
  const origin = new URL(process.argv[2]);
  assert.equal(origin.hostname, "127.0.0.1");
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
  try {
    const page = await browser.newPage({ colorScheme: "dark" });
    for (const route of ["/", "/help.html"]) {
      await page.goto(new URL(route, origin).href);
      const colors = await page.locator(".brand-symbol").evaluate(mark => [
        getComputedStyle(mark).backgroundColor, getComputedStyle(document.documentElement).backgroundColor,
      ]);
      const [bright, dark] = colors.map(luminance).sort((a, b) => b - a);
      const ratio = (bright + 0.05) / (dark + 0.05);
      assert.ok(ratio >= 3, route + " dark idle contrast " + ratio.toFixed(3) + ":1");
    }
    await page.goto(origin.href);
    await page.locator("#office-color").fill("#33ccff");
    const mark = page.locator(".brand-symbol");
    assert.equal(await mark.evaluate(e => getComputedStyle(e).backgroundColor), "rgb(51, 204, 255)");
    await page.getByRole("switch", { name: "Dark mode" }).click();
    await page.locator("#office-color").fill("#000000");
    assert.equal(await mark.evaluate(e => getComputedStyle(e).backgroundColor), "rgb(0, 0, 0)");
    console.log("PASS: dark idle contrast, original readable accent, light-mode black");
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
