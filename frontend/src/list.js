import "./list.scss";
import superagent from "superagent";
import stubbedImage from "./loading.svg";
import path from "path";
import copyImage from "./copy.svg";
import openImage from "./open.svg";
import Clipboard from "clipboard";
import deleteImage from "./delete.svg";
import commonCode from "./commonCode.js";

window.addEventListener("load", async function() {
  const fileGrid = document.getElementById("file-grid");
  const files = await client.getFiles();
  for (const file of files) {
    fileGrid.appendChild(renderFile(file));
  }
});

function renderFile(filename) {
  const fileContainer = document.createElement("div");
  fileContainer.classList = "file-container col-12 col-sm-12 col-md-6 col-lg-4";
  const fileWrap = document.createElement("div");
  fileWrap.classList = "file-wrap";
  const previewContainer = document.createElement("div");
  previewContainer.classList = "preview-container";
  let previewTransport = document.createElement("img");
  previewTransport.classList = "stubbed-preview preview-transport";
  previewTransport.src = stubbedImage;
  previewContainer.attributes["data-filename"] = filename;

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
  openBtn.href = `${client.endpoint}/../i/${filename}`;
  openBtn.target = "_blank";

  const clipboard = new Clipboard(copyBtn, {
    text: function() {
      return openBtn.href;
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
      removeAlert(deleteAlert);
      deleteAlert = null;
    }
    try {
      await client.deleteFile(filename.substring(0, filename.lastIndexOf(".")));
      fileContainer.remove();
    } catch (err) {
      if (err.message == "NOT_FOUND") {
        deleteAlert = commonCode.sendAlert(
          "warning",
          "Failed to remove file because it couldn't be found. Was it deleted by someone else?"
        );
        return fileContainer.remove();
      }
      deleteAlert = commonCode.sendAlert(
        "danger",
        `An unknown error occurred while trying to remove that file: ${
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

  previewContainer.appendChild(previewTransport);
  previewTransport.addEventListener("load", function() {
    observer.observe(previewContainer);
    if (isVisible(previewContainer)) {
      console.log("Render!");
      renderRealPreview(filename, previewContainer);
    }
  });
  fileWrap.appendChild(previewContainer);
  fileWrap.appendChild(bottomRow);

  fileContainer.appendChild(fileWrap);
  return fileContainer;
}

const observer = new IntersectionObserver(
  function(entries) {
    for (const entry of entries) {
      if (
        !entry.isIntersecting ||
        entry.target.attributes["data-loaded-preview"] == "true"
      )
        return;
      renderRealPreview(entry.target.attributes["data-filename"], entry.target);
    }
  },
  {
    rootMargin: "60px"
  }
);

async function renderRealPreview(filename, previewContainer) {
  previewContainer.attributes["data-loaded-preview"] = "true";
  const req = superagent
    .get(`${client.endpoint}/../i/${filename}`)
    .responseType("blob");
  const progressBarWrap = document.createElement("div");
  const loadingBlock = document.createElement("div");
  loadingBlock.classList = "loading-block";
  progressBarWrap.classList = "progress";
  const progressBar = document.createElement("div");
  previewContainer.innerHTML = "";
  progressBar.classList =
    "progress-bar progress-bar-striped progress-bar-animated bg-primary";
  req.on("progress", function(prog) {
    progressBar.style.width = `${prog.percent || 0}%`;
  });

  progressBarWrap.appendChild(progressBar);
  loadingBlock.appendChild(progressBarWrap);
  previewContainer.appendChild(loadingBlock);

  const res = await req;
  const blobUrl = URL.createObjectURL(res.body);
  let previewTransport = null;
  if (res.body.type.startsWith("video/")) {
    previewTransport = document.createElement("video");
    previewTransport.controls = true;
    const previewSource = document.createElement("source");
    previewSource.type = res.body.type;
    previewSource.src = blobUrl;
    previewTransport.appendChild(previewSource);
    previewTransport.addEventListener("canplaythrough", function() {
      loadingBlock.remove();
      previewContainer.appendChild(previewTransport);
      // Reasonable guess
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    });
  } else if (res.body.type.startsWith("audio/")) {
    previewTransport = document.createElement("div");
    const previewImage = document.createElement("img");
    previewImage.src = audioThumbnail;
    previewImage.classList = "audio-thumb";
    const previewAudio = document.createElement("audio");
    const previewSource = document.createElement("source");
    previewAudio.controls = true;
    previewSource.type = res.body.type;
    previewSource.src = blobUrl;
    previewAudio.appendChild(previewSource);
    previewTransport.appendChild(previewImage);
    previewTransport.appendChild(previewAudio);
    previewAudio.addEventListener("canplaythrough", function() {
      loadingBlock.remove();
      previewContainer.appendChild(previewTransport);
      // Reasonable guess
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    });
  } else {
    const blobUrl = URL.createObjectURL(res.body);
    previewTransport = document.createElement("img");
    previewTransport.src = blobUrl;
    previewTransport.addEventListener("load", function() {
      loadingBlock.remove();
      URL.revokeObjectURL(blobUrl);
      previewContainer.appendChild(previewTransport);
    });
  }
  previewTransport.classList += " preview-transport";
}

function isVisible(elem) {
  const rect = elem.getBoundingClientRect();
  const windowHeight =
    window.innerHeight || document.documentElement.clientHeight;
  const windowWidth = window.innerWidth || document.documentElement.clientWidth;

  return (
    rect.top <= windowHeight &&
    rect.top + rect.height >= 0 &&
    rect.left <= windowWidth &&
    rect.left + rect.width >= 0
  );
}
