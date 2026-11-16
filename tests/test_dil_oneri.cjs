const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '..', 'site.js'), 'utf8');
const start = source.indexOf('  (function () {', source.indexOf('// ------------------------------------------------------------ dil seçici'));
const end = source.indexOf("  $$('details.dil", start);
const code = source.slice(start, end);
const saved = {};
function render(languages, language = 'tr') {
  const nodes = [];
  const make = tag => ({tag, children: [], handlers: {},
    appendChild(child) { this.children.push(child); },
    setAttribute(k, v) { this[k] = v; },
    addEventListener(k, f) { this.handlers[k] = f; },
    remove() { nodes.splice(nodes.indexOf(this), 1); }
  });
  const body = {insertBefore(node) { nodes.push(node); }};
  const translations = {tr: {url: '/', lang: 'tr'}, nl: {url: '/nl/gamenieuws/haber.html', lang: 'nl', metin: 'Deze pagina is ook beschikbaar in het Nederlands.', ac: 'Openen', kapat: 'Sluiten'}};
  const context = {d: {getElementById: () => ({textContent: JSON.stringify(translations)}), createElement: make},
    B: body, DIL: language, navigator: {languages},
    depo: {al: key => saved[key] || null, koy: (key, value) => { saved[key] = value; }}};
  vm.runInNewContext(code, context);
  return nodes;
}
let nodes = render(['nl-NL', 'en-US']);
assert.equal(nodes.length, 1);
assert.equal(nodes[0].lang, 'nl');
assert.equal(nodes[0].children[0].href, '/nl/gamenieuws/haber.html');
assert.match(nodes[0].children[0].textContent, /Nederlands/);
nodes[0].children[1].handlers.click();
assert.equal(nodes.length, 0);
assert.equal(render(['nl-NL']).length, 0);
delete saved['cag-dil-oneri'];
assert.equal(render(['tr-TR', 'nl-NL']).length, 0);
assert.equal(render(['nl-NL'], 'nl').length, 0);
nodes = render(['nl-BE']);
nodes[0].children[0].handlers.click();
assert.equal(saved['cag-dil-oneri'], 'nl');
const norm = source.slice(source.indexOf('  function norm('), source.indexOf('  function yaziyor('));
const result = vm.runInNewContext(norm + "norm('免费游戏和优惠').includes(norm('游戏'))");
assert.equal(result, true);
console.log('Dil önerisi, kalıcı kapatma/seçim ve Çince alt dizgi araması geçti.');
