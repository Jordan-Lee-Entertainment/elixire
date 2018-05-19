import $ from "jquery";
import "select2";
import "select2/dist/css/select2.css";
window.addEventListener("DOMContentLoaded", function() {
  // Query strings are slow
  function officialDomainAdd(domain) {
    console.log(domain);
    if (domain.id === undefined) return domain.text;
    const domainWrap = document.createElement("div");
    domainWrap.innerText = domain.text;
    if (window.client.domains.officialDomains.includes(Number(domain.id))) {
      domainWrap.classList = "official-domain";
      domainWrap.appendChild(officialTag.cloneNode(true));
    }
    return domainWrap;
  }
  $(document.getElementById("domain-selector")).select2({
    templateResult: officialDomainAdd
  });
});

const officialTag = document.createElement("span");
officialTag.innerText = "OFFICIAL";
officialTag.classList = "badge badge-bill badge-success";
