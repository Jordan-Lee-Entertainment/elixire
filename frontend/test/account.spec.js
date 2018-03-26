const createPage = require("./createPage.js");
const faker = require("faker");
const store = require("./testStore.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const superagent = require("superagent");

describe("Account page", function() {
  it("Redirects when logged out", async function() {
    const page = await createPage("/account.html", true);
    if (page.url() == `http://localhost:${jestPupConfig.port}/account.html`)
      await page.waitForNavigation();
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/account.html");
  });

  it("Errors when invalid password is provided", async function() {
    const page = await createPage("/account.html");
    await page.type("#password", faker.internet.password());
    const password = faker.internet.password();
    await page.type("#new-password1", password);
    await page.type("#new-password2", password);
    await page.click("#submit-btn");
    await page.waitForSelector("#password:invalid");
  });

  it("Errors when non-matching passwords", async function() {
    const page = await createPage("/account.html");
    await page.type("#new-password1", faker.internet.password());
    await page.type("#new-password2", faker.internet.password());
    await page.click("#submit-btn");
    await page.waitForSelector("#new-password2:invalid");
  });

  it("Generates a token and redirects", async function() {
    const page = await createPage("/account.html");
    await page.click('button[data-target="#password-modal"]');
    await new Promise(resolve => setTimeout(resolve, 300));
    await page.type("#token-password", store.password);
    await page.keyboard.press("Enter");
    await page.waitForNavigation();
    await expect(page.evaluate(() => window.location.hash)).resolves.toMatch(
      new RegExp(`^#${store.token.split(".")[0]}\.`)
    );
  });

  it("Shows an error if invalid password on token modal", async function() {
    const page = await createPage("/account.html");
    await page.type("#token-password", faker.internet.password());
    await page.keyboard.press("Enter");
    await page.waitForSelector("#token-password:invalid");
  });
});
