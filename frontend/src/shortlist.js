import "./shortlist.scss";
import superagent from "superagent";
import stubbedImage from "./loading.svg";
import path from "path";
import copyImage from "./copy.svg";
import openImage from "./open.svg";
import Clipboard from "clipboard";
import deleteImage from "./delete.svg";
import commonCode from "./commonCode.js";

window.addEventListener("load", async function() {
  const linkGrid = document.getElementById("link-grid");
  const { shortens } = await client.getFiles();
  for (const link of shortens) {
    linkGrid.appendChild(renderLink(link));
  }
});

function renderLink([shortLink, destLink]) {
  const linkContainer = document.createElement("div");
  linkContainer.classList = "link-container col-12"; // col-sm-12 col-md-6 col-lg-4";

  const linkWrap = document.createElement("div");
  linkWrap.classList = "link-wrap";
  const shortMapping = document.createElement("span");
  const shortL = document.createElement("a");
  shortL.href = client.endpoint + "/../s/" + shortLink;
  shortL.innerText = shortL.href;
  shortL.href = destLink;
  shortL.classList = "shortened";
  const longL = document.createElement("a");
  longL.href = destLink;
  longL.innerText = destLink;
  const arrow = document.createElement("span");
  arrow.innerText = " → ";
  shortMapping.appendChild(shortL);
  shortMapping.appendChild(arrow);
  shortMapping.appendChild(longL);
  linkWrap.appendChild(shortMapping);

  // link bar
  const iconRow = document.createElement("div");
  const bottomRow = document.createElement("div");
  const deleteBtn = document.createElement("a");
  const copyBtn = document.createElement("a");
  const openBtn = document.createElement("a");
  const copyImg = document.createElement("img");
  const openImg = document.createElement("img");
  const deleteImg = document.createElement("img");
  openImg.src = openImage;
  copyImg.src = copyImage;
  copyBtn.href = "#";
  deleteImg.src = deleteImage;
  openBtn.appendChild(openImg);

  copyBtn.appendChild(copyImg);
  openBtn.classList = "vector-btn";
  copyBtn.classList = "vector-btn";
  openBtn.href = destLink;
  openBtn.target = "_blank";

  const clipboard = new Clipboard(copyBtn, {
    text: function() {
      return shortL.innerText;
    }
  });
  clipboard.on("success", function(ev) {
    const alertId = commonCode.sendAlert("success", "Copied to clipboard!");
    setTimeout(() => commonCode.removeAlert(alertId), 1500);
  });
  copyBtn.addEventListener("click", function(ev) {
    ev.preventDefault();
  });

  bottomRow.classList = "bottom-row";
  iconRow.classList = "icon-row";
  deleteBtn.classList = "vector-btn";
  deleteBtn.appendChild(deleteImg);
  deleteBtn.href = "#";
  let deleteAlert = null;
  deleteBtn.addEventListener("click", async function(ev) {
    ev.preventDefault();
    if (deleteAlert) {
      commonCode.removeAlert(deleteAlert);
      deleteAlert = null;
    }
    try {
      await client.deleteLink(shortLink);
      linkContainer.remove();
    } catch (err) {
      if (err.message == "NOT_FOUND") {
        deleteAlert = commonCode.sendAlert(
          "warning",
          "Failed to remove shortlink because it couldn't be found. Was it deleted by someone else?"
        );
        return linkContainer.remove();
      }
      deleteAlert = commonCode.sendAlert(
        "danger",
        `An unknown error occurred while trying to remove that link: ${
          err.message
        }`
      );
      throw err;
    }
  });
  iconRow.appendChild(copyBtn);
  iconRow.appendChild(deleteBtn);
  iconRow.appendChild(openBtn);
  bottomRow.appendChild(iconRow);

  linkContainer.appendChild(linkWrap);
  linkContainer.appendChild(bottomRow);
  return linkContainer;
}
