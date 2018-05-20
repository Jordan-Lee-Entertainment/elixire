if (!window.location.hash.substring(1)) window.location = "/";

window.client
  .deleteConfirm(window.location.hash.substring(1))
  .then(r => (window.location = "/"));
