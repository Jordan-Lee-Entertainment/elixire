import "./about.scss";

window.addEventListener("load", function() {
  const mems = Array.from(document.getElementsByClassName("team-name"));
  for (const mem of mems) {
    const tag = mem.attributes["data-discordtag"].value;
    const tagSplit = tag.split("#");
    const username = tagSplit[0];
    const discriminator = tagSplit[1];
    const oldName = mem.innerText;
    mem.addEventListener("mouseenter", show);
    let shown = false;
    function show(ev) {
      if (touchTap(ev)) {
        return;
      }
      shown = true;
      mem.innerText = username;
      const discrim = document.createElement("span");
      discrim.classList = "discrim";
      discrim.innerText = "#" + discriminator;
      mem.appendChild(discrim);
    }
    mem.addEventListener("mouseleave", hide);
    function hide(ev) {
      if (touchTap(ev)) {
        return;
      }
      shown = false;
      mem.innerText = oldName;
    }
    mem.addEventListener("click", function(ev) {
      if (!touchTap(ev)) return;
      if (shown) hide();
      else show();
    });
  }
});

function touchTap(ev) {
  return ev && ev.sourceCapabilities && ev.sourceCapabilities.firesTouchEvents;
}
