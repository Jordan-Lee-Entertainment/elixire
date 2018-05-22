import "@/styles/album.scss";

window.addEventListener("load", function() {
  const player = document.getElementById("player");
  let hasMovingClass = false;
  let timeout = null;
  let hovering = false;
  player.addEventListener("mouseover", function(ev) {
    if (
      hovering == ev.target ||
      ev.target.classList.toString().includes("hoverable")
    )
      hovering = ev.target;
    else hovering = false;
  });
  player.addEventListener("mouseout", function(ev) {
    if (
      hovering == ev.target ||
      ev.target.classList.toString().includes("hoverable")
    )
      hovering = ev.target;
    else hovering = false;
  });
  player.addEventListener("mousemove", function(ev) {
    interaction();
  });
  const others = document.getElementById("others");
  others.addEventListener("scroll", function() {
    interaction();
  });
  function interaction() {
    if (!hasMovingClass) {
      player.classList = "player mouse-moving";
      hasMovingClass = true;
    }
    if (timeout) clearTimeout(timeout);
    if (!hovering)
      timeout = setTimeout(() => {
        hasMovingClass = false;
        player.classList = "player";
      }, 2500);
  }

  const miniPlayer = document.createElement("div");
  miniPlayer.classList = "mini-player hoverable";
  const image = document.createElement("img");
  image.classList = "hoverable";

  function renderPreview(frag, index, source) {
    const newMiniPlayer = miniPlayer.cloneNode();
    const newImage = image.cloneNode();
    newImage.src = `//${domain}/t/s${source}`;
    newMiniPlayer.appendChild(newImage);
    newMiniPlayer.addEventListener("click", function() {
      selected = Number(index);
      doBig();
    });
    frag.appendChild(newMiniPlayer);
  }

  let selected = 0;
  const fragment = document.createDocumentFragment();
  const [domain, remainder] = window.location.hash.substring(1).split(";"); // yeah yeah I know bad idea whatever
  if (!remainder) window.location.href = "/";
  const files = remainder.split(",");
  if (!files.length) window.location.href = "/";
  const bigImage = document.getElementById("big-image");
  doBig();
  for (const index in files) {
    renderPreview(fragment, index, files[index]);
  }
  others.appendChild(fragment);
  function doBig() {
    bigImage.src = `//${domain}/i/${files[selected]}`;
  }

  const left = document.getElementById("left-arrow");
  const right = document.getElementById("right-arrow");
  left.addEventListener("click", function() {
    if (files[Number(selected) - 1]) {
      selected--;
      doBig();
    }
  });
  right.addEventListener("click", function() {
    if (files[Number(selected) + 1]) {
      selected++;
      doBig();
    }
  });
});
