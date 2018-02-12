import "bootstrap";
import "./commonCode.js";

const authenticatedPages = ["/upload.html", "/logout.html", "/account.html"];

const profilePromise = window.client
  .getProfile()
  .then(res => res)
  .catch(err => {
    console.log(err);
    if (err.message != "BAD_AUTH") throw err;
  });

window.addEventListener("load", async function() {
  console.log("Dom loaded");
  const navLinks = document.getElementsByClassName("intellectual-link");
  for (const navLink of navLinks) {
    const targetURL = navLink.attributes["data-target"].value;
    if (window.location.pathname == targetURL) {
      if (navLink.classList.contains("nav-link"))
        navLink.parentNode.classList += " active";
      continue;
    }
    navLink.href = targetURL;
  }

  const profileDisplay = document.getElementById("profile-container");
  window.client.profile = await profilePromise;
  console.log(window.client.profile);
  if (window.client.profile) {
    document.getElementById("nav-account").innerText =
      window.client.profile.username;
    document.body.classList += " logged-in";
  } else if (authenticatedPages.includes(window.location.pathname)) {
    console.log("gaygyagy", window.client.profile);
    // Hash param is used to know where to redirect back to after login.
    window.location.hash = window.location.pathname;
    window.location.pathname = "/login.html";
  }
});