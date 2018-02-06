import "bootstrap";
import "bootstrap/scss/bootstrap.scss";

window.addEventListener("load", function() {
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
});
