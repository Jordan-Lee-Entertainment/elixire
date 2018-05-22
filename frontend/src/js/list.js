import "@/styles/list.scss";
import superagent from "superagent";
import stubbedImage from "@/icons/loading.svg";
import path from "path";
import copyImage from "@/icons/copy.svg";
import openImage from "@/icons/open.svg";
import Clipboard from "clipboard";
import deleteImage from "@/icons/delete.svg";
import commonCode from "./commonCode.js";
import filesize from "file-size";

let loadedAll = false;

let wantsToDelete = null;
window.addEventListener("load", async function() {
  const fileGrid = document.getElementById("file-grid");
  let pageNum = 0;
  const modalShowBtn = document.getElementById("show-delete-modal");
  const deleteAlerts = {};
  const fileContainers = {};
  await loadMore(0);
  async function loadMore(pageNum = 0) {
    const frag = document.createDocumentFragment();
    const { files } = await client.getFiles(pageNum);
    const fileList = [];
    for (const shortname in files) {
      fileList.push(files[shortname]);
    }
    if (fileList.length === 0) {
      return (loadedAll = true);
    }
    const fileListSorted = fileList.sort(
      (b, a) => Number(a.snowflake) - Number(b.snowflake)
    );
    for (const file of fileListSorted) {
      fileContainers[file.shortname] = renderFile(file);
      frag.appendChild(fileContainers[file.shortname]);
    }
    fileGrid.appendChild(frag);
  }

  window.addEventListener("scroll", ev => {
    if (
      window.innerHeight + window.scrollY >= document.body.offsetHeight &&
      !loadedAll
    ) {
      // got the bottom of the page, load some more
      loadMore(++pageNum);
    }
  });

  const deleteConfirm = document.getElementById("delete-confirm");
  deleteConfirm.addEventListener("click", function() {
    actuallyDelete();
  });

  async function actuallyDelete() {
    const toDelete = wantsToDelete;
    wantsToDelete = null;
    if (deleteAlerts[toDelete]) {
      removeAlert(deleteAlerts[toDelete]);
      deleteAlerts[toDelete] = null;
    }
    try {
      await client.deleteFile(toDelete);
      fileContainers[toDelete].remove();
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
  }

  function renderFile(file) {
    const fileContainer = document.createElement("div");
    fileContainer.classList =
      "file-container col-12 col-sm-12 col-md-6 col-lg-4";
    const fileWrap = document.createElement("div");
    fileWrap.classList = "file-wrap";
    const previewContainer = document.createElement("div");
    previewContainer.classList = "preview-container";
    let previewTransport = document.createElement("img");
    previewTransport.classList = "stubbed-preview preview-transport";
    previewTransport.src = stubbedImage;
    previewContainer.attributes["data-url"] = file.thumbnail;

    const fileSize = document.createElement("div");
    fileSize.innerText = filesize(file.size).human();
    fileSize.classList = "file-size text-muted";

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
    openBtn.href = file.url;
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
    deleteBtn.addEventListener("click", function(ev) {
      ev.preventDefault();
      wantsToDelete = file.shortname;
      modalShowBtn.click();
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
        renderRealPreview(file.thumbnail, previewContainer);
      }
    });
    fileWrap.appendChild(previewContainer);
    fileWrap.appendChild(fileSize);
    fileWrap.appendChild(bottomRow);

    fileContainer.appendChild(fileWrap);
    return fileContainer;
  }
});

const observer = new IntersectionObserver(
  function(entries) {
    for (const entry of entries) {
      if (
        !entry.isIntersecting ||
        entry.target.attributes["data-loaded-preview"] == "true"
      )
        return;
      renderRealPreview(entry.target.attributes["data-url"], entry.target);
    }
  },
  {
    rootMargin: "60px"
  }
);

async function renderRealPreview(fileUrl, previewContainer) {
  previewContainer.attributes["data-loaded-preview"] = "true";
  const req = superagent.get(fileUrl).responseType("blob");
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
