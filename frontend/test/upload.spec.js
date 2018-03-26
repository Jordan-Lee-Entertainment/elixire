const createPage = require("./createPage.js");
const superagent = require("superagent");
const path = require("path");
const jestPupConfig = require("../jest-puppeteer.config.js");
const store = require("./testStore.js");

describe("Upload page", function() {
  it("Loads without errors when logged in", async function() {
    const page = await createPage("/upload.html");
  });

  it("Redirects when logged out", async function() {
    const page = await createPage("/upload.html", true);
    if (page.url() == `http://localhost:${jestPupConfig.port}/upload.html`)
      await page.waitForNavigation();
  });

  // Yeah this one is big, but I don't really think it should be split up tbh
  it("Uploads an image, displays the progress and preview with a functional delete button", async function() {
    const page = await createPage("/upload.html");
    const uploadHandle = await page.$("#upload-input");
    await expect(Promise.resolve(uploadHandle)).resolves.not.toBe(null);
    await uploadHandle.uploadFile(__dirname + "/testimage.png");
    await page.waitForSelector(".drop-invitation #progress-bar");
    const savedFileHandle = await page.waitForSelector(".saved-file");
    const preview = await savedFileHandle.$(".new-file-icon");
    await expect(Promise.resolve(preview)).resolves.not.toBe(null);
    await expect(
      preview.getProperty("src").then(r => r.jsonValue())
    ).resolves.toMatch(/^blob:http:\/\/localhost:\d*\/[0-9a-f\-]*$/);
    const filename = await savedFileHandle.$("span:nth-child(2)");
    const filesize = await savedFileHandle.$("span:nth-child(3)");
    const link = await savedFileHandle.$("a");
    await expect(Promise.resolve(filename)).resolves.not.toBeNull();
    await expect(Promise.resolve(filesize)).resolves.not.toBe(null);
    await expect(Promise.resolve(link)).not.toBe(null);
    await expect(
      filename.getProperty("innerText").then(r => r.jsonValue())
    ).resolves.toBe("testimage.png");
    await expect(
      filesize.getProperty("innerText").then(r => r.jsonValue())
    ).resolves.toBe("1.20 KiB");
    await expect(
      link.getProperty("href").then(r => r.jsonValue())
    ).resolves.toMatch(/\.png$/);
    const deleteBtn = await savedFileHandle.$(".delete-btn");
    await deleteBtn.click();
    await page.waitForSelector(".saved-file", {
      hidden: true
    });
    console.log("Deleted!");
  });

  it("Sets admin=1 flag", async function() {
    const page = await createPage("/upload.html", "admin");
    const uploadHandle = await page.$("#upload-input");
    return expect(Promise.resolve(uploadHandle)).resolves.not.toBe(null);
    await uploadHandle.uploadFile(__dirname + "/testimage.png");
    console.log("uwu");
    const requestUrl = await new Promise((resolve, reject) => {
      page.on("request", onRequest);
      async function onRequest(req) {
        const url = req.url();
        console.log("uwu", url);
        if (!url.match(/\/api\/upload(?:\?admin=1)?$/)) {
          return;
        }
        page.removeListener("request", onRequest);
        resolve(req.url());
      }
    });
    await expect(requestUrl).toMatch(/\?admin=1$/);
    const deleteBtn = await page.$(".delete-btn");
    await deleteBtn.click();
    console.log("Now we wait...");
  });

  it("Shows a warning on full quota", async function() {
    const page = await createPage("/upload.html", "fullquota");
    const uploadHandle = await page.$("#upload-input");
    await uploadHandle.uploadFile(__dirname + "/testimage.png");
    const alert = await page.waitForSelector(".alert.alert-danger", {
      timeout: 3000
    });
    await expect(
      alert.getProperty("innerText").then(a => a.jsonValue())
    ).resolves.toMatch(/quota/);
  });

  it("Shows a warning when bad mime type", async function() {
    const page = await createPage("/upload.html");
    const uploadHandle = await page.$("#upload-input");
    await uploadHandle.uploadFile(__dirname + "/testfilebadmime.txt");
    const alert = await page.waitForSelector(".alert.alert-danger");
    const alertContent = await alert
      .getProperty("innerText")
      .then(a => a.jsonValue());
    await expect(alertContent).toMatch(/Bad image!/);
  });

  it("Shows a warning when file already removed", async function() {
    const page = await createPage("/upload.html");
    const uploadHandle = await page.$("#upload-input");
    await uploadHandle.uploadFile(__dirname + "/testimage.png");
    const fileHandle = await page.waitForSelector(".saved-file");
    const fileUrl = await fileHandle.$('a[href^="http"]');
    const url = await fileUrl.getProperty("innerText").then(a => a.jsonValue());
    const shortCode = await path.parse(url).name;

    try {
      await superagent
        .delete(`http://localhost:${jestPupConfig.server.port}/api/delete`)
        .send({
          filename: shortCode
        })
        .set("Authorization", store.token);
    } catch (err) {
      console.log(err);
      throw err;
    }
    const deleteBtn = await fileHandle.$(".delete-btn");
    await deleteBtn.click();
    const alert = await page.waitForSelector(".alert.alert-warning");
    await expect(
      alert.getProperty("innerText").then(a => a.jsonValue())
    ).resolves.toMatch(/couldn't be found/);
  });
});
