import "./account.scss";
import "./forms.scss";

window.addEventListener("load", async function() {
  const username = document.getElementById("profile-username");
  username.innerText = window.client.profile.username;
  if (window.client.profile.admin) {
    const adminBadge = document.createElement("span");
    adminBadge.innerText = "ADMIN";
    adminBadge.classList = "badge badge-pill badge-primary";
    username.appendChild(adminBadge);
  }
  const domainSelector = document.getElementById("domain-selector");
  domainSelector.value = window.client.profile.domain;
  const quota = await window.client.getQuota();
  document.getElementById("profile-quota").innerText = quota / 1024 / 1024;
  const domains = await window.client.getDomains();
  for (const domainId in domains) {
    const domainElem = document.createElement("option");
    domainElem.value = domainId;
    domainElem.innerText = domains[domainId];
    domainSelector.appendChild(domainElem);
  }
});
