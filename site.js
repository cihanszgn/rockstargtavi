/* CTRL+A GAME — tek betik. Harici kütüphane yok. Her parça kendi işaretini (data-*) arar; sayfada yoksa çalışmaz. */
(function () {
  'use strict';
  var d = document, H = d.documentElement, B = d.body;
  if (!B) return;
  var DIL = B.getAttribute('data-dil') || 'tr';
  var M = {};
  try { M = JSON.parse(d.getElementById('cag-metin').textContent); } catch (e) { M = {}; }
  var MAC = /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent || '');
  var DIALOG = typeof HTMLDialogElement === 'function';

  // ------------------------------------------------------------ yardımcılar
  function $(s, k) { return (k || d).querySelector(s); }
  function $$(s, k) { return Array.prototype.slice.call((k || d).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function norm(s) {
    return String(s || '').toLowerCase().replace(/ı/g, 'i').normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9\u3400-\u9fff]+/g, ' ').trim();
  }
  function yaziyor(el) {
    if (!el || !el.tagName) return false;
    var t = el.tagName;
    return t === 'INPUT' || t === 'TEXTAREA' || t === 'SELECT' || el.isContentEditable;
  }
  var depo = {
    al: function (k, s) { try { return (s ? sessionStorage : localStorage).getItem(k); } catch (e) { return null; } },
    koy: function (k, v, s) { try { (s ? sessionStorage : localStorage).setItem(k, v); } catch (e) { /* özel pencere */ } }
  };
  function birim(n, i) { return n + ' ' + (n === 1 ? (M.tekil || [])[i] : (M.birim || [])[i]); }
  function gunYaz(iso, uzun) {
    var p = String(iso).slice(0, 10).split('-');
    var t = new Date(+p[0], +p[1] - 1, +p[2], 12);
    if (isNaN(t)) return iso;
    return t.toLocaleDateString(DIL, uzun ? { day: 'numeric', month: 'long', year: 'numeric' } : { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function bin(x, ayrac) { return String(x).replace(/\B(?=(\d{3})+(?!\d))/g, ayrac); }
  function fiyatYaz(n, para) {
    var s = { USD: '$', TRY: '\u20ba', EUR: '\u20ac', GBP: '\u00a3' }[para || 'USD'] || para;
    var p = Number(n).toFixed(2).split('.'), t = parseInt(p[0], 10), g;
    if (DIL === 'en') return s + bin(t, ',') + '.' + p[1];
    if (DIL === 'tr') g = bin(t, '.');
    else if (DIL === 'fr') g = bin(t, '\u202f');
    else g = t >= 10000 ? bin(t, '.') : String(t);
    return g + ',' + p[1] + '\u00a0' + s;
  }
  function yuzdeYaz(n) {
    n = Math.floor(Number(n) + 0.5);
    if (DIL === 'tr') return '\u2212%' + n;
    if (DIL === 'en') return '\u2212' + n + '%';
    return '\u2212' + n + '\u00a0%';
  }
  function disariTikla(el, kapat) {
    d.addEventListener('click', function (e) { if (!el.contains(e.target)) kapat(); });
  }
  // hareket: kullanıcı azaltılmış hareket istiyorsa hiçbir süs çalışmaz
  var azMq = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : null;
  function az() { return !!(azMq && azMq.matches); }
  var INCE = !!(window.matchMedia && matchMedia('(hover: hover) and (pointer: fine)').matches);
  var IO = typeof IntersectionObserver === 'function';
  var ANIM = typeof Element.prototype.animate === 'function';
  // öğe ekrana girip çıkınca haber ver (IO yoksa hep görünür say)
  function gozle(el, cb, kenar) {
    if (!IO) { cb(true); return; }
    new IntersectionObserver(function (g) { cb(g[g.length - 1].isIntersecting); }, { rootMargin: kenar || '0px' }).observe(el);
  }

  // ------------------------------------------------------------ tema
  function temaUygula(t) {
    H.setAttribute('data-tema', t);
    $$('meta[name="theme-color"]').forEach(function (m) { m.setAttribute('content', t === 'acik' ? '#F3F5F9' : '#0B101B'); });
    $$('[data-tema-dugme]').forEach(function (b) { b.setAttribute('aria-pressed', t === 'acik' ? 'true' : 'false'); });
  }
  function temaDegistir(e) {
    var t = H.getAttribute('data-tema') === 'acik' ? 'koyu' : 'acik';
    var yap = function () { temaUygula(t); depo.koy('cag-tema', t); d.dispatchEvent(new CustomEvent('cag-tema')); };
    if (!d.startViewTransition || az() || d.hidden) { yap(); return; }
    // dairesel açılış: tıklanan noktadan (klavyede düğmenin ortasından) yayılır
    var x = innerWidth - 48, y = 30;
    var dg = e && e.target && e.target.closest ? e.target.closest('[data-tema-dugme]') : $('.ust [data-tema-dugme]');
    if (e && e.clientX) { x = e.clientX; y = e.clientY; }
    else if (dg) { var r = dg.getBoundingClientRect(); if (r.width) { x = r.left + r.width / 2; y = r.top + r.height / 2; } }
    var yc = Math.ceil(Math.sqrt(Math.pow(Math.max(x, innerWidth - x), 2) + Math.pow(Math.max(y, innerHeight - y), 2)));
    H.classList.add('tema-gecis');
    var bitir = function () { H.classList.remove('tema-gecis'); };
    var vt;
    try { vt = d.startViewTransition(yap); } catch (er) { bitir(); yap(); return; }
    vt.ready.then(function () {
      H.animate({ clipPath: ['circle(0px at ' + x + 'px ' + y + 'px)', 'circle(' + yc + 'px at ' + x + 'px ' + y + 'px)'] },
        { duration: 560, easing: 'cubic-bezier(.45,0,.2,1)', pseudoElement: '::view-transition-new(root)' });
    }).catch(bitir);
    vt.finished.then(bitir, bitir);
  }
  temaUygula(H.getAttribute('data-tema') || 'koyu');
  d.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-tema-dugme]')) temaDegistir(e);
  });
  if (MAC) $$('[data-mod]').forEach(function (k) { k.textContent = '\u2318'; });

  // ------------------------------------------------------------ dil seçici
  $$('img.kg-img').forEach(function (img) {
    img.addEventListener('error', function () { img.remove(); });
    if (img.complete && !img.naturalWidth) img.remove();
  });
  (function () {
    var kayit = d.getElementById('cag-dil-onerileri'), diller;
    if (!kayit || depo.al('cag-dil-oneri')) return;
    try { diller = JSON.parse(kayit.textContent); } catch (e) { return; }
    var tercih = navigator.languages || [navigator.language || ''];
    for (var i = 0; i < tercih.length; i++) {
      var kod = String(tercih[i]).toLowerCase().split('-')[0];
      if (!diller[kod]) continue;
      // En yüksek öncelikli desteklenen dil zaten görüntüleniyorsa önerme.
      if (kod === DIL) return;
      var t = diller[kod], bant = d.createElement('aside'), a = d.createElement('a'), kapat = d.createElement('button');
      bant.className = 'dil-oneri';
      bant.lang = t.lang;
      a.href = t.url;
      a.textContent = t.metin + ' → ' + t.ac;
      a.addEventListener('click', function () { depo.koy('cag-dil-oneri', kod); });
      kapat.type = 'button';
      kapat.textContent = '×';
      kapat.setAttribute('aria-label', t.kapat);
      kapat.addEventListener('click', function () { depo.koy('cag-dil-oneri', 'kapali'); bant.remove(); });
      bant.appendChild(a);
      bant.appendChild(kapat);
      B.insertBefore(bant, B.firstChild);
      return;
    }
  })();
  $$('details.dil, details.nav-grup').forEach(function (el) {
    disariTikla(el, function () { el.open = false; });
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && el.open) { el.open = false; $('summary', el).focus(); }
    });
  });

  // ------------------------------------------------------------ pencere (dialog) ortak
  function pencere(sinif, baslik) {
    var dl = d.createElement('dialog');
    dl.className = sinif;
    dl.setAttribute('aria-label', baslik);
    dl.addEventListener('click', function (e) { if (e.target === dl) dl.close(); });
    B.appendChild(dl);
    return dl;
  }
  function pencereBas(baslik) {
    return '<div class="pencere-bas"><h2>' + esc(baslik) + '</h2><button type="button" class="kapat-dugme" data-kapat aria-label="' +
      esc(M.kapat) + '">\u00d7</button></div>';
  }
  function kapatBagla(dl) {
    dl.addEventListener('click', function (e) { if (e.target.closest('[data-kapat]')) dl.close(); });
  }
  function acikPencere() { return $('dialog[open]'); }

  // ------------------------------------------------------------ arama paleti
  var palet = null, pGiris, pListe, pDizin = null, pYukleniyor = false, pSecili = 0, pOgeler = [];
  var ARA_SVG = (function () { var s = $('[data-ara-ac] svg'); return s ? s.outerHTML : ''; })();

  function paletKur() {
    palet = pencere('palet', M.ara_aria || 'Search');
    palet.innerHTML = '<div class="palet-ic"><div class="palet-ust">' + ARA_SVG +
      '<input class="palet-giris" type="text" role="combobox" aria-expanded="true" aria-controls="palet-liste" aria-autocomplete="list"' +
      ' autocomplete="off" spellcheck="false" aria-label="' + esc(M.ara_aria) + '" placeholder="' + esc(M.palet_yer) + '"><kbd>Esc</kbd></div>' +
      '<ul class="palet-liste" id="palet-liste" role="listbox" aria-label="' + esc(M.ara_aria) + '"></ul>' +
      '<div class="palet-alt"><span>' + esc(M.palet_ipucu) + '</span><span><kbd>Esc</kbd> ' + esc(M.k_kapat) + '</span></div></div>';
    pGiris = $('.palet-giris', palet);
    pListe = $('.palet-liste', palet);
    pGiris.addEventListener('input', function () { pSecili = 0; paletCiz(); });
    pGiris.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!pOgeler.length) return;
        pSecili = (pSecili + (e.key === 'ArrowDown' ? 1 : -1) + pOgeler.length) % pOgeler.length;
        paletSec();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        paletAc(pOgeler[pSecili]);
      }
    });
    pListe.addEventListener('mousemove', function (e) {
      var li = e.target.closest('[data-i]');
      if (li && +li.getAttribute('data-i') !== pSecili) { pSecili = +li.getAttribute('data-i'); paletSec(); }
    });
    pListe.addEventListener('click', function (e) {
      var li = e.target.closest('[data-i]');
      if (li) paletAc(pOgeler[+li.getAttribute('data-i')]);
    });
  }
  function paletDizin() {
    if (pDizin || pYukleniyor) return;
    pYukleniyor = true;
    fetch(B.getAttribute('data-ara'), { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) { pDizin = Array.isArray(j) ? j : []; if (palet && palet.open) paletCiz(); })
      .catch(function () { pDizin = []; })
      .then(function () { pYukleniyor = false; });
  }
  function hizliOgeler() {
    var o = (M.bolumler || []).map(function (b) { return { t: b[1], u: b[2], tus: String(b[0]) }; });
    o.push({ t: M.k_tema, f: temaDegistir, tus: 'T' });
    $$('.ust .dil-liste a:not([aria-current])').forEach(function (a) {
      o.push({ t: a.textContent.replace(/^[A-Z]{2}/, '').trim(), u: a.getAttribute('href'), tus: a.getAttribute('hreflang').toUpperCase() });
    });
    return o;
  }
  function paletBul(q) {
    var tok = norm(q).split(' ').filter(Boolean), nq = norm(q), sonuc = [];
    (pDizin || []).forEach(function (x) {
      var hay = x.x || '';
      for (var i = 0; i < tok.length; i++) if (hay.indexOf(tok[i]) < 0) return;
      var bt = norm(x.t), puan = 0;
      if (bt === nq) puan += 6;
      if (bt.indexOf(nq) === 0) puan += 4;
      else if ((' ' + bt).indexOf(' ' + tok[0]) >= 0) puan += 2;
      if (x.k === 'sayfa') puan += 1.5;
      if (x.k === 'gta') puan += 0.5;
      sonuc.push({ x: x, p: puan });
    });
    sonuc.sort(function (a, b) { return b.p - a.p || String(b.x.d || '').localeCompare(String(a.x.d || '')); });
    return sonuc.slice(0, 9).map(function (s) {
      return { t: s.x.t, u: s.x.u, tur: (M.tur_ara || {})[s.x.k] || s.x.k, d: s.x.d };
    });
  }
  function paletCiz() {
    var q = pGiris.value.trim(), h = [];
    if (!q) {
      pOgeler = hizliOgeler();
      h.push('<li class="palet-grup" role="presentation">' + esc(M.palet_hizli) + '</li>');
    } else {
      pOgeler = paletBul(q);
    }
    pOgeler.forEach(function (o, i) {
      h.push('<li class="palet-oge" role="option" id="po-' + i + '" data-i="' + i + '" aria-selected="false">' +
        (o.tus ? '<kbd class="tus">' + esc(o.tus) + '</kbd>' : '<span class="palet-tur">' + esc(o.tur) + '</span>') +
        '<span class="palet-ad">' + esc(o.t) + '</span>' +
        (o.d ? '<span class="palet-tarih">' + esc(gunYaz(o.d)) + '</span>' : '') + '</li>');
    });
    if (q && !pOgeler.length) {
      h.push('<li class="palet-bos" role="presentation">' + esc(pDizin ? String(M.palet_bos || '').replace('{q}', q) : '\u2026') + '</li>');
    }
    pListe.innerHTML = h.join('');
    if (pSecili >= pOgeler.length) pSecili = 0;
    paletSec();
  }
  function paletSec() {
    $$('.palet-oge', pListe).forEach(function (li) {
      var on = +li.getAttribute('data-i') === pSecili;
      li.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) li.scrollIntoView({ block: 'nearest' });
    });
    if (pOgeler.length) pGiris.setAttribute('aria-activedescendant', 'po-' + pSecili);
    else pGiris.removeAttribute('aria-activedescendant');
  }
  function paletAc(o) {
    if (!o) return;
    if (o.f) { palet.close(); o.f(); return; }
    palet.close();
    location.href = o.u;
  }
  function paletiAc() {
    if (!DIALOG) return;
    if (!palet) paletKur();
    var ac = acikPencere();
    if (ac && ac !== palet) ac.close();
    if (!palet.open) palet.showModal();
    pGiris.value = '';
    pSecili = 0;
    paletDizin();
    paletCiz();
    pGiris.focus();
  }
  d.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-ara-ac]')) { e.preventDefault(); paletiAc(); }
  });

  // ------------------------------------------------------------ kısayol yardımı
  var yardim = null;
  function yardimAc() {
    if (!DIALOG) return;
    if (!yardim) {
      yardim = pencere('yardim', M.kisayollar);
      var mod = MAC ? '\u2318' : 'Ctrl';
      var satirlar = [
        ['<kbd>' + mod + '</kbd><kbd>K</kbd><kbd>/</kbd>', M.k_ara],
        ['<kbd>0</kbd>\u2013<kbd>' + (M.bolumler || []).reduce(function (a, b) { return Math.max(a, +b[0] || 0); }, 0) + '</kbd>', M.k_bolum],
        ['<kbd>T</kbd>', M.k_tema],
        ['<kbd>?</kbd>', M.k_yardim],
        ['<kbd>Esc</kbd>', M.k_kapat]
      ];
      var bolum = (M.bolumler || []).map(function (b) { return '<kbd>' + b[0] + '</kbd> ' + esc(b[1]); }).join('<br>');
      yardim.innerHTML = pencereBas(M.kisayollar) + '<dl class="kisayol-liste">' + satirlar.map(function (s) {
        return '<dt>' + s[0] + '</dt><dd>' + esc(s[1]) + (s[1] === M.k_bolum ? '<br><small>' + bolum + '</small>' : '') + '</dd>';
      }).join('') + '</dl>';
      kapatBagla(yardim);
    }
    var ac = acikPencere();
    if (ac && ac !== yardim) ac.close();
    if (!yardim.open) yardim.showModal();
  }

  // ------------------------------------------------------------ mobil çekmece
  var cekmece = null;
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-cekmece]');
    if (!a || !DIALOG) return;
    e.preventDefault();
    if (!cekmece) {
      cekmece = pencere('cekmece', M.menu);
      var kollar = $$('.alt .alt-kol').map(function (k) { return k.outerHTML; }).join('');
      cekmece.innerHTML = pencereBas(M.menu) + '<div class="cekmece-ic"><div class="cekmece-arac">' +
        '<button type="button" class="dugme" data-ara-ac>' + ARA_SVG + esc(M.ara_aria) + '</button>' +
        '<button type="button" class="dugme" data-tema-dugme>' + esc(M.k_tema) + '</button></div>' + kollar + '</div>';
      kapatBagla(cekmece);
      cekmece.addEventListener('click', function (ev) { if (ev.target.closest('a[href]')) cekmece.close(); });
    }
    cekmece.showModal();
  });

  // ------------------------------------------------------------ klavye kısayolları
  d.addEventListener('keydown', function (e) {
    var k = e.key;
    if ((e.ctrlKey || e.metaKey) && !e.altKey && (k === 'k' || k === 'K')) { e.preventDefault(); paletiAc(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || yaziyor(e.target) || acikPencere()) return;
    if (k === '/') { e.preventDefault(); paletiAc(); }
    else if (k === '?') { e.preventDefault(); yardimAc(); }
    else if (k === 't' || k === 'T') { temaDegistir(); }
    else if (/^[0-9]$/.test(k)) {
      var b = (M.bolumler || []).filter(function (x) { return String(x[0]) === k; })[0];
      if (b) location.href = b[2];
    }
  });

  // ------------------------------------------------------------ takip listesi
  function takipAl() {
    try { var o = JSON.parse(depo.al('cag-takip') || '{}'); return o && typeof o === 'object' ? o : {}; } catch (e) { return {}; }
  }
  function takipKoy(o) {
    depo.koy('cag-takip', JSON.stringify(o));
    takipBoya();
    d.dispatchEvent(new CustomEvent('cag-takip'));
  }
  function takipBoya() {
    var o = takipAl();
    $$('[data-takip]').forEach(function (b) {
      var on = Object.prototype.hasOwnProperty.call(o, b.getAttribute('data-takip'));
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      var y = $('[data-takip-yazi]', b);
      if (y) y.textContent = on ? M.takipte : M.takip_et;
      if (on) b.title = M.takip_birak; else b.removeAttribute('title');
    });
  }
  d.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-takip]');
    if (!b) return;
    var o = takipAl(), k = b.getAttribute('data-takip');
    if (Object.prototype.hasOwnProperty.call(o, k)) delete o[k]; else o[k] = b.getAttribute('data-ad') || k;
    takipKoy(o);
  });
  window.addEventListener('storage', function (e) { if (e.key === 'cag-takip') { takipBoya(); d.dispatchEvent(new CustomEvent('cag-takip')); } });

  // ana sayfa: "Takip ettiklerin"
  (function () {
    var blok = $('#takip'), liste = $('[data-takip-liste]'), ipucu = $('[data-takip-ipucu]');
    if (!blok || !liste) return;
    var veri = {};
    try { veri = JSON.parse($('#takip-veri').textContent); } catch (e) { veri = {}; }
    function ciz() {
      var o = takipAl(), anahtar = Object.keys(o), h = [];
      anahtar.forEach(function (k) {
        var v = veri[k] || { a: o[k] };
        var ad = v.a || o[k];
        var p = [];
        if (v.t) {
          p.push('<p>' + esc(M.cikis_tarihi) + ': <a href="' + esc(v.u || '#') + '"><time datetime="' + esc(v.t) + '">' + esc(gunYaz(v.t, true)) +
            '</time></a> <span class="kalan" data-kalan data-hedef="' + esc(v.t) + '" data-gecti="' + esc(M.cikti) + '"></span></p>');
        } else if (v.u) {
          p.push('<p><a href="' + esc(v.u) + '">' + esc(M.cikis_tarihi) + '</a></p>');
        }
        (v.h || []).slice(0, 1).forEach(function (x) { p.push('<p>' + esc(M.son_haber) + ': <a href="' + esc(x[1]) + '">' + esc(x[0]) + '</a></p>'); });
        if (v.s) p.push('<p>' + esc(M.radar) + ': <a href="' + esc(v.s[1]) + '">' + esc(v.s[0]) + '</a></p>');
        if (!p.length) p.push('<p>' + esc(M.bilgi_yok) + '</p>');
        h.push('<li><h3>' + esc(ad) + '</h3>' + p.join('') +
          '<button type="button" class="takip" data-takip="' + esc(k) + '" data-ad="' + esc(ad) + '" aria-pressed="true">' +
          '<span class="takip-isaret" aria-hidden="true"></span><span data-takip-yazi>' + esc(M.takipte) + '</span></button></li>');
      });
      var odak = d.activeElement && liste.contains(d.activeElement);
      liste.innerHTML = h.join('');
      blok.hidden = !h.length;
      if (ipucu) ipucu.hidden = !!h.length;
      takipBoya();
      kalanlar();
      if (odak) { var h2 = $('h2', blok); if (h2 && h.length) { h2.tabIndex = -1; h2.focus(); } }
    }
    d.addEventListener('cag-takip', ciz);
    ciz();
  })();
  takipBoya();

  // ------------------------------------------------------------ geri sayım ve kalan süreler
  function kalanMetin(el) {
    var h = el.getAttribute('data-hedef') || '', gecti = el.getAttribute('data-gecti') || M.gecti;
    if (/^\d{4}-\d{2}-\d{2}$/.test(h)) {
      var p = h.split('-'), hedef = new Date(+p[0], +p[1] - 1, +p[2]), bugun = new Date();
      bugun.setHours(0, 0, 0, 0);
      var g = Math.round((hedef - bugun) / 864e5);
      return g < 0 ? gecti : g === 0 ? M.bugun : birim(g, 0);
    }
    var z = Date.parse(h);
    if (isNaN(z)) return el.textContent;
    var sn = Math.floor((z - Date.now()) / 1000);
    if (sn <= 0) return gecti;
    var gun = Math.floor(sn / 86400), saat = Math.floor(sn % 86400 / 3600), dk = Math.floor(sn % 3600 / 60);
    if (gun >= 2) return birim(gun, 0);
    if (gun === 1) return birim(1, 0) + ' ' + birim(saat, 1);
    if (saat >= 1) return birim(saat, 1) + (dk ? ' ' + birim(dk, 2) : '');
    return birim(Math.max(dk, 1), 2);
  }
  function kalanlar() {
    $$('[data-kalan]').forEach(function (el) { var t = kalanMetin(el); if (el.textContent !== t) el.textContent = t; });
  }
  function iki(n) { return n < 10 ? '0' + n : String(n); }
  var sayaclar = $$('[data-geri-sayim]');
  function sayacCiz() {
    var simdi = Date.now();
    sayaclar = sayaclar.filter(function (el) {
      var z = Date.parse(el.getAttribute('data-hedef'));
      if (isNaN(z)) return false;
      var sn = Math.floor((z - simdi) / 1000);
      if (sn <= 0) {
        el.innerHTML = '<p class="gs-bitti">' + esc(el.getAttribute('data-bitti')) + '</p>';
        el.removeAttribute('role');
        var kok = el.closest('section') || d;
        var h1 = $('[data-cikti-h1]', kok), p = $('[data-cikti-p]', kok);
        if (h1) h1.textContent = h1.getAttribute('data-cikti-h1');
        if (p) p.innerHTML = p.getAttribute('data-cikti-p');
        return false;
      }
      var deg = { g: Math.floor(sn / 86400), s: iki(Math.floor(sn % 86400 / 3600)), d: iki(Math.floor(sn % 3600 / 60)), sn: iki(sn % 60) };
      $$('[data-b]', el).forEach(function (b) { var v = String(deg[b.getAttribute('data-b')]); if (b.textContent !== v) b.textContent = v; });
      return true;
    });
  }

  // Epic: süresi dolanı gizle, başlayanı "şu an" yap, saati yerel saate çevir
  var yerelBicim = (function () {
    try { return new Intl.DateTimeFormat(DIL, { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' }); } catch (e) { return null; }
  })();
  function epicGuncelle() {
    var simdi = Date.now();
    $$('[data-epic]').forEach(function (li) {
      var bas = Date.parse(li.getAttribute('data-bas')), bit = Date.parse(li.getAttribute('data-bit'));
      if (bit && simdi >= bit) { li.hidden = true; return; }
      if (li.getAttribute('data-durum') === 'yakinda' && bas && simdi >= bas) {
        li.setAttribute('data-durum', 'simdi');
        var c = $('[data-durum-yazi]', li);
        if (c) { c.textContent = M.simdi; c.className = 'cip cip-ucretsiz'; }
        var ke = $('[data-kalan-etiket]', li), kl = $('[data-kalan]', li), se = $('[data-saat-etiket]', li), tm = $('time[data-yerel]', li);
        if (ke) ke.textContent = M.bitise;
        if (kl) kl.setAttribute('data-hedef', li.getAttribute('data-bit'));
        if (se) se.textContent = M.bitis;
        if (tm) tm.setAttribute('datetime', li.getAttribute('data-bit'));
      }
    });
    if (yerelBicim) {
      $$('time[data-yerel]').forEach(function (t) {
        var z = Date.parse(t.getAttribute('datetime'));
        if (!isNaN(z)) { var s = yerelBicim.format(new Date(z)); if (t.textContent !== s) t.textContent = s; }
      });
    }
  }
  epicGuncelle();
  kalanlar();
  if (sayaclar.length) { sayacCiz(); setInterval(sayacCiz, 1000); }
  setInterval(function () { epicGuncelle(); kalanlar(); }, 30000);

  // ------------------------------------------------------------ liste süzgeçleri (haber, söylenti, takvim)
  $$('[data-suzgec-kok]').forEach(function (kok) {
    var form = $('[data-suzgec]', kok);
    if (!form) return;
    var ogeler = $$('[data-oge]', kok), gruplar = $$('[data-grup]', kok), bos = $('[data-bos]', kok), sonuc = $('[data-sonuc]', kok);
    var temizle = $('[data-temizle]', form), ara = $('[data-arama]', form), takipli = $('[data-takipli]', form);
    var secim = {};
    var alanlar = {};
    $$('button[data-alan]', form).forEach(function (b) { alanlar[b.getAttribute('data-alan')] = true; });

    function dugmeBoya() {
      $$('button[data-alan]', form).forEach(function (b) {
        var a = b.getAttribute('data-alan');
        b.setAttribute('aria-pressed', (secim[a] || '') === b.getAttribute('data-deger') ? 'true' : 'false');
      });
    }
    function urlYaz() {
      var p = new URLSearchParams();
      if (ara && ara.value.trim()) p.set('q', ara.value.trim());
      Object.keys(secim).forEach(function (a) { if (secim[a]) p.set(a, secim[a]); });
      if (takipli && takipli.checked) p.set('takip', '1');
      var qs = p.toString();
      try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash); } catch (e) { /* file:// */ }
    }
    var hazir = false, bosMetin = null;
    function uygula(yazma) {
      var q = norm(ara ? ara.value : ''), tok = q ? q.split(' ') : [], tk = takipAl(), n = 0;
      var tkVar = takipli && takipli.checked;
      // FLIP: yerini değiştiren öğe eski yerinden kayar, yeni görünen belirir (yalnız ekrandakiler)
      var flip = hazir && ANIM && !az() && ogeler.length <= 600;
      if (flip) ogeler.forEach(function (o) { o._r = o.hidden ? null : o.getBoundingClientRect(); });
      ogeler.forEach(function (o) {
        var ok = true;
        Object.keys(secim).forEach(function (a) {
          if (!ok || !secim[a]) return;
          var v = o.getAttribute('data-' + a) || '';
          if (a === 'platform') { if ((' ' + v + ' ').indexOf(' ' + secim[a] + ' ') < 0) ok = false; }
          else if (v !== secim[a]) ok = false;
        });
        if (ok && tok.length) {
          var x = o.getAttribute('data-ara') || '';
          for (var i = 0; i < tok.length; i++) if (x.indexOf(tok[i]) < 0) { ok = false; break; }
        }
        if (ok && tkVar && !Object.prototype.hasOwnProperty.call(tk, o.getAttribute('data-oyun'))) ok = false;
        o.hidden = !ok;
        if (ok) n++;
      });
      gruplar.forEach(function (g) { g.hidden = !$$('[data-oge]', g).some(function (o) { return !o.hidden; }); });
      if (flip) {
        var vh = innerHeight;
        ogeler.forEach(function (o) {
          var r0 = o._r; o._r = null;
          if (o.hidden) return;
          var r1 = o.getBoundingClientRect();
          if (!r1.height || r1.bottom < 0 || r1.top > vh) return;
          if (r0 && r0.height && Math.abs(r0.top - r1.top) < vh) {
            var dx = r0.left - r1.left, dy = r0.top - r1.top;
            if (Math.abs(dx) + Math.abs(dy) < 1) return;
            o.animate([{ transform: 'translate(' + dx + 'px,' + dy + 'px)' }, { transform: 'none' }],
              { duration: 380, easing: 'cubic-bezier(.2,.8,.2,1)' });
          } else {
            o.animate([{ opacity: 0, transform: 'translateY(10px) scale(.98)' }, { opacity: 1, transform: 'none' }],
              { duration: 300, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'backwards' });
          }
        });
      }
      hazir = true;
      var aktif = !!(q || tkVar || Object.keys(secim).some(function (a) { return secim[a]; }));
      if (bos) {
        bos.hidden = n > 0 || !ogeler.length;
        // adedi 0 olan bir seçenek (ör. henüz yalanlanan söylenti yok) seçildiyse "şu an kayıt yok" açıklaması
        var sifir = bos.getAttribute('data-sifir'), sifirSecili = !n && sifir && $$('button[data-adet="0"]', form).some(function (b) {
          var a = b.getAttribute('data-alan');
          return !!secim[a] && secim[a] === b.getAttribute('data-deger');
        });
        if (bosMetin === null) bosMetin = bos.textContent;
        var yeni = sifirSecili ? sifir : bosMetin;
        if (bos.textContent !== yeni) bos.textContent = yeni;
      }
      if (temizle) temizle.hidden = !aktif;
      if (sonuc) sonuc.textContent = n === 1 ? sonuc.getAttribute('data-bir') : String(sonuc.getAttribute('data-cok') || '').replace('{n}', n);
      if (aktif) $$('details[data-grup]', kok).forEach(function (g) { if (!g.hidden) g.open = true; });
      dugmeBoya();
      if (!yazma) urlYaz();
    }
    // adres çubuğundaki süzgeçleri uygula
    var ilk = new URLSearchParams(location.search);
    if (ara && ilk.get('q')) ara.value = ilk.get('q');
    Object.keys(alanlar).forEach(function (a) {
      var v = ilk.get(a);
      if (v && $('button[data-alan="' + a + '"][data-deger="' + v.replace(/[^a-z0-9-]/g, '') + '"]', form)) secim[a] = v;
    });
    if (takipli && ilk.get('takip') === '1') takipli.checked = true;

    form.addEventListener('submit', function (e) { e.preventDefault(); });
    form.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-alan]');
      if (b) { secim[b.getAttribute('data-alan')] = b.getAttribute('data-deger'); uygula(); return; }
      if (e.target.closest('[data-temizle]')) {
        secim = {};
        if (ara) ara.value = '';
        if (takipli) takipli.checked = false;
        uygula();
        if (ara) ara.focus();
      }
    });
    if (ara) ara.addEventListener('input', function () { uygula(); });
    if (takipli) takipli.addEventListener('change', function () { uygula(); });
    d.addEventListener('cag-takip', function () { if (takipli && takipli.checked) uygula(true); });
    uygula(true);
  });

  // ------------------------------------------------------------ haber listesi: ızgara / liste görünümü (tercih saklanır)
  var gorDugmeler = $$('[data-gorunum]');
  function gorBoya() {
    var g = H.getAttribute('data-gor') === 'liste' ? 'liste' : 'izgara';
    gorDugmeler.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-gorunum') === g ? 'true' : 'false'); });
  }
  if (gorDugmeler.length) {
    gorBoya();
    gorDugmeler.forEach(function (b) {
      b.addEventListener('click', function () {
        var g = b.getAttribute('data-gorunum');
        if (g === 'liste') H.setAttribute('data-gor', 'liste'); else H.removeAttribute('data-gor');
        depo.koy('cag-gorunum', g);
        gorBoya();
      });
    });
  }

  // ------------------------------------------------------------ takvim dosyası (.ics)
  function icsKac(s) { return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n'); }
  function katla(s) {
    var out = '', n = 0, enc = window.TextEncoder ? new TextEncoder() : null;
    for (var i = 0; i < s.length; i++) {
      var ch = s.charAt(i);
      if (ch >= '\ud800' && ch <= '\udbff' && i + 1 < s.length) { ch += s.charAt(++i); }
      var b = enc ? enc.encode(ch).length : 1;
      if (n + b > 74) { out += '\r\n '; n = 1; }
      out += ch;
      n += b;
    }
    return out;
  }
  function icsYap(ogeler) {
    var z = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
    var s = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//CTRL+A GAME//' + DIL.toUpperCase(), 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH'];
    ogeler.forEach(function (o) {
      var p = o.tarih.split('-');
      var son = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + 1)).toISOString().slice(0, 10).replace(/-/g, '');
      s.push('BEGIN:VEVENT', 'UID:' + o.id + '@ctrl-agame.com', 'DTSTAMP:' + z, 'DTSTART;VALUE=DATE:' + o.tarih.replace(/-/g, ''),
        'DTEND;VALUE=DATE:' + son, 'SUMMARY:' + icsKac(o.ad + ' (' + M.cikis_tarihi + ')'), 'URL:' + o.url, 'TRANSP:TRANSPARENT', 'END:VEVENT');
    });
    s.push('END:VCALENDAR');
    return s.map(katla).join('\r\n') + '\r\n';
  }
  function indir(ad, metin) {
    var blob = new Blob([metin], { type: 'text/calendar;charset=utf-8' });
    var a = d.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = ad;
    B.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function icsOge(b) {
    return { id: b.getAttribute('data-id'), ad: b.getAttribute('data-ad'), tarih: b.getAttribute('data-tarih'), url: b.getAttribute('data-url') };
  }
  d.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-ics]');
    if (b) { var o = icsOge(b); indir('ctrl-agame-' + o.id + '.ics', icsYap([o])); return; }
    var t = e.target.closest && e.target.closest('[data-ics-takip]');
    if (!t) return;
    var tk = takipAl(), bugun = new Date(), gorulen = {}, liste = [];
    bugun.setHours(0, 0, 0, 0);
    $$('[data-ics]').forEach(function (x) {
      var li = x.closest('[data-oyun]'), o = icsOge(x), p = o.tarih.split('-');
      if (!li || gorulen[o.id] || !Object.prototype.hasOwnProperty.call(tk, li.getAttribute('data-oyun'))) return;
      if (new Date(+p[0], +p[1] - 1, +p[2]) < bugun) return;
      gorulen[o.id] = 1;
      liste.push(o);
    });
    var durum = $('[data-ics-durum]');
    if (!liste.length) { if (durum) durum.textContent = M.ics_bos; return; }
    if (durum) durum.textContent = '';
    indir('ctrl-agame-takip.ics', icsYap(liste));
  });

  // ------------------------------------------------------------ paylaş
  $$('[data-paylas-web]').forEach(function (b) { if (navigator.share) b.hidden = false; });
  d.addEventListener('click', function (e) {
    var k = e.target.closest && e.target.closest('[data-kopyala]');
    var w = e.target.closest && e.target.closest('[data-paylas-web]');
    if (!k && !w) return;
    var kutu = (k || w).closest('.kutu') || d, durum = $('[data-paylas-durum]', kutu);
    if (w) {
      var h1 = $('h1');
      navigator.share({ title: h1 ? h1.textContent : d.title, url: location.href.split('#')[0].split('?')[0] }).catch(function () { /* vazgeçildi */ });
      return;
    }
    panoya(k.getAttribute('data-kopyala'), function () {
      if (durum) { durum.textContent = M.kopyalandi; setTimeout(function () { durum.textContent = ''; }, 4000); }
    });
  });
  function panoya(metin, bitti) {
    var yedek = function () {
      var t = d.createElement('textarea');
      t.value = metin; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
      B.appendChild(t); t.select();
      try { if (d.execCommand('copy')) bitti(); } catch (er) { /* yok */ }
      t.remove();
    };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(metin).then(bitti, yedek); else yedek();
  }

  // ------------------------------------------------------------ indirimler (CheapShark canlı, yoksa anlık görüntü)
  var CS = 'https://www.cheapshark.com/api/1.0/';
  function csGetir(yol) {
    var anahtar = 'cag-cs:' + yol, eski = depo.al(anahtar, true);
    if (eski) {
      try { var o = JSON.parse(eski); if (Date.now() - o.z < 6e5) return Promise.resolve(o); } catch (e) { /* bozuk */ }
    }
    var denetim = new AbortController();
    var zaman = setTimeout(function () { denetim.abort(); }, 10000);
    return fetch(CS + yol, { referrerPolicy: 'no-referrer', credentials: 'omit', signal: denetim.signal })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (v) { var o = { z: Date.now(), v: v }; depo.koy(anahtar, JSON.stringify(o), true); return o; })
      .finally(function () { clearTimeout(zaman); });
  }
  function sayi(x) { var n = parseFloat(x); return isNaN(n) ? 0 : n; }
  function sade(f) {
    return {
      dealID: String(f.dealID || ''), gameID: String(f.gameID || ''), title: String(f.title || ''), storeID: String(f.storeID || ''),
      salePrice: Math.round(sayi(f.salePrice) * 100) / 100, normalPrice: Math.round(sayi(f.normalPrice) * 100) / 100,
      savings: Math.round(sayi(f.savings) * 100) / 100, metacriticScore: parseInt(f.metacriticScore, 10) || 0,
      releaseDate: parseInt(f.releaseDate, 10) || 0, dealRating: sayi(f.dealRating), thumb: String(f.thumb || ''),
      enDusuk: f.enDusuk
    };
  }

  $$('[data-firsat]').forEach(function (kok) {
    var mod = kok.getAttribute('data-firsat'), boyut = parseInt(kok.getAttribute('data-boyut'), 10) || 60;
    var liste = $('[data-firsat-liste]', kok), bos = $('[data-firsat-bos]', kok), durum = $('[data-firsat-durum]', kok);
    var daha = $('[data-firsat-daha]', kok), form = $('[data-firsat-form]', kok), betik = $('script[type="application/json"]', kok);
    if (!liste || !betik) return;
    var veri;
    try { veri = JSON.parse(betik.textContent); } catch (e) { return; }
    var mag = {};
    (veri.magazalar || []).forEach(function (m) { mag[String(m.id)] = m; });
    var izinli = Object.keys(mag);
    if (!izinli.length) return;
    var epicAd = {};
    (veri.epic || []).forEach(function (t) { epicAd[t] = 1; });
    var bosIlk = bos ? bos.textContent : '';
    var sayfa = 0, sonListe = [], gorulen = {}, istekNo = 0, enDusuk = {};

    function satir(f) {
      var m = mag[f.storeID] || { ad: '', ikon: '' };
      var dusuk = f.enDusuk != null && f.salePrice <= f.enDusuk + 0.005;
      var resim = /^https:\/\//.test(f.thumb)
        ? '<img class="f-resim" src="' + esc(f.thumb) + '" width="120" height="45" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
        : '<span class="f-resim" aria-hidden="true"></span>';
      var ikon = m.ikon ? '<img class="f-ikon" src="' + esc(m.ikon) + '" width="16" height="16" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">' : '';
      var bedava = f.salePrice <= 0.001;
      return '<li class="firsat">' + resim + '<div class="f-bilgi">' +
        '<a class="f-ad" href="https://www.cheapshark.com/redirect?dealID=' + esc(f.dealID) + '" rel="noopener nofollow">' + esc(f.title) + '</a>' +
        '<span class="f-alt"><span class="f-magaza">' + ikon + esc(m.ad) + '</span>' +
        (dusuk ? '<span class="rozet">' + esc(M.rozet_dusuk) + '</span>' : '') + '</span></div><div class="f-fiyat">' +
        (f.savings >= 1 ? '<span class="f-yuzde">' + yuzdeYaz(f.savings) + '</span>' : '') +
        (f.normalPrice > f.salePrice ? '<del>' + fiyatYaz(f.normalPrice) + '</del>' : '') +
        '<strong>' + (bedava ? esc(M.ucretsiz) : fiyatYaz(f.salePrice)) + '</strong></div></li>';
    }
    function secenek() {
      var s = { q: '', magaza: '', fiyat: '', indirim: '', sira: 'Deal Rating', dusuk: false };
      if (form) {
        s.q = form.elements.q.value.trim();
        s.magaza = form.elements.magaza.value;
        s.fiyat = form.elements.fiyat.value;
        s.indirim = form.elements.indirim.value;
        s.sira = form.elements.sira.value || 'Deal Rating';
        s.dusuk = form.elements.dusuk.checked;
      }
      return s;
    }
    function aktifMi(s) { return !!(s.q || s.magaza || s.fiyat || s.indirim || s.dusuk); }
    function yerelSuz(ls, s) {
      var tok = norm(s.q).split(' ').filter(Boolean);
      return ls.filter(function (f) {
        if (mod === 'ucretsiz' && epicAd[norm(f.title)]) return false;
        if (s.magaza && f.storeID !== s.magaza) return false;
        if (s.fiyat && f.salePrice > +s.fiyat) return false;
        if (s.indirim && f.savings < +s.indirim) return false;
        if (s.dusuk && !(f.enDusuk != null && f.salePrice <= f.enDusuk + 0.005)) return false;
        if (tok.length) { var t = norm(f.title); for (var i = 0; i < tok.length; i++) if (t.indexOf(tok[i]) < 0) return false; }
        return true;
      });
    }
    function sirala(ls, sira) {
      var k = {
        'Savings': function (a, b) { return b.savings - a.savings; },
        'Price': function (a, b) { return a.salePrice - b.salePrice; },
        'Metacritic': function (a, b) { return b.metacriticScore - a.metacriticScore; },
        'Recent': function (a, b) { return b.releaseDate - a.releaseDate; }
      }[sira];
      return k ? ls.slice().sort(k) : ls;
    }
    // yüklenirken iskelet satırlar: liste boşsa yerine, "daha fazla"da sona eklenir
    function iskelet(n) {
      var h = '';
      for (var i = 0; i < n; i++) {
        h += '<li class="firsat iskelet" aria-hidden="true"><span class="f-resim"></span><div class="f-bilgi">' +
          '<span class="isk" style="width:' + (52 + (i * 17) % 38) + '%"></span><span class="isk isk-kisa"></span></div>' +
          '<div class="f-fiyat"><span class="isk isk-fiyat"></span></div></li>';
      }
      return h;
    }
    function iskeletAt() {
      $$('.iskelet', liste).forEach(function (li) { li.parentNode.removeChild(li); });
      liste.removeAttribute('aria-busy');
    }
    function ciz(ls, s, ekle) {
      var gorunen = mod === 'mini' ? ls.slice(0, boyut) : ls;
      var h = gorunen.map(satir).join('');
      iskeletAt();
      if (ekle) liste.insertAdjacentHTML('beforeend', h); else liste.innerHTML = h;
      var bosMu = !liste.children.length;
      if (bos) {
        bos.hidden = !bosMu;
        bos.textContent = bosMu && s && aktifMi(s) ? M.bos_filtre : bosIlk;
      }
    }
    function durumYaz(t) { if (durum) durum.textContent = t; }
    function saatYaz(z) { return new Date(z).toLocaleTimeString(DIL, { hour: '2-digit', minute: '2-digit' }); }
    function yedekGoster(s) {
      var ls = (veri.firsatlar || []).map(sade);
      ls = sirala(yerelSuz(ls, s), s.sira);
      ciz(ls, s);
      if (daha) daha.hidden = true;
      var g = String(veri.guncel || '').slice(0, 10);
      durumYaz(g ? String(M.hata_canli || '').replace('{tarih}', gunYaz(g, true)) : '');
    }
    function enDusukGetir(ls, no) {
      var ids = ls.map(function (f) { return f.gameID; }).filter(function (id) { return id && !(id in enDusuk); });
      var parcalar = [];
      for (var i = 0; i < ids.length; i += 25) parcalar.push(ids.slice(i, i + 25));
      return Promise.all(parcalar.map(function (p) {
        return csGetir('games?ids=' + p.join(',')).then(function (o) {
          Object.keys(o.v || {}).forEach(function (id) {
            var c = o.v[id] && o.v[id].cheapestPriceEver;
            if (c && c.price != null) enDusuk[id] = sayi(c.price);
          });
        }).catch(function () { /* rozet yok */ });
      })).then(function () {
        if (no !== istekNo) return;
        ls.forEach(function (f) { if (f.gameID in enDusuk) f.enDusuk = enDusuk[f.gameID]; });
      });
    }
    function yukle(ekle) {
      var s = secenek(), no = ++istekNo;
      if (!ekle) { sayfa = 0; sonListe = []; gorulen = {}; }
      var p = new URLSearchParams();
      p.set('storeID', s.magaza || izinli.join(','));
      p.set('pageSize', String(mod === 'mini' ? 12 : boyut));
      p.set('pageNumber', String(sayfa));
      p.set('sortBy', mod === 'ucretsiz' ? 'Deal Rating' : s.sira);
      if (mod === 'ucretsiz') p.set('upperPrice', '0');
      else { p.set('onSale', '1'); if (s.fiyat) p.set('upperPrice', s.fiyat); }
      if (s.q) p.set('title', s.q);
      if (!ekle) {
        durumYaz(M.yukleniyor);
        iskeletAt();
        if (bos) bos.hidden = true;
        liste.setAttribute('aria-busy', 'true');
        if (!liste.children.length) liste.innerHTML = iskelet(mod === 'mini' ? Math.min(boyut, 5) : 6);
      } else {
        liste.insertAdjacentHTML('beforeend', iskelet(3));
      }
      if (daha) daha.disabled = true;
      csGetir('deals?' + p.toString()).then(function (o) {
        if (no !== istekNo) return;
        if (!Array.isArray(o.v)) throw new Error('bicim');
        if (!o.v.length && !ekle && !aktifMi(s)) throw new Error('bos');
        var ham = o.v.map(sade).filter(function (f) {
          if (!mag[f.storeID] || gorulen[f.gameID]) return false;
          gorulen[f.gameID] = 1;
          return true;
        });
        var bitti = function () {
          if (no !== istekNo) return;
          var yeni = yerelSuz(ham, s);
          sonListe = sonListe.concat(yeni);
          ciz(yeni, s, ekle);
          if (daha) { daha.hidden = o.v.length < boyut; daha.disabled = false; }
          durumYaz(String(M.canli || '').replace('{saat}', saatYaz(o.z)));
        };
        if (mod === 'ucretsiz') { bitti(); return; }
        var hedef = mod === 'mini' ? ham.slice(0, boyut) : ham;
        if (s.dusuk) return enDusukGetir(hedef, no).then(bitti);
        bitti();
        // rozetler sonradan gelir; satırları yeniden çiz
        return enDusukGetir(hedef, no).then(function () {
          if (no !== istekNo) return;
          ciz(sonListe, s, false);
        });
      }).catch(function () {
        if (no !== istekNo) return;
        if (ekle) { iskeletAt(); if (daha) { daha.disabled = false; } return; }
        yedekGoster(s);
      });
    }

    if (form) {
      var ilk = new URLSearchParams(location.search);
      ['q', 'magaza', 'fiyat', 'indirim', 'sira'].forEach(function (a) {
        var v = ilk.get(a), el = form.elements[a];
        if (!v || !el) return;
        if (el.tagName === 'SELECT') { if ($$('option', el).some(function (o) { return o.value === v; })) el.value = v; }
        else el.value = v.slice(0, 80);
      });
      if (ilk.get('dusuk') === '1') form.elements.dusuk.checked = true;
      var bekle = null;
      var urlYaz = function () {
        var s = secenek(), p = new URLSearchParams();
        if (s.q) p.set('q', s.q);
        ['magaza', 'fiyat', 'indirim'].forEach(function (a) { if (s[a]) p.set(a, s[a]); });
        if (s.sira && s.sira !== 'Deal Rating') p.set('sira', s.sira);
        if (s.dusuk) p.set('dusuk', '1');
        var qs = p.toString();
        try { history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '')); } catch (e) { /* file:// */ }
      };
      form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(bekle); urlYaz(); yukle(false); });
      form.addEventListener('change', function (e) { if (e.target.name === 'q') return; clearTimeout(bekle); urlYaz(); yukle(false); });
      form.elements.q.addEventListener('input', function () { clearTimeout(bekle); bekle = setTimeout(function () { urlYaz(); yukle(false); }, 450); });
    }
    if (daha) daha.addEventListener('click', function () { sayfa += 1; yukle(true); });
    yukle(false);
  });

  // ============================================================ hareket katmanı
  // İçerik JS'siz de görünür: gizli başlangıçlar yalnız JS'in eklediği sınıflarla gelir.
  // Yalnız transform/opacity canlandırılır; sekme gizliyken ya da öğe ekran dışındayken durur.
  function sekme() { H.classList.toggle('sekme-gizli', d.hidden); }
  d.addEventListener('visibilitychange', sekme);
  sekme();

  // ------------------------------------------------------------ başlık harf harf yazılır
  (function () {
    var h1 = $('[data-yaz]');
    if (!h1) return;
    if (az() || !h1.textContent.trim()) { h1.classList.add('hazir'); return; }
    var sayac = 0, son = null;
    function bol(kaynak, hedef) {
      Array.prototype.slice.call(kaynak.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          n.nodeValue.split(/(\s+)/).forEach(function (par) {
            if (!par) return;
            if (/^\s+$/.test(par)) { hedef.appendChild(d.createTextNode(' ')); return; }
            var k = d.createElement('span');
            k.className = 'kelime';
            (par.match(/[\ud800-\udbff][\udc00-\udfff]|[\s\S]/g) || []).forEach(function (c) {
              var h = d.createElement('span');
              h.className = 'harf';
              h.style.setProperty('--i', sayac++);
              h.textContent = c;
              k.appendChild(h);
            });
            hedef.appendChild(k);
            son = k;
          });
        } else if (n.nodeType === 1) {
          var kp = n.cloneNode(false);
          hedef.appendChild(kp);
          bol(n, kp);
          kp.style.setProperty('--n', sayac);
        }
      });
    }
    var sahne = d.createElement('span');
    sahne.className = 'yaz-sahne';
    sahne.setAttribute('aria-hidden', 'true');
    bol(h1, sahne);
    if (son) { var im = d.createElement('span'); im.className = 'yaz-imlec'; son.appendChild(im); }
    var okunur = d.createElement('span');
    okunur.className = 'gizli';
    okunur.textContent = h1.textContent.replace(/\s+/g, ' ').trim();
    h1.textContent = '';
    h1.appendChild(okunur);
    h1.appendChild(sahne);
    h1.style.setProperty('--n', sayac);
    h1.classList.add('hazir', 'yaziyor');
  })();

  // ------------------------------------------------------------ ana sayfa: tuş matrisi (canvas) ve imleç ışığı
  (function () {
    var tuval = $('.hero-tuval');
    if (!tuval || !tuval.getContext) return;
    var hero = tuval.parentNode, cx = tuval.getContext('2d');
    if (!cx) return;
    var isik = $('.hero-isik', hero);
    var W = 0, Y = 0, hucre = 52, kol = 0, sat = 0, tus = [], izgara = null, renk = {};
    var fx = -1e4, fy = -1e4, gorunur = true, raf = 0, son = 0, sonYak = 0, secim = null, sonrakiSecim = 0;
    function kutu(c, x, y, w, h, r) {
      c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
      c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
    }
    function renkAl() {
      var s = getComputedStyle(H);
      renk.cizgi = s.getPropertyValue('--cizgi').trim() || '#2A3958';
      renk.secim = s.getPropertyValue('--secim').trim() || '#3B6CF6';
      renk.acik = H.getAttribute('data-tema') === 'acik';
    }
    function izgaraCiz() {
      if (!W) return;
      var o = tuval.width / W;
      izgara = izgara || d.createElement('canvas');
      izgara.width = tuval.width; izgara.height = tuval.height;
      var c = izgara.getContext('2d');
      c.setTransform(o, 0, 0, o, 0, 0);
      c.clearRect(0, 0, W, Y);
      c.beginPath();
      for (var r = 0; r < sat; r++) for (var k = 0; k < kol; k++) kutu(c, k * hucre + 5, r * hucre + 5, hucre - 10, hucre - 10, 7);
      c.globalAlpha = renk.acik ? .75 : .6;
      c.lineWidth = 1;
      c.strokeStyle = renk.cizgi;
      c.stroke();
    }
    function boyut() {
      var r = tuval.getBoundingClientRect();
      if (!r.width || !r.height) return;
      W = r.width; Y = r.height;
      var o = Math.min(window.devicePixelRatio || 1, 2);
      tuval.width = Math.round(W * o); tuval.height = Math.round(Y * o);
      cx.setTransform(o, 0, 0, o, 0, 0);
      hucre = W < 700 ? 42 : 54;
      kol = Math.ceil(W / hucre); sat = Math.ceil(Y / hucre);
      tus = [];
      for (var i = 0; i < kol * sat; i++) tus.push(az() ? (Math.sin(i * 12.9898) * 43758.5453 % 1 > .86 ? .7 : 0) : 0);
      izgaraCiz();
      kare(0, true);
    }
    function kare(t, durgun) {
      cx.clearRect(0, 0, W, Y);
      if (izgara) cx.drawImage(izgara, 0, 0, W, Y);
      var ust = renk.acik ? .16 : .3;
      if (!durgun && t - sonYak > 85) { sonYak = t; tus[(Math.random() * tus.length) | 0] = 1; }
      cx.fillStyle = renk.secim;
      for (var r = 0; r < sat; r++) {
        for (var k = 0; k < kol; k++) {
          var i = r * kol + k, p = tus[i], x = k * hucre, y = r * hucre;
          var dx = x + hucre / 2 - fx, dy = y + hucre / 2 - fy, uz = Math.sqrt(dx * dx + dy * dy);
          var a = Math.max(Math.abs(p), uz < 180 ? (1 - uz / 180) * .8 : 0);
          if (a > .02) { cx.globalAlpha = a * ust; cx.beginPath(); kutu(cx, x + 5, y + 5, hucre - 10, hucre - 10, 7); cx.fill(); }
          if (!durgun) tus[i] = p * .952;
        }
      }
      // Ctrl+A: arada bir tuş öbeği seçilir
      if (!durgun) {
        if (!secim && t > sonrakiSecim && kol > 4 && sat > 2) {
          var gw = 3 + ((Math.random() * 4) | 0), gh = 2 + ((Math.random() * 2) | 0);
          secim = { k: (Math.random() * (kol - gw)) | 0, r: (Math.random() * (sat - gh)) | 0, w: gw, h: gh, t: t };
        }
        if (secim) {
          var g = (t - secim.t) / 1800;
          if (g >= 1) { secim = null; sonrakiSecim = t + 4200 + Math.random() * 3000; }
          else {
            var buy = Math.min(1, g / .35), sol = g < .7 ? 1 : 1 - (g - .7) / .3;
            var e = 1 - Math.pow(1 - buy, 3);
            var sx = secim.k * hucre + 2, sy = secim.r * hucre + 2;
            var sw = Math.max(hucre - 4, (secim.w * hucre - 4) * e), sh = Math.max(hucre - 4, (secim.h * hucre - 4) * e);
            cx.globalAlpha = sol * (renk.acik ? .1 : .16);
            cx.beginPath(); kutu(cx, sx, sy, sw, sh, 9); cx.fill();
            cx.globalAlpha = sol * (renk.acik ? .45 : .6);
            cx.lineWidth = 1.5; cx.strokeStyle = renk.secim; cx.stroke();
          }
        }
      }
      cx.globalAlpha = 1;
    }
    function dongu(t) {
      raf = 0;
      if (!gorunur || d.hidden || az()) return;
      if (t - son >= 33) { son = t; kare(t, false); }
      raf = requestAnimationFrame(dongu);
    }
    function basla() { if (!raf && gorunur && !d.hidden && !az()) raf = requestAnimationFrame(dongu); }
    function dur() { if (raf) cancelAnimationFrame(raf); raf = 0; }
    renkAl();
    boyut();
    var bekle = 0;
    var yeniden = function () { if (!bekle) bekle = requestAnimationFrame(function () { bekle = 0; boyut(); }); };
    if (window.ResizeObserver) new ResizeObserver(yeniden).observe(hero); else addEventListener('resize', yeniden);
    if (window.MutationObserver) new MutationObserver(function () { renkAl(); izgaraCiz(); kare(0, true); }).observe(H, { attributes: true, attributeFilter: ['data-tema'] });
    gozle(hero, function (v) { gorunur = v; if (v) basla(); else dur(); });
    d.addEventListener('visibilitychange', function () { if (d.hidden) dur(); else basla(); });
    if (azMq && azMq.addEventListener) azMq.addEventListener('change', function () { boyut(); basla(); });
    if (INCE) {
      var izle = function (e) {
        if (e.pointerType && e.pointerType !== 'mouse') return;
        var r = hero.getBoundingClientRect();
        fx = e.clientX - r.left; fy = e.clientY - r.top;
        if (az()) return;
        hero.classList.add('fare');
        if (isik) isik.style.transform = 'translate3d(' + fx.toFixed(0) + 'px,' + fy.toFixed(0) + 'px,0)';
      };
      hero.addEventListener('pointermove', izle, { passive: true });
      hero.addEventListener('pointerleave', function () { fx = fy = -1e4; hero.classList.remove('fare'); });
    }
  })();

  // ------------------------------------------------------------ sayılar sayarak gelir
  (function () {
    if (az() || !IO) return;
    $$('.durum-cubugu b').forEach(function (b) {
      var hedef = parseInt(b.textContent, 10);
      if (!(hedef > 1) || String(hedef) !== b.textContent.trim()) return;
      b.style.minWidth = b.getBoundingClientRect().width + 'px';
      var basladi = false;
      gozle(b, function (v) {
        if (!v || basladi) return;
        basladi = true;
        var t0 = performance.now(), sure = 900 + Math.min(hedef, 60) * 8;
        b.textContent = '0';
        (function adim(t) {
          var g = Math.min(1, (t - t0) / sure);
          b.textContent = String(Math.round(hedef * (1 - Math.pow(1 - g, 4))));
          if (g < 1) requestAnimationFrame(adim);
        })(t0);
      });
    });
  })();

  // ------------------------------------------------------------ kaydırınca beliren bloklar
  var bekleyenler = [];
  (function () {
    if (az() || !IO) return;
    var vh = innerHeight;
    var secici = '.o-bolum>*,.o-ek,.o-kart,.o-komsu,.o-tanitim,main .blok-bas,main .panel,main .tuslar>li,' +
      'main .takip-liste>li,main .radar-liste>li,.alt-ic>*';
    var io = new IntersectionObserver(function (g) {
      var k = 0;
      g.forEach(function (x) {
        if (!x.isIntersecting) return;
        var el = x.target;
        io.unobserve(el);
        el.style.setProperty('--gecikme', Math.min(k++, 6) * 70 + 'ms');
        el.classList.add('gorundu');
        var bitti = function (e) {
          if (e && e.target !== el) return;
          el.removeEventListener('transitionend', bitti);
          el.classList.remove('bekle', 'gorundu');
          el.style.removeProperty('--gecikme');
        };
        el.addEventListener('transitionend', bitti);
        setTimeout(bitti, 2200);
      });
    }, { rootMargin: '0px 0px -6% 0px' });
    $$(secici).forEach(function (el) {
      if (el.closest('dialog,.liste-yan,.o-ic,[hidden]') || (el.parentElement && el.parentElement.closest('.bekle'))) return;
      var r = el.getBoundingClientRect();
      if (!r.height || r.top < vh * .92 || r.left >= innerWidth) return;
      el.classList.add('bekle');
      bekleyenler.push(el);
      io.observe(el);
    });
  })();
  addEventListener('beforeprint', function () {
    bekleyenler.forEach(function (el) { el.classList.add('gorundu'); });
  });

  // ------------------------------------------------------------ kartlarda eğim, parıltı ve tuş basışı (yalnız fare)
  (function () {
    if (!INCE || az()) return;
    function bagla(el) {
      var ic = false, bas = false, raf = 0, px = 0, py = 0;
      el.classList.add('egim');
      function yaz() {
        raf = 0;
        if (!ic) return;
        var r = el.getBoundingClientRect();
        if (!r.width) return;
        var x = (px - r.left) / r.width, y = (py - r.top) / r.height, g = r.width > 360 ? 4 : 7;
        el.style.transform = 'perspective(900px) rotateX(' + ((.5 - y) * g).toFixed(2) + 'deg) rotateY(' +
          ((x - .5) * g * 1.2).toFixed(2) + 'deg) translate3d(0,' + (bas ? 2 : -3) + 'px,0)';
        el.style.setProperty('--sx', (px - r.left).toFixed(0) + 'px');
        el.style.setProperty('--sy', (py - r.top).toFixed(0) + 'px');
      }
      function iste() { if (!raf) raf = requestAnimationFrame(yaz); }
      el.addEventListener('pointerenter', function (e) {
        if (e.pointerType !== 'mouse') return;
        ic = true; px = e.clientX; py = e.clientY;
        el.classList.add('egik');
        iste();
      });
      el.addEventListener('pointermove', function (e) { if (ic) { px = e.clientX; py = e.clientY; iste(); } }, { passive: true });
      el.addEventListener('pointerdown', function () { if (ic) { bas = true; el.classList.add('basili'); iste(); } });
      el.addEventListener('pointerup', function () { bas = false; el.classList.remove('basili'); iste(); });
      el.addEventListener('pointerleave', function () {
        ic = false; bas = false;
        el.classList.remove('egik', 'basili');
        el.style.transform = '';
      });
    }
    $$('.tuslar a, .o-kart>a').forEach(bagla);
  })();

  // ------------------------------------------------------------ gündem şeridi
  $$('.gundem').forEach(function (g) {
    var serit = $('.gundem-serit', g), liste = $('.gundem-liste', g), dg = $('.gundem-dugme', g);
    if (!serit || !liste) return;
    if (az()) { if (dg) dg.hidden = true; return; }
    function sure() {
      var w = liste.getBoundingClientRect().width;
      if (w) serit.style.setProperty('--gd-sure', Math.max(30, Math.round(w / 45)) + 's');
    }
    function durdur(v, kaydet) {
      g.classList.toggle('durdu', v);
      if (dg) dg.setAttribute('aria-label', dg.getAttribute(v ? 'data-bas' : 'data-dur') || '');
      if (kaydet) depo.koy('cag-gundem', v ? 'dur' : 'akis');
    }
    sure();
    if (window.ResizeObserver) new ResizeObserver(sure).observe(liste);
    if (dg) dg.addEventListener('click', function () { durdur(!g.classList.contains('durdu'), true); });
    durdur(depo.al('cag-gundem') === 'dur', false);
    gozle(g, function (v) { g.classList.toggle('ekran-disi', !v); });
    g.classList.add('akiyor');
  });

  // ------------------------------------------------------------ mobil süzgeç aç/kapa ve etkin süzgeç sayısı
  $$('.sz-ac').forEach(function (b) {
    var yan = b.parentNode, form = d.getElementById(b.getAttribute('aria-controls')), say = $('[data-sz-say]', b);
    if (!form) return;
    b.addEventListener('click', function () {
      var ac = b.getAttribute('aria-expanded') !== 'true';
      b.setAttribute('aria-expanded', ac ? 'true' : 'false');
      yan.classList.toggle('acik', ac);
      if (ac && ANIM && !az()) {
        form.animate([{ opacity: 0, transform: 'translateY(-8px)' }, { opacity: 1, transform: 'none' }],
          { duration: 280, easing: 'cubic-bezier(.34,1.3,.64,1)' });
      }
    });
    function sayYaz() {
      var n = 0;
      $$('button[data-alan][aria-pressed="true"]', form).forEach(function (x) { if (x.getAttribute('data-deger')) n++; });
      $$('input', form).forEach(function (x) {
        if (x.type === 'checkbox' ? x.checked : (x.type === 'search' || x.type === 'text') && x.value.trim()) n++;
      });
      $$('select', form).forEach(function (x) { if (x.value && x.name !== 'sira') n++; });
      if (say) { say.hidden = !n; say.textContent = n ? String(n) : ''; }
    }
    ['input', 'change', 'click'].forEach(function (t) { form.addEventListener(t, function () { setTimeout(sayYaz, 0); }); });
    setTimeout(sayYaz, 0);
  });

  // ------------------------------------------------------------ rehber sayfası: içindekiler, ilerleme, çapa kopyalama
  (function () {
    var sayfa = $('.o-sayfa');
    if (!sayfa) return;
    var ic = $('.o-ic', sayfa), icAc = $('.o-ic-ac', sayfa), simdi = $('.o-ic-simdi', sayfa), duyuru = d.getElementById('o-duyuru');
    var liste = ic && $('.o-ic-liste', ic), baglar = {}, etkin = null;
    // uzun içindekilerde etkin bağlantı panelin kendi kaydırmasında görünür kalsın (masaüstü: .o-ic, mobil: açık liste); sayfa kaydırılmaz
    function etkinGoster() {
      var a = etkin && baglar[etkin];
      if (!a) return;
      [ic, liste].forEach(function (k) {
        if (!k || k.scrollHeight <= k.clientHeight + 1) return;
        var kr = k.getBoundingClientRect(), ar = a.getBoundingClientRect(), pay = 28;
        if (ar.top < kr.top + pay) k.scrollTop += ar.top - kr.top - pay;
        else if (ar.bottom > kr.bottom - pay) k.scrollTop += ar.bottom - kr.bottom + pay;
      });
    }
    function icKapat(odak) {
      if (!ic || !ic.classList.contains('acik')) return;
      ic.classList.remove('acik');
      if (icAc) { icAc.setAttribute('aria-expanded', 'false'); if (odak) icAc.focus(); }
    }
    if (ic && icAc) {
      icAc.addEventListener('click', function () {
        var a = !ic.classList.contains('acik');
        ic.classList.toggle('acik', a);
        icAc.setAttribute('aria-expanded', a ? 'true' : 'false');
        if (a) etkinGoster();
      });
      ic.addEventListener('click', function (e) { if (e.target.closest('.o-ic-liste a')) icKapat(false); });
      ic.addEventListener('keydown', function (e) { if (e.key === 'Escape') icKapat(true); });
      disariTikla(ic, function () { icKapat(false); });
    }
    $$('.o-ic-liste a[href^="#"]', sayfa).forEach(function (a) { baglar[decodeURIComponent(a.getAttribute('href').slice(1))] = a; });
    var bolumler = $$('.o-makale section[id]', sayfa).filter(function (s) { return baglar[s.id]; });
    function isaretle(id) {
      if (id === etkin) return;
      etkin = id;
      Object.keys(baglar).forEach(function (k) {
        if (k === id) baglar[k].setAttribute('aria-current', 'true'); else baglar[k].removeAttribute('aria-current');
      });
      if (simdi) simdi.textContent = id && baglar[id] ? baglar[id].textContent : '';
      etkinGoster();
    }
    var cubuk = $('.o-ilerleme span', sayfa), makale = $('.o-makale', sayfa), bekle = 0;
    function olc() {
      bekle = 0;
      var ust = parseFloat(getComputedStyle(H).getPropertyValue('--ust-h')) || 64, id = '';
      for (var i = 0; i < bolumler.length; i++) {
        if (bolumler[i].getBoundingClientRect().top <= ust + 110) id = bolumler[i].id; else break;
      }
      if (bolumler.length && innerHeight + scrollY >= d.documentElement.scrollHeight - 4 && etkin) id = bolumler[bolumler.length - 1].id;
      isaretle(id);
      if (cubuk && makale) {
        var r = makale.getBoundingClientRect(), bas = r.top + scrollY - ust, son = r.bottom + scrollY - innerHeight;
        var p = son > bas ? (scrollY - bas) / (son - bas) : 1;
        cubuk.style.transform = 'scaleX(' + Math.max(0, Math.min(1, p)).toFixed(4) + ')';
      }
    }
    function iste() { if (!bekle) bekle = requestAnimationFrame(olc); }
    addEventListener('scroll', iste, { passive: true });
    addEventListener('resize', iste);
    olc();
    sayfa.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a.o-capa');
      if (!a) return;
      e.preventDefault();
      var hash = a.getAttribute('href'), hedef = d.getElementById(decodeURIComponent(hash.slice(1)));
      try { history.replaceState(null, '', hash); } catch (er) { /* file:// */ }
      if (hedef) hedef.scrollIntoView({ behavior: az() ? 'auto' : 'smooth', block: 'start' });
      panoya(location.origin + location.pathname + hash, function () {
        a.classList.add('kopyalandi');
        if (duyuru) { duyuru.textContent = ''; setTimeout(function () { duyuru.textContent = M.kopyalandi || ''; }, 40); }
        setTimeout(function () { a.classList.remove('kopyalandi'); }, 1800);
      });
    });
    var acilan = [];
    addEventListener('beforeprint', function () {
      acilan = $$('details', sayfa).filter(function (x) { return !x.open; });
      acilan.forEach(function (x) { x.open = true; });
    });
    addEventListener('afterprint', function () { acilan.forEach(function (x) { x.open = false; }); acilan = []; });
    var kah = $('.o-kahraman', sayfa);
    if (kah) gozle(kah, function (v) { kah.classList.toggle('o-durgun', !v); });
  })();

  // ------------------------------------------------------------ haber videosu (kart + haber sayfası)
  // Adresler sunucuda data-* olarak yazılır; bayt, kart ekrana girip oynatılacağı an çekilir. Aynı anda tek video oynar.
  (function () {
    var ogeler = $$('.kg-videolu[data-video], .vp[data-video]');
    if (!ogeler.length) return;
    var BAG = navigator.connection || null;
    var DUR = 'cag-video-dur';
    var aktif = null, devam = null, liste = [];

    // kendiliğinden oynatma izni: azaltılmış hareket, veri tasarrufu/2g ya da kullanıcı daha önce durdurduysa yok
    function otoIzin() {
      if (az() || depo.al(DUR) === '1') return false;
      return !(BAG && (BAG.saveData || /2g$/.test(BAG.effectiveType || '')));
    }
    function etiket(o) {
      var oyn = o.kap.classList.contains('oynuyor');
      $$('[data-video-dugme]', o.kap).forEach(function (b) {
        b.setAttribute('aria-label', b.getAttribute(oyn ? 'data-etiket-durdur' : 'data-etiket-oynat') || '');
      });
    }
    function katman(o) {
      if (o.v) return o.v;
      var v = d.createElement('video');
      v.className = 'kg-vid';
      v.muted = true; v.loop = true; v.preload = 'none';
      v.setAttribute('muted', ''); v.setAttribute('playsinline', ''); v.setAttribute('aria-hidden', 'true');
      v.src = o.kap.getAttribute('data-video');
      o.kap.insertBefore(v, $('.kg-vid-ui', o.kap));
      o.v = v;
      bagla(o, v);
      return v;
    }
    function bagla(o, v) {
      v.addEventListener('playing', function () { o.kap.classList.add('oynuyor'); etiket(o); });
      v.addEventListener('pause', function () { o.kap.classList.remove('oynuyor'); etiket(o); });
      v.addEventListener('error', function () {
        if (v.error && v.error.code === 1) return; // MEDIA_ERR_ABORTED: biz durdurduk, kaynak bozuk değil
        o.kap.classList.remove('oynuyor');
        if (o.tur === 'kart' && v.parentNode) { v.parentNode.removeChild(v); o.v = null; }
        if (aktif === o) aktif = null;
      });
    }
    function oynat(o) {
      if (aktif && aktif !== o) dur(aktif, false);
      var v = katman(o);
      aktif = o;
      var p = v.play();
      if (p && p.catch) p.catch(function () { if (aktif === o) aktif = null; });
    }
    function dur(o, elle) {
      if (o.v) o.v.pause();
      if (elle) { o.elle = true; depo.koy(DUR, '1'); }
      if (aktif === o) aktif = null;
    }
    function acik(o) { return !!o.v && !o.v.paused && !o.v.ended; }

    liste = ogeler.map(function (kap) {
      var sayfa = kap.classList.contains('vp');
      var o = { kap: kap, tur: sayfa ? 'sayfa' : 'kart', v: sayfa ? $('.vp-v', kap) : null, elle: false, oran: 0 };
      if (sayfa && o.v) {
        o.v.removeAttribute('controls'); // JS varken kendi düğmelerimiz çalışır; yoksa yerel denetimler kalır
        bagla(o, o.v);
      }
      return o;
    });
    function bul(el) {
      var k = el && el.closest ? el.closest('.kg-videolu, .vp') : null;
      for (var i = 0; i < liste.length; i++) if (liste[i].kap === k) return liste[i];
      return null;
    }

    if (IO) {
      var gz = new IntersectionObserver(function (g) {
        g.forEach(function (n) {
          var o = bul(n.target);
          if (!o) return;
          // ekrandan yüksek öğede görünebilecek en fazla kadarına göre oran
          var boy = Math.min(n.boundingClientRect.height || 1, innerHeight || 1);
          o.oran = n.isIntersecting ? n.intersectionRect.height / boy : 0;
          o.orta = n.isIntersecting ? n.intersectionRect.top + n.intersectionRect.height / 2 : 0;
          if (o.oran < 0.35) { o.elle = false; if (aktif === o) dur(o, false); }
        });
        // aynı satırda birkaç kart birden görünebilir: ekranın ortasına en yakın tek kart oynar
        if (aktif && aktif.oran >= 0.5) return;
        var en = null, ort = (innerHeight || 1) / 2;
        liste.forEach(function (o) {
          if (o.oran < 0.65 || o.elle) return;
          if (!en || Math.abs(o.orta - ort) < Math.abs(en.orta - ort)) en = o;
        });
        if (en && !acik(en) && otoIzin()) oynat(en);
      }, { threshold: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.8, 1] });
      liste.forEach(function (o) { gz.observe(o.kap); });
    }

    d.addEventListener('visibilitychange', function () {
      if (d.hidden) { if (aktif) { devam = aktif; dur(aktif, false); } }
      else if (devam) { var o = devam; devam = null; if (!o.elle && o.oran >= 0.65 && otoIzin()) oynat(o); }
    });

    d.addEventListener('click', function (e) {
      var t = e.target;
      if (!t.closest) return;
      var o = bul(t);
      if (!o) return;
      var ses = t.closest('[data-video-ses]');
      var cc = t.closest('[data-video-cc]');
      if (ses && o.v) {
        o.v.muted = !o.v.muted;
        ses.classList.toggle('sesli', !o.v.muted);
        ses.setAttribute('aria-label', ses.getAttribute(o.v.muted ? 'data-etiket-ac' : 'data-etiket-kapat') || '');
        return;
      }
      if (cc && o.v && o.v.textTracks && o.v.textTracks[0]) {
        var iz = o.v.textTracks[0], goster = iz.mode !== 'showing';
        iz.mode = goster ? 'showing' : 'hidden';
        cc.setAttribute('aria-pressed', goster ? 'true' : 'false');
        return;
      }
      if (t.closest('[data-video-dugme]') || t.closest('.kg-vid') || t.closest('.vp-v')) {
        if (acik(o)) dur(o, true); else { o.elle = false; oynat(o); }
      }
    });
  })();
})();
