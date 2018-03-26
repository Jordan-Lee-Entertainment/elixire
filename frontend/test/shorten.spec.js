const createPage = require("./createPage.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const faker = require("faker");

describe("Shorten page", function() {
  it("Redirects when logged out", async function() {
    const page = await createPage("/shorten.html", true);
    if (page.url() == `http://localhost:${jestPupConfig.port}/shorten.html`)
      await page.waitForNavigation();
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/shorten.html");
  });

  it("Shortens urls", async function() {
    const page = await createPage("/shorten.html");
    const url = faker.internet.url();
    await page.type("#long-link", url);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#long-link.is-valid");
  });

  it("Dedupes reused urls", async function() {
    const page = await createPage("/shorten.html");
    const url = faker.internet.url();
    await page.type("#long-link", url);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#long-link.is-valid");
    const longLink = await page.$("#long-link");
    const shortened = await longLink
      .getProperty("value")
      .then(r => r.jsonValue());
    await page.$eval("#long-link", link => (link.value = ""));
    await page.type("#long-link", url);
    await page.keyboard.press("Enter");
    await page.waitForFunction(
      url => url != document.getElementById("long-link").value,
      {
        polling: "mutation"
      },
      url
    );
    const dupeLink = await longLink
      .getProperty("value")
      .then(r => r.jsonValue());
    await expect(dupeLink).toBe(shortened);
    await page.$eval("#long-link", link => (link.value = ""));
    const secondLink = faker.internet.url();
    await page.type("#long-link", secondLink);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#long-link.is-valid");
    const secondShortened = await longLink
      .getProperty("value")
      .then(r => r.jsonValue());
    await expect(secondShortened).not.toBe(shortened);

    await page.$eval("#long-link", link => (link.value = ""));
    await page.type("#long-link", shortened);
    await page.keyboard.press("Enter");
    await expect(
      page.waitForFunction(
        url => url != document.getElementById("long-link").value,
        {
          polling: "mutation",
          timeout: 1000
        },
        shortened
      )
    ).rejects.toThrow("waiting failed: timeout 1000ms exceeded");
  });
});
