import "./token.scss";
import uploaders from "./uploaders.js";

window.addEventListener("load", async function() {
  const token = window.location.hash.substring(1);
  document.getElementById("token").innerText = token;
  const kshareConfig = uploaders.kshareConfig(token);
  const sharexConfig = uploaders.sharexConfig(token);
  const elixireManager = uploaders.elixireManager(token);

  document.getElementById("kshare-config").innerText = kshareConfig;
  document.getElementById("sharex-config").innerText = sharexConfig;
  highlight.highlightBlock(document.getElementById("sharex-config"));
  highlight.highlightBlock(document.getElementById("kshare-config"));

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
  const elixireManagerDl = document.getElementById("elixire-manager-dl");
  elixireManagerDl.href = URL.createObjectURL(
    new Blob([elixireManager], { type: "application/json" })
  );
  elixireManagerDl.download = "elixiremanager.sh";
});
