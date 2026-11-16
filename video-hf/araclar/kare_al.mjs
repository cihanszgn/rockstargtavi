// Kare alma aracı (tasarım denetimi için): projeyi Chrome'da açar, zaman çizelgesini verilen saniyelere sarar, PNG yazar.
// Kullanım: node kare_al.mjs --klasor K --dosya index.html --cikti DIR --anlar "ad:1.5,ad2:3" --chrome CHROME --hf HF_KOKU [--olcek 1]
// Yalnız kare almak içindir; görünen sahne süreye göre seçilir (gerçek çizimle aynı görüntüyü verir).
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import path from "node:path";

const arg = {};
for (let i = 2; i < process.argv.length; i += 2) arg[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
const klasor = path.resolve(arg.klasor);
const cikti = path.resolve(arg.cikti);
fs.mkdirSync(cikti, { recursive: true });
const anlar = arg.anlar.split(",").map((s) => { const [ad, sn] = s.split(":"); return [ad, parseFloat(sn)]; });
const olcek = parseFloat(arg.olcek || "1");
const puppeteer = createRequire(path.join(arg.hf, "package.json"))("puppeteer-core");
const tarayici = await puppeteer.launch({
  executablePath: arg.chrome, headless: "shell",
  args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files", "--font-render-hinting=none"],
});
try {
  const sayfa = await tarayici.newPage();
  await sayfa.setViewport({ width: 1080, height: 1920, deviceScaleFactor: olcek });
  sayfa.on("pageerror", (e) => console.error("sayfa hatası:", e.message));
  sayfa.on("console", (m) => { if (m.type() === "error") console.error("konsol:", m.text()); });
  await sayfa.goto(pathToFileURL(path.join(klasor, arg.dosya || "index.html")).href, { waitUntil: "load" });
  await sayfa.evaluate(() => document.fonts.ready);
  for (let d = 0; d < 300; d++) {
    if (await sayfa.evaluate(() => !!(window.__timelines && window.__timelines.main))) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  for (const [ad, sn] of anlar) {
    await sayfa.evaluate((sn) => {
      window.__timelines.main.seek(sn, false);
      document.querySelectorAll("section.sc").forEach((s) => {
        const b = parseFloat(s.dataset.start), u = parseFloat(s.dataset.duration);
        s.style.display = sn >= b && sn < b + u ? "" : "none";
      });
    }, sn);
    await new Promise((r) => setTimeout(r, 60));
    await sayfa.screenshot({ path: path.join(cikti, ad + ".png"), type: "png" });
  }
} finally {
  await tarayici.close();
}
