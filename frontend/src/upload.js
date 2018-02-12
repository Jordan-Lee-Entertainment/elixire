// Stub
import commonCode from "./commonCode";
import "./upload.scss";
import filesize from "file-size";
import Clipboard from "clipboard";

window.addEventListener("load", function() {
  let error = null;
  const uploadInput = document.getElementById("upload-input");
  const dropZone = document.body.parentElement;
  const dropCard = document.getElementById("dropper-card");
  const progressBar = document.getElementById("progress-bar");
  const savedFiles = document.getElementById("saved-files");
  const uploadText = document.getElementById("uploading-text");
  dropZone.addEventListener("dragover", function(ev) {
    if (Array.from(ev.dataTransfer.items).find(item => item.kind == "file")) {
      ev.preventDefault();
      dropZone.classList = "show-popover";
    }
  });
  dropZone.addEventListener("dragleave", function(ev) {
    if (ev.screenX == 0 && ev.screenY == 0) dropZone.classList = "";
  });
  dropZone.addEventListener("drop", function(ev) {
    ev.preventDefault();
    dropZone.classList = "show-popover";
    uploadInput.files = ev.dataTransfer.files;
  });
  uploadInput.addEventListener("change", upload);
  async function upload() {
    if (!uploadInput.files.length) return console.log("gya!!");
    const fileSize = filesize(uploadInput.files[0].size).human();
    uploadText.innerText = `Uploading ${
      uploadInput.files[0].name
    } (${fileSize})`;
    if (error) {
      commonCode.removeAlert(error);
      error = null;
    }
    dropZone.classList = "show-popover";
    const uploadReq = window.client.upload(uploadInput.files[0]);
    console.log(uploadReq);
    uploadReq.on("progress", function(prog) {
      console.log(prog);
      if (prog.direction == "upload")
        progressBar.style.width = `${prog.percent || 0}%`;
    });
    try {
      const url = await uploadReq
        .then(res => res.body.url)
        .catch(err => Promise.reject(window.client.handleErr(err)));
      uploadText.innerText = "Drop to upload!";
      dropZone.classList = "";
      progressBar.style.width = "0";
      const newFile = document.createElement("div");
      const newFileIcon = document.createElement("img");
      const newFileLabel = document.createElement("span");
      const newFileSize = document.createElement("span");
      const newFileURL = document.createElement("a");
      newFileURL.href = "#";
      newFileURL.innerText = url;
      newFileIcon.src = url;
      newFileLabel.innerText = uploadInput.files[0].name;
      newFileSize.innerText = fileSize;
      newFile.classList = "saved-file";
      const clipboard = new Clipboard(newFileURL, {
        text: function() {
          return url;
        }
      });
      clipboard.on("success", function(ev) {
        const alertId = commonCode.sendAlert("success", "Copied to clipboard!");
        setTimeout(() => commonCode.removeAlert(alertId), 1500);
      });
      newFile.appendChild(newFileIcon);
      newFile.appendChild(newFileLabel);
      newFile.appendChild(newFileSize);
      newFile.appendChild(newFileURL);
      savedFiles.appendChild(newFile);
      uploadInput.value = "";
    } catch (err) {
      uploadInput.value = "";
      uploadText.innerText = "Drop to upload!";
      dropZone.classList = "";
      progressBar.style.width = "0";
      if (err.message == "BAD_IMAGE") {
        // Wrong mime-type??
        error = commonCode.sendAlert(
          "danger",
          "Bad image! You aren't allowed to upload images of that type!"
        );
      } else if (err.message == "RATELIMITED") {
        error = commonCode.sendAlert(
          "danger",
          "You have expended your weekly quota or uploading this would cause you to expend it"
        );
      } else {
        error = commonCode.sendAlert(
          "danger",
          `An unknown error occurred while trying to upload your file: ${
            err.message
          }`
        );
        throw err;
      }
    }
  }
});
