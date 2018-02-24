import "./account.scss";
import "./forms.scss";

window.addEventListener("load", async function() {
  const username = document.getElementById("profile-username");
  await window.profilePromise;
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
  const password = document.getElementById("password");
  const tokenPassword = document.getElementById("token-password");
  const generateTokenBtn = document.getElementById("generate-token");
  const generateModalBtn = document.getElementById("generate-modal-btn");
  const passwordForm = document.getElementById("password-form");
  generateModalBtn.addEventListener("click", function() {
    tokenPassword.value = password.value || "";
  });
  tokenPassword.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") {
      createToken();
    }
  });
  generateTokenBtn.addEventListener("click", function() {
    createToken();
  });
  async function createToken() {
    try {
      const token = await client.generateToken(tokenPassword.value);
      window.location.hash = token;
      window.location.pathname = "/token.html";
    } catch (err) {
      tokenPassword.setCustomValidity("Incorrect password!");
      passwordForm.classList = "was-validated needs-validation";
      tokenPassword.value = "";
      tokenPassword.focus();
      return;
    }
  }
  passwordForm.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });

  const revokePassword = document.getElementById("revoke-password");
  const revokeBtn = document.getElementById("revoke-btn");
  const stayLoggedIn = document.getElementById("stay-logged-in");
  const revokeForm = document.getElementById("revoke-form");
  revokeBtn.addEventListener("click", function() {
    revokeToken();
  });
  revokePassword.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") {
      revokeToken();
    }
  });

  async function revokeToken() {
    try {
      await client.revokeTokens(revokePassword.value);
      if (stayLoggedIn.checked) {
        console.log(client.profile.username);
        const token = await client.login(
          client.profile.username,
          revokePassword.value
        );
        console.log("BITCH TOKEN!", token);
        window.localStorage.setItem("token", token);
        // Reload
        window.location.href = "";
      }
      window.location.pathname = "/";
    } catch (err) {
      revokePassword.setCustomValidity("Incorrect password!");
      revokeForm.classList = "was-validated needs-validation";
      revokePassword.value = "";
      revokePassword.focus();
      return;
    }
  }
});
