// Peach Bottom 2 control room: polls the plant session and works the benchboard controls.
// Every control is on the boards (pb2world.js); the menu only sets the speed, restarts the
// plant and holds the instructor's faults.
import { RoomWorld, ROD_GRID } from "./pb2world.js";
import { RoomSound } from "./pb2audio.js";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let info = null;
let state = null;
let world = null;
let eventsAfter = 0;
let run = null;
const sound = new RoomSound();
const hist = [];           // [{t, r}] recent readings for the recorders
const HIST_MAX = 4000;
const log = [];

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
  if (!res.ok || data.ok === false) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function cmd(action, args = {}) {
  try {
    await api("/api/pb2/command", { action, ...args });
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

let promptTimer = null;
function setPrompt(text, sticky = false) {
  const p = $("#prompt");
  clearTimeout(promptTimer);
  p.hidden = !text;
  p.textContent = text || "";
  if (text && !sticky) promptTimer = setTimeout(() => (p.hidden = true), 2500);
}

function fmtTime(s) {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

// ------------------------------------------------------------------ the controls on the boards

// What each panel control does (role from the model's extras). Spring-return switches and
// pushbuttons act on the click; the rod pushbuttons drive while held.
function control(role, args, mesh) {
  const L = state?.lamps || {};
  const r = state?.readings || {};
  const label = mesh?.userData?.label || role;
  const m = /^srv_(\d+)$/.exec(role);
  if (m) return cmd("srv", { valve: +m[1] });
  const fp = /^feed_pump_[abc]$/.test(role);
  switch (role) {
    case "info": return setPrompt(label);
    case "scram": return cmd("scram");
    case "scram_reset": return cmd("scram_reset");
    case "rod_in": return cmd("rod_drive", { direction: "in" });
    case "rod_out": return cmd("rod_drive", { direction: "out" });
    case "rod_stop": return cmd("rod_drive", { direction: "stop" });
    case "rod_notch_out": return cmd("rod_notch", { notches: 1 });
    case "rod_select": {
      if (args.u === undefined) return;
      const i = Math.floor(args.u * 15), j = Math.floor(args.v * 15);
      const rod = ROD_GRID.find((q) => q.i === i && q.j === j);
      if (!rod) return setPrompt("No rod at that position");
      return cmd("rod_select", { rod: rod.name });
    }
    case "recirc_pump_a": return cmd("recirc_pump", { pump: "a" });
    case "recirc_pump_b": return cmd("recirc_pump", { pump: "b" });
    case "recirc_raise": return cmd("recirc_speed", { delta: 2 });
    case "recirc_lower": return cmd("recirc_speed", { delta: -2 });
    case "level_sp_raise": case "feed_raise": return cmd("level_setpoint", { delta: 1 });
    case "level_sp_lower": case "feed_lower": return cmd("level_setpoint", { delta: -1 });
    case "hpci": case "rcic": case "core_spray": case "lpci": return cmd(role);
    case "hpci_avail": return cmd("available", { system: "hpci", available: !L.hpci_avail });
    case "rcic_avail": return cmd("available", { system: "rcic", available: !L.rcic_avail });
    case "bypass_avail": return cmd("available", { system: "bypass", available: !L.bypass_avail });
    case "condenser_avail": return cmd("available", { system: "condenser", available: !L.condenser_avail });
    case "ads_inhibit": return cmd("ads_inhibit");
    case "ads_manual": return cmd("ads_manual");
    case "msiv": return cmd("msiv");
    case "turbine_trip": return cmd("turbine_trip");
    case "turbine_reset": return cmd("turbine_reset");
    case "press_sp_raise": return cmd("pressure_setpoint", { delta: 5 });
    case "press_sp_lower": return cmd("pressure_setpoint", { delta: -5 });
    case "gen_breaker": return cmd("gen_breaker");
    case "station_blackout": return cmd("station_blackout");
    case "mode_switch": return cmd("mode_switch");
    case "slc": return cmd("slc");
    case "ann_ack": return cmd("ann_ack");
    case "ann_reset": return cmd("ann_reset");
    case "ann_test": return cmd("ann_test");
    default:
      if (fp) return cmd("feed_pump");
      return setPrompt(`${label} (${r.mode || ""})`);
  }
}

// ------------------------------------------------------------------ polling and the HUD

let polling = false;
async function poll() {
  if (polling) return;   // a command's refresh and the timer must not overlap, or events repeat
  polling = true;
  try {
    const s = await api(`/api/pb2/state?events_after=${eventsAfter}`);
    if (run !== null && s.run !== run) { hist.length = 0; log.length = 0; eventsAfter = 0; return poll(); }
    run = s.run;
    state = s;
    if (!hist.length || s.time_s > hist[hist.length - 1].t) {
      hist.push({ t: s.time_s, r: s.readings });
      if (hist.length > HIST_MAX) hist.splice(0, hist.length - HIST_MAX);
    }
    for (const e of s.events) {
      if (e.i < eventsAfter) continue;
      log.push(e);
      eventsAfter = e.i + 1;
    }
    if (log.length > 6) log.splice(0, log.length - 6);
    render(s);
  } catch (e) {
    $("#banner").textContent = `Lost the session: ${e.message}`;
    $("#banner").hidden = false;
  } finally {
    polling = false;
  }
}

function render(s) {
  $("#clock").textContent = fmtTime(s.time_s);
  $("#speedTag").textContent = s.speed === 0 ? "paused" : `${s.speed}×`;
  $("#speedTag").classList.toggle("paused", s.speed === 0);
  $("#powerTag").textContent = `${s.readings.aprm.toFixed(1)} %  ${s.readings.pressure.toFixed(0)} psig  L ${s.readings.level.toFixed(0)} in`;
  $$("#speed button").forEach((b) => b.classList.toggle("on", +b.dataset.speed === s.speed));
  const banner = $("#banner");
  if (s.scrammed) {
    banner.textContent = `SCRAM: ${s.scram_causes.join("; ")}`;
    banner.className = "banner";
    banner.hidden = false;
  } else if (s.alarms.length) {
    banner.textContent = s.alarms.join("  ·  ");
    banner.className = "banner info";
    banner.hidden = false;
  } else banner.hidden = true;
  $("#log").innerHTML = log.map((e) => `<div class="${e.kind}">${fmtTime(e.t)}  ${e.message}</div>`).join("");
  $("#rpsFail").setAttribute("aria-pressed", String(!!s.lamps.rps_trouble));
  $("#rpsFail").classList.toggle("on", !!s.lamps.rps_trouble);
  world?.update(s, hist);
}

// ------------------------------------------------------------------ menu

function showMenu(on) {
  $("#menu").hidden = !on;
  if (on) world?.setActive(false);
  else world?.setActive(true);
}

function enterRoom() {
  document.activeElement?.blur?.();
  document.body.classList.remove("main-menu");
  $("#menuTitle").textContent = "Peach Bottom Unit 2 - Menu";
  showMenu(false);
  sound.start();   // needs the click on "Enter" before the browser will play anything
  if (!world) return;
  world.setActive(true);
  world.lock();
}

async function toggleFullscreen() {
  try {
    if (info?.native_window) await api("/api/window/fullscreen", {});
    else if (document.fullscreenElement) await document.exitFullscreen();
    else {
      await document.documentElement.requestFullscreen();
      await navigator.keyboard?.lock?.(["Escape"]).catch(() => {});
    }
  } catch (e) { toast(`Full screen: ${e.message}`); }
}

function buildMenu() {
  $("#speed").innerHTML = info.speeds.map((s) => `<button data-speed="${s}">${s === 0 ? "❚❚" : `${s}×`}</button>`).join("");
  $$("#speed button").forEach((b) => b.addEventListener("click", () => cmd("speed", { speed: +b.dataset.speed })));
  const states = info.plants?.pb2?.initial_states || { full_power: "Full power" };
  $("#initial").innerHTML = Object.entries(states).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  $("#restart").addEventListener("click", () => cmd("reset", { initial: $("#initial").value }));
  $("#rpsFail").addEventListener("click", () => cmd("fault", { which: "rps" }));
  $("#tsvBypass").addEventListener("click", (e) => {
    const on = e.currentTarget.getAttribute("aria-pressed") !== "true";
    e.currentTarget.setAttribute("aria-pressed", String(on));
    e.currentTarget.classList.toggle("on", on);
    cmd("fault", { which: "tsv_scram", enabled: !on });
  });
  $("#sboBtn").addEventListener("click", () => cmd("station_blackout"));
  $("#lofwBtn").addEventListener("click", () => cmd("feed_pump"));
  $("#fullscreenBtn").addEventListener("click", toggleFullscreen);
  const prefs = (() => { try { return JSON.parse(localStorage.getItem("pb2.sound") || "{}"); } catch { return {}; } })();
  if (typeof prefs.on === "boolean") $("#soundOn").checked = prefs.on;
  if (typeof prefs.vol === "number") $("#soundVol").value = prefs.vol;
  const applySound = () => {
    sound.setEnabled($("#soundOn").checked);
    sound.setVolume(+$("#soundVol").value);
    try { localStorage.setItem("pb2.sound", JSON.stringify({ on: $("#soundOn").checked, vol: +$("#soundVol").value })); } catch { /* private window */ }
  };
  $("#soundOn").addEventListener("change", () => { sound.start(); applySound(); });
  $("#soundVol").addEventListener("input", () => { sound.start(); applySound(); });
  applySound();
  $("#enterBtn").addEventListener("click", enterRoom);
  document.addEventListener("keydown", (e) => {
    if (e.code === "KeyF" && !e.target.closest?.("input, select, textarea")) { e.preventDefault(); toggleFullscreen(); }
    if (e.code !== "Escape") return;
    e.preventDefault();
    if ($("#menu").hidden) showMenu(true);
    else if (!document.body.classList.contains("main-menu")) enterRoom();
  });
}

async function boot() {
  info = await api("/api/info");
  buildMenu();
  await poll();
  setInterval(poll, 200);
  if (info.models) {
    world = new RoomWorld($("#world"), {
      command: control,
      prompt: setPrompt,
      lockChange: (locked, unsupported) => {
        document.body.classList.toggle("looking", locked);
        if (unsupported) setPrompt("Drag to look around, click a control to use it");
        else if (!locked && $("#menu").hidden) showMenu(true);
      },
    });
    window.pb2 = { world, hist };
    try {
      await world.load("/models/pb2_control_room.glb");
      world.setActive(false);
      if (state) world.update(state, hist);
      $("#enterBtn").textContent = "Enter the control room";
      $("#enterBtn").disabled = false;
    } catch (e) {
      world = null;
      $("#enterBtn").textContent = `Control room unavailable: ${e.message}`;
    }
  } else {
    $("#enterBtn").textContent = "The 3D control room is not in this install";
  }
}

boot().catch((e) => {
  document.body.innerHTML = `<pre style="padding:20px;color:#f87171">Could not start the control room: ${e.message}</pre>`;
});
