// Renders puritty.svg (32 px and up) and puritty-small.svg (16 to 24 px)
// to PNGs with transparent backgrounds, by Chromium through Playwright.
// Run from a directory whose node_modules has playwright:
//   node <this> <icon dir>
const { chromium } = require(process.cwd() + "/node_modules/playwright");
const fs = require("fs");
const dir = process.argv[2];
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ deviceScaleFactor: 1 });
  for (const size of [16, 20, 24, 32, 40, 48, 64, 256]) {
    const svg = fs.readFileSync(`${dir}/${size <= 24 ? "puritty-small.svg" : "puritty.svg"}`, "utf8");
    await pg.setViewportSize({ width: size, height: size });
    await pg.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:${size}px;height:${size}px}</style>${svg}`);
    await pg.screenshot({ path: `${dir}/png/${size}.png`, omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  }
  await b.close();
})();
