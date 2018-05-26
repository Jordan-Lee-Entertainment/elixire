import "@/styles/account.scss";
import "@/styles/forms.scss";
import common from "./commonCode.js";

const EMAIL_RE = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;

window.addEventListener("DOMContentLoaded", async function() {
  const username = document.getElementById("profile-username");
  await window.profilePromise;
  username.innerText = window.client.profile.username;
  if (window.client.profile.admin) {
    const adminBadge = document.createElement("span");
    adminBadge.innerText = "ADMIN";
    adminBadge.classList = "badge badge-pill badge-primary";
    username.parentNode.appendChild(adminBadge);
  }
  const quota = await window.client.getQuota();
  document.getElementById("profile-quota").innerText =
    quota.limit / 1024 / 1024;
  document.getElementById("profile-used").innerText = Math.round(
    quota.used / 1024 / 1024 || 0
  );
  document.getElementById("s-profile-used").innerText = quota.shortenused || 0;
  document.getElementById("s-profile-quota").innerText = quota.shortenlimit;
  const { domains, officialDomains } = await window.client.getDomains();
  console.log("Fetched domains:", domains);
  const options = Object.entries(domains).map(
    ([id, domain]) => new Option(domain, id, false, false)
  );
  const domainSelector = document.getElementById("domain-selector");
  for (const option of options) {
    domainSelector.appendChild(option);
  }
  domainSelector.value = window.client.profile.domain;
  const wildcard = document.getElementById("wildcard");
  wildcard.value = window.client.profile.subdomain || "";
  const email = document.getElementById("email");
  email.value = window.client.profile.email || "";
  function checkDomainSelector() {
    if (domains[domainSelector.value].startsWith("*.")) {
      domainSelector.parentNode.classList = "form-group show-wildcard";
    } else {
      domainSelector.parentNode.classList = "form-group";
    }
  }
  try {
    checkDomainSelector();
  } catch (err) {}
  // This would be an addEventListener but jQuery is garbage
  domainSelector.onchange = checkDomainSelector;
  const tokenPassword = document.getElementById("token-password");
  const generateTokenBtn = document.getElementById("generate-token");
  const passwordForm = document.getElementById("password-form");

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

  const deleteForm = document.getElementById("delete-form");
  deleteForm.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });

  const deletePassword = document.getElementById("delete-password");
  const deleteBtn = document.getElementById("delete-btn");
  const deleteAccountBtn = document.getElementById("delete-modal-btn");
  deleteBtn.addEventListener("click", function() {
    deleteAccount();
  });
  deletePassword.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") {
      deleteAccount();
    }
  });
  async function deleteAccount() {
    try {
      const emailToken = await client.deleteAccount(deletePassword.value);
      deleteAccountBtn.click();
    } catch (err) {
      deletePassword.setCustomValidity("Invalid Password!");
      deleteForm.classList = "needs-validation was-validated";
    }
  }

  async function revokeToken() {
    try {
      await client.revokeTokens(revokePassword.value);
      if (stayLoggedIn.checked) {
        const token = await client.login(
          client.profile.username,
          revokePassword.value
        );
        window.localStorage.setItem("token", token);
        // Reload
        window.location.href = "";
        return;
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

  let errorBox = null;
  const submitBtn = document.getElementById("submit-btn");
  const newPassword = document.getElementById("new-password1");
  const password = document.getElementById("password");
  const newPassword2 = document.getElementById("new-password2");
  let domainId = client.profile.domain;
  let wildcardVal = client.profile.subdomain;
  let emailVal = client.profile.email;
  submitBtn.addEventListener("click", async function() {
    if (errorBox) common.removeAlert(errorBox);
    let error = false;
    if (newPassword.value && newPassword2.value != newPassword.value) {
      newPassword2.setCustomValidity("Doesn't match!");
      error = true;
    }
    if (!password.value) {
      password.setCustomValidity("Invalid password!");
      error = true;
    }
    if (!email.value.match(EMAIL_RE)) {
      email.setCustomValidity("Invalid email!");
      error = true;
    }
    updateForm.classList = "was-validated needs-validation form-wrap";
    if (error) return;

    const modifications = {};

    if (newPassword.value) modifications.new_password = newPassword.value;
    if (domainSelector.value != domainId) {
      modifications.domain = Number(domainSelector.value);
    }
    if (
      wildcard.value != wildcardVal &&
      domains[domainSelector.value].startsWith("*.")
    )
      modifications.subdomain = wildcard.value;

    if (!Object.keys(modifications).length) return; // No changes to be made
    modifications.password = password.value;

    if (email.value != emailVal) {
      modifications.email = email.value;
    }

    try {
      await client.updateAccount(modifications);
      errorBox = common.sendAlert("success", "Your changes have been saved!");
      if (modifications.domain) domainId = modifications.domain;
      if (modifications.subdomain) wildcardVal = modifications.subdomain;
      if (modifications.email) emailVal = modifications.email;
    } catch (err) {
      if (err.message == "BAD_AUTH") {
        password.setCustomValidity("Invalid password!");
        updateForm.classList = "was-validated needs-validation form-wrap";
      } else {
        errorBox = common.sendAlert("danger", "An unknown error occurred");
        throw err;
      }
      return;
    }
    if (modifications.new_password) {
      window.localStorage.setItem("token", client.token);
      window.location.href = "";
    }
  });

  const updateForm = document.getElementById("update-form");
  updateForm.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });

  const queuePosition = document.getElementById("queue-position");
  const dumpWrap = document.getElementById("datadump");
  const fileNum = document.getElementById("file-num");
  const fileMax = document.getElementById("file-max");
  const dumpBtn = document.getElementById("request-data");
  dumpBtn.addEventListener("click", async function() {
    await client.requestDump();
    await renderDataDump();
  });
  async function renderDataDump() {
    const dumpStatus = await client.dumpStatus();
    if (dumpStatus.state == "not_in_queue") {
      dumpWrap.classList = "state-none";
    } else if (dumpStatus.state == "in_queue") {
      dumpWrap.classList = "state-requested";
      queuePosition.innerText = ordinal(dumpStatus.position);
    } else if (dumpStatus.state == "processing") {
      dumpWrap.classList = "state-processing";
      fileNum.innerText = dumpStatus.files_done;
      fileMax.innerText = dumpStatus.total_files;
    }
  }
  await renderDataDump();
});
