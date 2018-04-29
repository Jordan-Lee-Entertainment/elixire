import $ from "jquery";
import "select2";
import "select2/dist/css/select2.css";
window.addEventListener("DOMContentLoaded", function() {
  // Query strings are slow
  $(document.getElementById("domain-selector")).select2();
});
