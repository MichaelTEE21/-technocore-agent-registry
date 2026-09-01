/* Platform UI: sidebar, copy, wizard */
(function () {
  "use strict";

  var toggle = document.querySelector("[data-nav-toggle]");
  var sidebar = document.querySelector("[data-sidebar]");
  var nav = document.querySelector("[data-nav]");
  if (toggle && sidebar) {
    toggle.addEventListener("click", function () {
      var open = sidebar.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      if (nav) nav.classList.toggle("is-open", open);
    });
  } else if (toggle && nav) {
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

  var wizard = document.querySelector("[data-wizard]");
  if (wizard) {
    var step = 1;
    function show(n) {
      step = n;
      wizard.querySelectorAll("[data-step]").forEach(function (pane) {
        var on = Number(pane.getAttribute("data-step")) === n;
        pane.hidden = !on;
        pane.classList.toggle("is-on", on);
      });
      wizard.querySelectorAll("[data-step-btn]").forEach(function (tab) {
        tab.classList.toggle("is-on", Number(tab.getAttribute("data-step-btn")) === n);
      });
      if (n === 5) {
        var box = document.getElementById("review-box");
        if (box) {
          var fd = new FormData(wizard);
          var caps = fd.getAll("capability");
          box.innerHTML =
            "<dl class=\"facts\">" +
            "<dt>Name</dt><dd>" + (fd.get("name") || "") + "</dd>" +
            "<dt>Id</dt><dd><code>" + (fd.get("id") || "") + "</code></dd>" +
            "<dt>DID</dt><dd><code>" + (fd.get("did") || "") + "</code></dd>" +
            "<dt>Capabilities</dt><dd>" + (caps.join(", ") || "(none)") + "</dd>" +
            "<dt>Status</dt><dd>" + (fd.get("status") || "") + "</dd>" +
            "<dt>Fictional</dt><dd>" + (fd.get("fictional") ? "yes" : "no") + "</dd>" +
            "</dl>";
        }
      }
    }
    wizard.querySelectorAll("[data-next]").forEach(function (b) {
      b.addEventListener("click", function () { show(Math.min(5, step + 1)); });
    });
    wizard.querySelectorAll("[data-prev]").forEach(function (b) {
      b.addEventListener("click", function () { show(Math.max(1, step - 1)); });
    });
    wizard.querySelectorAll("[data-step-btn]").forEach(function (b) {
      b.addEventListener("click", function () {
        show(Number(b.getAttribute("data-step-btn")));
      });
    });
  }
})();
