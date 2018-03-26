const puppeteer = require("puppeteer");
const jestPupConfig = require("../jest-puppeteer.config.js");
const store = require("./testStore.js");

/**
 * Creates a page to have tests run on
 *
 * @param {String} [pagePath="/index.html"] - The path to navigate the page to.
 * @param {Boolean|String} [loggedOut=false] - If true, the token localStorage item will be empty, if it's a string, then a different account is used based on the value.
 * @returns {puppeteer.Page} The page to run tests in
 */
async function createPage(pagePath = "/index.html", loggedOut = false) {
  const bPage = await browser.newPage();
  const errors = [];
  const tokenMap = {
    admin: store.adminToken,
    nofiles: store.noFilesToken,
    user: store.token,
    fullquota: store.quotaToken
  };
  const token = loggedOut === true ? "" : tokenMap[loggedOut] || store.token;
  await bPage.goto(`http://localhost:${jestPupConfig.server.port}/index.html`, {
    waitUntil: "domcontentloaded"
  });
  await bPage.evaluate(token => {
    window.localStorage.setItem("token", token);
  }, token);
  bPage.on("pageerror", function(errorThrown) {
    errors.push(errorThrown);
  });
  await bPage.goto(`http://localhost:${jestPupConfig.server.port}${pagePath}`, {
    waitUntil: "networkidle0"
  });
  if (errors.length) {
    throw errors;
  }
  return bPage;
}

module.exports = createPage;
