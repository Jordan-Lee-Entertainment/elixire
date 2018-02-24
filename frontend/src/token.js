import "./token.scss";

window.addEventListener("load", async function() {
  const token = window.location.hash.substring(1);
  document.getElementById("token").innerText = token;
  const kshareConfig = JSON.stringify(
    {
      name: "elixire",
      desc: "elixire is the future",
      target: `${window.client.endpoint}/upload`,
      format: "multipart-form-data",
      base64: false,
      headers: {
        Authorization: token
      },
      body: [
        {
          "__Content-Type": "/%contenttype/",
          name: "f",
          filename: "/image.%format/",
          body: "/%imagedata/"
        }
      ],
      return: ".url"
    },
    null,
    2
  );
  const sharexConfig = JSON.stringify(
    {
      Name: "Elixire",
      DestinationType: "ImageUploader",
      RequestURL: `${window.client.endpoint}/upload`,
      FileFormName: "f",
      Headers: {
        Authorization: token
      },
      URL: "$json:url$"
    },
    null,
    2
  );

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
});
