const createPage = require("./createPage.js");
const store = require("./testStore.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const superagent = require("superagent");

describe("Token page", function() {
  it("Loads without errors", async function() {
    const page = await createPage("/token.html");
  });

  it("Highlights the codeblocks", async function() {
    const page = await createPage("/token.html");
    await page.waitForSelector("#kshare-config .hljs-attr");
    await page.waitForSelector("#sharex-config .hljs-attr");
  });

  it("Substitutes token in configs", async function() {
    const page = await createPage("/token.html#tokenvalue");
    const tokenElem = await page.$("#token");
    const tokenHandle = await tokenElem.getProperty("innerText");
    const subToken = await tokenHandle.jsonValue();
    await expect(subToken).toBe("tokenvalue");
  });

  it("Has functional download buttons", async function() {
    const page = await createPage("/token.html#tokenvalue");
    const kshareDl = await page.$("#kshare-dl");
    const sharexDl = await page.$("#sharex-dl");
    const managerDl = await page.$("#elixire-manager-dl");
    await expect(
      await (await kshareDl.getProperty("href")).jsonValue()
    ).toMatch(/^blob:http:\/\/localhost/);
    await expect(
      await (await sharexDl.getProperty("href")).jsonValue()
    ).toMatch(/^blob:http:\/\/localhost/);
    await expect(
      await (await managerDl.getProperty("href")).jsonValue()
    ).toMatch(/^blob:http:\/\/localhost/);
  });
});
