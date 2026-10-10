// PUR-1 control room: polls the local simulator session and sends operator commands.
// The operator walks the reactor hall (world.js); the controls live on the console's two
// workstations, which open as the station overlays below, and on its hard-wired buttons.
import { ReactorView } from "./view3d.js";
import { HallWorld } from "./world.js";
import { startMenuBackground } from "./menubg.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let info = null;
let state = null;
let eventsAfter = 0;
let trendAfter = -1;
let trend = [];          // [t, power_w, ch2_pct, ch4_pct, peak_fuel_c, pool_c]
let trendWindow = 600;
let view = null;          // core camera on the plant workstation
let world = null;         // the walkable hall
let station = null;       // open workstation: "reactor", "plant" or null
let menuBg = null;        // the main menu's animated background, until the hall is entered
const ann = {};           // annunciator states, shared with the hall's lamps

// ------------------------------------------------------------------ API

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function cmd(action, args = {}) {
  try {
    await api("/api/command", { action, ...args });
    poll();
  } catch (e) {
    toast(e.message);
  }
}

let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 4000);
}

// ------------------------------------------------------------------ formatting

function fmtTime(s) {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return [h, m, sec].map((v) => String(v).padStart(2, "0")).join(":");
}
function fmtSig(v, digits = 3) {
  if (v === null || v === undefined || !isFinite(v)) return "-";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(digits - 1).replace("e+", "e");
  return v.toPrecision(digits).replace(/\.0+$|(\.\d*?)0+$/, "$1");
}
function fmtPower(w) {
  if (w === null || !isFinite(w)) return "-";
  if (w >= 1000) return `${fmtSig(w / 1000)} kW`;
  if (w >= 1) return `${fmtSig(w)} W`;
  if (w >= 1e-3) return `${fmtSig(w * 1e3)} mW`;
  return `${fmtSig(w * 1e6)} µW`;
}
function fmtPeriod(p) {
  if (p === null || p === undefined || !isFinite(p) || Math.abs(p) > 9999) return "∞";
  return `${p > 0 ? "+" : ""}${p.toFixed(Math.abs(p) < 100 ? 1 : 0)} s`;
}
function logFrac(v, lo, hi) {
  if (!(v > 0)) return 0;
  return Math.min(1, Math.max(0, (Math.log10(v) - Math.log10(lo)) / (Math.log10(hi) - Math.log10(lo))));
}

// ------------------------------------------------------------------ static UI built once

const ANNUNCIATORS = [
  ["scram", "Reactor scram"],
  ["setback", "Setback"],
  ["interlock", "Rod withdrawal interlock"],
  ["period", "Short period"],
  ["power", "High power"],
  ["chan", "Channel inoperable"],
  ["pooltemp", "Pool temp high"],
  ["poollevel", "Pool level low"],
  ["rad", "Radiation high"],
  ["servo", "Servo control"],
  ["source", "Source inserted"],
  ["rps", "RPS bypassed"],
];

function buildStatic() {
  $("#annunciators").innerHTML = ANNUNCIATORS
    .map(([k, label]) => `<div class="ann" data-ann="${k}">${label}</div>`).join("");

  $("#speed").innerHTML = info.speeds
    .map((s) => `<button data-speed="${s}">${s === 0 ? "❚❚" : `${s}×`}</button>`).join("");
  $$("#speed button").forEach((b) => b.addEventListener("click", () => cmd("speed", { speed: +b.dataset.speed })));

  $("#initial").innerHTML = Object.entries(info.initial_states)
    .map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $("#restart").addEventListener("click", async () => {
    if (!confirm("Restart the simulation from the selected initial state?")) return;
    await cmd("reset", { initial: $("#initial").value });
    resetBuffers();
  });

  // Bar tick labels.
  $$(".bar").forEach((bar) => {
    const ticks = $(".ticks", bar);
    if (!ticks) return;
    const vals = ticks.dataset.ticks.split(",").map(Number);
    const log = bar.classList.contains("log");
    const lo = vals[0], hi = vals[vals.length - 1];
    ticks.innerHTML = vals.map((v) => {
      const f = log ? logFrac(v, lo, hi) : (v - lo) / (hi - lo);
      const label = v >= 1000 || (v > 0 && v < 0.01) ? v.toExponential(0).replace("e+", "e") : v;
      return `<span style="left:${f * 100}%">${label}</span>`;
    }).join("");
    $$(".mark-line", bar).forEach((m) => {
      const at = +m.dataset.at;
      const f = log ? logFrac(at, lo, hi) : (at - lo) / (hi - lo);
      m.style.left = `${f * 100}%`;
    });
  });

  $$("[data-range]").forEach((b) => b.addEventListener("click", () => {
    const step = b.dataset.range;
    cmd("range", step === "auto" ? { step, enabled: !state.channels.auto_range } : { step });
  }));

  $$("#trendWindow button").forEach((b) => b.addEventListener("click", () => {
    trendWindow = +b.dataset.w;
    $$("#trendWindow button").forEach((x) => x.classList.toggle("on", x === b));
    drawTrend();
  }));

  $("#stopAll").addEventListener("click", () => cmd("stop_all"));
  $("#scramBtn").addEventListener("click", () => cmd("scram"));
  $("#resetScram").addEventListener("click", () => cmd("reset_scram"));
  $("#servoBtn").addEventListener("click", () => cmd("servo", {
    enabled: !state.servo.enabled, setpoint_w: +$("#setpoint").value,
  }));
  $("#setpointBtn").addEventListener("click", () => cmd("servo", {
    enabled: state.servo.enabled, setpoint_w: +$("#setpoint").value,
  }));
  $("#sourceBtn").addEventListener("click", () => cmd("source", { inserted: !state.source_inserted }));

  $("#truthToggle").addEventListener("click", (e) => {
    const on = document.body.classList.toggle("truth");
    e.currentTarget.classList.toggle("on", on);
    e.currentTarget.setAttribute("aria-pressed", on);
    drawTrend();
  });
  $("#instructorToggle").addEventListener("click", () => toggleDrawer());
  $("#closeInstructor").addEventListener("click", () => toggleDrawer(false));
  buildInstructor();

  $$("[data-close]").forEach((b) => b.addEventListener("click", () => closeStation()));
  $("#enterBtn").addEventListener("click", () => enterHall());
  document.addEventListener("keydown", (e) => {
    if (e.code === "KeyF" && !e.repeat && !e.metaKey && !e.ctrlKey && !e.target.closest?.("input, select, textarea")) {
      toggleFullscreen();
      return;
    }
    if (e.code !== "Escape" || $("#updateDlg").open) return;
    e.preventDefault();       // Esc is ours: menus and workstations, never the window's full screen
    if (station) closeStation();
    else if (!$("#instructor").hidden) toggleDrawer(false);
    else if ($("#menu").hidden) showMenu(true);
  });

  $("#fullscreenBtn").addEventListener("click", toggleFullscreen);
  $("#updateBtn").addEventListener("click", openUpdates);
  $("#saveToken").addEventListener("click", saveToken);
  $("#installBtn").addEventListener("click", installUpdate);
}

function toggleDrawer(force) {
  const d = $("#instructor");
  const open = force ?? d.hidden;
  d.hidden = !open;
  $("#instructorToggle").classList.toggle("on", open);
}

function buildInstructor() {
  $("#expBtn").addEventListener("click", () => cmd("experiment", {
    dollars: +$("#expDollars").value, ramp_s: +$("#expRamp").value,
  }));
  $("#faultBtn").addEventListener("click", () => cmd("channel_fault", {
    channel: $("#faultCh").value, mode: $("#faultMode").value, value: +$("#faultValue").value,
  }));
  $("#chillerBtn").addEventListener("click", () => cmd("chiller", { available: !state.process.chiller_available }));
  $("#leakBtn").addEventListener("click", () => cmd("leak", { m_per_hour: +$("#leakRate").value }));
  const prot = () => cmd("protection", {
    enabled: state.protection.enabled,
    failed_trips: [$("#failPeriod").checked && "period", $("#failRad").checked && "radiation"].filter(Boolean),
  });
  $("#failPeriod").addEventListener("change", prot);
  $("#failRad").addEventListener("change", prot);
  $("#rpsBtn").addEventListener("click", () => cmd("protection", { enabled: !state.protection.enabled }));
}

function buildRods() {
  const reg = state.regulating_rod;
  $("#rods").innerHTML = Object.keys(state.rods).map((name) => `
    <div class="rod ${name === reg ? "rr" : "ss"}" data-rod="${name}">
      <div class="rod-name">${name}</div>
      <div class="rod-col"><div class="core-zone"></div><div class="blade"></div><div class="drive"></div></div>
      <div class="rod-pos digits">-</div>
      <div class="rod-state"></div>
      <div class="rod-btns">
        <button data-dir="in" title="Hold to drive in">IN ▼</button>
        <button data-dir="out" title="Hold to drive out">OUT ▲</button>
      </div>
      <div class="rod-worth"></div>
    </div>`).join("");

  // Core zone: the active fuel height on the rod scale (absorber offset to offset + 61 cm).
  const travel = Object.values(state.rods)[0].travel_cm;
  $$(".core-zone").forEach((z) => {
    z.style.bottom = `${(5.9 / travel) * 100}%`;
    z.style.height = `${(Math.min(61, travel - 5.9) / travel) * 100}%`;
  });

  $$(".rod").forEach((el) => {
    const name = el.dataset.rod;
    $$("[data-dir]", el).forEach((b) => {
      const start = (e) => {
        e.preventDefault();
        b.setPointerCapture?.(e.pointerId);
        b.classList.add("held");
        cmd("drive", { rod: name, direction: b.dataset.dir });
      };
      const stop = () => {
        if (!b.classList.contains("held")) return;
        b.classList.remove("held");
        cmd("drive", { rod: name, direction: "stop" });
      };
      b.addEventListener("pointerdown", start);
      b.addEventListener("pointerup", stop);
      b.addEventListener("pointercancel", stop);
      b.addEventListener("lostpointercapture", stop);
    });
  });

  $("#rodFaults").innerHTML = Object.keys(state.rods).map((name) => `
    <label>${name} <select data-rodfault="${name}">
      <option value="none">Normal</option><option value="stuck">Stuck</option><option value="runaway">Runaway</option>
    </select></label>`).join("");
  $$("[data-rodfault]").forEach((s) => s.addEventListener("change", () =>
    cmd("rod_fault", { rod: s.dataset.rodfault, fault: s.value })));
}

function resetBuffers() {
  trend = [];
  trendAfter = -1;
  eventsAfter = 0;
  $("#events").innerHTML = "";
}

// ------------------------------------------------------------------ render

function setAnn(key, cls) {
  ann[key] = cls || null;
  const el = $(`[data-ann="${key}"]`);
  el.className = "ann" + (cls ? ` lit-${cls}` : "");
}

// ------------------------------------------------------------------ hall, workstations and menu

function showMenu(on) {
  $("#menu").hidden = !on;
  if (on) world?.setActive(false);
  else if (!station) world?.setActive(true);
}

// Full screen goes through the native window in the Mac app (Esc cannot leave it); in a
// browser it uses the Fullscreen API and, where supported, keeps Esc with a keyboard lock.
async function toggleFullscreen() {
  try {
    if (info?.native_window) {
      await api("/api/window/fullscreen", {});
    } else if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await document.documentElement.requestFullscreen();
      await navigator.keyboard?.lock?.(["Escape"]).catch(() => {});
    }
  } catch (e) {
    toast(`Full screen: ${e.message}`);
  }
}

// The first time the operator goes in, the main menu becomes the pause menu.
function leaveMainMenu() {
  if (!menuBg) return;
  menuBg.stop();
  menuBg = null;
  document.body.classList.remove("main-menu");
  $("#menuTitle").textContent = "PUR-1 Simulator - Menu";
}

function enterHall() {
  document.activeElement?.blur?.();   // keys go to the hall, not the menu button
  leaveMainMenu();
  showMenu(false);
  if (!world) return;
  world.setActive(true);
  world.lock();
}

async function openStation(name) {
  leaveMainMenu();
  station = name;
  world?.setActive(false);
  $("#menu").hidden = true;
  $("#prompt").hidden = true;
  $("#station-reactor").hidden = name !== "reactor";
  $("#station-plant").hidden = name !== "plant";
  document.body.classList.add("at-station");
  if (name === "plant") {
    drawTrend();
    if (!view && info.models) {
      try {
        view = new ReactorView($("#view3d"), "/models/");
        await view.load("pur1_core");
        if (state) view.update(state);
      } catch (e) {
        $("#view3d").innerHTML = `<div class="view-msg">Core camera unavailable: ${e.message}</div>`;
      }
    }
  }
}

function closeStation() {
  if (!station) return;
  station = null;
  $("#station-reactor").hidden = true;
  $("#station-plant").hidden = true;
  document.body.classList.remove("at-station");
  if (world) {
    world.setActive(true);
    // Pointer lock needs a click; Esc does not count as one.
    if (!world.dragLook) setPrompt("Click to look around", true);
  }
}

let promptTimer = null;
function setPrompt(text, sticky = false) {
  const p = $("#prompt");
  clearTimeout(promptTimer);
  p.hidden = !text;
  p.textContent = text || "";
  if (text && !sticky) promptTimer = setTimeout(() => (p.hidden = true), 2500);
}

function render() {
  const s = state;
  const ch = s.channels;
  const truth = document.body.classList.contains("truth");

  $("#clock").textContent = fmtTime(s.time_s);
  $$("[data-status=clock]").forEach((el) => { el.textContent = fmtTime(s.time_s); });
  $$("[data-status=msg]").forEach((el) => {
    el.textContent = s.scrammed ? `SCRAM: ${s.scram_causes.join("; ")}` : s.alarms[0] || "Ready";
  });
  $$("#speed button").forEach((b) => b.classList.toggle("on", +b.dataset.speed === s.speed));

  // Channels
  const period = (el, p) => {
    const pe = $(".period", el);
    $("[data-v=period]", el).textContent = fmtPeriod(p);
    pe.classList.toggle("short", p !== null && p > 0 && p < 15);
    pe.classList.toggle("trip", p !== null && p > 0 && p < 7);
  };
  const fill = (el, f, hot, trip) => {
    const b = $(".fill", el);
    b.style.width = `${f * 100}%`;
    b.classList.toggle("hot", !!hot && !trip);
    b.classList.toggle("trip", !!trip);
  };
  const c1 = $("#ch1");
  $("[data-v=value]", c1).textContent = ch.ch1_saturated ? "SAT" : fmtSig(ch.ch1_cps);
  fill(c1, logFrac(ch.ch1_cps, 0.1, 1e5));
  period(c1, ch.ch1_saturated ? null : ch.ch1_period_s);
  c1.classList.toggle("fault", ch.faults.ch1 !== "none");

  const c2 = $("#ch2");
  $("[data-v=value]", c2).textContent = fmtSig(ch.ch2_percent);
  fill(c2, logFrac(ch.ch2_percent, 1e-5, 100 * 3), ch.ch2_percent > 105, ch.ch2_percent >= 120);
  period(c2, ch.ch2_period_s);
  c2.classList.toggle("fault", ch.faults.ch2 !== "none" || !ch.ch2_hv_ok);
  $("[data-v=truth]", c2).textContent = `true ${fmtPower(s.true.power_w)}`;
  $("[data-v=truth]", c1).textContent = `true ${fmtSig(s.true.power_w / s.reactor.rated_w * 100)} % rated`;

  const c3 = $("#ch3");
  const w = ch.ch3_power_w;
  const [val, unit] = fmtPower(w).split(" ");
  $("[data-v=value]", c3).textContent = val;
  $("[data-v=unit]", c3).textContent = unit || "W";
  $("[data-v=range]", c3).textContent = `range ${ch.ch3_range + 1}/16 · ${fmtPower(ch.ch3_range_w)} FS`;
  $("[data-v=pct]", c3).textContent = `${ch.ch3_percent_of_range.toFixed(1)}% of range`;
  fill(c3, ch.ch3_percent_of_range / 150, ch.ch3_percent_of_range > 105, ch.ch3_percent_of_range >= 120);
  $('[data-range="auto"]').classList.toggle("on", ch.auto_range);
  c3.classList.toggle("fault", ch.faults.ch3 !== "none");

  const c4 = $("#ch4");
  $("[data-v=value]", c4).textContent = ch.ch4_percent.toFixed(1);
  fill(c4, ch.ch4_percent / 150, ch.ch4_percent > 105, ch.ch4_percent >= 120);
  c4.classList.toggle("fault", ch.faults.ch4 !== "none");

  // Rods
  if (!$("#rods .rod")) buildRods();
  for (const [name, r] of Object.entries(s.rods)) {
    const el = $(`.rod[data-rod="${name}"]`);
    $(".blade", el).style.height = `${(r.position_cm / r.travel_cm) * 100}%`;
    $(".drive", el).style.bottom = `calc(${(r.drive_cm / r.travel_cm) * 100}% - 1px)`;
    $(".rod-pos", el).textContent = `${r.position_cm.toFixed(1)} cm`;
    el.classList.toggle("unlatched", !r.latched);
    const st = $(".rod-state", el);
    let label = "", cls = "";
    if (r.runaway) [label, cls] = ["drive runaway", "bad"];
    else if (r.stuck) [label, cls] = ["stuck", "bad"];
    else if (r.falling) [label, cls] = ["dropping", "bad"];
    else if (!r.latched) [label, cls] = ["unlatched · drive in", "bad"];
    else if (r.moving) [label, cls] = [r.command > 0 ? "withdrawing" : r.command < 0 ? "inserting" : "moving", "moving"];
    else if (name === s.regulating_rod && s.servo.enabled) [label, cls] = ["on servo", "moving"];
    st.textContent = label;
    st.className = `rod-state ${cls}`;
    $(".rod-worth", el).textContent = `holds −$${r.worth_dollars.toFixed(2)}`;
    const servoOwned = name === s.regulating_rod && s.servo.enabled;
    $$("[data-dir]", el).forEach((b) => (b.disabled = servoOwned));
  }

  // Servo / source / scram
  $("#servoBtn").classList.toggle("on", s.servo.enabled);
  $("#servoBtn").textContent = s.servo.enabled ? "Servo ON" : "Servo OFF";
  $("#servoErr").textContent = s.servo.enabled ? `${(s.servo.error * 100).toFixed(1)} %` : "-";
  if (document.activeElement !== $("#setpoint")) $("#setpoint").value = s.servo.setpoint_w || 10000;
  $("#sourceBtn").classList.toggle("on", s.source_inserted);
  $("#sourceBtn").textContent = s.source_inserted ? "Source IN" : "Source OUT";
  $("#sourceHint").textContent = s.source_inserted ? "Pu-Be source at the core" : "Withdraw above about 5 W";
  $("#resetScram").disabled = !s.scrammed;

  // Annunciators
  const alarms = s.alarms.join("|");
  const p2 = ch.ch2_period_s;
  setAnn("scram", s.scrammed ? "alarm" : "");
  setAnn("setback", s.setback ? "alarm" : "");
  setAnn("interlock", s.interlocks.length ? "warn" : "");
  setAnn("period", p2 !== null && p2 > 0 && p2 < 15 ? (p2 < 7 ? "alarm" : "warn") : "");
  setAnn("power", ch.ch4_percent >= 110 || ch.ch2_percent >= 110 ? "alarm" : ch.ch4_percent > 105 ? "warn" : "");
  setAnn("chan", /inoperable|downscale/i.test(alarms) ? "alarm" : "");
  setAnn("pooltemp", /Pool temperature/.test(alarms) ? "warn" : "");
  setAnn("poollevel", /Pool level/.test(alarms) ? "alarm" : "");
  setAnn("rad", /radiation|air monitor/i.test(alarms + s.scram_causes.join("|")) ? "alarm" : "");
  setAnn("servo", /Servo deviation/.test(alarms) ? "warn" : s.servo.enabled ? "ok" : "");
  setAnn("source", s.source_inserted ? "ok" : "");
  setAnn("rps", !s.protection.enabled || s.protection.failed_trips.length ? "alarm" : "");

  // Banner for fuel limits and RPS
  const banner = $("#banner");
  let msg = "";
  if (s.true.fuel_damage > 0) msg = `Fuel damage: ${(s.true.fuel_damage * 100).toFixed(2)}% of the core. Fission products are in the pool water.`;
  else if (s.scrammed) msg = `SCRAM: ${s.scram_causes.join("; ")}. Drive the shim drives in to re-latch, then reset the scram.`;
  banner.hidden = !msg;
  banner.textContent = msg;
  banner.className = "banner" + (s.scrammed && !s.true.fuel_damage ? " info" : "");

  // Process
  const lvl = s.process.pool_level_m;
  const rows = [
    ["Pool temperature", `${s.process.pool_temp_c.toFixed(2)} °C`, s.process.pool_temp_c > 29.7 ? "warn" : ""],
    ["Water above core", `${lvl.toFixed(2)} m`, lvl < 3.96 ? "alarm" : ""],
    ["Chiller", s.process.chiller_available ? "running" : "tripped", s.process.chiller_available ? "" : "warn"],
    ["Pool top", `${fmtSig(s.radiation_mr_h.pool_top)} mR/h`, s.radiation_mr_h.pool_top >= 50 ? "alarm" : ""],
    ["Console", `${fmtSig(s.radiation_mr_h.console)} mR/h`, s.radiation_mr_h.console >= 7.5 ? "alarm" : ""],
    ["Water monitor", `${fmtSig(s.radiation_mr_h.water)} mR/h`, s.radiation_mr_h.water >= 7.5 ? "alarm" : ""],
    ["Air monitor", `${fmtSig(s.radiation_mr_h.air)} mR/h`, s.radiation_mr_h.air >= 1 ? "alarm" : ""],
  ];
  if (truth) {
    rows.push(
      ["True power", fmtPower(s.true.power_w), "true"],
      ["Thermal power", fmtPower(s.true.thermal_power_w), "true"],
      ["Peak fuel temp", `${s.true.peak_fuel_temp_c.toFixed(1)} °C`, s.true.peak_fuel_temp_c > 530 ? "alarm" : "true"],
      ["Core water temp", `${s.true.core_temp_c.toFixed(2)} °C`, "true"],
      ["Void fraction", `${(s.true.void_fraction * 100).toFixed(2)} %`, "true"],
      ["Energy released", `${s.true.energy_kwh.toFixed(3)} kWh`, "true"],
    );
  }
  $("#process").innerHTML = rows.map(([k, v, c]) => `<span class="k">${k}</span><span class="v ${c}">${v}</span>`).join("");

  const rho = s.reactivity_dollars;
  const names = { excess: "Core excess", rods: "Control rods", fuel_temp: "Fuel temperature",
    moderator_temp: "Moderator temperature", void: "Void", xenon: "Xenon", samarium: "Samarium",
    burnup: "Burnup", experiments: "Experiments" };
  $("#rho").innerHTML = (truth ? Object.entries(names) : [])
    .map(([k, n]) => `<span class="k">${n}</span><span class="v">${rho[k] >= 0 ? "+" : "−"}$${Math.abs(rho[k]).toFixed(3)}</span>`)
    .join("") + `<span class="k total">Net reactivity</span><span class="v total">${truth
      ? `${rho.total >= 0 ? "+" : "−"}$${Math.abs(rho.total).toFixed(4)}`
      : "turn on True values"}</span>`;

  $("#interlocks").textContent = s.interlocks.length ? `Interlock: ${s.interlocks.join("; ")}` : "";

  // Instructor controls
  $("#chillerBtn").classList.toggle("on", s.process.chiller_available);
  $("#chillerBtn").textContent = s.process.chiller_available ? "Chiller running" : "Chiller tripped";
  $("#rpsBtn").classList.toggle("on", s.protection.enabled);
  $("#rpsBtn").textContent = s.protection.enabled ? "RPS in service" : "RPS FAILED";
  $("#failPeriod").checked = s.protection.failed_trips.includes("period");
  $("#failRad").checked = s.protection.failed_trips.includes("radiation");
  for (const [name, r] of Object.entries(s.rods)) {
    const sel = $(`[data-rodfault="${name}"]`);
    if (sel && document.activeElement !== sel) sel.value = r.runaway ? "runaway" : r.stuck ? "stuck" : "none";
  }

  view?.update(s);
  world?.update(s, trend, ann);
  $("#speedTag").textContent = s.speed === 0 ? "paused" : `${s.speed}×`;
  $("#speedTag").classList.toggle("paused", s.speed === 0);
}

function appendEvents(events) {
  const ol = $("#events");
  for (const e of events) {
    const li = document.createElement("li");
    li.className = e.kind;
    li.innerHTML = `<span class="t">${fmtTime(e.t)}</span><span class="kind"></span><span class="m"></span>`;
    $(".kind", li).textContent = e.kind;
    $(".m", li).textContent = e.message;
    ol.prepend(li);
  }
  while (ol.children.length > 500) ol.lastChild.remove();
}

// ------------------------------------------------------------------ trend chart

function drawTrend() {
  const cv = $("#trend");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (!W || !H) return; // workstation closed
  if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, W, H);
  if (!state) return;

  const css = getComputedStyle(cv);       // the workstation theme sets the --trend-* colours
  const col = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  g.fillStyle = col("--trend-bg", "transparent");
  g.fillRect(0, 0, W, H);
  const L = 54, R = 46, T = 10, B = 22;
  const pw = W - L - R, ph = H - T - B;
  const tEnd = Math.max(state.time_s, trendWindow * 0.02);
  const tStart = tEnd - trendWindow;
  const lo = -3, hi = 5; // log10 W: 1 mW to 100 kW
  const x = (t) => L + ((t - tStart) / trendWindow) * pw;
  const y = (w) => T + (1 - (Math.log10(Math.max(w, 1e-3)) - lo) / (hi - lo)) * ph;
  const tmax = Math.max(60, ...trend.filter((p) => p[0] >= tStart).map((p) => p[4] + 10));
  const yT = (c) => T + (1 - (c - 0) / tmax) * ph;

  g.font = "10px " + css.getPropertyValue("--mono");
  g.strokeStyle = col("--trend-grid", "#1c2533");
  g.fillStyle = col("--trend-text", "#4b5869");
  g.lineWidth = 1;
  for (let e = lo; e <= hi; e++) {
    const yy = Math.round(y(10 ** e)) + 0.5;
    g.beginPath(); g.moveTo(L, yy); g.lineTo(L + pw, yy); g.stroke();
    g.textAlign = "right";
    g.fillText(fmtPower(10 ** e), L - 6, yy + 3);
  }
  const step = trendWindow / 6;
  g.textAlign = "center";
  for (let i = 0; i <= 6; i++) {
    const t = tStart + i * step;
    if (t < 0) continue;
    g.fillText(fmtTime(t).replace(/^00:/, ""), x(t), H - 6);
  }
  g.textAlign = "left";
  for (let i = 0; i <= 4; i++) {
    const c = (tmax * i) / 4;
    g.fillStyle = col("--trend-fuel", "#a16207");
    g.fillText(`${c.toFixed(0)}°C`, L + pw + 6, yT(c) + 3);
  }
  // 10 kW rated and 12 kW licensed lines
  g.strokeStyle = col("--trend-limit", "rgba(248,113,113,.5)");
  g.setLineDash([4, 4]);
  g.beginPath(); g.moveTo(L, y(12000)); g.lineTo(L + pw, y(12000)); g.stroke();
  g.setLineDash([]);

  const pts = trend.filter((p) => p[0] >= tStart - 1);
  const line = (fx, fy, color, width = 1.5, dash = []) => {
    g.strokeStyle = color; g.lineWidth = width; g.setLineDash(dash);
    g.beginPath();
    pts.forEach((p, i) => (i ? g.lineTo(fx(p), fy(p)) : g.moveTo(fx(p), fy(p))));
    g.stroke();
    g.setLineDash([]);
  };
  g.save();
  g.beginPath(); g.rect(L, T, pw, ph); g.clip();
  line((p) => x(p[0]), (p) => yT(p[4]), col("--trend-fuel", "rgba(251,191,36,.7)"), 1.2);
  line((p) => x(p[0]), (p) => y(p[3] / 100 * state.reactor.rated_w), col("--trend-ch4", "#64748b"), 1.2);
  line((p) => x(p[0]), (p) => y(p[2] / 100 * state.reactor.rated_w), col("--trend-ch2", "#4fc3f7"), 2);
  if (document.body.classList.contains("truth")) line((p) => x(p[0]), (p) => y(p[1]), col("--trend-true", "#e2e8f0"), 1.2, [5, 4]);
  g.restore();

  // legend
  const items = [["CH2 log power", col("--trend-ch2", "#4fc3f7")], ["CH4 safety", col("--trend-ch4", "#64748b")],
    ["Peak fuel temp", col("--trend-fuel", "#fbbf24")]];
  if (document.body.classList.contains("truth")) items.push(["True power", col("--trend-true", "#e2e8f0")]);
  let lx = L + 8;
  g.font = "11px " + css.getPropertyValue("--sans");
  for (const [label, color] of items) {
    g.fillStyle = color; g.fillRect(lx, T + 6, 10, 3);
    g.fillStyle = col("--trend-text", "#9aa7b6"); g.fillText(label, lx + 14, T + 11);
    lx += g.measureText(label).width + 30;
  }
}

// ------------------------------------------------------------------ polling

let polling = false;
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const s = await api(`/api/state?events_after=${eventsAfter}&trend_after=${trendAfter}`);
    if (state && (s.time_s < state.time_s - 1e-6 || s.event_count < eventsAfter)) {
      resetBuffers(); // the session was restarted
      polling = false;
      return poll();
    }
    state = s;
    if (s.trend.length) {
      trend.push(...s.trend);
      trendAfter = s.trend[s.trend.length - 1][0];
      if (trend.length > 8000) trend = trend.slice(-7200);
    }
    if (s.events.length) {
      appendEvents(s.events);
      eventsAfter = s.event_count;
    }
    render();
    drawTrend();
  } catch (e) {
    const b = $("#banner");
    b.hidden = false;
    b.className = "banner";
    b.textContent = `Lost contact with the simulator: ${e.message}`;
  } finally {
    polling = false;
  }
}

// ------------------------------------------------------------------ updates

let lastUpdate = null;
async function checkUpdates(quiet = true) {
  try {
    lastUpdate = await api("/api/update");
    $("#updateBtn").classList.toggle("has-update", lastUpdate.status === "available");
    $("#updateBtn").textContent = lastUpdate.status === "available" ? "Update available" : "Updates";
  } catch (e) {
    if (!quiet) toast(e.message);
  }
  return lastUpdate;
}

async function openUpdates() {
  const dlg = $("#updateDlg");
  $("#buildInfo").textContent = info.packaged ? `Build ${info.build} · ${String(info.commit).slice(0, 7)}`
    : `Running from source (v${info.version})`;
  $("#updMsg").textContent = "Checking…";
  $("#updNotes").hidden = true;
  $("#installBtn").hidden = true;
  $("#tokenRow").hidden = !info.packaged;
  $("#saveToken").hidden = !info.packaged;
  dlg.showModal();
  const u = await checkUpdates(false);
  if (!u) return;
  $("#updMsg").textContent = u.message;
  if (u.status === "available" && u.notes) {
    $("#updNotes").textContent = u.notes;
    $("#updNotes").hidden = false;
  }
  $("#installBtn").hidden = !u.can_install;
}

async function saveToken() {
  try {
    const r = await api("/api/update/token", { token: $("#tokenInput").value });
    $("#tokenInput").value = "";
    info.has_token = r.has_token;
    openUpdates();
  } catch (e) {
    toast(e.message);
  }
}

async function installUpdate() {
  $("#installBtn").disabled = true;
  $("#updMsg").textContent = "Downloading the update. The app will restart by itself.";
  try {
    await api("/api/update/install", {});
  } catch (e) {
    $("#updMsg").textContent = `Update failed: ${e.message}`;
    $("#installBtn").disabled = false;
  }
}

// ------------------------------------------------------------------ boot

async function boot() {
  try { menuBg = startMenuBackground($("#menuBg")); } catch { /* decoration only */ }
  info = await api("/api/info");
  buildStatic();
  await poll();
  setInterval(poll, 200);
  if (info.models) {
    world = new HallWorld($("#world"), {
      use: openStation,
      command: cmd,
      prompt: setPrompt,
      lockChange: (locked, unsupported) => {
        document.body.classList.toggle("looking", locked);
        if (unsupported) setPrompt("Drag to look around, click a control to use it");
        else if (!locked && !station && $("#menu").hidden) showMenu(true);
      },
    });
    window.pur1 = { world };  // handle for debugging from the console
    $("#enterBtn").textContent = "Loading the hall…";
    $("#enterBtn").disabled = true;
    try {
      await world.load("/models/reactor_hall.glb");
      world.setActive(false);
      $("#enterBtn").textContent = "Enter the hall";
      $("#enterBtn").disabled = false;
    } catch (e) {
      world = null;
      $("#enterBtn").textContent = `Hall unavailable: ${e.message}`;
    }
  } else {
    $("#enterBtn").textContent = "The 3D hall is not in this install";
    $("#view3d").innerHTML = '<div class="view-msg">3D models are not in this install.</div>';
  }
  if (!world) {
    // No hall to walk: open the reactor workstation directly so the plant can still be run.
    $("#enterBtn").disabled = false;
    $("#enterBtn").onclick = () => openStation("reactor");
  }
  window.addEventListener("resize", drawTrend);
  if (info.packaged) {
    checkUpdates();
    setInterval(checkUpdates, 6 * 3600 * 1000);
  }
}

boot().catch((e) => {
  document.body.innerHTML = `<pre style="padding:20px;color:#f87171">Could not start the control room: ${e.message}</pre>`;
});
