/* Smoke test for a no-framework clickable prototype.
 * Copy to <projeto>/testes/smoke.js and adapt the WALK section at the bottom.
 * Run: node testes/smoke.js
 *
 * Loads the prototype's real dados.js + app.js inside node's `vm` against a mock DOM,
 * then simulates the actual journey (clicks, typing, assertions). No browser needed.
 *
 * TRAP 1: top-level `const` in a vm script is NOT a property of the sandbox object.
 *         Read it with vm.runInContext("MODULOS", sandbox), never sandbox.MODULOS.
 * TRAP 2: don't do this via `node -e "eval(fs.readFileSync(...))"` — same scoping bite
 *         plus quoting pain on Windows bash. Keep it in a file.
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const raiz = path.join(__dirname, "..");
const ler = (p) => fs.readFileSync(path.join(raiz, p), "utf8");

/* ============================ mock DOM ============================ */
function novoEl(tag = "div") {
  const e = {
    tagName: tag, children: [], classList: new Set(), style: {}, dataset: {},
    _html: "", onclick: null, oninput: null, value: "", scrollTop: 0,
    appendChild(c) { this.children.push(c); c.parentNode = this; return c; },
    get innerHTML() { return this._html; },
    set innerHTML(v) {
      this._html = v; this.children = [];
      if (v === "") return;
      const p = parse(v); if (p) this.children.push(p);
    },
    querySelector(s) { return buscar(this, s)[0] || null; },
    querySelectorAll(s) { return buscar(this, s); },
    get firstElementChild() { return this.children[0] || null; },
    get textContent() { return (this._text || "") + this.children.map(c => c.textContent).join(""); },
  };
  e.classList.add = (...c) => c.forEach(x => Set.prototype.add.call(e.classList, x));
  e.classList.remove = (...c) => c.forEach(x => Set.prototype.delete.call(e.classList, x));
  e.classList.contains = (c) => Set.prototype.has.call(e.classList, c);
  e.classList.toggle = (c) => (e.classList.contains(c) ? e.classList.remove(c) : e.classList.add(c));
  return e;
}

/* Minimal HTML parser — enough for template literals built by el(`<div class=...>`). */
function parse(html) {
  html = html.trim();
  const m = html.match(/^<(\w+)([^>]*)>/);
  if (!m) return null;
  const [, tag, attrs] = m;
  const e = novoEl(tag);
  const cls = attrs.match(/class="([^"]*)"/);
  if (cls) cls[1].trim().split(/\s+/).filter(Boolean).forEach(c => e.classList.add(c));
  const idm = attrs.match(/id="([^"]*)"/); if (idm) e.id = idm[1];
  const val = attrs.match(/value="([^"]*)"/); if (val) e.value = val[1];

  const auto = /^<\w+[^>]*\/?>$/.test(html) && !html.includes("</");
  if (!auto) {
    const fecha = html.lastIndexOf("</" + tag);
    const dentro = fecha > 0 ? html.slice(html.indexOf(">") + 1, fecha) : "";
    e._text = dentro.replace(/<[^>]*>/g, " ");
    let resto = dentro, guard = 0;
    const selfClose = new Set(["input", "br", "img", "hr", "meta", "link"]);
    while (resto.trim() && guard++ < 300) {
      const mm = resto.match(/<(\w+)/); if (!mm) break;
      const ini = resto.indexOf(mm[0]), t = mm[1];
      let fim;
      if (selfClose.has(t)) fim = resto.indexOf(">", ini) + 1;
      else {
        let d = 0; const re = new RegExp(`<${t}\\b|</${t}>`, "g"); re.lastIndex = ini;
        let mt; while ((mt = re.exec(resto))) {
          if (mt[0][1] === "/") d--; else d++;
          if (d === 0) { fim = mt.index + mt[0].length; break; }
        }
        if (fim === undefined) break;
      }
      const filho = parse(resto.slice(ini, fim)); if (filho) e.appendChild(filho);
      resto = resto.slice(fim);
    }
  }
  return e;
}

function buscar(raizEl, sel) {
  const out = [];
  const teste = (e) =>
    sel.startsWith("#") ? e.id === sel.slice(1)
    : sel.startsWith(".") ? e.classList.contains(sel.slice(1))
    : e.tagName === sel;
  (function anda(e) { e.children.forEach(c => { if (teste(c)) out.push(c); anda(c); }); })(raizEl);
  return out;
}

/* ============================ ambiente ============================ */
const telaEl = novoEl("div"); telaEl.id = "tela";
const store = {};
const sandbox = {
  document: {
    getElementById: (id) => (id === "tela" ? telaEl : null),
    createElement: (t) => novoEl(t),
  },
  localStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => (store[k] = String(v)),
    removeItem: (k) => delete store[k],
  },
  window: { print: () => {} },
  alert: (m) => sandbox.__alertas.push(m),
  confirm: () => true,
  console,
  __alertas: [],
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(ler("js/dados.js"), sandbox);
vm.runInContext(ler("js/app.js"), sandbox);

/* ============================ helpers ============================ */
const falhas = [];
const ok = (cond, msg) => { if (!cond) falhas.push(msg); };
const achar = (cls) => buscar(telaEl, "." + cls);
const acharId = (id) => buscar(telaEl, "#" + id)[0];
const textoTela = () => telaEl.textContent.replace(/\s+/g, " ");

/* ===================== WALK — adapte daqui pra baixo =====================
 * Padrão: encontre o controle, dispare .onclick()/.oninput(), afirme o efeito.
 * Cubra: (1) tela inicial  (2) índice/jornada  (3) TODOS os passos, respondendo
 * cada tipo de campo  (4) persistência no store  (5) aritmética  (6) tela final.
 */
const PASSOS = vm.runInContext("MODULOS", sandbox);   // <- TRAP 1

ok(achar("capa").length === 1, "capa não renderizou");
acharId("ir").onclick();
ok(achar("cartao").length === PASSOS.length, "índice não listou todos os passos");

for (let i = 0; i < PASSOS.length; i++) {
  const m = PASSOS[i];
  achar("cartao")[i].onclick();
  const perguntas = achar("pergunta");
  ok(perguntas.length === m.perguntas.length, `passo ${m.id}: nº de perguntas`);

  m.perguntas.forEach((q, qi) => {
    const bloco = perguntas[qi]; if (!bloco) return;
    if (q.tipo === "escolha" || q.tipo === "multi") {
      const ops = buscar(bloco, ".opcao");
      ok(ops.length === q.opcoes.length, `passo ${m.id}/${q.id}: opções`);
      ops[0] && ops[0].onclick();
    } else if (q.tipo === "escala") {
      const bs = buscar(bloco, ".bolinha");
      ok(bs.length === 5, `passo ${m.id}: escala`);
      bs[3] && bs[3].onclick();
    } else {
      const inp = buscar(bloco, "input")[0];
      ok(!!inp, `passo ${m.id}/${q.id}: input`);
      if (inp) { inp.value = q.tipo === "numero" ? "10" : "teste"; inp.oninput(); }
    }
  });

  const concluir = buscar(telaEl, ".btn").filter(b => b.classList.contains("btn-coral"));
  ok(concluir.length === 1, `passo ${m.id}: botão concluir`);
  concluir[0].onclick();
  buscar(telaEl, ".btn").find(b => b.classList.contains("btn-claro")).onclick(); // volta
}

const salvo = JSON.parse(store[Object.keys(store)[0]] || "{}");
ok(Object.keys(salvo).length === PASSOS.length, "persistência incompleta");

const final = buscar(telaEl, ".btn").find(b => /plano|resumo|final/i.test(b.textContent));
ok(!!final, "botão da tela final ausente");
if (final) {
  final.onclick();
  ok(achar("passo-item").length === PASSOS.length, "tela final não reuniu os passos");
  // ok(/R\$ 11,00/.test(textoTela()), "número calculado não apareceu");  // ajuste
}

/* ============================ resultado ============================ */
if (falhas.length) {
  console.log(`❌ ${falhas.length} FALHA(S):`);
  falhas.forEach(f => console.log("   - " + f));
  process.exit(1);
}
console.log("✅ Todos os testes passaram");
