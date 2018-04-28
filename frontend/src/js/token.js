import "@/styles/token.scss";
import uploaders from "./uploaders.js";
import "highlightjs/styles/solarized-light.css";

window.addEventListener("load", async function() {
  const token = window.location.hash.substring(1);
  document.getElementById("token").innerText = token;
  const kshareConfig = uploaders.kshareConfig(token);
  const sharexConfig = uploaders.sharexConfig(token);

  document.getElementById("kshare-config").innerText = kshareConfig;
  document.getElementById("sharex-config").innerText = sharexConfig;

  const kshareDl = document.getElementById("kshare-dl");
  kshareDl.href = URL.createObjectURL(
    new Blob([kshareConfig], { type: "application/json" })
  );
  kshareDl.download = "elixire.uploader";
  const sharexDl = document.getElementById("sharex-dl");
  sharexDl.href = URL.createObjectURL(
    new Blob([sharexConfig], { type: "application/json" })
  );
  sharexDl.download = "elixire.sxcu";
  // This way we can still await the highlight deps
  window.profilePromise.then(() => {
    const elixireManager = uploaders.elixireManager(token);
    const elixireManagerDl = document.getElementById("elixire-manager-dl");
    elixireManagerDl.href = URL.createObjectURL(
      new Blob([elixireManager], { type: "application/json" })
    );
    elixireManagerDl.download = "elixiremanager.sh";
  });

  const highlight = await import("highlightjs/highlight.pack.js");
  highlight.highlightBlock(document.getElementById("sharex-config"));
  highlight.highlightBlock(document.getElementById("kshare-config"));
  console.log("highlighted!");
});
