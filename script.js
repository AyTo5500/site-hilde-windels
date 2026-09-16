/* Hilde Windels, portfolio
   Tijdsbalk: verticaal scrollen wordt horizontaal, en het werk waar je
   staat vult de detailregel links. Geen dependencies. */

/* ---- Hamburgermenu ----
   Draait op elke pagina, dus los van de tijdsbalk hieronder. */
(function () {
  "use strict";

  var MOBIEL = "(max-width: 700px), (max-height: 520px)";
  var burger = document.getElementById("burger");
  var nav = document.getElementById("menu");
  if (!burger || !nav) return;

  function zet(open) {
    document.body.classList.toggle("is-menu-open", open);
    burger.setAttribute("aria-expanded", open ? "true" : "false");
    burger.setAttribute("aria-label", open ? "Menu sluiten" : "Menu openen");
  }

  burger.addEventListener("click", function () {
    zet(!document.body.classList.contains("is-menu-open"));
  });

  /* Een link volgen sluit het menu; bij een anker blijf je anders op een leeg scherm */
  nav.addEventListener("click", function (e) {
    if (e.target.closest("a")) zet(false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") zet(false);
  });

  /* Draai je terug naar een breed scherm, dan hoort het paneel weg te zijn */
  window.addEventListener("resize", function () {
    if (!window.matchMedia(MOBIEL).matches) zet(false);
  });

  /* ---- Balk verbergen bij naar beneden scrollen, terughalen bij omhoog ---- */
  var DREMPEL = 6;        /* px, zodat trillen van de vinger niets doet */
  var VRIJLOOP = 90;      /* px, bovenin blijft de balk altijd staan */
  var vorigeY = 0;
  var verborgen = false;

  function scrollY() {
    return window.pageYOffset || document.documentElement.scrollTop || 0;
  }

  function verberg(ja) {
    if (ja === verborgen) return;
    verborgen = ja;
    document.body.classList.toggle("is-bar-hidden", ja);
  }

  window.addEventListener("scroll", function () {
    if (document.body.classList.contains("is-menu-open")) return;
    var y = scrollY();
    var verschil = y - vorigeY;
    if (Math.abs(verschil) < DREMPEL) return;
    if (y <= VRIJLOOP) verberg(false);
    else if (verschil > 0) verberg(true);
    else verberg(false);
    vorigeY = y;
  }, { passive: true });
})();

(function () {
  "use strict";

  var list = document.getElementById("tl");
  var track = list && list.parentElement;
  var focus = document.getElementById("focus");
  if (!list || !track) return;

  var items = Array.prototype.slice.call(list.children);
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Detailregel bijwerken ----
     Elke beschrijving krijgt een onzichtbare tweelingtekst in dezelfde
     rastercel. Het vak houdt zo de hoogte van de langste beschrijving, bij
     elke schermbreedte, en de tijdsbalk eronder blijft stilstaan. */
  var live = focus && focus.querySelector(".focus__live");

  if (focus && live) {
    items.forEach(function (el) {
      var sizer = document.createElement("span");
      sizer.className = "focus__sizer";
      sizer.setAttribute("aria-hidden", "true");
      sizer.textContent = el.getAttribute("data-detail") || "";
      focus.appendChild(sizer);
    });
  }

  var current = null;
  function show(item) {
    if (!item || item === current) return;
    current = item;
    items.forEach(function (el) { el.classList.toggle("is-active", el === item); });
    if (!live) return;
    var text = item.getAttribute("data-detail") || "";
    live.classList.add("is-fading");
    window.setTimeout(function () {
      live.textContent = text;
      live.classList.remove("is-fading");
    }, reduced ? 0 : 180);
  }

  /* Het werk dat het dichtst bij de linkerrand van de balk staat */
  function nearest() {
    var edge = track.getBoundingClientRect().left + 24;
    var best = null, bestDist = Infinity;
    items.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.right < edge) return;
      var d = Math.abs(r.left - edge);
      if (d < bestDist) { bestDist = d; best = el; }
    });
    return best || items[0];
  }

  var ticking = false;
  track.addEventListener("scroll", function () {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      show(nearest());
      ticking = false;
    });
  }, { passive: true });

  /* Hover heeft voorrang op de scrollpositie */
  items.forEach(function (el) {
    el.addEventListener("mouseenter", function () { show(el); });
  });
  track.addEventListener("mouseleave", function () { show(nearest()); });

  /* ---- Muiswiel: verticaal scrollen beweegt de balk ---- */
  window.addEventListener("wheel", function (e) {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    var max = track.scrollWidth - track.clientWidth;
    if (max <= 0) return;
    var next = track.scrollLeft + e.deltaY;
    if (next < 0 || next > max) return;      /* aan het einde weer vrijgeven */
    e.preventDefault();
    track.scrollLeft = next;
  }, { passive: false });

  /* ---- Pijltjestoetsen ---- */
  window.addEventListener("keydown", function (e) {
    var step = track.clientWidth * 0.7;
    if (e.key === "ArrowRight") track.scrollBy({ left: step, behavior: reduced ? "auto" : "smooth" });
    if (e.key === "ArrowLeft") track.scrollBy({ left: -step, behavior: reduced ? "auto" : "smooth" });
  });

  show(items[0]);

  /* ---- Kijker: de foto's van een werk op ware grootte ---- */
  var kijker = document.getElementById("kijker");
  if (!kijker) return;

  var kImg = document.getElementById("kijker-img");
  var kTitel = document.getElementById("kijker-titel");
  var kDetail = document.getElementById("kijker-detail");
  var kTeller = document.getElementById("kijker-teller");
  var kVorige = document.getElementById("kijker-vorige");
  var kVolgende = document.getElementById("kijker-volgende");

  var reeks = [];
  var index = 0;
  var opener = null;

  function toon(i) {
    if (i < 0 || i >= reeks.length) return;
    index = i;
    kImg.src = reeks[i];
    kTeller.textContent = reeks.length > 1 ? (i + 1) + " / " + reeks.length : "";
    kVorige.disabled = i === 0;
    kVolgende.disabled = i === reeks.length - 1;

    /* de volgende alvast ophalen, zodat bladeren niet hapert */
    if (reeks[i + 1]) new Image().src = reeks[i + 1];
  }

  function openKijker(item) {
    reeks = (item.getAttribute("data-fotos") || "").split("|").filter(Boolean);
    if (!reeks.length) return;
    opener = item.querySelector(".tl__frame");
    kTitel.textContent = item.querySelector(".tl__title").textContent;
    kDetail.textContent = item.querySelector(".tl__year").textContent +
      ". " + (item.getAttribute("data-detail") || "");
    kImg.alt = kTitel.textContent;
    kijker.hidden = false;
    document.body.classList.add("is-kijker-open");
    toon(0);
    document.getElementById("kijker-sluit").focus();
  }

  function sluit() {
    kijker.hidden = true;
    document.body.classList.remove("is-kijker-open");
    kImg.removeAttribute("src");
    if (opener) opener.focus();
  }

  items.forEach(function (item) {
    item.querySelector(".tl__frame").addEventListener("click", function () { openKijker(item); });
  });

  document.getElementById("kijker-sluit").addEventListener("click", sluit);
  kVorige.addEventListener("click", function () { toon(index - 1); });
  kVolgende.addEventListener("click", function () { toon(index + 1); });

  /* Klikken naast de foto sluit ook */
  kijker.addEventListener("click", function (e) {
    if (e.target === kijker) sluit();
  });

  document.addEventListener("keydown", function (e) {
    if (kijker.hidden) return;
    if (e.key === "Escape") sluit();
    if (e.key === "ArrowRight") toon(index + 1);
    if (e.key === "ArrowLeft") toon(index - 1);
  });

  /* Vegen op een touchscreen */
  var startX = null;
  kijker.addEventListener("touchstart", function (e) {
    startX = e.changedTouches[0].clientX;
  }, { passive: true });
  kijker.addEventListener("touchend", function (e) {
    if (startX === null) return;
    var d = e.changedTouches[0].clientX - startX;
    startX = null;
    if (Math.abs(d) < 45) return;
    toon(d < 0 ? index + 1 : index - 1);
  }, { passive: true });
})();
