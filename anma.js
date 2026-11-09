/* 10 Kasım anma ekranı: yalnız Türkiye saatiyle 10 Kasım 2026'da, ilk girişte bir kez gösterilir.
   Test: sayfa adresine ?anma=1 ekle. Fotoğraf: Wikimedia Commons, kamu malı (1930). */
(function () {
  var GUN = "2026-11-10", ANAHTAR = "anma-2026-11-10";
  var test = /[?&]anma=1/.test(location.search);
  function bugunTR() {
    try {
      return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
    } catch (e) {
      return new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10);
    }
  }
  if (!test) {
    if (bugunTR() !== GUN) return;
    try { if (localStorage.getItem(ANAHTAR)) return; localStorage.setItem(ANAHTAR, "1"); } catch (e) {}
  }
  var dil = (document.documentElement.lang || "tr").slice(0, 2);
  var alt = {
    en: "Remembering Mustafa Kemal Atatürk, founder of the Republic of Türkiye.",
    fr: "En mémoire de Mustafa Kemal Atatürk, fondateur de la République de Turquie.",
    es: "En memoria de Mustafa Kemal Atatürk, fundador de la República de Turquía."
  }[dil] || "";
  var kapatYazi = { en: "Continue to site", fr: "Accéder au site", es: "Ir al sitio" }[dil] || "Siteye geç";

  var css = "#anma{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.94);display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;transition:opacity .8s}" +
    "#anma.acik{opacity:1}" +
    "#anma figure{margin:0;max-width:380px;width:100%;text-align:center;color:#eee;font-family:Georgia,'Times New Roman',serif}" +
    "#anma img{width:100%;max-height:62vh;object-fit:cover;object-position:top;filter:grayscale(1);border:1px solid #444;box-shadow:0 0 40px rgba(255,255,255,.08)}" +
    "#anma .ad{margin:16px 0 2px;font-size:1.05rem;letter-spacing:.12em;text-transform:uppercase;color:#bbb}" +
    "#anma .yil{font-size:.9rem;color:#888;margin:0 0 12px}" +
    "#anma .soz{font-size:1.5rem;margin:0;color:#fff}" +
    "#anma .alt{font-size:.85rem;color:#999;margin:8px 0 0;font-family:system-ui,sans-serif}" +
    "#anma button{margin-top:20px;background:none;border:1px solid #666;color:#ccc;padding:8px 18px;border-radius:4px;cursor:pointer;font:inherit;font-size:.9rem}" +
    "#anma button:hover,#anma button:focus-visible{border-color:#fff;color:#fff}";

  function kur() {
    var s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    var d = document.createElement("div");
    d.id = "anma"; d.setAttribute("role", "dialog"); d.setAttribute("aria-modal", "true"); d.setAttribute("aria-label", "10 Kasım");
    d.innerHTML = '<figure><img src="/ataturk.jpg" width="520" height="681" alt="Mustafa Kemal Atatürk">' +
      '<figcaption><p class="ad">Mustafa Kemal Atatürk</p><p class="yil">1881 – 10 Kasım 1938</p>' +
      '<p class="soz">Saygı ve özlemle anıyoruz.</p>' + (alt ? '<p class="alt">' + alt + "</p>" : "") +
      '<button type="button">' + kapatYazi + "</button></figcaption></figure>";
    document.body.appendChild(d);
    var eskiTasma = document.body.style.overflow; document.body.style.overflow = "hidden";
    function kapat() {
      d.classList.remove("acik");
      setTimeout(function () { d.remove(); document.body.style.overflow = eskiTasma; }, 800);
      document.removeEventListener("keydown", tus);
    }
    function tus(e) { if (e.key === "Escape") kapat(); }
    d.querySelector("button").addEventListener("click", kapat);
    d.addEventListener("click", function (e) { if (e.target === d) kapat(); });
    document.addEventListener("keydown", tus);
    requestAnimationFrame(function () { d.classList.add("acik"); d.querySelector("button").focus(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", kur); else kur();
})();
