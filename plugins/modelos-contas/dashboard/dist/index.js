/**
 * Modelos e Contas — visao unificada (modelo padrao, reservas, prioridade das
 * contas e limites reais). Plain IIFE sobre window.__HERMES_PLUGIN_SDK__.
 */
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const { React } = SDK;
  const h = React.createElement;
  const { useState, useEffect, useCallback, useMemo } = SDK.hooks;
  const C = SDK.components;
  const API = "/api/plugins/modelos-contas";

  const post = (url, body) => SDK.fetchJSON(url, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });

  function when(ts) {
    if (!ts) return "";
    let t = typeof ts === "string" ? Date.parse(ts) : Number(ts) * (Number(ts) > 1e12 ? 1 : 1000);
    if (!isFinite(t)) return "";
    const d = new Date(t), diff = t - Date.now();
    const loc = d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
    if (diff <= 0) return loc;
    const hrs = Math.floor(diff / 3.6e6), min = Math.floor((diff % 3.6e6) / 6e4);
    return loc + (hrs >= 24 ? ` (em ${Math.floor(hrs / 24)}d ${hrs % 24}h)` : ` (em ${hrs}h${String(min).padStart(2, "0")})`);
  }

  const KIND = {
    ok: ["#16a34a", "disponivel"], warn: ["#d97706", ""], bad: ["#dc2626", ""], reserva: ["#6b7280", ""],
  };
  function Pill(props) {
    const s = props.status || {};
    const col = (KIND[s.kind] || KIND.reserva)[0];
    const txt = s.text + (s.until ? " ate " + when(s.until) : "");
    return h("span", { style: { fontSize: 12, fontWeight: 600, padding: "2px 10px", borderRadius: 99,
      color: col, border: `1px solid ${col}`, whiteSpace: "nowrap" } }, txt);
  }

  function Bar(props) {
    const v = Math.max(0, Math.min(100, Number(props.pct)));
    const ok = isFinite(v);
    const col = v < 70 ? "#16a34a" : v < 90 ? "#d97706" : "#dc2626";
    return h("div", { style: { display: "grid", gridTemplateColumns: "150px 1fr 48px", gap: 10, alignItems: "center", marginTop: 6 } },
      h("span", { style: { fontSize: 13 } }, props.label),
      h("div", null,
        h("div", { style: { height: 8, borderRadius: 8, background: "var(--border, #e5e7eb)", overflow: "hidden" } },
          ok ? h("i", { style: { display: "block", height: "100%", width: v + "%", background: col } }) : null),
        props.reset ? h("div", { style: { fontSize: 11, opacity: 0.7, marginTop: 2 } }, "renova " + when(props.reset)) : null),
      h("b", { style: { textAlign: "right", fontSize: 13 } }, ok ? Math.round(v) + "%" : "—"));
  }

  function Section(props) {
    return h(C.Card, { style: { marginBottom: 16 } },
      h(C.CardHeader, null, h(C.CardTitle, null, props.title),
        props.hint ? h("div", { style: { fontSize: 13, opacity: 0.7, marginTop: 4 } }, props.hint) : null),
      h(C.CardContent, null, props.children));
  }

  function Sel(props) {
    return h("select", {
      value: props.value || "", onChange: (e) => props.onChange(e.target.value), disabled: props.disabled,
      style: { padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border, #d1d5db)",
        background: "var(--background, transparent)", color: "inherit", minWidth: props.width || 200 },
    }, props.placeholder ? h("option", { value: "" }, props.placeholder) : null,
      (props.options || []).map((o) => h("option", { key: o.value, value: o.value }, o.label)));
  }

  function ModelPicker(props) {
    const provs = props.options || [];
    const row = provs.find((p) => p.slug === props.provider);
    const models = (row && row.models) || [];
    const mopts = models.map((m) => ({ value: m, label: m }));
    if (props.model && !models.includes(props.model)) mopts.unshift({ value: props.model, label: props.model });
    return h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" } },
      h(Sel, { value: props.provider, width: 180, placeholder: "provedor...",
        options: provs.map((p) => ({ value: p.slug, label: p.name })),
        onChange: (v) => props.onChange(v, "") }),
      h(Sel, { value: props.model, width: 240, placeholder: "modelo...", options: mopts,
        disabled: !props.provider, onChange: (v) => props.onChange(props.provider, v) }));
  }

  function Page() {
    const [st, setSt] = useState(null);
    const [lim, setLim] = useState(null);
    const [opts, setOpts] = useState([]);
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState(null);
    const [primary, setPrimary] = useState({ provider: "", model: "" });
    const [chain, setChain] = useState([]);

    const say = (text, bad) => { setMsg({ text, bad }); setTimeout(() => setMsg(null), 6000); };

    const loadState = useCallback(() => SDK.fetchJSON(API + "/state").then((s) => {
      setSt(s);
      if (s && s.primary) setPrimary({ provider: s.primary.provider || "", model: s.primary.model || "" });
      if (s && s.fallback) setChain(s.fallback.map((f) => Object.assign({}, f)));
    }), []);
    const loadLimits = useCallback((refresh) => {
      setLim((l) => Object.assign({}, l || {}, { loading: true }));
      return SDK.fetchJSON(API + "/limits" + (refresh ? "?refresh=true" : ""))
        .then(setLim).catch(() => setLim({ accounts: {}, error: "nao foi possivel consultar os limites agora" }));
    }, []);

    useEffect(() => {
      loadState().catch(() => say("Nao consegui ler a configuracao do Hermes.", true));
      loadLimits(false);
      SDK.fetchJSON("/api/model/options?explicit_only=true")
        .then((p) => setOpts((p && p.providers) || [])).catch(() => setOpts([]));
    }, []);

    // Grava o modelo padrao pela rota nativa; resolve true quando gravou.
    const setMain = (target, confirm) => post("/api/model/set", { scope: "main", provider: target.provider,
      model: target.model, base_url: target.base_url || undefined, confirm_expensive_model: !!confirm })
      .then((r) => {
        if (r && r.confirm_required) {
          return window.confirm(r.confirm_message + "\n\nSalvar mesmo assim?") ? setMain(target, true) : false;
        }
        if (r && r.ok === false) throw new Error(r.error || r.detail || "falhou");
        return true;
      });

    const savePrimary = () => {
      if (!primary.provider || !primary.model) return say("Escolha provedor e modelo.", true);
      setBusy(true);
      setMain(primary, false)
        .then((ok) => { if (!ok) return; say("Modelo padrao salvo. Vale para conversas novas."); return loadState(); })
        .catch((e) => say("Nao foi possivel salvar o modelo padrao: " + (e.message || e), true))
        .finally(() => setBusy(false));
    };

    const saveChain = () => {
      if (chain.some((c) => !c.provider || !c.model)) return say("Complete provedor e modelo em cada reserva.", true);
      setBusy(true);
      post(API + "/fallback", { chain })
        .then(() => { say("Reservas salvas."); return loadState(); })
        .catch((e) => say("Nao foi possivel salvar as reservas: " + (e.message || e), true))
        .finally(() => setBusy(false));
    };

    // Padrao + reservas como uma lista so: subir uma reserva para o topo a torna o modelo padrao.
    const moveOrder = (i, d) => {
      const all = [primary].concat(chain); const j = i + d;
      if (j < 0 || j >= all.length) return;
      [all[i], all[j]] = [all[j], all[i]];
      setPrimary(all[0]); setChain(all.slice(1));
    };

    const saveOrder = () => {
      if ([primary].concat(chain).some((c) => !c.provider || !c.model)) return say("Complete provedor e modelo em cada linha.", true);
      setBusy(true);
      (dirtyPrimary ? setMain(primary, false) : Promise.resolve(true))
        .then((ok) => {
          if (!ok) return false;
          return dirtyChain ? post(API + "/fallback", { chain }).then(() => true) : true;
        })
        .then((ok) => { if (!ok) return; say("Ordem salva. Vale para conversas novas."); return loadState(); })
        .catch((e) => say("Nao foi possivel salvar a ordem: " + (e.message || e), true))
        .finally(() => setBusy(false));
    };

    const move = (provider, entry, to) => {
      setBusy(true);
      post(API + "/priority", { provider, id: entry.id, priority: to })
        .then((r) => { if (r && r.note) say(r.note); return loadState(); })
        .catch((e) => say("Nao foi possivel mudar a prioridade: " + (e.message || e), true))
        .finally(() => setBusy(false));
    };

    const toggle = (provider, entry) => {
      setBusy(true);
      post(API + "/enabled", { provider, id: entry.id, enabled: entry.disabled })
        .then(() => { say(entry.disabled ? "Conta liberada para o Hermes." : "Conta bloqueada: continua logada, o Hermes pula ela."); return loadState(); })
        .catch((e) => say("Nao foi possivel mudar o bloqueio: " + (e.message || e), true))
        .finally(() => setBusy(false));
    };

    const moveChain = (i, d) => {
      const c = chain.slice(); const j = i + d;
      if (j < 0 || j >= c.length) return;
      [c[i], c[j]] = [c[j], c[i]]; setChain(c);
    };

    const dirtyPrimary = st && st.primary && (primary.provider !== st.primary.provider || primary.model !== st.primary.model);
    const dirtyChain = st && JSON.stringify(chain.map((c) => [c.provider, c.model])) !==
      JSON.stringify((st.fallback || []).map((c) => [c.provider, c.model]));

    const poolMap = useMemo(() => {
      const m = {}; ((st && st.pools) || []).forEach((p) => { m[p.provider] = p; if (p.serves) m[p.serves] = p; }); return m;
    }, [st]);

    if (!st) return h("div", { style: { padding: 24 } }, "Carregando...");
    if (st.error) return h("div", { style: { padding: 24, color: "#dc2626" } }, st.error);

    const usable = (prov) => {
      const p = poolMap[prov]; if (!p) return null;
      if (p.external) return p.entries[0].label;
      return p.entries.filter((e) => !e.disabled && (e.status.kind === "ok" || e.status.kind === "warn")).length
        + "/" + p.entries.length + " conta(s) disponivel(is)";
    };
    const Btn = (props) => h(C.Button, Object.assign({ size: "sm", variant: "outline", disabled: busy }, props));

    // --- ordem editavel (estado local; "Salvar ordem" grava padrao e reservas)
    const order = [primary].concat(chain).map((o, i) => Object.assign({ role: i ? "Reserva " + i : "Padrao" }, o));

    return h("div", { style: { maxWidth: 1000, padding: "8px 4px" } },
      msg ? h("div", { style: { position: "sticky", top: 0, zIndex: 5, padding: "10px 14px", marginBottom: 12, borderRadius: 8,
        background: msg.bad ? "#fee2e2" : "#dcfce7", color: msg.bad ? "#991b1b" : "#166534" } }, msg.text) : null,

      h(Section, { title: "Ordem em que o Hermes tenta",
        hint: "Use as setas para mudar a ordem; o primeiro vira o modelo padrao. Dentro de cada provedor, todas as contas sao tentadas antes de passar para o proximo." },
        order.map((o, i) => h("div", { key: i, style: { display: "flex", gap: 12, alignItems: "center", padding: "6px 0",
          borderTop: i ? "1px solid var(--border, #e5e7eb)" : "none" } },
          h("b", { style: { width: 24, opacity: 0.6 } }, i + 1),
          h("div", { style: { flex: 1 } }, h("div", { style: { fontWeight: 600 } }, o.model || "(escolha o modelo)"),
            h("div", { style: { fontSize: 12, opacity: 0.7 } }, o.role + " · " + (o.provider || "?"))),
          h("span", { style: { fontSize: 12, opacity: usable(o.provider) == null ? 0.7 : 1 } },
            usable(o.provider) == null ? "sem conta no pool" : usable(o.provider)),
          order.length > 1 ? h(Btn, { title: "Tentar antes", disabled: busy || i === 0, onClick: () => moveOrder(i, -1) }, "↑") : null,
          order.length > 1 ? h(Btn, { title: "Tentar depois", disabled: busy || i === order.length - 1, onClick: () => moveOrder(i, 1) }, "↓") : null)),
        (dirtyPrimary || dirtyChain) ? h("div", { style: { display: "flex", gap: 8, marginTop: 10 } },
          h(C.Button, { size: "sm", disabled: busy, onClick: saveOrder }, "Salvar ordem"),
          h(Btn, { onClick: () => { setPrimary(Object.assign({}, st.primary)); setChain((st.fallback || []).map((f) => Object.assign({}, f))); } }, "Desfazer")) : null),

      h(Section, { title: "Modelo padrao", hint: "Gravado na configuracao do Hermes; vale para conversas novas." },
        h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" } },
          h(ModelPicker, { options: opts, provider: primary.provider, model: primary.model,
            onChange: (p, m) => setPrimary({ provider: p, model: m }) }),
          h(C.Button, { size: "sm", disabled: busy || !dirtyPrimary, onClick: () => savePrimary(false) }, "Salvar"),
          dirtyPrimary ? h(Btn, { onClick: () => setPrimary(Object.assign({}, st.primary)) }, "Desfazer") : null)),

      h(Section, { title: "Modelos de reserva", hint: "Usados, em ordem, quando todas as contas do modelo padrao falham." },
        chain.length ? null : h("div", { style: { fontSize: 13, opacity: 0.7, marginBottom: 8 } }, "Nenhuma reserva."),
        chain.map((c, i) => h("div", { key: i, style: { display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" } },
          h("b", { style: { width: 24, opacity: 0.6 } }, i + 1),
          h(ModelPicker, { options: opts, provider: c.provider, model: c.model,
            onChange: (p, m) => { const n = chain.slice(); n[i] = Object.assign({}, n[i], { provider: p, model: m }); setChain(n); } }),
          h(Btn, { onClick: () => moveChain(i, -1), disabled: busy || i === 0 }, "↑"),
          h(Btn, { onClick: () => moveChain(i, 1), disabled: busy || i === chain.length - 1 }, "↓"),
          h(Btn, { onClick: () => setChain(chain.filter((_, j) => j !== i)) }, "Remover"))),
        h("div", { style: { display: "flex", gap: 8, marginTop: 4 } },
          h(Btn, { onClick: () => setChain(chain.concat([{ provider: "", model: "" }])) }, "+ Adicionar reserva"),
          h(C.Button, { size: "sm", disabled: busy || !dirtyChain, onClick: saveChain }, "Salvar reservas"),
          dirtyChain ? h(Btn, { onClick: () => setChain((st.fallback || []).map((f) => Object.assign({}, f))) }, "Desfazer") : null)),

      h(Section, { title: "Contas e limites",
        hint: lim && lim.checked_at ? "Uso consultado nos provedores em " + lim.checked_at + "." : "Consultando uso nos provedores..." },
        h("div", { style: { marginBottom: 10 } },
          h(Btn, { onClick: () => loadLimits(true), disabled: busy || (lim && lim.loading) },
            lim && lim.loading ? "Consultando..." : "Atualizar limites")),
        lim && lim.error ? h("div", { style: { color: "#dc2626", fontSize: 13 } }, lim.error) : null,
        st.pools.map((p) => h("div", { key: p.provider, style: { marginBottom: 18 } },
          h("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "baseline",
            borderBottom: "1px solid var(--border, #e5e7eb)", paddingBottom: 4, marginBottom: 6 } },
            h("b", null, (p.title || p.provider) + (p.provider === st.primary.provider || p.serves === st.primary.provider ? "  (padrao)" : "")),
            h("span", { style: { fontSize: 12, opacity: 0.7 } }, p.external ? "login fora do pool" : "estrategia " + p.strategy)),
          p.entries.map((e, idx) => {
            const q = (lim && lim.accounts && lim.accounts[e.id]) || null;
            return h("div", { key: e.id, style: { padding: "8px 0", borderTop: idx ? "1px dashed var(--border, #e5e7eb)" : "none" } },
              h("div", { style: { display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" } },
                h("b", { style: { width: 28, opacity: 0.6 } }, "#" + (idx + 1)),
                h("div", { style: { flex: 1, minWidth: 200 } },
                  h("div", { style: { fontWeight: 600 } }, e.label),
                  h("div", { style: { fontSize: 12, opacity: 0.7 } },
                    [q && q.email, q && q.plan, e.source, e.requests != null ? e.requests + " uso(s)" : null].filter(Boolean).join(" · "))),
                h(Pill, { status: e.status }),
                st.capabilities && st.capabilities.disable && !p.external && !p.serves
                  ? h(Btn, { title: e.disabled ? "Deixar o Hermes usar esta conta" : "Manter logada, mas o Hermes nao usa",
                    onClick: () => toggle(p.provider, e) }, e.disabled ? "Liberar" : "Bloquear") : null,
                p.entries.length > 1 ? h(Btn, { title: e.can_up ? "Subir prioridade" : (e.locked_reason || ""), disabled: busy || !e.can_up, onClick: () => move(p.provider, e, idx - 1) }, "↑") : null,
                p.entries.length > 1 ? h(Btn, { title: e.can_down ? "Descer prioridade" : (e.locked_reason || ""), disabled: busy || !e.can_down, onClick: () => move(p.provider, e, idx + 1) }, "↓") : null),
              e.locked_reason ? h("div", { style: { paddingLeft: 38, fontSize: 12, opacity: 0.75, marginTop: 2 } }, "🔒 " + e.locked_reason) : null,
              q && q.windows ? h("div", { style: { paddingLeft: 38 } }, q.windows.map((w, k) => h(Bar, Object.assign({ key: k }, w)))) : null,
              q && q.error ? h("div", { style: { paddingLeft: 38, fontSize: 12, color: "#dc2626", marginTop: 4 } }, q.error) : null,
              !q && !(lim && lim.loading) && !["anthropic", "openai-codex"].includes(p.provider)
                ? h("div", { style: { paddingLeft: 38, fontSize: 12, opacity: 0.6 } }, "este provedor nao informa cota") : null);
          })))));
  }

  if (window.__HERMES_PLUGINS__ && typeof window.__HERMES_PLUGINS__.register === "function") {
    window.__HERMES_PLUGINS__.register("modelos-contas", Page);
  }
})();
