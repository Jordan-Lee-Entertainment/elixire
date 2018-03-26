const createPage = require("./createPage.js");
const store = require("./testStore.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const superagent = require("superagent");
const faker = require("faker");

describe("Login page", function() {
  it("Loads without errors when logged out", async function() {
    console.log("Are you being resolved for me wtf?");
    const page = await createPage("/login.html", true);
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/login.html");
    console.log("fml");
  });

  it("Redirects upon successful login and sets token in localStorage", async function() {
    const page = await createPage("/login.html", true);
    await page.type("#username", store.username);
    await page.keyboard.press("Enter");
    await page.type("#password", store.password);
    await page.keyboard.press("Enter");
    console.log("uuwuuuuuuuu");
    await page.waitForNavigation();
    console.log(":3");
    const setToken = await page.evaluate(function() {
      return window.localStorage.getItem("token");
    });
    await expect(setToken).toBeTruthy();
    const response = await superagent
      .get(`http://localhost:${jestPupConfig.server.port}/api/profile`)
      .set("Authorization", setToken);
    await expect(response.body.username).toEqual(store.username);
    console.log("Redirected etc!");
  });

  it("Shows an error when invalid credentials are provided", async function() {
    const page = await createPage("/login.html", true);
    await page.type("#username", faker.internet.userName());
    await page.keyboard.press("Enter");
    await page.type("#password", faker.internet.password());
    await page.keyboard.press("Enter");
    await page.waitForSelector("#alert-area .alert.alert-danger");
  });
});
