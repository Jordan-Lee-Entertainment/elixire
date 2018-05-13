import "./commonCode.js";

const authenticatedPages = [
  "/upload.html",
  "/logout.html",
  "/account.html",
  "/list.html",
  "/shortlist.html",
  "/shorten.html"
];

const profilePromise = window.client
  .getProfile()
  .then(res => res)
  .catch(err => {
    console.log(err);
    if (err.message != "BAD_AUTH") throw err;
  });
window.profilePromise = profilePromise;

window.addEventListener("DOMContentLoaded", async function() {
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
  const profileCache = JSON.parse(
    window.localStorage.getItem("profile-cache") || null
  );
  if (profileCache) isLoggedIn(profileCache);
  window.client.profile = await profilePromise;
  console.log(window.client.profile);
  function isLoggedIn(profile) {
    document.getElementById("nav-account").innerText = profile.username;
    document.body.classList += " logged-in";
  }
  if (!window.client.profile) {
    window.localStorage.removeItem("profile-cache");
  }
  if (window.client.profile) {
    isLoggedIn(window.client.profile);
    window.localStorage.setItem(
      "profile-cache",
      JSON.stringify(window.client.profile)
    );
  } else if (authenticatedPages.includes(window.location.pathname)) {
    // Hash param is used to know where to redirect back to after login.
    document.getElementById("garfield-login").href = `/login.html#${
      window.location.pathname
    }`;
    document.body.classList += " show-garfield";
    document.title = "Access Denied | Elixire";
  }
});

window.addEventListener("error", function(event) {
  // oopsie woopsie
  console.log(event);
  document.body.classList += " error-thrown";
  const errorInfo = document.getElementById("error-info");
  errorInfo.innerText = event.message;
  const filename = document.getElementById("filename");
  filename.innerText = `${event.filename}:${event.lineno}:${event.colno}`;
});
