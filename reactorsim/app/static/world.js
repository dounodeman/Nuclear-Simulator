// The reactor hall as a place to walk around in first person.
//
// Loads models/export/reactor_hall.glb (Y up, metres, pool centre at the origin, floor at y = 0,
// console and video wall to the east, +x). The operator walks with WASD and looks with the mouse.
// Every control is on the console: the two workstation screens open the reactor-control and
// plant-data computers, and the hard-wired buttons (rod drives, scram, magnet power, key switch)
// act directly. Screens, rod readouts, annunciators and the video wall show the live plant.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/three/loaders/GLTFLoader.js";

const EYE = 1.65;          // eye height above the floor, m
const RADIUS = 0.28;       // body radius for collisions, m
const STEP_UP = 0.42;      // highest step the walker climbs, m
const STEP_DOWN = 0.5;     // largest drop the walker takes; anything deeper is a ledge
const WALK = 1.5, RUN = 3.2;  // m/s
const REACH = 2.3;         // how far away a control can be used, m
const SHIELD_CLEAR = 2.29 + RADIUS;  // the deck guard rail keeps walkers out of this radius
const SPAWN = { x: 4.3, z: 3.2, yaw: Math.atan2(4.3, 3.2), pitch: -0.12 };  // facing the pool

// What each named object on the console does.
const ROD_BUTTON = /^ui_Rod_(SS1|SS2|RR|NS|FC)_(Up|Down)$/;
const LABELS = {
  ui_Display_Left: ["station", "reactor", "Reactor control workstation"],
  Display_Left_Bezel: ["station", "reactor", "Reactor control workstation"],
  Keyboard: ["station", "reactor", "Reactor control workstation"],
  Trackball: ["station", "reactor", "Reactor control workstation"],
  ui_Display_Right: ["station", "plant", "Plant data workstation"],
  Display_Right_Bezel: ["station", "plant", "Plant data workstation"],
  Keyboard_2: ["station", "plant", "Plant data workstation"],
  ui_Scram_Console: ["scram", null, "Manual SCRAM (console)"],
  ui_Scram_Hallway: ["scram", null, "Manual SCRAM (hallway)"],
  ui_MagnetPower_Switch: ["scram", null, "Magnet power: cut (scram)"],
  ui_KeySwitch_Master: ["reset", null, "Master key switch: reset scram"],
  Rack_1_RTP3000_RPS_RCS: ["info", null, "Rack 1: RTP 3000 protection and control system"],
  Rack_2_Mirion_NI_Channels: ["info", null, "Rack 2: Mirion nuclear instrument channels"],
  Rack_3_Historian_Workstation: ["info", null, "Rack 3: historian"],
  Rack_4_DataDiode_Network: ["info", null, "Rack 4: data diode and network"],
  Rack_5_UPS_30min: ["info", null, "Rack 5: UPS, 30 minutes"],
  Chiller_36kBtu: ["info", null, "Pool chiller, 36 kBtu/h"],
  IonExchanger_MixedBed: ["info", null, "Mixed-bed ion exchanger"],
  Pump_30gpm: ["info", null, "Primary purification pump, 30 gpm"],
  CAM: ["info", null, "Continuous air monitor"],
  RAM_PoolTop: ["info", null, "Area radiation monitor: pool top"],
  RAM_Console: ["info", null, "Area radiation monitor: console"],
  RAM_WaterProcess: ["info", null, "Area radiation monitor: water process"],
  Bridge_Structure: ["info", null, "Reactor bridge with the five drives"],
};

const ANNUNCIATOR_KEYS = ["scram", "setback", "interlock", "period", "power", "chan",
  "pooltemp", "poollevel", "rad", "servo", "source", "rps"];
const ANN_COLORS = { alarm: 0xff3b30, warn: 0xffb020, ok: 0x30d158 };

export class HallWorld {
  constructor(el, hooks) {
    this.el = el;
    this.hooks = hooks;  // { use(station), command(action, args), prompt(text|null), lockChange(locked) }
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    el.appendChild(this.renderer.domElement);
    this.canvas = this.renderer.domElement;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0b0f14);
    this.camera = new THREE.PerspectiveCamera(70, 1, 0.05, 80);
    this.camera.rotation.order = "YXZ";

    this.scene.add(new THREE.HemisphereLight(0xf4f6ff, 0x3a3f48, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 0.9);
    sun.position.set(2, 6.5, 1);
    this.scene.add(sun);
    for (const [x, z] of [[-2.5, -3.5], [-2.5, 3.5], [2.5, -3.5], [2.5, 3.5], [7, -3.5], [7, 3.5]]) {
      const l = new THREE.PointLight(0xfff6e8, 6, 12, 1.6);
      l.position.set(x, 6.3, z);
      this.scene.add(l);
    }
    this.glowLight = new THREE.PointLight(0x4fc3f7, 0, 6, 1.5);
    this.glowLight.position.set(0, -3.9, 0);
    this.scene.add(this.glowLight);

    this.pos = new THREE.Vector3(SPAWN.x, 0, SPAWN.z);  // feet
    this.yaw = SPAWN.yaw;
    this.pitch = SPAWN.pitch;
    this.keys = new Set();
    this.active = true;         // false while a workstation is open
    this.locked = false;
    this.dragLook = false;      // fallback when pointer lock is unavailable
    this.hover = null;
    this.held = null;
    this.ray = new THREE.Raycaster();
    this.colliders = [];
    this.pickables = [];
    this.screens = {};
    this.rods = {};
    this.glow = [];
    this.annunciators = [];
    this.clock = new THREE.Clock();

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
      const name = this._named(o);
      if (!name.startsWith("fx_") && !["Ceiling", "HVAC_Ducts", "LightFixtures"].includes(name)) {
        this.colliders.push(o);
      }
      const rod = /^ui_Rod_(SS1|SS2|RR)$/.exec(name);
      if (rod) {
        o.userData.baseY = o.position.y;
        this.rods[rod[1]] = o;
      }
      if (name === "fx_CherenkovGlow") {
        o.material = o.material.clone();
        o.material.depthWrite = false;
        this.glow.push(o);
      }
      if (name === "fx_PoolWater") o.material.depthWrite = false;
      if (name.startsWith("Lamp") || o.material?.name === "Lamp") o.material.emissiveIntensity = 2;
      const kind = LABELS[name] || (ROD_BUTTON.test(name) ? ["rod", null, ""] : null);
      if (kind) {
        o.material = o.material.clone();
        o.userData.action = kind;
        o.userData.baseEmissive = o.material.emissive?.clone();
        this.pickables.push(o);
      }
      if (/^ui_Annunciator_\d+$/.test(name)) {
        o.material = o.material.clone();
        this.annunciators[+name.slice(-2) - 1] = o;
      }
    });

    // Live screens: workstation displays, rod position readouts and the 4 x 3 video wall.
    this.screens.left = this._screen("ui_Display_Left", 1024, 576);
    this.screens.right = this._screen("ui_Display_Right", 1024, 576);
    for (const r of ["SS1", "SS2", "RR", "NS", "FC"]) this.screens[`ro_${r}`] = this._screen(`ui_Readout_${r}`, 256, 96);
    const tiles = [];
    this.root.traverse((o) => { if (/^ui_VideoWall_r\dc\d$/.test(o.name)) tiles.push(o); });
    // Order tiles as the operator sees them: rows top to bottom, columns left to right (+z is right).
    const centre = (o) => new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3());
    tiles.sort((a, b) => {
      const ca = centre(a), cb = centre(b);
      return Math.abs(ca.y - cb.y) > 0.2 ? cb.y - ca.y : ca.z - cb.z;
    });
    this.wall = tiles.map((t) => this._screen(t.name, 512, 288, t));

    this.renderer.setAnimationLoop(() => this._frame());
  }

  _named(o) {
    // A glTF node with several primitives loads as a Group of unnamed Meshes; use the node's name.
    return o.name || o.parent?.name || "";
  }

  _screen(name, w, h, obj) {
    obj = obj || this.root.getObjectByName(name);
    if (!obj) return null;
    const mesh = obj.isMesh ? obj : obj.getObjectByProperty("isMesh", true);
    const cv = document.createElement("canvas");
    cv.width = w;
    cv.height = h;
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    // The screens face west (-x); give them UVs from world z (left to right) and y (up).
    const g = mesh.geometry.clone();
    const p = g.attributes.position;
    const v = new THREE.Vector3();
    const pts = [];
    for (let i = 0; i < p.count; i++) pts.push(v.fromBufferAttribute(p, i).applyMatrix4(mesh.matrixWorld).clone());
    const zs = pts.map((q) => q.z), ys = pts.map((q) => q.y);
    const z0 = Math.min(...zs), z1 = Math.max(...zs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const uv = new Float32Array(p.count * 2);
    pts.forEach((q, i) => {
      uv[2 * i] = (q.z - z0) / (z1 - z0 || 1);
      uv[2 * i + 1] = (q.y - y0) / (y1 - y0 || 1);
    });
    g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    mesh.geometry = g;
    const keepPick = mesh.userData.action;
    mesh.material = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false });
    if (keepPick) mesh.userData.baseEmissive = null;
    return { cv, ctx: cv.getContext("2d"), tex, mesh };
  }

  // ------------------------------------------------------------------ input

  _bindInput() {
    const c = this.canvas;
    document.addEventListener("keydown", (e) => {
      if (e.target.closest?.("input, select, textarea, dialog")) return;
      this.keys.add(e.code);
      if (e.code === "KeyE" && this.active && !e.repeat) this._press();
    });
    document.addEventListener("keyup", (e) => {
      this.keys.delete(e.code);
      if (e.code === "KeyE") this._release();
    });
    window.addEventListener("blur", () => { this.keys.clear(); this._release(); });

    document.addEventListener("pointerlockchange", () => {
      this.locked = document.pointerLockElement === c;
      if (this.locked) this._lockPending = false;
      if (!this.locked) this._release();
      this.hooks.lockChange?.(this.locked);
    });
    document.addEventListener("pointerlockerror", () => {
      this.dragLook = true;
      this.hooks.lockChange?.(false, true);
    });

    let down = null;
    c.addEventListener("mousedown", (e) => {
      if (!this.active || e.button !== 0) return;
      if (this.locked) { this._press(); return; }
      down = { x: e.clientX, y: e.clientY, moved: false };
      if (this.dragLook) this._pickAt(e.clientX, e.clientY) && this._press();
    });
    window.addEventListener("mousemove", (e) => {
      if (this.locked) {
        this._look(e.movementX, e.movementY);
      } else if (down && this.dragLook) {
        if (Math.abs(e.clientX - down.x) + Math.abs(e.clientY - down.y) > 4) {
          down.moved = true;
          if (!this.held) this._look(e.movementX, e.movementY);
        }
      } else if (this.dragLook && this.active) {
        this._pickAt(e.clientX, e.clientY);
      }
    });
    window.addEventListener("mouseup", () => {
      this._release();
      if (down && !this.dragLook && !down.moved) this.lock();
      down = null;
    });
  }

  lock() {
    if (this.dragLook || !this.active) return;
    this._lockPending = true;
    const fallback = () => {
      if (!this._lockPending || this.locked || this.dragLook) return;
      this._lockPending = false;
      this.dragLook = true;
      this.hooks.lockChange?.(false, true);
    };
    try {
      const r = this.canvas.requestPointerLock();
      if (r && r.catch) r.catch(fallback);
      // Some embedded web views ignore the request without an error; fall back to drag-to-look.
      setTimeout(fallback, 1500);
    } catch {
      fallback();
    }
  }

  unlock() {
    if (document.pointerLockElement) document.exitPointerLock();
  }

  setActive(on) {
    this.active = on;
    this.keys.clear();
    this._release();
    if (!on) {
      this.unlock();
      this._setHover(null);
    }
  }

  _look(dx, dy) {
    // Browsers sometimes report a large jump on the first event after pointer lock.
    dx = Math.max(-120, Math.min(120, dx));
    dy = Math.max(-120, Math.min(120, dy));
    this.yaw -= dx * 0.0022;
    this.pitch = Math.max(-1.45, Math.min(1.45, this.pitch - dy * 0.0022));
  }

  _press() {
    const o = this.hover;
    if (!o) return;
    const [kind, arg, label] = o.userData.action;
    if (kind === "station") {
      this.hooks.use(arg);
    } else if (kind === "scram") {
      this.hooks.command("scram");
      this._flash(o);
    } else if (kind === "reset") {
      this.hooks.command("reset_scram");
      this._flash(o);
    } else if (kind === "rod") {
      const [, rod, dir] = ROD_BUTTON.exec(this._named(o));
      if (rod === "NS") {
        this.hooks.command("source", { inserted: dir === "Down" });
      } else if (rod === "FC") {
        this.hooks.prompt("The fission chamber drive is not modelled yet");
      } else {
        this.held = { rod, o };
        this.hooks.command("drive", { rod, direction: dir === "Up" ? "out" : "in" });
      }
      this._flash(o, !!this.held);
    } else if (kind === "info") {
      this.hooks.prompt(label);
    }
  }

  _release() {
    if (!this.held) return;
    this.hooks.command("drive", { rod: this.held.rod, direction: "stop" });
    this._unflash(this.held.o);
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

  // ------------------------------------------------------------------ picking

  _pickFrom(ndc) {
    this.ray.setFromCamera(ndc, this.camera);
    this.ray.far = REACH + 0.4;
    const hits = this.ray.intersectObjects(this.colliders.concat(this.pickables), false);
    const hit = hits.find((h) => h.object.visible);
    const o = hit && hit.object.userData.action && hit.distance <= REACH ? hit.object : null;
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
    if (prev && prev !== this.held?.o && prev.material.emissive) {
      prev.material.emissive.copy(prev.userData.baseEmissive || new THREE.Color(0));
    }
    this.hover = o;
    if (o && o.material.emissive && o !== this.held?.o) o.material.emissive.setHex(0x1a3a4a);
    if (!o) { this.hooks.prompt(null); return; }
    const [kind, , label] = o.userData.action;
    const name = this._named(o);
    let text = label;
    if (kind === "rod") {
      const [, rod, dir] = ROD_BUTTON.exec(name);
      text = rod === "NS" ? `Neutron source drive ${dir === "Up" ? "OUT (withdraw)" : "IN (insert)"}`
        : rod === "FC" ? "Fission chamber drive" : `${rod} drive ${dir === "Up" ? "UP (withdraw)" : "DOWN (insert)"}`;
    }
    const verb = kind === "station" ? "Click to use" : kind === "rod" ? "Hold to drive"
      : kind === "info" ? "" : "Click";
    this.hooks.prompt(verb ? `${verb}: ${text}` : text, true);
  }

  // ------------------------------------------------------------------ movement

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
    let f = (k.has("KeyW") || k.has("ArrowUp") ? 1 : 0) - (k.has("KeyS") || k.has("ArrowDown") ? 1 : 0);
    let s = (k.has("KeyD") || k.has("ArrowRight") ? 1 : 0) - (k.has("KeyA") || k.has("ArrowLeft") ? 1 : 0);
    if (!f && !s) return;
    const n = Math.hypot(f, s);
    const speed = (k.has("ShiftLeft") || k.has("ShiftRight") ? RUN : WALK) * dt / n;
    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw));
    const right = new THREE.Vector3(-fwd.z, 0, fwd.x);
    const d = fwd.multiplyScalar(f * speed).add(right.multiplyScalar(s * speed));
    // Move along x and z separately so the walker slides along walls.
    this._tryMove(d.x, 0);
    this._tryMove(0, d.z);
  }

  _tryMove(dx, dz) {
    const len = Math.hypot(dx, dz);
    if (len < 1e-6) return;
    const to = new THREE.Vector3(this.pos.x + dx, this.pos.y, this.pos.z + dz);
    if (Math.hypot(to.x, to.z) < SHIELD_CLEAR) return;
    const dir = new THREE.Vector3(dx / len, 0, dz / len);
    for (const h of [STEP_UP + 0.03, 1.1, 1.75]) {
      this.ray.set(new THREE.Vector3(this.pos.x, this.pos.y + h, this.pos.z), dir);
      this.ray.far = len + RADIUS;
      if (this.ray.intersectObjects(this.colliders, false).length) return;
    }
    // Floor under the new position and under the toes: climb steps as soon as a foot is on
    // them, refuse ledges (the pool, the edge of the shield deck).
    const floorAt = (x, z) => {
      this.ray.set(new THREE.Vector3(x, this.pos.y + STEP_UP + 0.02, z), new THREE.Vector3(0, -1, 0));
      this.ray.far = STEP_UP + STEP_DOWN + 0.05;
      const hit = this.ray.intersectObjects(this.colliders, false)[0];
      return hit ? hit.point.y : null;
    };
    const under = floorAt(to.x, to.z);
    const toes = floorAt(to.x + dir.x * RADIUS * 0.9, to.z + dir.z * RADIUS * 0.9);
    if (under === null || toes === null) return;
    to.y = Math.max(under, toes);
    this.pos.copy(to);
  }

  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // ------------------------------------------------------------------ live plant on the hall's screens

  update(s, trend, ann) {
    if (!this.root) return;
    for (const [name, obj] of Object.entries(this.rods)) {
      const r = s.rods[name];
      if (r) obj.position.y = obj.userData.baseY + r.position_cm / 100;
    }
    const p = s.true.power_w;
    const f = Math.max(0, Math.min(1.6, Math.log10(Math.max(p, 1e-6)) / 4));
    for (const m of this.glow) {
      m.visible = f > 0.01;
      m.material.opacity = Math.min(0.85, 0.15 + 0.5 * f);
      m.material.emissiveIntensity = 8 * f;
    }
    this.glowLight.intensity = 6 * f;

    ANNUNCIATOR_KEYS.forEach((key, i) => {
      const o = this.annunciators[i];
      if (!o) return;
      const st = ann[key];
      const blink = st === "alarm" && Math.floor(performance.now() / 500) % 2;
      o.material.emissive.setHex(st && !blink ? ANN_COLORS[st] : 0x000000);
      o.material.emissiveIntensity = st ? 1.5 : 0;
    });

    if (this.screens.left) drawReactorScreen(this.screens.left, s);
    if (this.screens.right) drawPlantScreen(this.screens.right, s, trend);
    for (const r of ["SS1", "SS2", "RR"]) {
      const sc = this.screens[`ro_${r}`];
      if (sc) drawSegment(sc, `${r} ${s.rods[r] ? s.rods[r].position_cm.toFixed(1) : "--.-"}`, "#ffb020");
    }
    if (this.screens.ro_NS) drawSegment(this.screens.ro_NS, s.source_inserted ? "NS IN" : "NS OUT", "#30d158");
    if (this.screens.ro_FC) drawSegment(this.screens.ro_FC, "FC --", "#5b6573");
    this.wall.forEach((sc, i) => sc && WALL[i] && WALL[i](sc, s, trend));
    for (const sc of Object.values(this.screens).concat(this.wall)) if (sc) sc.tex.needsUpdate = true;
  }
}

// ------------------------------------------------------------------ screen drawing

const MONO = '"SF Mono", Menlo, Consolas, monospace';
const SANS = '-apple-system, "Segoe UI", system-ui, sans-serif';

function fmt(v, d = 3) {
  if (v === null || v === undefined || !isFinite(v)) return "--";
  if (v === 0) return "0";
  const a = Math.abs(v);
  return a >= 1e5 || a < 1e-2 ? v.toExponential(d - 1).replace("e+", "e") : v.toPrecision(d);
}
function fmtW(w) {
  if (!isFinite(w)) return "--";
  return w >= 1000 ? `${fmt(w / 1000)} kW` : w >= 1 ? `${fmt(w)} W` : `${fmt(w * 1000)} mW`;
}
function fmtP(p) {
  return p === null || !isFinite(p) || Math.abs(p) > 9999 ? "∞" : `${p > 0 ? "+" : ""}${p.toFixed(1)} s`;
}

function bg(sc, title, accent = "#4fc3f7") {
  const { ctx: g, cv } = sc;
  g.fillStyle = "#06090d";
  g.fillRect(0, 0, cv.width, cv.height);
  const h = cv.height / 9;
  g.fillStyle = "#0f1a24";
  g.fillRect(0, 0, cv.width, h);
  g.fillStyle = accent;
  g.font = `600 ${h * 0.5}px ${SANS}`;
  g.textBaseline = "middle";
  g.fillText(title, h * 0.4, h / 2);
  return h;
}

function drawReactorScreen(sc, s) {
  const { ctx: g, cv } = sc;
  const h = bg(sc, "PUR-1 REACTOR CONTROL", s.scrammed ? "#ff6b6b" : "#4fc3f7");
  const W = cv.width;
  g.textBaseline = "alphabetic";
  g.fillStyle = "#8aa0b4";
  g.font = `${h * 0.4}px ${SANS}`;
  g.fillText("POWER (CH2 LOG)", 40, h * 1.9);
  g.fillStyle = "#e8f6ff";
  g.font = `${h * 1.25}px ${MONO}`;
  g.fillText(`${fmt(s.channels.ch2_percent)} %`, 40, h * 3.3);
  g.font = `${h * 0.5}px ${MONO}`;
  g.fillStyle = "#8aa0b4";
  g.fillText(`Period ${fmtP(s.channels.ch2_period_s)}`, 40, h * 4.1);
  g.fillText(`Linear ${fmtW(s.channels.ch3_power_w)}   Safety ${s.channels.ch4_percent.toFixed(1)} %`, 40, h * 4.8);
  // rods
  const names = Object.keys(s.rods);
  names.forEach((n, i) => {
    const r = s.rods[n];
    const x = W * 0.58 + i * W * 0.13, top = h * 1.5, bh = h * 4.6, bw = W * 0.06;
    g.strokeStyle = "#2a3a4c";
    g.strokeRect(x, top, bw, bh);
    g.fillStyle = n === s.regulating_rod ? "#c084fc" : "#94a3b8";
    const f = r.position_cm / r.travel_cm;
    g.fillRect(x + 4, top + bh * (1 - f), bw - 8, bh * f);
    g.fillStyle = "#cfe3f3";
    g.font = `${h * 0.42}px ${MONO}`;
    g.fillText(n, x, top + bh + h * 0.6);
    g.fillText(r.position_cm.toFixed(1), x, top + bh + h * 1.15);
  });
  // status line
  const y = h * 8.2;
  g.font = `600 ${h * 0.55}px ${SANS}`;
  if (s.scrammed) {
    g.fillStyle = "#ff3b30";
    g.fillRect(0, h * 7.4, W, h * 1.6);
    g.fillStyle = "#fff";
    g.fillText("SCRAM  " + s.scram_causes.join("; ").slice(0, 60), 40, y);
  } else {
    g.fillStyle = s.servo.enabled ? "#30d158" : "#8aa0b4";
    g.fillText(s.servo.enabled ? `SERVO ON  ${fmtW(s.servo.setpoint_w)}` : "SERVO OFF", 40, y);
    g.fillStyle = "#4fc3f7";
    g.fillText("Click to use", W - 260, y);
  }
}

function drawPlantScreen(sc, s, trend) {
  const { ctx: g, cv } = sc;
  const h = bg(sc, "PLANT DATA", "#fbbf24");
  const W = cv.width;
  // mini power trend, last 10 minutes, log 1 mW to 100 kW
  const x0 = 40, y0 = h * 1.4, pw = W * 0.6, ph = h * 4.4;
  g.strokeStyle = "#1c2733";
  for (let e = -3; e <= 5; e++) {
    const yy = y0 + ph * (1 - (e + 3) / 8);
    g.beginPath(); g.moveTo(x0, yy); g.lineTo(x0 + pw, yy); g.stroke();
  }
  const t1 = s.time_s, t0 = t1 - 600;
  g.strokeStyle = "#4fc3f7";
  g.lineWidth = 3;
  g.beginPath();
  let first = true;
  for (const p of trend) {
    if (p[0] < t0) continue;
    const w = Math.max(p[2] / 100 * s.reactor.rated_w, 1e-3);
    const xx = x0 + ((p[0] - t0) / 600) * pw, yy = y0 + ph * (1 - (Math.log10(w) + 3) / 8);
    first ? g.moveTo(xx, yy) : g.lineTo(xx, yy);
    first = false;
  }
  g.stroke();
  g.lineWidth = 1;
  g.fillStyle = "#8aa0b4";
  g.font = `${h * 0.38}px ${SANS}`;
  g.textBaseline = "alphabetic";
  g.fillText("Power, last 10 min", x0, y0 + ph + h * 0.6);
  // numbers
  const rx = x0 + pw + 40;
  const rows = [
    ["Pool", `${s.process.pool_temp_c.toFixed(2)} °C`],
    ["Level", `${s.process.pool_level_m.toFixed(2)} m`],
    ["Pool top", `${fmt(s.radiation_mr_h.pool_top)} mR/h`],
    ["Chiller", s.process.chiller_available ? "on" : "TRIP"],
  ];
  rows.forEach(([k, v], i) => {
    g.fillStyle = "#8aa0b4";
    g.font = `${h * 0.38}px ${SANS}`;
    g.fillText(k, rx, y0 + h * (0.4 + i * 1.1));
    g.fillStyle = "#e8f6ff";
    g.font = `${h * 0.55}px ${MONO}`;
    g.fillText(v, rx, y0 + h * (0.95 + i * 1.1));
  });
  // alarms
  g.font = `${h * 0.42}px ${SANS}`;
  const alarms = s.alarms.length ? s.alarms : ["No active alarms"];
  alarms.slice(0, 2).forEach((a, i) => {
    g.fillStyle = s.alarms.length ? "#ffb020" : "#30d158";
    g.fillText(a.slice(0, 64), 40, h * (7.4 + i * 0.7));
  });
  g.fillStyle = "#fbbf24";
  g.fillText("Click to use", W - 230, h * 8.6);
}

function drawSegment(sc, text, color) {
  const { ctx: g, cv } = sc;
  g.fillStyle = "#050607";
  g.fillRect(0, 0, cv.width, cv.height);
  g.fillStyle = color;
  g.font = `${cv.height * 0.5}px ${MONO}`;
  g.textBaseline = "middle";
  g.textAlign = "center";
  g.fillText(text, cv.width / 2, cv.height / 2);
  g.textAlign = "left";
}

function tile(sc, title, value, sub, color = "#e8f6ff", alert = null) {
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.fillStyle = alert === "alarm" ? "#3a0a0c" : alert === "warn" ? "#2e2306" : "#070b10";
  g.fillRect(0, 0, W, H);
  g.strokeStyle = "#1e2a36";
  g.lineWidth = 4;
  g.strokeRect(2, 2, W - 4, H - 4);
  g.textBaseline = "alphabetic";
  g.fillStyle = "#7f93a8";
  g.font = `600 ${H * 0.12}px ${SANS}`;
  g.fillText(title, 22, H * 0.2);
  g.fillStyle = color;
  g.font = `${H * 0.3}px ${MONO}`;
  g.fillText(value, 22, H * 0.6);
  g.fillStyle = "#8aa0b4";
  g.font = `${H * 0.11}px ${MONO}`;
  g.fillText(sub, 22, H * 0.85);
}

function rodTile(sc, s, n) {
  const r = s.rods[n];
  if (!r) return tile(sc, n, "--", "");
  const state = r.falling ? "DROPPING" : !r.latched ? "UNLATCHED" : r.moving ? "MOVING" : "LATCHED";
  tile(sc, `ROD ${n}`, `${r.position_cm.toFixed(1)} cm`, `${state}  −$${r.worth_dollars.toFixed(2)}`,
    n === s.regulating_rod ? "#d8b4fe" : "#e2e8f0", !r.latched ? "warn" : null);
  const { ctx: g, cv } = sc;
  const f = r.position_cm / r.travel_cm;
  g.fillStyle = "#1e2a36";
  g.fillRect(cv.width - 60, 30, 26, cv.height - 60);
  g.fillStyle = n === s.regulating_rod ? "#c084fc" : "#94a3b8";
  g.fillRect(cv.width - 60, 30 + (cv.height - 60) * (1 - f), 26, (cv.height - 60) * f);
}

const WALL = [
  (sc, s) => tile(sc, "CH1 STARTUP", s.channels.ch1_saturated ? "SAT" : `${fmt(s.channels.ch1_cps)} cps`,
    `period ${fmtP(s.channels.ch1_saturated ? null : s.channels.ch1_period_s)}`),
  (sc, s) => tile(sc, "CH2 LOG POWER", `${fmt(s.channels.ch2_percent)} %`, `period ${fmtP(s.channels.ch2_period_s)}`,
    "#7dd3fc", s.channels.ch2_period_s > 0 && s.channels.ch2_period_s < 15 ? "warn" : null),
  (sc, s) => tile(sc, "CH3 LINEAR", fmtW(s.channels.ch3_power_w),
    `${s.channels.ch3_percent_of_range.toFixed(1)}% of ${fmtW(s.channels.ch3_range_w)}`),
  (sc, s) => tile(sc, "CH4 SAFETY", `${s.channels.ch4_percent.toFixed(1)} %`, "trip 120 %", "#e2e8f0",
    s.channels.ch4_percent >= 110 ? "alarm" : null),
  (sc, s) => rodTile(sc, s, "SS1"),
  (sc, s) => rodTile(sc, s, "SS2"),
  (sc, s) => rodTile(sc, s, "RR"),
  (sc, s) => tile(sc, "SERVO", s.servo.enabled ? "AUTO" : "MANUAL", `setpoint ${fmtW(s.servo.setpoint_w)}`,
    s.servo.enabled ? "#30d158" : "#e2e8f0"),
  (sc, s) => tile(sc, "POOL TEMPERATURE", `${s.process.pool_temp_c.toFixed(2)} °C`,
    s.process.chiller_available ? "chiller running" : "CHILLER TRIPPED", "#e2e8f0",
    s.process.pool_temp_c > 29.7 ? "warn" : null),
  (sc, s) => tile(sc, "WATER ABOVE CORE", `${s.process.pool_level_m.toFixed(2)} m`, "alarm below 3.96 m", "#e2e8f0",
    s.process.pool_level_m < 3.96 ? "alarm" : null),
  (sc, s) => tile(sc, "RADIATION", `${fmt(s.radiation_mr_h.pool_top)} mR/h`,
    `console ${fmt(s.radiation_mr_h.console)}  water ${fmt(s.radiation_mr_h.water)}`, "#e2e8f0",
    s.radiation_mr_h.pool_top >= 50 ? "alarm" : null),
  (sc, s) => s.scrammed
    ? tile(sc, "REACTOR", "SCRAM", s.scram_causes.join("; ").slice(0, 34), "#ff6b6b", "alarm")
    : tile(sc, "REACTOR", s.setback ? "SETBACK" : s.true.power_w > 1 ? "AT POWER" : "SHUTDOWN",
      s.alarms[0] ? s.alarms[0].slice(0, 34) : "no alarms", s.setback ? "#ffb020" : "#30d158",
      s.setback ? "warn" : null),
];
