window.addEventListener("DOMContentLoaded", async function() {
  const profile = await window.profilePromise;
  if (profile) {
    const action = document.getElementById("frontpage-action");
    action.innerText = "Upload";
    action.href = "/upload.html";
  }

  const domainListContainer = document.getElementById("domain-list");

  const domains = await client.getDomains();
  // I'd use Object.values but we need to support other browsers and I don't feel like finding a polyfill
  const domainArr = Object.keys(domains).map(k => domains[k]);
  const domainList = document.getElementById("domain-ul");
  while (domainList.firstChild) {
    domainList.removeChild(domainList.firstChild);
  }
  for (const domain of domainArr) {
    const domainLi = document.createElement("li");
    domainLi.innerText = domain;
    domainList.appendChild(domainLi);
  }
  // Clone it for the infinite scroller to not break
  const clonedDomain = domainList.cloneNode(true);
  clonedDomain.removeAttribute("id");
  domainList.parentNode.appendChild(clonedDomain);
  // Round down to the nearest tenth, so 57 becomes 'over 50 domains'
  document.getElementById("relative-domain-count").innerText =
    Math.floor(domainArr.length / 10) * 10;
});
