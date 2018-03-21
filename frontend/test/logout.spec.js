const createPage = require("./createPage.js");
const jestPupConfig = require("../jest-puppeteer.config.js");

describe("Logout page", function() {
  it("Redirects and unsets token", async function() {
    const page = await createPage("/logout.html");
    if (
      page.url() == `http://localhost:${jestPupConfig.server.port}/logout.html`
    )
      await page.waitForNavigation();
    await expect(page.url()).toBe(
      `http://localhost:${jestPupConfig.server.port}/index.html`
    );
    await expect(
      await page.evaluate(() => window.localStorage.getItem("token"))
    ).toBeFalsy();
  });
});
