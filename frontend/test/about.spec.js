const createPage = require("./createPage.js");

describe("About page", function() {
  it("Loads without errors when logged out", async function() {
    const page = await createPage("/about.html", true);
  });

  it("Loads without errors when logged in", async function() {
    const page = await createPage("/about.html");
  });

  it("Changes to discrim when hovered", async function() {
    const page = await createPage("/about.html");

    const memberChosen = await page.$(".team-name");
    await expect(await memberChosen.$(".discrim")).toBeFalsy();
    await memberChosen.hover();
    const expectedTag = await (await (await (await memberChosen.getProperty(
      "attributes"
    )).getProperty("data-discordtag")).getProperty("value")).jsonValue();

    const discrimHandle = await page.waitForSelector(
      `h3[data-discordtag="${expectedTag}"].team-name > .discrim`
    );

    const discrim = await (await discrimHandle.getProperty(
      "innerText"
    )).jsonValue();
    await expect(discrim).toBe(
      await expectedTag.substring(
        expectedTag.lastIndexOf("#"),
        expectedTag.length
      )
    );
    await page.mouse.move(0, 0);
    await expect(await memberChosen.$(".discrim")).toBeFalsy();
  });

  it("Changes to discrim when tapped", async function() {
    const page = await createPage("/about.html");

    const memberChosen = await page.$(".team-name");
    await expect(await memberChosen.$(".discrim")).toBeFalsy();
    await memberChosen.tap();
    const expectedTag = await (await (await (await memberChosen.getProperty(
      "attributes"
    )).getProperty("data-discordtag")).getProperty("value")).jsonValue();

    const discrimHandle = await page.waitForSelector(
      `h3[data-discordtag="${expectedTag}"].team-name > .discrim`
    );

    const discrim = await (await discrimHandle.getProperty(
      "innerText"
    )).jsonValue();
    await expect(discrim).toBe(
      await expectedTag.substring(
        expectedTag.lastIndexOf("#"),
        expectedTag.length
      )
    );
    await memberChosen.tap();
    await expect(await memberChosen.$(".discrim")).toBeFalsy();
  });
});
