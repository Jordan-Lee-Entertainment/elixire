import Client from "./Client.js";
import uuid from "uuid/v1";

window.client = new Client({
  endpoint: `${window.location.origin}/api`,
  token: window.localStorage.getItem("token")
});

function sendAlert(type, message) {
  const id = uuid();
  const alertElem = document.createElement("div");
  alertElem.classList = `alert alert-${type}`;
  alertElem.attributes.role = "alert";
  alertElem.innerText = message;
  alertElem.id = id;
  document.getElementById("alert-area").appendChild(alertElem);
  return id;
}

function removeAlert(id) {
  const elem = document.getElementById(id);
  if (elem) elem.remove();
}

export default {
  client,
  sendAlert,
  removeAlert
};
