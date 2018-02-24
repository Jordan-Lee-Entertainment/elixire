import "./about.scss";

window.addEventListener("load", function() {
  const mems = Array.from(document.getElementsByClassName("team-name"));
  for (const mem of mems) {
    const tag = mem.attributes["data-discordtag"].value;
    const tagSplit = tag.split("#");
    const username = tagSplit[0];
    const discriminator = tagSplit[1];
    const oldName = mem.innerText;
    mem.addEventListener("mouseenter", function() {
      mem.innerText = username;
      const discrim = document.createElement("span");
      discrim.classList = "discrim";
      discrim.innerText = "#" + discriminator;
      mem.appendChild(discrim);
      console.log(discrim);
    });
    mem.addEventListener("mouseleave", function(ev) {
      mem.innerText = oldName;
    });
  }
});
