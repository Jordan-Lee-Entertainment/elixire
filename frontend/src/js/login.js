// Stub
import commonCode from "./commonCode.js";
import "@/styles/forms.scss";

window.addEventListener("load", async function() {
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const keepLogin = document.getElementById("keep-logged-in");
  const keepLoginBtn = document.getElementById("save-password");
  keepLogin.addEventListener("change", function() {
    if (!keepLogin.checked) {
      return;
    }
    keepLogin.checked = false;
    const btn = document.createElement("button");
    btn.setAttribute("data-toggle", "modal");
    btn.setAttribute("data-target", "#remember-modal");
    btn.classList = "btn btn-primary";
    btn.type = "button";
    btn.style.display = "none";
    document.body.appendChild(btn);
    btn.click();
  });
  keepLoginBtn.addEventListener("click", function() {
    keepLogin.checked = true;
  });
  const submit = document.getElementById("submit-btn");
  let alertId = null;
  username.focus();
  username.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") password.focus();
  });
  submit.addEventListener("click", login);
  password.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") login();
  });
  async function login() {
    if (alertId) commonCode.removeAlert(alertId);
    try {
      const token = keepLogin.checked
        ? await commonCode.client.generateToken(password.value, username.value)
        : await commonCode.client.login(username.value, password.value);
      window.localStorage.setItem("token", token);
      window.location.pathname = window.location.hash.substring(1) || "/";
    } catch (err) {
      console.log(err.message);
      if (err.message == "BAD_AUTH") {
        alertId = commonCode.sendAlert("danger", "Bad username or password!");
      } else {
        alertId = commonCode.sendAlert(
          "danger",
          `An unknown error occurred: ${err.message}`
        );
        throw err;
      }
    }
  }

  const resetForm = document.getElementById("reset-form");
  const resetUsername = document.getElementById("reset-username");
  resetForm.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });
  const resetBtn = document.getElementById("reset-btn");
  resetBtn.addEventListener("click", async function() {
    try {
      await client.resetPassword(resetUsername.value);
      resetModalBtn.click();
    } catch (err) {
      resetUsername.setCustomValidity("Invalid username");
      resetForm.classList = "was-validated needs-validation";
    }
  });
});
