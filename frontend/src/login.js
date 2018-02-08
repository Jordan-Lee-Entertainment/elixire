// Stub
import commonCode from "./commonCode.js";
import "./forms.scss";

window.addEventListener("load", async function() {
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const submit = document.getElementById("submit-btn");
  let alertId = null;
  submit.addEventListener("click", async function() {
    if (alertId) commonCode.removeAlert(alertId);
    try {
      const token = await commonCode.client.login(
        username.value,
        password.value
      );
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
  });
});
