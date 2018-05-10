// Stub
import commonCode from "./commonCode.js";
import "@/styles/forms.scss";
const USERNAME_RE = /^[a-z]{1}[a-zA-Z0-9_]{2,19}$/;
// (Stolen from https://stackoverflow.com/a/46181)
const EMAIL_RE = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
const DISCORD_RE = /^[^#]{2,32}#\d{4}$/i;

window.addEventListener("load", async function() {
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const discord = document.getElementById("discord");
  const email = document.getElementById("email");
  const submit = document.getElementById("submit-btn");
  const form = document.getElementById("signup-form");
  form.addEventListener("submit", function(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    return false;
  });

  let alertId = null;
  username.focus();
  username.addEventListener("keydown", function(ev) {
    console.log("focus email?");
    if (ev.key == "Enter") return email.focus();
  });
  email.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") return discord.focus();
  });
  discord.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") return password.focus();
  });
  password.addEventListener("keydown", function(ev) {
    if (ev.key == "Enter") return signup();
  });

  function invalidate(elem, reason) {
    elem.setCustomValidity(reason);
    if (elem.type == "password") elem.value = "";
    let invalid = elem.parentNode.lastChild;
    invalid.innerText = reason;
    elem.focus();
  }

  submit.addEventListener("click", signup);

  const fields = [username, password, email, discord];
  async function signup() {
    if (alertId) commonCode.removeAlert(alertId);
    let valid = true;
    for (const field of fields) {
      field.setCustomValidity("");
    }
    if (!username.value.match(USERNAME_RE)) {
      invalidate(
        username,
        "Bad username, must be alphanumeric (underscores are allowed), start with a lowercase letter, and be between 3 and 20 characters"
      );
      valid = false;
    }
    if (!(password.value.length > 8 && password.value.length < 100)) {
      invalidate(password, "Passwords must be between 8 and 100 characters");
      valid = false;
    }
    if (!email.value.match(EMAIL_RE)) {
      invalidate(email, "Invalid email");
      valid = false;
    }
    if (!discord.value.match(DISCORD_RE)) {
      invalidate(discord, "Invalid DiscordTag");
      valid = false;
    }
    if (!valid) {
      form.classList = "was-validated needs-validation form";
      alertId = commonCode.sendAlert(
        "danger",
        "There was something wrong with your input, please fix the form and resubmit"
      );
      return;
    }
    try {
      await client.signup({
        username: username.value,
        password: password.value,
        email: email.value,
        discord: discord.value
      });
      window.location.pathname = window.location.hash.substring(1) || "/";
    } catch (err) {
      alertId = commonCode.sendAlert(
        "danger",
        `An unknown error occurred: ${err.message}`
      );
      throw err;
    }
  }
});
