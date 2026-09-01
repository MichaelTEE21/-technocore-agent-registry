/* Lightweight Agent Network UI. Copy + mobile nav only. */
(function () {
  "use strict";

  var toggle = document.querySelector("[data-nav-toggle]");
  var nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.getAttribute("data-copy") || "";
    var label = btn.getAttribute("data-label") || btn.textContent;
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      btn.textContent = "Select to copy";
      return;
    }
    navigator.clipboard.writeText(text).then(function () {
      btn.textContent = "Copied";
      btn.classList.add("is-copied");
      window.setTimeout(function () {
        btn.textContent = label;
        btn.classList.remove("is-copied");
      }, 1400);
    }).catch(function () {
      btn.textContent = "Select to copy";
    });
  });
})();
