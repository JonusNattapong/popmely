/* popmely dashboard — renders the /api/data payload. No external dependencies. */

(() => {
  "use strict";

  const REFRESH_MS = 15000;
  const state = { data: null, auto: false, timer: null, tables: {} };

  // -- utilities ---------------------------------------------------------

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* SQLite datetime('now') writes UTC without a zone marker — parse as UTC. */
  function parseTs(s) {
    if (!s) return null;
    const iso = String(s).includes("T") ? s : String(s).replace(" ", "T") + "Z";
    const d = new Date(iso);
    return isNaN(d) ? null : d;
  }

  function fmtTs(s, withDate = true) {
    const d = parseTs(s);
    if (!d) return "—";
    const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return withDate ? `${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${time}` : time;
  }

  const fmtNum = (v, digits = 2) =>
    v === null || v === undefined || v === "" ? "—"
      : Number(v).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });

  const fmtMoney = (v, signed = false) => {
    if (v === null || v === undefined || v === "") return "—";
    const n = Number(v);
    const sign = signed && n > 0 ? "+" : n < 0 ? "-" : "";
    return `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const fmtPct = (v, digits = 1) =>
    v === null || v === undefined ? "—" : `${Number(v).toFixed(digits)}%`;

  const cssVar = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* Axis ticks land on round numbers (1/2/5 x 10^n), never raw data bounds. */
  function niceTicks(lo, hi, target = 4) {
    if (!(hi > lo)) return { lo, hi: lo + 1, ticks: [lo, lo + 1], decimals: 0 };
    const raw = (hi - lo) / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) * mag;
    const start = Math.floor(lo / step) * step;
    const end = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let t = start; t <= end + step / 2; t += step) ticks.push(Number(t.toFixed(6)));
    return { lo: start, hi: end, ticks, decimals: step < 1 ? Math.min(2, -Math.floor(Math.log10(step))) : 0 };
  }

  /* Status is never carried by color alone: every chip pairs a dot with an icon and text. */
  function chip(status, icon, label) {
    return `<span class="chip s-${status}"><span class="dot"></span><span class="icon">${icon}</span>${esc(label)}</span>`;
  }

  function outcomeChip(outcome) {
    const o = String(outcome || "").toUpperCase();
    if (o === "WIN") return chip("good", "▲", "Win");
    if (o === "LOSS") return chip("critical", "▼", "Loss");
    if (o === "BREAKEVEN") return chip("neutral", "=", "Breakeven");
    return chip("neutral", "○", "Pending");
  }

  function empty(msg) {
    return `<div class="empty">${esc(msg)}</div>`;
  }

  // -- tooltip -----------------------------------------------------------

  let tipEl = null;
  function showTip(html, x, y) {
    if (!tipEl) {
      tipEl = document.createElement("div");
      tipEl.className = "tooltip";
      document.body.appendChild(tipEl);
    }
    tipEl.innerHTML = html;
    tipEl.style.display = "block";
    const r = tipEl.getBoundingClientRect();
    const left = Math.min(Math.max(8, x + 14), window.innerWidth - r.width - 8);
    const top = Math.min(Math.max(8, y - r.height - 12), window.innerHeight - r.height - 8);
    tipEl.style.left = `${left}px`;
    tipEl.style.top = `${top}px`;
  }
  function hideTip() { if (tipEl) tipEl.style.display = "none"; }

  // -- chart: score over events (single series, no legend needed) ---------

  function renderScoreChart(host, history, maxScore) {
    const pts = history.map((h, i) => ({
      i,
      v: Number(h.score_after),
      event: h.event_type,
      change: Number(h.points_change),
      tier: h.tier,
      detail: h.detail,
      at: h.created_at,
    }));

    const width = Math.max(320, host.clientWidth);
    const H = 240, padL = 44, padR = 56, padT = 16, padB = 34;
    const plotW = width - padL - padR, plotH = H - padT - padB;

    const vals = pts.map((p) => p.v);
    let rawLo = Math.min(...vals), rawHi = Math.max(...vals);
    if (rawHi === rawLo) { rawLo = Math.max(0, rawLo - 5); rawHi = Math.min(maxScore, rawHi + 5); }
    const scale = niceTicks(Math.max(0, rawLo), Math.min(maxScore, rawHi));
    const lo = Math.max(0, scale.lo), hi = Math.min(maxScore, scale.hi) > lo ? Math.min(maxScore, scale.hi) : lo + 1;
    const yTicks = scale.ticks.filter((t) => t >= lo && t <= hi);

    const x = (i) => padL + (pts.length === 1 ? plotW / 2 : (i / (pts.length - 1)) * plotW);
    const y = (v) => padT + plotH - ((v - lo) / (hi - lo)) * plotH;

    const series = cssVar("--series-1");
    const surface = cssVar("--surface-1");

    const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
    const area = pts.length > 1
      ? `${line} L${x(pts.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)} L${x(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z`
      : "";

    const last = pts[pts.length - 1];

    host.innerHTML = `
      <svg class="chart" viewBox="0 0 ${width} ${H}" width="${width}" height="${H}" role="img"
           aria-label="Credit score after each recorded event">
        ${yTicks.map((t) => `<line class="tick-line" x1="${padL}" x2="${padL + plotW}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}"/>`).join("")}
        ${yTicks.map((t) => `<text class="axis-label" x="${padL - 8}" y="${(y(t) + 4).toFixed(1)}" text-anchor="end">${t.toFixed(scale.decimals)}</text>`).join("")}
        <line class="axis-line" x1="${padL}" x2="${padL + plotW}" y1="${padT + plotH}" y2="${padT + plotH}"/>
        ${area ? `<path d="${area}" fill="${series}" fill-opacity="0.10"/>` : ""}
        ${pts.length > 1 ? `<path d="${line}" fill="none" stroke="${series}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` : ""}
        <circle cx="${x(last.i).toFixed(1)}" cy="${y(last.v).toFixed(1)}" r="4.5" fill="${series}" stroke="${surface}" stroke-width="2"/>
        <text class="value-label" x="${(x(last.i) + 10).toFixed(1)}" y="${(y(last.v) + 4).toFixed(1)}">${last.v.toFixed(1)}</text>
        <text class="axis-label" x="${padL}" y="${H - 10}">${esc(fmtTs(pts[0].at))}</text>
        <text class="axis-label" x="${padL + plotW}" y="${H - 10}" text-anchor="end">${esc(fmtTs(last.at))}</text>
        <line id="score-cross" class="axis-line" x1="0" x2="0" y1="${padT}" y2="${padT + plotH}" style="display:none" stroke-dasharray="0"/>
        <rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="transparent" id="score-hit"/>
      </svg>`;

    // Nearest-point hover: the hit area is the whole plot, not the 9px dot.
    const svg = host.querySelector("svg");
    const hit = host.querySelector("#score-hit");
    const cross = host.querySelector("#score-cross");

    hit.addEventListener("mousemove", (ev) => {
      const box = svg.getBoundingClientRect();
      const scale = width / box.width;
      const mx = (ev.clientX - box.left) * scale;
      let best = pts[0], bestD = Infinity;
      for (const p of pts) {
        const d = Math.abs(x(p.i) - mx);
        if (d < bestD) { bestD = d; best = p; }
      }
      cross.style.display = "";
      cross.setAttribute("x1", x(best.i));
      cross.setAttribute("x2", x(best.i));
      const sign = best.change > 0 ? "+" : "";
      showTip(
        `<div class="tt-title">${esc(best.event)} · ${esc(best.tier)}</div>
         <div class="tt-row">Score after: ${best.v.toFixed(2)}</div>
         <div class="tt-row">Change: ${sign}${best.change.toFixed(2)}</div>
         <div class="tt-row">${esc(fmtTs(best.at))}</div>`,
        ev.clientX, ev.clientY);
    });
    hit.addEventListener("mouseleave", () => { hideTip(); cross.style.display = "none"; });
  }

  // -- chart: horizontal bars (single hue — magnitude, not identity) ------

  function renderBars(host, items, opts = {}) {
    const width = Math.max(320, host.clientWidth);
    const rowH = 34, padL = Math.min(190, Math.max(90, opts.labelWidth || 130)), padR = 64, padT = 6, padB = 6;
    const H = padT + padB + items.length * rowH;
    const plotW = width - padL - padR;
    const max = Math.max(...items.map((d) => d.value), 1);
    const series = cssVar("--series-1");
    const barH = Math.min(24, rowH - 12);
    const r = 4;

    // Rounded at the data end, square at the baseline.
    const barPath = (w, top) => {
      const rr = Math.min(r, w);
      return `M${padL},${top} H${padL + w - rr} Q${padL + w},${top} ${padL + w},${top + rr}` +
             ` V${top + barH - rr} Q${padL + w},${top + barH} ${padL + w - rr},${top + barH} H${padL} Z`;
    };

    host.innerHTML = `
      <svg class="chart" viewBox="0 0 ${width} ${H}" width="${width}" height="${H}" role="img"
           aria-label="${esc(opts.aria || "Bar chart")}">
        <line class="axis-line" x1="${padL}" x2="${padL}" y1="${padT}" y2="${H - padB}"/>
        ${items.map((d, i) => {
          const top = padT + i * rowH + (rowH - barH) / 2;
          const w = Math.max(2, (d.value / max) * plotW);
          return `
            <text class="axis-label" x="${padL - 10}" y="${top + barH / 2 + 4}" text-anchor="end">${esc(d.label)}</text>
            <path d="${barPath(w, top)}" fill="${series}" data-i="${i}"/>
            <text class="value-label" x="${padL + w + 8}" y="${top + barH / 2 + 4}">${esc(d.display ?? d.value)}</text>
            <rect x="${padL}" y="${padT + i * rowH}" width="${plotW + padR - 8}" height="${rowH}" fill="transparent" data-hit="${i}"/>`;
        }).join("")}
      </svg>`;

    host.querySelectorAll("[data-hit]").forEach((el) => {
      el.addEventListener("mousemove", (ev) => {
        const d = items[Number(el.dataset.hit)];
        showTip(`<div class="tt-title">${esc(d.label)}</div>${d.tip || `<div class="tt-row">${esc(d.display ?? d.value)}</div>`}`,
          ev.clientX, ev.clientY);
      });
      el.addEventListener("mouseleave", hideTip);
    });
  }

  // -- tables ------------------------------------------------------------

  function table(cols, rows) {
    if (!rows.length) return empty("No rows recorded yet.");
    return `<div class="table-scroll"><table>
      <thead><tr>${cols.map((c) => `<th class="${c.num ? "num" : ""}">${esc(c.label)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) => `<tr>${cols.map((c) => {
        const v = c.get(r);
        return `<td class="${c.num ? "num" : ""} ${c.strong ? "strong" : ""} ${c.wrapNote ? "wrap-note" : ""}">${c.html ? v : esc(v)}</td>`;
      }).join("")}</tr>`).join("")}</tbody>
    </table></div>`;
  }

  /* Every chart ships a table twin so no value is reachable only by hovering. */
  function chartCard(host, title, sub, chartFn, tableHtml, key) {
    const showTable = !!state.tables[key];
    host.innerHTML = `
      <div class="card-head">
        <div>
          <h2>${esc(title)}</h2>
          <p class="sub">${esc(sub)}</p>
        </div>
        <button type="button" data-twin="${key}" aria-pressed="${showTable}">${showTable ? "Chart" : "Table"}</button>
      </div>
      <div class="card-body"></div>`;

    const body = host.querySelector(".card-body");
    if (showTable) body.innerHTML = tableHtml;
    else chartFn(body);

    host.querySelector("[data-twin]").addEventListener("click", () => {
      state.tables[key] = !state.tables[key];
      render(state.data);
    });
  }

  // -- sections ----------------------------------------------------------

  const TIER_ICON = { GREEN: "●", YELLOW: "▲", ORANGE: "▲", CRITICAL: "■" };

  function renderHero(cs) {
    const host = $("hero-card");
    if (!cs || !cs.initialized) {
      host.innerHTML = `<h2>Trading credit score</h2>
        <p class="sub">Risk tier that governs lot sizing.</p>
        ${empty(cs?.message || "Not initialized yet — run mt5_score_init to start scoring.")}`;
      return;
    }

    const fillColor = `var(--status-${cs.status})`;
    host.innerHTML = `
      <div class="hero">
        <div class="hero-figure">
          <div class="hero-label">Trading credit score</div>
          <div class="hero-value">${cs.current_score.toFixed(1)} <span class="of">/ ${cs.max_score}</span></div>
          ${chip(cs.status, TIER_ICON[cs.tier] || "●", `${cs.tier} tier · ${Math.round(cs.lot_multiplier * 100)}% lot size`)}
        </div>
        <div class="hero-meter">
          <div class="meter-track"><div class="meter-fill" style="width:${Math.max(0, Math.min(100, cs.percent))}%;background:${fillColor}"></div></div>
          <div class="meter-scale"><span>0</span><span>30 · orange</span><span>50 · yellow</span><span>70 · green</span><span>${cs.max_score}</span></div>
          <p class="sub" style="margin-top:10px">
            ${cs.trading_allowed ? "Trading permitted at the tier multiplier." : "Trading halted — score is in the critical band."}
            Recovered ${fmtMoney(cs.total_recoveries).replace("$", "")} pts, deducted ${fmtMoney(cs.total_deductions).replace("$", "")} pts
            (net ${cs.net_change >= 0 ? "+" : ""}${cs.net_change.toFixed(2)}).
          </p>
        </div>
      </div>`;
  }

  function tile(label, value, note, noteClass = "") {
    return `<div class="card">
      <div class="tile-label">${esc(label)}</div>
      <div class="tile-value">${value}</div>
      <div class="tile-note ${noteClass}">${note ?? ""}</div>
    </div>`;
  }

  function renderKpis(d) {
    const cs = d.credit_score || {}, sig = d.signals || {}, jr = d.journal || {}, bt = d.backtests || {};
    const jrClass = jr.profit_usd > 0 ? "up" : jr.profit_usd < 0 ? "down" : "";

    $("kpi-row").innerHTML = [
      tile("Win streak", cs.winning_streak ?? "—",
        `Loss streak ${cs.losing_streak ?? 0}${cs.losing_streak >= 3 ? " · cool-off due" : ""}`,
        cs.losing_streak >= 3 ? "down" : ""),
      tile("Signals logged", sig.total ?? 0,
        `${sig.executed ?? 0} executed · ${sig.pending ?? 0} pending`),
      tile("Signal win rate", sig.win_rate === null || sig.win_rate === undefined ? "—" : fmtPct(sig.win_rate),
        sig.wins || sig.losses ? `${sig.wins} win / ${sig.losses} loss` : "No closed signals yet"),
      tile("Journaled P&L", fmtMoney(jr.profit_usd, true),
        `${jr.total ?? 0} note${jr.total === 1 ? "" : "s"}`, jrClass),
      tile("Avg confluence", sig.avg_confluence === null || sig.avg_confluence === undefined ? "—" : fmtPct(sig.avg_confluence, 0),
        "Across logged signals"),
      tile("Backtests", bt.total ?? 0,
        bt.avg_win_rate === null || bt.avg_win_rate === undefined ? "None archived" : `Avg win rate ${fmtPct(bt.avg_win_rate)}`),
    ].join("");
  }

  function renderScoreCard(d) {
    const cs = d.credit_score || {};
    const hist = cs.history || [];
    const host = $("card-score-history");

    if (!hist.length) {
      host.innerHTML = `<h2>Credit score trajectory</h2><p class="sub">Score after each scoring event.</p>${empty("No score events recorded yet.")}`;
      return;
    }

    const twin = table([
      { label: "#", get: (r) => r.id, num: true },
      { label: "Event", get: (r) => r.event_type, strong: true },
      { label: "Change", get: (r) => (r.points_change > 0 ? "+" : "") + Number(r.points_change).toFixed(2), num: true },
      { label: "Score after", get: (r) => Number(r.score_after).toFixed(2), num: true },
      { label: "Tier", get: (r) => r.tier },
      { label: "When", get: (r) => fmtTs(r.created_at) },
    ], hist);

    chartCard(host, "Credit score trajectory",
      `Score after each of the ${hist.length} recorded event${hist.length === 1 ? "" : "s"}, oldest to newest.`,
      (body) => renderScoreChart(body, hist, cs.max_score || 100), twin, "score");
  }

  function renderStrategyCard(d) {
    const rows = (d.signals && d.signals.by_strategy) || [];
    const host = $("card-strategies");

    if (!rows.length) {
      host.innerHTML = `<h2>Signals by strategy</h2><p class="sub">How many signals each strategy produced.</p>${empty("No signals logged yet.")}`;
      return;
    }

    const items = rows.map((r) => ({
      label: r.strategy || "—",
      value: r.total,
      display: String(r.total),
      tip: `<div class="tt-row">${r.total} signal${r.total === 1 ? "" : "s"} · ${r.executed} executed</div>
            <div class="tt-row">${r.wins} win / ${r.losses} loss</div>
            <div class="tt-row">P&amp;L ${fmtMoney(r.profit_usd, true)}</div>`,
    }));

    const twin = table([
      { label: "Strategy", get: (r) => r.strategy || "—", strong: true },
      { label: "Signals", get: (r) => r.total, num: true },
      { label: "Executed", get: (r) => r.executed, num: true },
      { label: "Wins", get: (r) => r.wins, num: true },
      { label: "Losses", get: (r) => r.losses, num: true },
      { label: "P&L", get: (r) => fmtMoney(r.profit_usd, true), num: true },
    ], rows);

    chartCard(host, "Signals by strategy", "Volume per strategy; hover for execution and outcome detail.",
      (body) => renderBars(body, items, { aria: "Signals logged per strategy", labelWidth: 150 }), twin, "strategies");
  }

  function renderSignals(d) {
    const rows = (d.signals && d.signals.recent) || [];
    $("card-signals").innerHTML = `
      <h2>Recent signals</h2>
      <p class="sub">Latest ${rows.length} entr${rows.length === 1 ? "y" : "ies"} from the bot signal audit log.</p>
      ${table([
        { label: "When", get: (r) => fmtTs(r.created_at) },
        { label: "Symbol", get: (r) => r.symbol, strong: true },
        { label: "TF", get: (r) => r.timeframe || "—" },
        { label: "Strategy", get: (r) => r.strategy },
        { label: "Type", get: (r) => `${r.signal_type}${r.direction ? ` (${r.direction})` : ""}` },
        { label: "Entry", get: (r) => fmtNum(r.entry_price), num: true },
        { label: "SL", get: (r) => fmtNum(r.sl_price), num: true },
        { label: "TP", get: (r) => fmtNum(r.tp_price), num: true },
        { label: "Confl.", get: (r) => (r.confluence_score === null ? "—" : fmtPct(r.confluence_score, 0)), num: true },
        { label: "Executed", get: (r) => (r.executed ? `#${r.execution_ticket ?? "—"}` : "No") },
        { label: "Outcome", get: (r) => outcomeChip(r.outcome), html: true },
        { label: "P&L", get: (r) => fmtMoney(r.profit_usd, true), num: true },
      ], rows)}`;
  }

  function renderJournal(d) {
    const rows = (d.journal && d.journal.recent) || [];
    $("card-journal").innerHTML = `
      <h2>Trade journal</h2>
      <p class="sub">Notes and AI reflections attached to trades.</p>
      ${table([
        { label: "When", get: (r) => fmtTs(r.created_at) },
        { label: "Symbol", get: (r) => r.symbol, strong: true },
        { label: "Action", get: (r) => r.action || "—" },
        { label: "Vol", get: (r) => (r.volume === null ? "—" : fmtNum(r.volume, 2)), num: true },
        { label: "Entry", get: (r) => fmtNum(r.entry_price), num: true },
        { label: "Exit", get: (r) => fmtNum(r.exit_price), num: true },
        { label: "P&L", get: (r) => fmtMoney(r.profit_usd, true), num: true },
        { label: "Strategy", get: (r) => r.strategy || "—" },
        { label: "Note", get: (r) => r.note, wrapNote: true },
        { label: "Tags", get: (r) => r.tags || "—" },
      ], rows)}`;
  }

  function renderBacktests(d) {
    const bt = d.backtests || {};
    const rows = bt.recent || [];
    $("card-backtests").innerHTML = `
      <h2>Backtest archive</h2>
      <p class="sub">${bt.total ? `${bt.total} archived run${bt.total === 1 ? "" : "s"} · net ${fmtMoney(bt.net_profit, true)} · worst drawdown ${fmtPct(bt.worst_drawdown)}` : "No runs archived yet."}</p>
      ${table([
        { label: "When", get: (r) => fmtTs(r.created_at) },
        { label: "Symbol", get: (r) => r.symbol, strong: true },
        { label: "TF", get: (r) => r.timeframe },
        { label: "Strategy", get: (r) => r.strategy },
        { label: "Bars", get: (r) => r.bars_count, num: true },
        { label: "Trades", get: (r) => r.total_trades, num: true },
        { label: "Win rate", get: (r) => fmtPct(r.win_rate), num: true },
        { label: "PF", get: (r) => fmtNum(r.profit_factor), num: true },
        { label: "Max DD", get: (r) => fmtPct(r.max_drawdown_pct), num: true },
        { label: "Net", get: (r) => fmtMoney(r.net_profit, true), num: true },
        { label: "Risk %", get: (r) => fmtNum(r.risk_percent, 1), num: true },
        { label: "R:R", get: (r) => fmtNum(r.rr_ratio, 1), num: true },
      ], rows)}`;
  }

  function renderEvents(d) {
    const rows = [...((d.credit_score && d.credit_score.history) || [])].reverse();
    $("card-events").innerHTML = `
      <h2>Credit score events</h2>
      <p class="sub">Every deduction, recovery, and reset, newest first.</p>
      ${table([
        { label: "When", get: (r) => fmtTs(r.created_at) },
        { label: "Event", get: (r) => r.event_type, strong: true },
        { label: "Change", get: (r) => (r.points_change > 0 ? "+" : "") + Number(r.points_change).toFixed(2), num: true },
        { label: "Score after", get: (r) => Number(r.score_after).toFixed(2), num: true },
        { label: "Tier", get: (r) => r.tier },
        { label: "Detail", get: (r) => r.detail || "—", wrapNote: true },
      ], rows)}`;
  }

  // -- top level ---------------------------------------------------------

  function render(d) {
    if (!d) return;
    state.data = d;

    const db = d.database || {};
    $("db-path").innerHTML = `<code>${esc(db.path || "—")}</code>`;
    $("db-size").textContent = db.size || "—";
    $("db-records").textContent = `${db.total_records ?? 0} records`;
    $("updated").textContent = fmtTs(d.generated_at, false);

    $("banner-slot").innerHTML = d.error
      ? `<div class="banner"><strong>Database unavailable.</strong> ${esc(d.error)}</div>` : "";

    if (d.status !== "success") {
      ["hero-card", "kpi-row", "card-score-history", "card-strategies", "card-signals",
       "card-journal", "card-backtests", "card-events"].forEach((id) => { $(id).innerHTML = ""; });
      return;
    }

    renderHero(d.credit_score);
    renderKpis(d);
    renderScoreCard(d);
    renderStrategyCard(d);
    renderSignals(d);
    renderJournal(d);
    renderBacktests(d);
    renderEvents(d);
  }

  async function load() {
    $("wrap").classList.add("loading");   // hold the previous render, no skeleton flash
    try {
      const res = await fetch("/api/data", { cache: "no-store" });
      render(await res.json());

      const goalRes = await fetch("/api/goal", { cache: "no-store" });
      const goal = await goalRes.json();
      renderGoal(goal);
    } catch (e) {
      $("banner-slot").innerHTML =
        `<div class="banner"><strong>Could not reach the dashboard server.</strong> ${esc(e.message)}</div>`;
    } finally {
      $("wrap").classList.remove("loading");
    }
  }

  function renderGoal(g) {
    const host = $("challenge-slot");
    if (!g || !g.running) {
      host.innerHTML = "";
      return;
    }
    const pct = Math.max(0, Math.min(100, g.progress_percent));
    host.innerHTML = `
      <div class="card" style="margin-bottom:16px; border-left: 4px solid var(--status-good)">
        <h2>Micro-Account Challenge: $${esc(g.initial_balance ?? 31)} to $${esc(g.target_balance)}</h2>
        <div style="margin-top: 12px; display: flex; justify-content: space-between; font-size: 14px;">
          <span>Current: <strong>${fmtMoney(g.current_equity)}</strong></span>
          <span>Target: <strong>${fmtMoney(g.target_balance)}</strong></span>
        </div>
        <div class="meter-track" style="margin-top: 8px; height: 12px; border-radius: 6px;">
          <div class="meter-fill" style="width:${pct}%; background:var(--status-good); border-radius: 6px;"></div>
        </div>
        <p class="sub" style="margin-top:8px;">Progress: ${pct.toFixed(2)}% · Trades: ${g.trades_executed} · Peak: ${fmtMoney(g.highest_equity)}</p>
      </div>
    `;
  }

  // -- controls ----------------------------------------------------------

  $("btn-refresh").addEventListener("click", load);

  $("btn-auto").addEventListener("click", () => {
    state.auto = !state.auto;
    const btn = $("btn-auto");
    btn.setAttribute("aria-pressed", String(state.auto));
    btn.textContent = `Auto-refresh: ${state.auto ? "on" : "off"}`;
    clearInterval(state.timer);
    if (state.auto) state.timer = setInterval(load, REFRESH_MS);
  });

  $("btn-theme").addEventListener("click", () => {
    const dark = document.documentElement.getAttribute("data-theme") === "dark"
      || (!document.documentElement.hasAttribute("data-theme")
          && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
    render(state.data);   // re-read the CSS vars the SVGs were built from
  });

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => render(state.data), 150);
  });

  load();
})();
