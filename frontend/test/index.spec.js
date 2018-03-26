const createPage = require("./createPage.js");

describe("Index page", function() {
  it("Loads without errors when logged out", async function() {
    const page = await createPage("/index.html", true);
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/index.html");
  });
});
