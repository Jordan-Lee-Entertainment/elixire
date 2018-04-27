// Stub
import commonCode from "./commonCode";
import "@/styles/upload.scss";
import filesize from "file-size";
import Clipboard from "clipboard";
import volumeUpIcon from "@/icons/speaker.svg";
import path from "path";

window.addEventListener("load", function() {
  let error = null;
  const uploadInput = document.getElementById("upload-input");
  const dropZone = document.body.parentElement;
  const dropCard = document.getElementById("dropper-card");
  const progressBar = document.getElementById("progress-bar");
  const savedFiles = document.getElementById("saved-files");
  const uploadText = document.getElementById("uploading-text");
  document.addEventListener("paste", function(ev) {
    const items = Array.from(
      (ev.clipboardData || ev.originalEvent.clipboardData).items
    );
    const file = items.find(itm => itm.kind == "file");
    if (!file) return;
    ev.preventDefault();
    dropZone.classList = "show-popover";
    upload(file.getAsFile());
  });
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
    upload(ev.dataTransfer.files[0]);
  });
  uploadInput.addEventListener("change", () => {
    upload(uploadInput.files[0]);
  });
  async function upload(file) {
    if (!file) return;
    const fileSize = filesize(file.size).human();
    uploadText.innerText = `Uploading ${file.name} (${fileSize})`;
    if (error) {
      commonCode.removeAlert(error);
      error = null;
    }
    dropZone.classList = "show-popover";
    const uploadReq = window.client.upload(file);
    let deleteAlert = null;
    uploadReq.on("progress", function(prog) {
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
      const newFileLabel = document.createElement("span");
      const newFileSize = document.createElement("span");
      const newFileURL = document.createElement("a");
      const deleteFile = document.createElement("a");
      deleteFile.href = "#";
      deleteFile.classList = "delete-btn greyscale-icon";
      deleteFile.innerHTML = "&times;";
      deleteFile.addEventListener("click", async function() {
        if (deleteAlert) {
          commonCode.removeAlert(deleteAlert);
          deleteAlert = null;
        }
        try {
          const fileName = path.basename(url);
          await client.deleteFile(
            fileName.substring(0, fileName.lastIndexOf("."))
          );
          newFile.remove();
        } catch (err) {
          if (err.message == "NOT_FOUND") {
            deleteAlert = commonCode.sendAlert(
              "warning",
              "Failed to remove file because it couldn't be found. Was it deleted by someone else?"
            );
            return newFile.remove();
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

      newFileURL.href = url;
      newFileURL.addEventListener("click", function(ev) {
        ev.preventDefault();
      });
      newFileURL.innerText = url;

      let newFileIcon = null;
      if (file.type.startsWith("video/")) {
        const imageBlob = new Blob([file], { type: file.type });
        const objectUrl = URL.createObjectURL(imageBlob);
        newFileIcon = document.createElement("video");
        newFileIcon.loop = true;
        newFileIcon.muted = true;
        const source = document.createElement("source");
        source.type = file.type;
        source.src = objectUrl;
        newFileIcon.appendChild(source);
        newFileIcon.addEventListener("loadeddata", function() {
          newFileIcon.play();
        });
      } else if (file.type.startsWith("audio/")) {
        newFileIcon = document.createElement("img");
        newFileIcon.src = volumeUpIcon;
      } else {
        const imageBlob = new Blob([file], { type: file.type });
        const objectUrl = URL.createObjectURL(imageBlob);
        newFileIcon = document.createElement("img");
        newFileIcon.src = objectUrl;
        newFileIcon.addEventListener("load", function() {
          URL.revokeObjectURL(objectUrl);
        });
      }
      newFileIcon.classList = "new-file-icon";
      newFileLabel.innerText = file.name;
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
      newFile.appendChild(deleteFile);
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
