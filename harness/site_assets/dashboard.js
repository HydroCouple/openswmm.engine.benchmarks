/* OpenSWMM Benchmarks dashboard: color mode, tooltips, sortable and filterable tables.
 *
 * The page works without this script: charts are drawn in SVG by the site build, every
 * value a tooltip shows is also in a table, and runs expand with <details>. The color mode
 * is stored as localStorage "mode" (auto, light or dark), the key the HydroCouple manuals
 * use, so one choice carries across the dashboard and its manual.
 */
(function () {
  "use strict";
  var root = document.documentElement;
  var dark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function resolved(mode) {
    if (mode === "light" || mode === "dark") return mode;
    return dark && dark.matches ? "dark" : "light";
  }
  function apply(mode) {
    root.dataset.mode = mode;
    root.dataset.theme = resolved(mode);
    var label = "Color mode: " + mode + " (select to change)";
    document.querySelectorAll(".mode-toggle").forEach(function (b) {
      b.setAttribute("aria-label", label);
      b.title = label;
    });
  }
  function stored() {
    try { return localStorage.getItem("mode") || "auto"; } catch (e) { return "auto"; }
  }
  apply(stored());
  if (dark && dark.addEventListener) {
    dark.addEventListener("change", function () { if (root.dataset.mode === "auto") apply("auto"); });
  }

  document.addEventListener("click", function (ev) {
    var b = ev.target.closest(".mode-toggle");
    if (b) {
      var next = { auto: "light", light: "dark", dark: "auto" }[root.dataset.mode || "auto"];
      try { localStorage.setItem("mode", next); } catch (e) { /* private mode: not remembered */ }
      apply(next);
    }
    document.querySelectorAll("details.manuals[open]").forEach(function (d) {
      if (!d.contains(ev.target)) d.removeAttribute("open");
    });
    var th = ev.target.closest("th[data-sort]");
    if (th) sortBy(th);
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") {
      document.querySelectorAll("details.manuals[open]").forEach(function (d) { d.removeAttribute("open"); });
      hide();
    }
  });

  // ── tooltips: the first line leads, the rest follow; text only, never markup ──
  var tip = document.createElement("div");
  tip.className = "tip";
  tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  var current = null;

  function show(el, x, y) {
    if (el !== current) {
      var lines = (el.getAttribute("data-tip") || "").split("\n");
      tip.textContent = "";
      var head = document.createElement("strong");
      head.textContent = lines[0];
      tip.appendChild(head);
      for (var i = 1; i < lines.length; i++) {
        var row = document.createElement("div");
        row.textContent = lines[i];
        tip.appendChild(row);
      }
      current = el;
    }
    tip.classList.add("on");
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var px = x + 14, py = y + 16;
    if (px + w > window.innerWidth - 8) px = x - w - 14;
    if (py + h > window.innerHeight - 8) py = y - h - 14;
    tip.style.left = Math.max(8, px) + "px";
    tip.style.top = Math.max(8, py) + "px";
  }
  function hide() { tip.classList.remove("on"); current = null; }

  document.addEventListener("pointermove", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-tip]") : null;
    if (el) show(el, ev.clientX, ev.clientY); else if (current) hide();
  });
  document.addEventListener("focusin", function (ev) {
    var el = ev.target.closest ? ev.target.closest("[data-tip]") : null;
    if (el) { var r = el.getBoundingClientRect(); show(el, r.left + r.width / 2, r.top); }
  });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, { passive: true });

  // ── sortable tables: data-sort on a <th>, data-sort="num" for numbers ──
  function key(cell, numeric) {
    if (!cell) return numeric ? -Infinity : "";
    var v = cell.getAttribute("data-v");
    if (v === null) v = cell.textContent.trim();
    if (numeric) { var n = parseFloat(v); return isNaN(n) ? -Infinity : n; }
    return v.toLowerCase();
  }
  function sortBy(th) {
    var table = th.closest("table");
    var body = table && table.tBodies[0];
    if (!body) return;
    var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
    var numeric = th.getAttribute("data-sort") === "num";
    var dir = th.getAttribute("aria-sort") === "descending" ? "ascending" : "descending";
    th.parentNode.querySelectorAll("th").forEach(function (h) { h.removeAttribute("aria-sort"); });
    th.setAttribute("aria-sort", dir);
    var rows = Array.prototype.slice.call(body.rows);
    rows.sort(function (a, b) {
      var x = key(a.cells[idx], numeric), y = key(b.cells[idx], numeric);
      var c = x < y ? -1 : x > y ? 1 : 0;
      return dir === "ascending" ? c : -c;
    });
    rows.forEach(function (r) { body.appendChild(r); });
  }

  // ── filterable tables: <input data-filter="table-id"> ──
  document.addEventListener("input", function (ev) {
    var input = ev.target;
    if (!input.matches || !input.matches("input[data-filter]")) return;
    var table = document.getElementById(input.getAttribute("data-filter"));
    if (!table || !table.tBodies[0]) return;
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    Array.prototype.forEach.call(table.tBodies[0].rows, function (r) {
      var hit = !q || r.textContent.toLowerCase().indexOf(q) >= 0;
      r.hidden = !hit;
      if (hit) shown++;
    });
    var count = document.querySelector("[data-count-for='" + table.id + "']");
    if (count) count.textContent = shown.toLocaleString();
  });

  // ── a link to #run-… opens that run ──
  function openFromHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    var el = id && document.getElementById(id);
    if (el && el.tagName === "DETAILS") el.open = true;
  }
  window.addEventListener("hashchange", openFromHash);
  openFromHash();
})();
