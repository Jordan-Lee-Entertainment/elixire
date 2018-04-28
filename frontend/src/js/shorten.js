import "@/styles/shorten.scss";
import common from "./commonCode.js";

window.addEventListener("load", function() {
  const shortenedUrls = {};
  const shortenBtn = document.getElementById("shorten-btn");
  const longLink = document.getElementById("long-link");
  let warn = null;
  let validitySet = false;
  longLink.addEventListener("keydown", function(ev) {
    if (validitySet) {
      longLink.classList = "form-control";
      validitySet = false;
    }
    if (ev.key == "Enter") shorten();
  });
  shortenBtn.addEventListener("click", shorten);
  async function shorten() {
    const url = longLink.value;
    if (!url) return;
    if (Object.values(shortenedUrls).find(shortUrl => url.startsWith(shortUrl)))
      return;
    if (shortenedUrls[url]) {
      longLink.value = shortenedUrls[url];
      return;
    }
    if (warn) {
      window.removeAlert(warn);
    }
    validitySet = true;
    try {
      const shortUrl = await client.shortenUrl(url);
      shortenedUrls[url] = shortUrl;
      longLink.value = shortUrl;
      longLink.classList = "form-control is-valid";
    } catch (err) {
      longLink.classList = "form-control is-invalid";
      if (err.message == "RATELIMITED") {
        warn = common.sendAlert(
          "danger",
          "You have reached the maximum amount of shortened URLs!"
        );
        return;
      }
      warn = common.sendAlert(
        "danger",
        `An unknown error occurred: ${err.message}`
      );
      throw err;
    }
  }
});
