// The Peach Bottom Unit 2 main control room as a place to stand in and work the boards.
//
// Loads models/export/pb2_control_room.glb (Y up, metres, floor at y = 0, the reactor benchboard
// P603 to the north at z = -4, P601 core cooling to the west, P653 turbine-generator to the east).
// Everything on the panels that reads or does something is a mesh named ui_... whose glTF extras
// (models/peach_bottom/panels.py) say what it is: a meter with its scale, a recorder with its
// pens, a lamp with the reading that lights it, a switch with its positions, a pushbutton with
// its role. The page draws the instrument faces on canvases from the live plant readings, so the
// scales and pointers are drawn, not textured, and the lamps and switch handles move.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/three/loaders/GLTFLoader.js";

const EYE = 1.65, RADIUS = 0.28, WALK = 1.5, RUN = 3.2, REACH = 2.0;
const SPAWN = { x: 0.0, z: 1.3, yaw: 0.0, pitch: -0.12 };   // inside the horseshoe, facing P603
const NO_COLLIDE = ["Ceiling", "LightFixtures", "Sign_Unit2", "WallClock", "ClockFrame"];

const SANS = '-apple-system, "Segoe UI", Helvetica, Arial, sans-serif';
const MONO = '"SF Mono", Menlo, Consolas, monospace';
const LAMP_RGB = { red: 0xff2a1a, green: 0x30ff50, amber: 0xffb020, white: 0xffffff, blue: 0x4080ff };

// Annunciator window engravings, by key (models/peach_bottom/control_room.py ANN_*).
const ANN_TEXT = {
  aprm_high: "APRM UPSCALE TRIP", aprm_flow: "APRM FLOW BIAS TRIP", aprm_setdown: "APRM SETDOWN TRIP", irm_high: "IRM UPSCALE",
  rod_block: "ROD BLOCK", rod_drift: "ROD DRIFT", select_error: "ROD SELECT ERROR", scram: "REACTOR SCRAM", half_scram: "RPS HALF SCRAM",
  rps_trouble: "RPS SYSTEM TROUBLE", level_low_l4: "RX LEVEL LOW L4", level_low_l3: "RX LEVEL LOW L3 SCRAM", level_high_l7: "RX LEVEL HIGH L7",
  level_high_l8: "RX LEVEL HIGH L8 TRIP", pressure_high: "RX PRESSURE HIGH", msl_low: "MSL PRESS LOW ISOL", tsv_closure: "TURB STOP VLV CLOSED",
  msiv_closure: "MSIV CLOSURE", mode_startup: "MODE SW NOT IN RUN", exclusion: "POWER/FLOW EXCLUSION", recirc_a_trip: "RECIRC PUMP A TRIP",
  recirc_b_trip: "RECIRC PUMP B TRIP", atws_rpt: "ATWS RPT", feed_trip: "FEED PUMPS TRIPPED", level_l2: "RX LEVEL LOW L2", level_l1: "RX LEVEL LOW L1",
  core_uncovered: "CORE UNCOVERED", fuel_damage: "FUEL FAILURE", srv_open: "SRV OPEN", hpci_init: "HPCI INITIATED", hpci_run: "HPCI RUNNING",
  rcic_init: "RCIC INITIATED", rcic_run: "RCIC RUNNING", cs_init: "CORE SPRAY INITIATED", cs_run: "CORE SPRAY RUNNING", lpci_init: "LPCI INITIATED",
  lpci_run: "LPCI RUNNING", ads_timer: "ADS TIMER RUNNING", ads_open: "ADS VALVES OPEN", ads_inhibit: "ADS INHIBITED", torus_temp: "TORUS WATER TEMP HI",
  torus_level: "TORUS LEVEL HI/LO", drywell_press: "DRYWELL PRESS HIGH", hpci_unavail: "HPCI OUT OF SERVICE", rcic_unavail: "RCIC OUT OF SERVICE",
  cs_unavail: "CORE SPRAY OOS", lpci_unavail: "LPCI OUT OF SERVICE", turbine_trip: "TURBINE TRIP", gen_breaker: "GEN BREAKER OPEN",
  tcv_fast: "TCV FAST CLOSURE", bypass_open: "BYPASS VALVES OPEN", bypass_unavail: "BYPASS VALVES OOS", condenser_low: "CONDENSER VACUUM LOW",
  ehc_trouble: "EHC TROUBLE", feed_a_trip: "RFPT A TRIP", feed_b_trip: "RFPT B TRIP", feed_c_trip: "RFPT C TRIP",
  station_blackout: "LOSS OF OFFSITE POWER", diesel_start: "DIESEL GEN AUTO START", spare: "",
};
const ANN_RED = new Set(["scram", "level_low_l3", "level_l2", "level_l1", "core_uncovered", "fuel_damage", "hpci_init", "rcic_init",
  "cs_init", "lpci_init", "ads_open", "turbine_trip", "msiv_closure", "station_blackout", "atws_rpt", "aprm_high", "aprm_flow"]);

// Control rod positions of a BWR/4 core: rods sit between four bundles on a 15 x 15 lattice
// named by odd coordinates 02..58; the 185 inside the core boundary are the ones on the display.
const ROD_GRID = [];
for (let j = 0; j < 15; j++) for (let i = 0; i < 15; i++) {
  const d = Math.hypot(i - 7, j - 7);
  if (d <= 7.4) ROD_GRID.push({ i, j, name: `${String(2 + 4 * i).padStart(2, "0")}-${String(2 + 4 * j).padStart(2, "0")}` });
}

function roomEnvironment(renderer) {
  const env = new THREE.Scene();
  const box = (w, h, d, color, x, y, z, side = THREE.FrontSide) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshBasicMaterial({ color, side }));
    m.position.set(x, y, z);
    env.add(m);
  };
  box(20, 3.2, 15, 0x6c6a62, 0, 1.6, 0, THREE.BackSide);
  for (const x of [-6, -2, 2, 6]) for (const z of [-4, 0, 4]) box(0.6, 0.05, 1.2, new THREE.Color(5, 5, 4.7), x, 3.15, z);
  const pm = new THREE.PMREMGenerator(renderer);
  const tex = pm.fromScene(env, 0.04).texture;
  pm.dispose();
  return tex;
}

export class RoomWorld {
  constructor(el, hooks) {
    this.el = el;
    this.hooks = hooks;   // { command(role, args, mesh), prompt(text, sticky), lockChange(locked, unsupported), history() }
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.85;
    el.appendChild(this.renderer.domElement);
    this.canvas = this.renderer.domElement;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b0f14);
    this.camera = new THREE.PerspectiveCamera(68, 1, 0.05, 60);
    this.camera.rotation.order = "YXZ";
    this.scene.environment = roomEnvironment(this.renderer);
    this.scene.add(new THREE.HemisphereLight(0xf6f7ff, 0x40443f, 0.45));
    for (const x of [-6, 0, 6]) for (const z of [-5, -1, 3]) {
      const l = new THREE.PointLight(0xfff5e6, 2.6, 11, 1.5);
      l.position.set(x, 3.05, z);
      this.scene.add(l);
    }
    this.pos = new THREE.Vector3(SPAWN.x, 0, SPAWN.z);
    this.yaw = SPAWN.yaw;
    this.pitch = SPAWN.pitch;
    this.keys = new Set();
    this.active = true;
    this.locked = false;
    this.dragLook = false;
    this.hover = null;
    this.held = null;
    this.ray = new THREE.Raycaster();
    this.colliders = [];
    this.pickables = [];
    this.faces = [];       // { mesh, ud, cv, ctx, tex }
    this.lamps = [];       // { mesh, ud }
    this.switches = [];    // { mesh, ud, pivot }
    this.clock = new THREE.Clock();
    this.blink = false;
    this._bindInput();
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
  }

  // ------------------------------------------------------------------ loading

  async load(url) {
    const gltf = await new GLTFLoader().loadAsync(url);
    this.root = gltf.scene;
    this.scene.add(this.root);
    this.root.updateMatrixWorld(true);
    this.root.traverse((o) => {
      if (!o.isMesh) return;
      const name = o.name || o.parent?.name || "";
      const ud = o.userData || {};
      if (!NO_COLLIDE.includes(name) && !name.startsWith("Lettering_") && !name.startsWith("Glass_")) this.colliders.push(o);
      if (ud.role || ud.label) {
        o.material = o.material.clone();
        o.userData.baseEmissive = o.material.emissive?.clone();
        this.pickables.push(o);
      }
      if (name.startsWith("Glass_")) {
        o.material = o.material.clone();
        o.material.transparent = true;
        o.material.opacity = 0.12;
        o.material.depthWrite = false;
      }
      if (ud.face === "lamp") {
        o.material = o.material.clone();
        this.lamps.push({ mesh: o, ud });
      } else if (ud.face && name.startsWith("ui_")) {
        this.faces.push(this._face(o, ud));
      }
      if (ud.positions !== undefined && ud.pivot_z !== undefined) {
        // Blender (x, y, z) became three (x, z, -y): the pivot sits on the handle's own axis.
        this.switches.push({ mesh: o, ud, pivot: new THREE.Vector3(0, ud.pivot_z, -ud.pivot_y), n: ud.positions.split(",").length });
      }
      if (o.material?.name === "PB_LightFixture") o.material.emissiveIntensity = 1.2;
    });
    this.renderer.setAnimationLoop(() => this._frame());
  }

  _face(mesh, ud) {
    // A drawn instrument face. The quad lies in the mesh's local y-z plane (facing local -x);
    // the operator's right is local +z and up is local +y, whatever way the panel is tilted.
    const g = mesh.geometry.clone();
    const p = g.attributes.position;
    let z0 = Infinity, z1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < p.count; i++) {
      z0 = Math.min(z0, p.getZ(i)); z1 = Math.max(z1, p.getZ(i));
      y0 = Math.min(y0, p.getY(i)); y1 = Math.max(y1, p.getY(i));
    }
    const uv = new Float32Array(p.count * 2);
    for (let i = 0; i < p.count; i++) {
      uv[2 * i] = (p.getZ(i) - z0) / (z1 - z0 || 1);
      uv[2 * i + 1] = (p.getY(i) - y0) / (y1 - y0 || 1);
    }
    g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    mesh.geometry = g;
    const w = z1 - z0, h = y1 - y0;
    const scale = ud.face === "ann" || ud.face === "core" || ud.face === "rodselect" ? 1400 : 2600;
    const cv = document.createElement("canvas");
    cv.width = Math.min(1536, Math.max(96, Math.round(w * scale)));
    cv.height = Math.min(1536, Math.max(96, Math.round(h * scale)));
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    mesh.material = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false });
    mesh.userData.baseEmissive = null;
    return { mesh, ud, cv, ctx: cv.getContext("2d"), tex, w, h };
  }

  // ------------------------------------------------------------------ input (as in world.js)

  _bindInput() {
    const c = this.canvas;
    document.addEventListener("keydown", (e) => {
      if (e.target.closest?.("input, select, textarea, dialog")) return;
      if (!e.metaKey && !e.ctrlKey && !(e.target.closest?.("button") && (e.key === "Enter" || e.key === " "))) e.preventDefault();
      this.keys.add(e.code);
      if (e.code === "KeyE" && this.active && !e.repeat) this._press();
    });
    document.addEventListener("keyup", (e) => {
      if (!e.metaKey && !e.ctrlKey && !e.target.closest?.("input, select, textarea, dialog, button")) e.preventDefault();
      this.keys.delete(e.code);
      if (e.code === "KeyE") this._release();
    });
    window.addEventListener("blur", () => { this.keys.clear(); this._release(); });
    document.addEventListener("pointerlockchange", () => {
      this.locked = document.pointerLockElement === c;
      if (!this.locked) this._release();
      this.hooks.lockChange?.(this.locked);
    });
    document.addEventListener("pointerlockerror", () => {
      this.dragLook = true;
      this.hooks.lockChange?.(false, true);
    });
    let down = null;
    c.addEventListener("contextmenu", (e) => e.preventDefault());
    c.addEventListener("mousedown", (e) => {
      e.preventDefault();
      if (!this.active || e.button !== 0) return;
      if (this.locked) { this._press(); return; }
      down = { x: e.clientX, y: e.clientY, moved: false };
      if (this.dragLook) this._pickAt(e.clientX, e.clientY) && this._press();
    });
    window.addEventListener("mousemove", (e) => {
      if (this.locked) this._look(e.movementX, e.movementY);
      else if (down && this.dragLook) {
        if (Math.abs(e.clientX - down.x) + Math.abs(e.clientY - down.y) > 4) {
          down.moved = true;
          if (!this.held) this._look(e.movementX, e.movementY);
        }
      } else if (this.dragLook && this.active) this._pickAt(e.clientX, e.clientY);
    });
    window.addEventListener("mouseup", () => {
      this._release();
      if (down && !this.dragLook && !down.moved) this.lock();
      down = null;
    });
  }

  lock() {
    if (this.dragLook || !this.active) return;
    try {
      const p = this.canvas.requestPointerLock({ unadjustedMovement: true });
      if (p?.catch) p.catch(() => this.canvas.requestPointerLock());
    } catch { this.canvas.requestPointerLock(); }
  }

  unlock() { if (this.locked) document.exitPointerLock(); }

  setActive(on) {
    this.active = on;
    if (!on) { this.keys.clear(); this._release(); this.unlock(); this._setHover(null); }
  }

  _look(dx, dy) {
    this.yaw -= dx * 0.0022;
    this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch - dy * 0.0022));
  }

  _press() {
    const o = this.hover;
    if (!o) return;
    const ud = o.userData;
    const role = ud.role || "info";
    const hold = role === "rod_in" || role === "rod_out";
    if (hold) this.held = o;
    const args = {};
    if (this.lastHit?.object === o && this.lastHit.uv) { args.u = this.lastHit.uv.x; args.v = this.lastHit.uv.y; }
    this.hooks.command(role, args, o);
    this._flash(o, hold);
  }

  _release() {
    if (!this.held) return;
    this.hooks.command("rod_stop", {}, this.held);
    this._unflash(this.held);
    this.held = null;
  }

  _flash(o, hold = false) {
    if (!o.material.emissive) return;
    o.material.emissive.setHex(0x666666);
    if (!hold) setTimeout(() => this._unflash(o), 180);
  }

  _unflash(o) {
    if (o.material.emissive) o.material.emissive.copy(o.userData.baseEmissive || new THREE.Color(0));
    if (o === this.hover) this._setHover(o, true);
  }

  _pickFrom(ndc) {
    this.ray.setFromCamera(ndc, this.camera);
    this.ray.far = REACH + 0.4;
    const hits = this.ray.intersectObjects(this.colliders.concat(this.pickables), false);
    const hit = hits.find((h) => h.object.visible && !(h.object.name || "").startsWith("Glass_"));
    const ud = hit?.object.userData;
    const o = hit && (ud.role || ud.label) && hit.distance <= REACH ? hit.object : null;
    this.lastHit = o ? hit : null;
    this._setHover(o);
    return o;
  }

  _pickAt(x, y) {
    const r = this.canvas.getBoundingClientRect();
    return this._pickFrom(new THREE.Vector2(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1));
  }

  _setHover(o, force = false) {
    if (o === this.hover && !force) return;
    const prev = this.hover;
    if (prev && prev !== this.held && prev.material.emissive) prev.material.emissive.copy(prev.userData.baseEmissive || new THREE.Color(0));
    this.hover = o;
    if (o && o.material.emissive && o !== this.held) o.material.emissive.setHex(0x1a3a4a);
    if (!o) { this.hooks.prompt(null); return; }
    const ud = o.userData;
    const role = ud.role || "info";
    const verb = role === "info" ? "" : role === "rod_in" || role === "rod_out" ? "Hold" : "Click";
    this.hooks.prompt(verb ? `${verb}: ${ud.label}` : ud.label, true);
  }

  _frame() {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    if (this.active) this._move(dt);
    this.camera.position.set(this.pos.x, this.pos.y + EYE, this.pos.z);
    this.camera.rotation.set(this.pitch, this.yaw, 0);
    if (this.active && (this.locked || this.keys.size)) this._pickFrom(new THREE.Vector2(0, 0));
    this.renderer.render(this.scene, this.camera);
  }

  _move(dt) {
    const k = this.keys;
    const f = (k.has("KeyW") || k.has("ArrowUp") ? 1 : 0) - (k.has("KeyS") || k.has("ArrowDown") ? 1 : 0);
    const s = (k.has("KeyD") || k.has("ArrowRight") ? 1 : 0) - (k.has("KeyA") || k.has("ArrowLeft") ? 1 : 0);
    if (!f && !s) return;
    const n = Math.hypot(f, s);
    const speed = (k.has("ShiftLeft") || k.has("ShiftRight") ? RUN : WALK) * dt / n;
    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const right = new THREE.Vector3(-fwd.z, 0, fwd.x);
    const d = fwd.multiplyScalar(f * speed).add(right.multiplyScalar(s * speed));
    this._tryMove(d.x, 0);
    this._tryMove(0, d.z);
  }

  _tryMove(dx, dz) {
    const len = Math.hypot(dx, dz);
    if (len < 1e-6) return;
    const dir = new THREE.Vector3(dx / len, 0, dz / len);
    for (const h of [0.35, 0.72, 1.1, 1.75]) {
      this.ray.set(new THREE.Vector3(this.pos.x, h, this.pos.z), dir);
      this.ray.far = len + RADIUS;
      if (this.ray.intersectObjects(this.colliders, false).length) return;
    }
    this.pos.x += dx;
    this.pos.z += dz;
  }

  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // ------------------------------------------------------------------ the live plant on the boards

  update(s, hist) {
    if (!this.root) return;
    const r = s.readings, L = s.lamps, ann = s.annunciators;
    const blink = Math.floor(performance.now() / 400) % 2 === 0;
    for (const { mesh, ud } of this.lamps) {
      const tag = ud.lamp;
      const on = tag === "" ? false : ann.__test__ ? true : !!L[tag];
      mesh.material.emissive.setHex(on ? LAMP_RGB[ud.colour] || 0xffffff : 0);
      mesh.material.emissiveIntensity = on ? 1.6 : 0;
      mesh.material.color.setHex(on ? LAMP_RGB[ud.colour] : 0x101010);
    }
    for (const sw of this.switches) {
      let idx = (sw.n - 1) / 2;
      if (!sw.ud.spring) {
        const v = sw.ud.tag ? r[sw.ud.tag] : undefined;
        idx = typeof v === "number" ? v : (sw.ud.tag && L[sw.ud.tag] ? sw.n - 1 : 0);
        if (sw.n === 2 && typeof v !== "number") idx = sw.ud.tag && L[sw.ud.tag] ? 1 : 0;
      }
      const angle = (idx - (sw.n - 1) / 2) * (sw.n > 3 ? 0.55 : 0.7);
      sw.mesh.rotation.set(angle, 0, 0);
      const p = sw.pivot.clone().applyAxisAngle(new THREE.Vector3(1, 0, 0), angle);
      sw.mesh.position.copy(sw.pivot).sub(p);
    }
    for (const f of this.faces) {
      const d = DRAW[f.ud.face];
      if (d) { d(f, r, L, ann, s, hist, blink); f.tex.needsUpdate = true; }
    }
  }
}

// ------------------------------------------------------------------ instrument faces

function val(r, tag) {
  const v = r[tag];
  return typeof v === "number" ? v : null;
}

function fmtNum(v, lo, hi) {
  if (v === null) return "--";
  const span = Math.abs(hi - lo);
  return span >= 1000 ? v.toFixed(0) : span >= 100 ? v.toFixed(0) : span >= 20 ? v.toFixed(1) : v.toFixed(2);
}

function cream(g, W, H) {
  g.fillStyle = "#efe9d6";
  g.fillRect(0, 0, W, H);
}

function vText(g, text, x, y, size, color = "#111", align = "center", bold = false, font = SANS) {
  g.font = `${bold ? "bold " : ""}${size}px ${font}`;
  g.fillStyle = color;
  g.textAlign = align;
  g.textBaseline = "middle";
  g.fillText(text, x, y);
}

// Vertical "edgewise" meter: scale up the left, red band over the trip zone, black pointer
// sliding in a slot on the right, legend engraved at the top and the unit at the bottom.
function drawMeter(f, r) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  cream(g, W, H);
  const lo = +ud.lo, hi = +ud.hi, log = +ud.log === 1;
  const top = H * 0.16, bot = H * 0.90, x0 = W * 0.42;
  const yOf = (v) => bot - (bot - top) * (Math.min(Math.max((v - lo) / (hi - lo), 0), 1));
  // red zone: above the trip value when it lies in the upper half, below it otherwise
  if (ud.red !== undefined && ud.red !== null) {
    const red = +ud.red;
    g.fillStyle = "#d42a1f";
    const upper = red > (lo + hi) / 2;
    g.fillRect(x0 - W * 0.05, upper ? yOf(hi) : yOf(red), W * 0.05, Math.abs(yOf(red) - (upper ? yOf(hi) : yOf(lo))));
  }
  g.strokeStyle = "#111";
  g.lineWidth = Math.max(1, W / 90);
  g.beginPath(); g.moveTo(x0, top); g.lineTo(x0, bot); g.stroke();
  const major = 10, minor = 5;
  const fs = Math.max(7, W * 0.11);
  for (let i = 0; i <= major * minor; i++) {
    const v = lo + (hi - lo) * i / (major * minor);
    const y = yOf(v);
    const big = i % minor === 0;
    g.beginPath(); g.moveTo(x0, y); g.lineTo(x0 - (big ? W * 0.14 : W * 0.07), y); g.stroke();
    if (big && (i / minor) % 2 === 0) {
      const t = log ? (v >= 0 ? `1E${Math.round(v)}` : `1E${Math.round(v)}`) : fmtNum(v, lo, hi).replace(/\.0+$/, "");
      vText(g, t, x0 - W * 0.17, y, fs, "#111", "right", false, SANS);
    }
  }
  // pointer
  const v = val(r, ud.tag);
  const y = v === null ? bot : yOf(log ? v : v);
  g.fillStyle = "#111";
  g.beginPath();
  g.moveTo(x0 + W * 0.02, y); g.lineTo(x0 + W * 0.30, y - W * 0.06); g.lineTo(x0 + W * 0.30, y + W * 0.06); g.closePath();
  g.fill();
  g.fillStyle = "#c81e14";
  g.fillRect(x0 + W * 0.02, y - Math.max(1, W * 0.012), W * 0.12, Math.max(2, W * 0.024));
  // legend and unit
  const legend = String(ud.legend || "");
  const lfs = Math.max(7, Math.min(W * 0.11, W * 1.6 / Math.max(6, legend.length)));
  vText(g, legend, W / 2, H * 0.06, lfs, "#111", "center", true);
  vText(g, String(ud.unit || ""), W / 2, H * 0.955, Math.max(7, W * 0.10), "#333", "center");
}

function drawRound(f, r) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  cream(g, W, H);
  const lo = +ud.lo, hi = +ud.hi;
  const cx = W / 2, cy = H * 0.56, R = Math.min(W, H) * 0.40;
  const a0 = Math.PI * 1.25, a1 = Math.PI * -0.25;   // 270 degree sweep, clockwise
  const aOf = (v) => a0 + (a1 - a0) * Math.min(Math.max((v - lo) / (hi - lo), 0), 1);
  if (ud.red !== undefined && ud.red !== null) {
    g.strokeStyle = "#d42a1f"; g.lineWidth = R * 0.08;
    const red = +ud.red, upper = red > (lo + hi) / 2;
    g.beginPath(); g.arc(cx, cy, R * 0.92, upper ? aOf(red) : aOf(lo), upper ? aOf(hi) : aOf(red), true); g.stroke();
  }
  g.strokeStyle = "#111"; g.lineWidth = Math.max(1, R * 0.02);
  g.beginPath(); g.arc(cx, cy, R, a0, a1, true); g.stroke();
  for (let i = 0; i <= 50; i++) {
    const v = lo + (hi - lo) * i / 50, a = aOf(v), big = i % 5 === 0;
    const r0 = big ? R * 0.84 : R * 0.92;
    g.beginPath(); g.moveTo(cx + R * Math.cos(a), cy - R * Math.sin(a)); g.lineTo(cx + r0 * Math.cos(a), cy - r0 * Math.sin(a)); g.stroke();
    if (big && i % 10 === 0) vText(g, fmtNum(v, lo, hi).replace(/\.0+$/, ""), cx + R * 0.70 * Math.cos(a), cy - R * 0.70 * Math.sin(a), R * 0.16, "#111");
  }
  const v = val(r, ud.tag);
  const a = aOf(v === null ? lo : v);
  g.strokeStyle = "#111"; g.lineWidth = Math.max(2, R * 0.04);
  g.beginPath(); g.moveTo(cx - R * 0.15 * Math.cos(a), cy + R * 0.15 * Math.sin(a)); g.lineTo(cx + R * 0.95 * Math.cos(a), cy - R * 0.95 * Math.sin(a)); g.stroke();
  g.fillStyle = "#111"; g.beginPath(); g.arc(cx, cy, R * 0.08, 0, Math.PI * 2); g.fill();
  vText(g, String(ud.legend || ""), cx, H * 0.08, Math.max(7, W * 0.09), "#111", "center", true);
  vText(g, String(ud.unit || ""), cx, cy + R * 0.45, Math.max(7, W * 0.09), "#333");
}

// Strip-chart recorder: the paper runs downward, the pens write at the top edge. The chart
// shows the last few minutes of plant time from the page's reading history.
const PEN = { red: "#d42a1f", green: "#1f8a3a", blue: "#2a4fd4" };
function drawRecorder(f, r, L, ann, s, hist) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#f6f2e4";
  g.fillRect(0, 0, W, H);
  const lo = +ud.lo, hi = +ud.hi;
  const tags = String(ud.tag).split(","), colours = String(ud.colours).split(",");
  const head = H * 0.14, x0 = W * 0.08, x1 = W * 0.96;
  const xOf = (v, i) => {
    // pens with a different range from the paper (level on a pressure chart) are scaled to it
    let a = lo, b = hi;
    if (tags[i] === "level" && hi > 200) { a = 0; b = 60; }
    if (tags[i] === "pressure" && hi <= 100) { a = 0; b = 1500; }
    if (tags[i] === "pressure" && lo < 0) { a = 0; b = 1500; }
    if (tags[i] === "core_flow" && hi === 125) { a = 0; b = 125; }
    if (tags[i] === "steam_flow" && hi >= 1000) { a = 0; b = 20; }
    if (tags[i] === "gen_hz") { a = 55; b = 65; }
    if (tags[i] === "bypass") { a = 0; b = 100; }
    if (tags[i] === "feed_flow" && lo < 0) { a = 0; b = 20; }
    if (tags[i] === "drywell_pressure") { a = -5; b = 80; }
    if (tags[i] === "srm") { a = -1; b = 6; }
    if (tags[i] === "thermal_power") { a = 0; b = 125; }
    return x0 + (x1 - x0) * Math.min(Math.max((v - a) / (b - a), 0), 1);
  };
  // chart grid
  g.strokeStyle = "#9bbf9e"; g.lineWidth = 1;
  for (let i = 0; i <= 10; i++) {
    const x = x0 + (x1 - x0) * i / 10;
    g.beginPath(); g.moveTo(x, head); g.lineTo(x, H); g.stroke();
  }
  const span = 600;   // seconds of plant time on the visible paper
  const t1 = s.time_s;
  const yOf = (t) => head + (H - head) * (t1 - t) / span;
  for (let k = 0; k <= span; k += 60) {
    const t = t1 - ((t1 % 60) + k);
    if (t < t1 - span) break;
    const y = yOf(t);
    g.strokeStyle = k % 300 === (t1 % 60 ? 0 : 0) ? "#9bbf9e" : "#9bbf9e";
    g.beginPath(); g.moveTo(x0, y); g.lineTo(x1, y); g.stroke();
  }
  // pens
  if (hist && hist.length > 1) {
    tags.forEach((tag, i) => {
      g.strokeStyle = PEN[colours[i]] || "#111";
      g.lineWidth = Math.max(1.5, W / 160);
      g.beginPath();
      let started = false;
      for (let k = hist.length - 1; k >= 0; k--) {
        const h = hist[k];
        if (h.t < t1 - span) break;
        const v = h.r[tag];
        if (typeof v !== "number") continue;
        const x = xOf(v, i), y = yOf(h.t);
        if (!started) { g.moveTo(x, y); started = true; } else g.lineTo(x, y);
      }
      g.stroke();
    });
  }
  // header: legend, current values in pen colours, scale ends
  g.fillStyle = "#2b2b2b";
  g.fillRect(0, 0, W, head);
  vText(g, String(ud.legend || ""), W / 2, head * 0.3, Math.max(7, Math.min(W * 0.055, W * 1.5 / Math.max(10, String(ud.legend).length))), "#eee", "center", true);
  tags.forEach((tag, i) => {
    const v = val(r, tag);
    vText(g, v === null ? "--" : fmtNum(v, lo, hi), x0 + (x1 - x0) * (i + 0.5) / tags.length, head * 0.72, Math.max(8, W * 0.06), PEN[colours[i]] || "#eee", "center", true, MONO);
  });
  vText(g, String(lo), x0, head + H * 0.03, Math.max(6, W * 0.04), "#444", "left");
  vText(g, `${hi} ${ud.unit || ""}`, x1, head + H * 0.03, Math.max(6, W * 0.04), "#444", "right");
}

function drawDigital(f, r, L, ann, s) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#160404";
  g.fillRect(0, 0, W, H);
  const v = r[ud.tag];
  let text;
  if (ud.tag === "time_since_scram") text = s.scrammed ? String(Math.floor(v || 0)).padStart(+ud.digits || 4, "0") : "";
  else if (typeof v === "string") text = v;
  else if (typeof v === "number") text = ud.tag === "rod_notch" ? String(Math.round(v)).padStart(2, "0") : ud.tag === "reactivity" ? (v >= 0 ? "+" : "-") + Math.abs(v).toFixed(2) : v.toFixed(0);
  else text = "--";
  vText(g, text, W / 2, H / 2, H * 0.72, "#ff3b1f", "center", true, MONO);
  vText(g, String(ud.legend || ""), W / 2, H * 0.92, Math.max(6, H * 0.13), "#aa7766", "center");
}

function drawMA(f, r, L) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  cream(g, W, H);
  const lo = +ud.lo, hi = +ud.hi;
  const v = val(r, ud.tag), sp = val(r, ud.setpoint);
  const top = H * 0.22, bot = H * 0.86, x = W * 0.5;
  const yOf = (q) => bot - (bot - top) * Math.min(Math.max((q - lo) / (hi - lo), 0), 1);
  g.strokeStyle = "#111"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(x, top); g.lineTo(x, bot); g.stroke();
  for (let i = 0; i <= 10; i++) {
    const y = top + (bot - top) * i / 10;
    g.beginPath(); g.moveTo(x - W * 0.08, y); g.lineTo(x + W * 0.08, y); g.stroke();
  }
  if (sp !== null) { g.fillStyle = "#2a4fd4"; g.beginPath(); g.moveTo(x - W * 0.1, yOf(sp)); g.lineTo(x - W * 0.3, yOf(sp) - W * 0.08); g.lineTo(x - W * 0.3, yOf(sp) + W * 0.08); g.fill(); }
  if (v !== null) { g.fillStyle = "#c81e14"; g.beginPath(); g.moveTo(x + W * 0.1, yOf(v)); g.lineTo(x + W * 0.3, yOf(v) - W * 0.08); g.lineTo(x + W * 0.3, yOf(v) + W * 0.08); g.fill(); }
  vText(g, String(ud.legend || ""), W / 2, H * 0.07, Math.max(6, W * 0.10), "#111", "center", true);
  vText(g, v === null ? "--" : fmtNum(v, lo, hi), W * 0.5, H * 0.95, Math.max(7, W * 0.12), "#c81e14", "center", true, MONO);
  vText(g, `SP ${sp === null ? "--" : fmtNum(sp, lo, hi)}`, W * 0.5, H * 0.15, Math.max(6, W * 0.09), "#2a4fd4", "center", false, MONO);
  const auto = L[`${ud.tag}_auto`];
  vText(g, auto ? "AUTO" : "MAN", W * 0.8, H * 0.15, Math.max(6, W * 0.08), auto ? "#1f8a3a" : "#b47a00", "center", true);
}

function drawThumbwheel(f, r) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#e8e8e2";
  g.fillRect(0, 0, W, H);
  const v = val(r, ud.tag);
  const n = +ud.digits || 3;
  const text = v === null ? "-".repeat(n) : String(Math.round(v)).padStart(n, "0");
  const cw = W / n;
  for (let i = 0; i < n; i++) {
    g.fillStyle = "#1a1a1a";
    g.fillRect(i * cw + cw * 0.08, H * 0.1, cw * 0.84, H * 0.8);
    vText(g, text[i], i * cw + cw / 2, H / 2, H * 0.62, "#f4f4f4", "center", true, MONO);
  }
}

function drawAnn(f, r, L, ann, s, hist, blink) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#2a2d2c";
  g.fillRect(0, 0, W, H);
  const rows = +ud.rows, cols = +ud.cols;
  const keys = String(ud.keys).split("|");
  const cw = W / cols, ch = H / rows;
  const test = !!ann.__test__;
  keys.forEach((key, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const x = col * cw, y = row * ch;
    const st = test ? "on" : ann[key] || "off";
    const lit = st === "on" || (st === "flash" && blink);
    const red = ANN_RED.has(key);
    g.fillStyle = lit ? (red ? "#ff4a3a" : "#ffd84a") : "#d9d6c8";
    if (!lit) g.fillStyle = "#cfcbbb";
    g.fillRect(x + cw * 0.04, y + ch * 0.06, cw * 0.92, ch * 0.88);
    if (!lit) {
      g.fillStyle = "rgba(20,20,20,0.55)";
      g.fillRect(x + cw * 0.04, y + ch * 0.06, cw * 0.92, ch * 0.88);
    }
    const text = ANN_TEXT[key] ?? key.toUpperCase();
    const words = text.split(" ");
    const lines = [];
    let cur = "";
    for (const w of words) {
      if ((cur + " " + w).trim().length > 12 && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim();
    }
    if (cur) lines.push(cur);
    const fs = Math.max(6, Math.min(ch * 0.22, cw * 0.13));
    lines.forEach((ln, k) => vText(g, ln, x + cw / 2, y + ch / 2 + (k - (lines.length - 1) / 2) * fs * 1.15, fs, lit ? "#111" : "#8a877a", "center", true));
  });
}

function drawCore(f, r, L, ann, s) {
  const { ctx: g, cv, ud } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#0a0a0a";
  g.fillRect(0, 0, W, H);
  const notch = val(r, "rod_notch");
  const sel = r.rod_selected;
  const cell = Math.min(W, H) / 15.6;
  const ox = (W - cell * 15) / 2, oy = (H - cell * 15) / 2;
  // core outline
  g.strokeStyle = "#444"; g.lineWidth = 1;
  g.beginPath(); g.arc(W / 2, H / 2, cell * 7.5, 0, Math.PI * 2); g.stroke();
  for (const rod of ROD_GRID) {
    const x = ox + rod.i * cell, y = oy + (14 - rod.j) * cell;
    g.fillStyle = rod.name === sel ? "#3a2a08" : "#161616";
    g.fillRect(x + 1, y + 1, cell - 2, cell - 2);
    const text = s.scrammed && notch < 0.5 ? "00" : notch === null ? "--" : String(Math.round(notch)).padStart(2, "0");
    const full = Math.round(notch || 0) >= 48;
    vText(g, text, x + cell / 2, y + cell * 0.5, cell * 0.55, s.scrammed ? "#ff3b1f" : full ? "#30ff50" : "#ff6a3a", "center", true, MONO);
  }
  vText(g, "FULL CORE DISPLAY   ROD POSITION (NOTCH 00 - 48)", W / 2, H * 0.025, Math.max(7, W * 0.022), "#bbb", "center", true);
  vText(g, `SELECTED ${sel || "--"}`, W * 0.5, H * 0.975, Math.max(7, W * 0.024), "#ffb020", "center", true, MONO);
}

function drawRodSelect(f, r) {
  const { ctx: g, cv } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#4a4e4c";
  g.fillRect(0, 0, W, H);
  const sel = r.rod_selected;
  const cell = Math.min(W, H) / 15.4;
  const ox = (W - cell * 15) / 2, oy = (H - cell * 15) / 2;
  for (const rod of ROD_GRID) {
    const x = ox + rod.i * cell, y = oy + (14 - rod.j) * cell;
    g.fillStyle = rod.name === sel ? "#ffe060" : "#d8d6cc";
    g.beginPath(); g.arc(x + cell / 2, y + cell / 2, cell * 0.40, 0, Math.PI * 2); g.fill();
    vText(g, rod.name, x + cell / 2, y + cell / 2, cell * 0.28, "#222", "center", false, MONO);
  }
}

function drawClock(f, r, L, ann, s) {
  const { ctx: g, cv } = f;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#f4f2ea";
  g.fillRect(0, 0, W, H);
  const cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.46;
  g.strokeStyle = "#111"; g.lineWidth = 2;
  for (let i = 0; i < 60; i++) {
    const a = i / 60 * Math.PI * 2, big = i % 5 === 0;
    g.beginPath(); g.moveTo(cx + R * Math.sin(a), cy - R * Math.cos(a)); g.lineTo(cx + R * (big ? 0.86 : 0.93) * Math.sin(a), cy - R * (big ? 0.86 : 0.93) * Math.cos(a)); g.stroke();
  }
  const t = 8 * 3600 + (s.time_s || 0);   // the shift starts at 08:00
  const hand = (frac, len, w, col = "#111") => {
    const a = frac * Math.PI * 2;
    g.strokeStyle = col; g.lineWidth = w;
    g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + R * len * Math.sin(a), cy - R * len * Math.cos(a)); g.stroke();
  };
  hand(((t / 3600) % 12) / 12, 0.55, 5);
  hand(((t / 60) % 60) / 60, 0.8, 4);
  hand((t % 60) / 60, 0.85, 1.5, "#c81e14");
}

const DRAW = {
  meter: drawMeter, round: drawRound, recorder: drawRecorder, digital: drawDigital, ma: drawMA,
  thumbwheel: drawThumbwheel, ann: drawAnn, core: drawCore, rodselect: drawRodSelect, clock: drawClock,
};

export { ROD_GRID };
