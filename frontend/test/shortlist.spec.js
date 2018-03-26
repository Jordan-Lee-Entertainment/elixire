const createPage = require("./createPage.js");
const store = require("./testStore.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const superagent = require("superagent");
const path = require("path");

describe("Shortlink list page", function() {
  it("Redirects when logged out", async function() {
    const page = await createPage("/shortlist.html", true);
    if (page.url() == `http://localhost:${jestPupConfig.port}/shortlist.html`)
      await page.waitForNavigation();
  });

  it("Loads without errors when logged in", async function() {
    await createPage("/shortlist.html");
  });

  it("Shows a message when the user has no shortened URLs", async function() {
    const page = await createPage("/shortlist.html", "nofiles");
    await expect(
      page.$(".no-links-upload-some:only-child")
    ).resolves.toBeTruthy();
  });

  it("Renders and loads links properly", async function() {
    const page = await createPage("/shortlist.html");
    await page.waitForSelector(".link-wrap");
  });

  it("Has a functional delete button", async function() {
    const page = await createPage("/shortlist.html");
    const linkPicked = await page.$(".link-container");
    const delBtn = await linkPicked.$(".vector-btn:nth-child(2)");
    await delBtn.click();
    const link = await linkPicked
      .$(".shortened")
      .then(a => a.getProperty("href"))
      .then(a => a.jsonValue());
    await page.waitForSelector(`a[src="${link}"]`, { hidden: true });
  });

  it("Has a functional open button", async function() {
    const page = await createPage("/shortlist.html");
    const openBtn = await page.$("a[href].vector-btn:last-child");
    const url = await openBtn.getProperty("href").then(a => a.jsonValue());
    await expect(url).toMatch(/^https?:\/\//);
  });

  it("Shows a warning when the link is already removed", async function() {
    const page = await createPage("/shortlist.html");
    const link = await page.$(".link-container");
    const linkUrl = await link
      .$(".shortened")
      .then(a => a.getProperty("innerText"))
      .then(a => a.jsonValue());
    const deleteBtn = await link.$(".icon-row a:nth-child(2)");
    try {
      await superagent
        .delete(
          `http://localhost:${jestPupConfig.server.port}/api/shortendelete`
        )
        .send({
          filename: path.basename(linkUrl)
        })
        .set("Authorization", store.token);
    } catch (err) {
      console.log(err);
      throw err;
    }
    await deleteBtn.click();
    await page.waitForSelector(".link-container", {
      hidden: true,
      timeout: 3000
    });
    const alert = await page.waitForSelector(".alert.alert-warning", {
      timeout: 3000
    });
    await expect(
      await alert.getProperty("innerText").then(a => a.jsonValue())
    ).toMatch(/couldn't be found/);
  });
});
