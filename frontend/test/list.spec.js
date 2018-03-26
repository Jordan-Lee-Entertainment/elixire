const createPage = require("./createPage.js");
const store = require("./testStore.js");
const jestPupConfig = require("../jest-puppeteer.config.js");
const superagent = require("superagent");
const path = require("path");

describe("File list page", function() {
  it("Redirects when logged out", async function() {
    const page = await createPage("/list.html", true);
    if (page.url() == `http://localhost:${jestPupConfig.port}/list.html`)
      await page.waitForNavigation();
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/list.html");
  });

  it("Shows a message when the user has no files", async function() {
    const page = await createPage("/list.html", "nofiles");
    await expect(
      page.$(".no-files-upload-some:only-child")
    ).resolves.toBeTruthy();
  });

  it("Renders and loads files properly", async function() {
    const page = await createPage("/list.html");
    await page.waitForSelector(
      '.file-container > .file-wrap > .preview-container > img[src^="blob:http://localhost"].preview-transport'
    );
  });

  it("Shows the correct filesize", async function() {
    const page = await createPage("/list.html");
    const size = await page.$(".file-size");
    const fileSize = await size
      .getProperty("innerText")
      .then(a => a.jsonValue());
    await expect(fileSize).toBe("1.20 KiB");
  });

  it("Has a functional delete button", async function() {
    const page = await createPage("/list.html");
    const filePicked = await page.$(".file-wrap");
    const delBtn = await filePicked.$(".vector-btn:nth-child(2)");
    await delBtn.click();
    const imageSource = await filePicked
      .$(".preview-container img")
      .then(a => a.getProperty("src"))
      .then(a => a.jsonValue());
    await page.waitForSelector(`img[src="${imageSource}"]`, { hidden: true });
  });

  it("Has a functional open button", async function() {
    const page = await createPage("/list.html");
    const openBtn = await page.$("a[href].vector-btn:last-child");
    const fileUrl = await openBtn.getProperty("href").then(a => a.jsonValue());
    await expect(fileUrl).toMatch(/^http:\/\/localhost/);
  });

  it("Renders only initial previews", async function() {
    const page = await createPage("/list.html");
    await page.waitForSelector("img:not(.stubbed-preview).preview-transport");
    await expect(page.$("img.stubbed-preview")).resolves.toBeTruthy();
  });

  it("Renders files only when in viewport", async function() {
    const page = await createPage("/list.html");
    await page.waitForSelector("img:not(.stubbed-preview).preview-transport", {
      timeout: 3000
    });
    const stubbedPrev = await page.$(
      ".file-container:last-child img.stubbed-preview"
    );
    // Because we load it as it comes into view, this is to make sure that we catch it
    await Promise.all([
      page.waitForSelector(".loading-block", {
        timeout: 3000
      }),
      page.evaluate(() =>
        document
          .querySelectorAll(".file-container:last-child img.stubbed-preview")[0]
          .scrollIntoViewIfNeeded()
      )
    ]);
  });

  it("Shows a warning when the file is already removed", async function() {
    const page = await createPage("/list.html");
    const file = await page.$(".file-container");
    const fileUrl = await file
      .$(".icon-row a:last-child")
      .then(a => a.getProperty("href"))
      .then(a => a.jsonValue());
    const deleteBtn = await file.$(".icon-row a:nth-child(2)");
    try {
      await superagent
        .delete(`http://localhost:${jestPupConfig.server.port}/api/delete`)
        .send({
          filename: path.parse(fileUrl).name
        })
        .set("Authorization", store.token);
    } catch (err) {
      console.log(err);
      throw err;
    }
    await deleteBtn.click();
    await page.waitForSelector(`a[href="${fileUrl}"]`, {
      hidden: true
    });
    const alert = await page.waitForSelector(".alert.alert-warning");
    await expect(
      await alert.getProperty("innerText").then(a => a.jsonValue())
    ).toMatch(/couldn't be found/);
  });
});
