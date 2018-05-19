import "@/styles/index.scss";

const officialTag = document.createElement("span");
officialTag.innerText = "OFFICIAL";
officialTag.classList = "badge badge-bill badge-success";

window.addEventListener("DOMContentLoaded", async function() {
  const profile = await window.profilePromise;
  if (profile) {
    const action = document.getElementById("frontpage-action");
    action.innerText = "Upload";
    action.href = "/upload.html";
  }

  const domainListContainer = document.getElementById("domain-list");

  const { officialDomains, domains } = await client.getDomains();
  // I'd use Object.values but we need to support other browsers and I don't feel like finding a polyfill
  const domainList = document.getElementById("domain-ul");
  while (domainList.firstChild) {
    domainList.removeChild(domainList.firstChild);
  }

  for (const domainId in domains) {
    const domainLi = document.createElement("li");
    domainLi.innerText = domains[domainId];
    console.log("aasss");
    if ((officialDomains || []).includes(Number(domainId))) {
      console.log("uwo");
      domainLi.classList = "official-domain";
      domainLi.appendChild(officialTag.cloneNode(true));
    }
    domainList.appendChild(domainLi);
  }
  // Clone it for the infinite scroller to not break
  const clonedDomain = domainList.cloneNode(true);
  clonedDomain.removeAttribute("id");
  domainList.parentNode.appendChild(clonedDomain);
  // Round down to the nearest tenth, so 57 becomes 'over 50 domains'
  document.getElementById("relative-domain-count").innerText =
    Math.floor(Object.keys(domains).length / 10) * 10;
});
