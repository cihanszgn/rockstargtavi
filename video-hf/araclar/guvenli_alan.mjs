// Güvenli alan denetimi: çizilecek Hyperframes projesini Chrome'da açar, her sahnede birkaç ana zaman çizelgesini
// o ana sarar ve görünen her metin parçasının kutusunu ölçer.
// Kural: okunur yazı y >= 220 ve y <= 1500; alt yarıda (y > 960) x <= 930; her yerde 40 <= x <= 1040;
// ayrıca sığdırma (.fit) taşması. Süs (data-dekor), geçiş katmanı ve ilerleme çubuğu denetim dışıdır (okunur yazı değil).
// Kullanım: node guvenli_alan.mjs --klasor K --rapor R.json --chrome CHROME --hf HF_KOKU --sahneler "[[0,3],...]" --sure 30 --sinir '{...}'
// Doluluk denetimi: sahne anahtar karesinde (süresinin %92'si) ön plan öğelerinin ([data-on]) birleşik sınır kutusunun yüksekliği
// güvenli alan yüksekliğinin (alt-ust) en az doluluk_min (varsayılan 0.70) katı olmalı; açılış başlığı yazısı baslik_min px'ten küçük olamaz.
// --sahneler üçüncü öğe olarak sahne türünü taşıyabilir: [[bas,bit,"baslik"],...] (türü verilmeyen sahnede doluluk ve başlık boyutu denetlenmez).
// Çıkış kodu: 0 ihlal yok, 3 ihlal var, 1 çalışmadı.
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const arg = {};
for (let i = 2; i < process.argv.length; i += 2) arg[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
const klasor = path.resolve(arg.klasor);
const sahneler = JSON.parse(arg.sahneler);
const S = JSON.parse(arg.sinir);
const puppeteer = createRequire(path.join(arg.hf, "package.json"))("puppeteer-core");

const OR = [0.45, 0.7, 0.92]; // sahne süresinin kesirleri: giriş animasyonları bitmiş anlar
const ihlaller = [];
const doluluk = [];
let olcum = 0;
let metin = 0;

const tarayici = await puppeteer.launch({
  executablePath: arg.chrome,
  headless: "shell",
  args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files", "--font-render-hinting=none"],
});
try {
  const sayfa = await tarayici.newPage();
  await sayfa.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });
  sayfa.on("pageerror", (e) => console.error("sayfa hatası:", e.message));
  await sayfa.goto(pathToFileURL(path.join(klasor, "index.html")).href, { waitUntil: "load" });
  await sayfa.evaluate(() => document.fonts.ready);
  // Zaman çizelgesinin kaydını bekle (waitForFunction headless-shell'de takılabiliyor; düz sorgu döngüsü kullanılır)
  let hazir = false;
  for (let d = 0; d < 300 && !hazir; d++) {
    hazir = await sayfa.evaluate(() => !!(window.__timelines && window.__timelines.main));
    if (!hazir) await new Promise((r) => setTimeout(r, 100));
  }
  if (!hazir) throw new Error("zaman çizelgesi (window.__timelines.main) 30 sn içinde kaydolmadı");

  for (let i = 0; i < sahneler.length; i++) {
    const [bas, bit, sablon = null] = sahneler[i];
    for (const k of OR) {
      const an = +(bas + (bit - bas) * k).toFixed(3);
      const sonuc = await sayfa.evaluate(
        (idx, an, S) => {
          const tl = window.__timelines.main;
          tl.seek(an, false);
          document.querySelectorAll("section.sc").forEach((s, j) => (s.style.display = j === idx ? "" : "none"));
          const kok = document.getElementById("s" + idx);
          const hud = document.getElementById("hud");
          const bulunan = [];
          const taşan = [];
          const etkinOpaklik = (e) => {
            let o = 1;
            for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
              const cs = getComputedStyle(n);
              if (cs.display === "none" || cs.visibility === "hidden") return 0;
              o *= parseFloat(cs.opacity);
            }
            return o;
          };
          const sayDolas = (koku) => {
            const w = document.createTreeWalker(koku, NodeFilter.SHOW_TEXT);
            for (let n = w.nextNode(); n; n = w.nextNode()) {
              const t = n.textContent.replace(/\s+/g, " ").trim();
              if (!t) continue;
              const e = n.parentElement;
              if (!e || e.closest("[data-dekor],.dekor-yazi,#gecis,#prog,svg")) continue;
              if (etkinOpaklik(e) < 0.6) continue;
              const r = document.createRange();
              r.selectNodeContents(n);
              // üst kutu taşanı kesiyorsa (overflow hidden / üç nokta) yalnız görünen kısım okunur yazıdır
              const kes = [];
              for (let n = e; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
                const c = getComputedStyle(n);
                if (c.overflowX !== "visible" || c.overflowY !== "visible") kes.push(n.getBoundingClientRect());
              }
              for (const b of r.getClientRects()) {
                let x1 = b.left, y1 = b.top, x2 = b.right, y2 = b.bottom;
                for (const k of kes) { x1 = Math.max(x1, k.left); y1 = Math.max(y1, k.top); x2 = Math.min(x2, k.right); y2 = Math.min(y2, k.bottom); }
                if (x2 - x1 < 2 || y2 - y1 < 2) continue;
                bulunan.push({ t, x1, y1, x2, y2 });
              }
            }
          };
          sayDolas(kok);
          // altyazı ve logo (HUD) da okunur yazıdır
          const altyazi = document.getElementById("sub");
          const logo = document.getElementById("logo");
          if (altyazi) sayDolas(altyazi);
          if (logo) sayDolas(logo);
          kok.querySelectorAll(".fit").forEach((e) => {
            if (etkinOpaklik(e) < 0.6) return;
            let sh = e.scrollHeight, sw = e.scrollWidth;
            // kelime kutulu başlıkta vurgu çerçevesi/animasyon scroll ölçüsünü şişirir: yerleşim (offset) ölçüsüne bak
            const bw = e.querySelectorAll(".bw");
            if (bw.length) {
              sh = 0; sw = 0;
              bw.forEach((b) => { let t = 0, l = 0, n = b; while (n && n !== e) { t += n.offsetTop; l += n.offsetLeft; n = n.offsetParent; } sh = Math.max(sh, t + b.offsetHeight); sw = Math.max(sw, l + b.offsetWidth); });
            }
            if (sh > e.clientHeight + Math.max(4, parseFloat(getComputedStyle(e).fontSize) * 0.3) || sw > e.clientWidth + 3)
              taşan.push({ t: (e.textContent || "").trim().slice(0, 40), sh, ch: e.clientHeight, sw, cw: e.clientWidth });
          });
          // doluluk: ön plan öğelerinin birleşik kutusu (yalnız görünür, opaklık >= 0.6), güvenli alana kırpılır
          let y1 = Infinity, y2 = -Infinity, adet = 0;
          kok.querySelectorAll("[data-on]").forEach((e) => {
            if (etkinOpaklik(e) < 0.6) return;
            const b = e.getBoundingClientRect();
            if (b.width < 2 || b.height < 2) return;
            y1 = Math.min(y1, Math.max(b.top, S.ust)); y2 = Math.max(y2, Math.min(b.bottom, S.alt)); adet++;
          });
          const bas = kok.querySelector(".bk-bas");
          const baslikPx = bas && etkinOpaklik(bas) >= 0.6 ? parseFloat(getComputedStyle(bas).fontSize) : null;
          return { bulunan, taşan, dolu: adet ? [y1, y2, adet] : null, baslikPx };
        },
        i,
        an,
        S,
      );
      olcum++;
      if (sablon !== null && k === OR[OR.length - 1]) {
        const min = S.doluluk_min ?? 0.7, yuk = S.alt - S.ust;
        const oran = sonuc.dolu ? Math.max(0, sonuc.dolu[1] - sonuc.dolu[0]) / yuk : 0;
        doluluk.push({ sahne: i, sablon, oran: +oran.toFixed(3) });
        if (oran < min) ihlaller.push({ sahne: i, an, metin: sablon, yon: "doluluk", deger: `${(oran * 100).toFixed(0)}% < ${(min * 100).toFixed(0)}%` });
        if (sonuc.baslikPx !== null && sonuc.baslikPx < (S.baslik_min ?? 96) - 0.5)
          ihlaller.push({ sahne: i, an, metin: sablon, yon: "başlık-boyutu", deger: `${sonuc.baslikPx}px < ${S.baslik_min ?? 96}px` });
      }
      for (const b of sonuc.bulunan) {
        metin++;
        const kontrol = [];
        if (b.y1 < S.ust - 0.5) kontrol.push(["üst", Math.round(b.y1), `y ${Math.round(b.y1)} < ${S.ust}`]);
        if (b.y2 > S.alt + 0.5) kontrol.push(["alt", Math.round(b.y2), `y ${Math.round(b.y2)} > ${S.alt}`]);
        if (b.x1 < S.sol - 0.5) kontrol.push(["sol", Math.round(b.x1), `x ${Math.round(b.x1)} < ${S.sol}`]);
        if (b.x2 > S.sag + 0.5) kontrol.push(["sağ", Math.round(b.x2), `x ${Math.round(b.x2)} > ${S.sag}`]);
        if (b.y2 > S.alt_yari && b.x2 > S.sag_alt + 0.5) kontrol.push(["sağ-alt", Math.round(b.x2), `x ${Math.round(b.x2)} > ${S.sag_alt} (y>${S.alt_yari})`]);
        for (const [yon, deger] of kontrol)
          ihlaller.push({ sahne: i, an, metin: b.t.slice(0, 50), yon, deger, kutu: [b.x1, b.y1, b.x2, b.y2].map(Math.round) });
      }
      for (const t of sonuc.taşan) ihlaller.push({ sahne: i, an, metin: t.t, yon: "taşma", deger: `${t.sh}/${t.ch} ${t.sw}/${t.cw}` });
    }
  }
} finally {
  await tarayici.close();
}

const ozet = { olcum_sayisi: olcum, metin_sayisi: metin, ihlal_sayisi: ihlaller.length, sinir: S, doluluk, ihlaller };
fs.mkdirSync(path.dirname(path.resolve(arg.rapor)), { recursive: true });
fs.writeFileSync(arg.rapor, JSON.stringify(ozet, null, 1), "utf-8");
process.exit(ihlaller.length ? 3 : 0);
