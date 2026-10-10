// The reactor hall as a place to walk around in first person.
//
// Loads models/export/reactor_hall.glb (Y up, metres, pool centre at the origin, floor at y = 0,
// console and video wall to the east, +x). The operator walks with WASD and looks with the mouse.
// Every control is on the desk console: the left and right monitors open the reactor-control and
// plant-data computers, the centre monitor mirrors the RTP operator display, and the hard-wired
// buttons (rod drives, scram, magnet power, key switch) act directly. Screens, rod readouts,
// annunciators, the I&C cabinet readouts and the video wall show the live plant.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/three/loaders/GLTFLoader.js";
import { applySurfaces } from "./textures.js";

const EYE = 1.65;          // eye height above the floor, m
const RADIUS = 0.28;       // body radius for collisions, m
const STEP_UP = 0.42;      // highest step the walker climbs, m
const STEP_DOWN = 0.5;     // largest drop the walker takes; anything deeper is a ledge
const WALK = 1.5, RUN = 3.2;  // m/s
const REACH = 2.3;         // how far away a control can be used, m
const SHIELD_CLEAR = 2.0 + RADIUS;   // the black pool wall (radius 2 m) keeps walkers out of this radius
const SPAWN = { x: 6.0, z: 5.0, yaw: Math.atan2(6.0, 5.0), pitch: -0.08 };  // inside the main door, facing the pool

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
  Mouse: ["station", "plant", "Plant data workstation"],
  ui_Display_Center: ["info", null, "RTP 3000 operator display: core mimic (read only)"],
  Display_Center_Bezel: ["info", null, "RTP 3000 operator display: core mimic (read only)"],
  Keyboard_3: ["info", null, "RTP 3000 operator display: core mimic (read only)"],
  Telephone: ["info", null, "Telephone to the control point and campus police"],
  ui_Scram_Console: ["scram", null, "Manual SCRAM (console)"],
  ui_Scram_Hallway: ["scram", null, "Manual SCRAM (hallway)"],
  ui_MagnetPower_Switch: ["scram", null, "Magnet power: cut (scram)"],
  ui_KeySwitch_Master: ["reset", null, "Master key switch: reset scram"],
  Cabinet_1_RTP3000_RPS_RCS: ["info", null, "Cabinet 1: RTP 3000 protection and control system"],
  Cabinet_2_Mirion_NI_Channels: ["info", null, "Cabinet 2: Mirion nuclear instrument channels"],
  Cabinet_3_Historian_DataDiode: ["info", null, "Cabinet 3: historian, data diode and network"],
  Cabinet_4_UPS_30min: ["info", null, "Cabinet 4: UPS, 30 minutes"],
  DiagBench_Top: ["info", null, "Diagnostics bench: data analysis and training workstations"],
  DiagBench_Rack: ["info", null, "Portable diagnostics rack"],
  Whiteboard: ["info", null, "Whiteboard: today's operations plan"],
  Stair_North: ["info", null, "Stair to the north platform"],
  Graphic_PUR1: ["info", null, "PUR-1: the nation's first all-digital I&C research reactor"],
  Graphic_Tagline: ["info", null, "PUR-1: the nation's first all-digital I&C research reactor"],
  Graphic_150_150: ["info", null, "PUR-1: the nation's first all-digital I&C research reactor"],
  Graphic_150_GIANT: ["info", null, "PUR-1: the nation's first all-digital I&C research reactor"],
  Graphic_150_LEAPS: ["info", null, "PUR-1: the nation's first all-digital I&C research reactor"],
  Chiller_36kBtu: ["info", null, "Pool chiller, 36 kBtu/h"],
  IonExchanger_MixedBed: ["info", null, "Mixed-bed ion exchanger"],
  Pump_30gpm: ["info", null, "Primary purification pump, 30 gpm"],
  CAM: ["info", null, "Continuous air monitor"],
  RAM_PoolTop: ["info", null, "Area radiation monitor: pool top"],
  RAM_Console: ["info", null, "Area radiation monitor: console"],
  RAM_WaterProcess: ["info", null, "Area radiation monitor: water process"],
  Bridge_Structure: ["info", null, "Reactor bridge with the five drives"],
  Bridge_Frame: ["info", null, "Reactor bridge with the five drives"],
  Bridge_Grating: ["info", null, "Bridge grating over the pool (the core opening is in the middle)"],
  Drive_Cage: ["info", null, "Drive cage over the core"],
  Drive_SS1: ["info", null, "SS1 drive: stepper motor, magnet and drive tube"],
  Drive_SS2: ["info", null, "SS2 drive: stepper motor, magnet and drive tube"],
  Drive_RR: ["info", null, "RR drive: stepper motor, magnet and drive tube"],
  Drive_NS: ["info", null, "Neutron source drive"],
  Drive_FC: ["info", null, "Fission chamber drive"],
  PoolExhaust_Duct: ["info", null, "Pool-top exhaust duct"],
  Door_Main_South: ["info", null, "Main door to the corridor"],
  Door_West: ["info", null, "West door"],
  Door_North: ["info", null, "North door"],
  Door_StorageRoom_North: ["info", null, "Storage room"],
};
// The parts of each keyboard, mouse and trackball work like the device itself.
for (const [part, of] of [["Keyboard_Keys", "Keyboard"], ["Trackball_Ball", "Trackball"],
  ["Trackball_Buttons", "Trackball"], ["Keyboard_2_Keys", "Keyboard_2"], ["Mouse_Pad", "Mouse"],
  ["Mouse_ButtonSplit", "Mouse"], ["Keyboard_3_Keys", "Keyboard_3"]]) LABELS[part] = LABELS[of];
// Thin overhead and wall-mounted detail that should not stop the walker.
const NO_COLLIDE = ["Ceiling", "HVAC_Ducts", "LightFixtures", "Conduit", "MonorailHoist", "Cabinet_CableTray",
  "PipeBrackets", "ProcessPiping_Hangers", "PoolExhaust_Duct", "DriveCables", "DriveCable_Yellow",
  "Mouse_Cable", "DiagBench_Mouse_Cable"];

const ANNUNCIATOR_KEYS = ["scram", "setback", "interlock", "period", "power", "chan",
  "pooltemp", "poollevel", "rad", "servo", "source", "rps"];
const ANN_COLORS = { alarm: 0xff3b30, warn: 0xffb020, ok: 0x30d158 };

function hallEnvironment(renderer) {
  // A rough stand-in for the hall seen from the middle of it (cream walls, a grey floor and rows
  // of bright ceiling fixtures), prefiltered for image-based lighting. Without it the stainless
  // and aluminium have nothing to reflect and render nearly black.
  const env = new THREE.Scene();
  const box = (w, h, d, color, x, y, z, side = THREE.FrontSide) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), new THREE.MeshBasicMaterial({ color, side }));
    m.position.set(x, y, z);
    env.add(m);
  };
  box(20, 8, 16, 0x6e6a60, 0, 3, 0, THREE.BackSide);
  box(19.8, 0.1, 15.8, 0x5a5a5a, 0, -0.95, 0);
  for (const x of [-6, -2, 2, 6]) for (const z of [-4, 0, 4]) box(1.2, 0.05, 0.3, new THREE.Color(6, 6, 5.6), x, 6.9, z);
  const pm = new THREE.PMREMGenerator(renderer);
  const tex = pm.fromScene(env, 0.04).texture;
  pm.dispose();
  return tex;
}

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

    this.scene.environment = hallEnvironment(this.renderer);   // reflections for the metal
    this.scene.add(new THREE.HemisphereLight(0xf4f6ff, 0x3a3f48, 0.6));
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
    this.poolLamp = new THREE.PointLight(0xe6f6ff, 0, 5, 1.2);  // lit only for the core camera
    this.poolLamp.position.set(0.7, -2.0, -0.6);
    this.scene.add(this.poolLamp);

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
    applySurfaces(this.root);   // block walls, epoxy floor, fabric, brushed steel, ... (textures.js)

    this.root.traverse((o) => {
      if (!o.isMesh) return;
      const name = this._named(o);
      if (!name.startsWith("fx_") && !NO_COLLIDE.includes(name)) {
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
    this.screens.center = this._screen("ui_Display_Center", 1024, 576);
    for (const r of ["SS1", "SS2", "RR", "NS", "FC"]) this.screens[`ro_${r}`] = this._screen(`ui_Readout_${r}`, 256, 96);
    const tiles = [];
    this.root.traverse((o) => { if (/^ui_VideoWall_r\dc\d$/.test(o.name)) tiles.push(o); });
    // Order tiles as the operator sees them: rows top to bottom, columns left to right (+z is right).
    const centre = (o) => new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3());
    tiles.sort((a, b) => {
      const ca = centre(a), cb = centre(b);
      return Math.abs(ca.y - cb.y) > 0.2 ? cb.y - ca.y : ca.z - cb.z;
    });
    // Columns 2 and 3 show the underwater core camera as one picture; row 2 of column 4 shows a
    // camera looking down the hall. The other tiles are drawn (see WALL).
    this.feedEvery = [100, 400];   // ms between frames of the core camera and the hall camera
    this.wall = tiles.map((t, i) => (tiles.length !== 12 || (i % 4 !== 1 && i % 4 !== 2 && i !== 7)
      ? this._screen(t.name, 512, 288, t) : null));
    if (tiles.length === 12) {
      const coreCam = new THREE.PerspectiveCamera(60, 1, 0.05, 8);
      coreCam.position.set(0.9, -2.55, 0.35);   // off to the side of the core, looking down at it
      coreCam.lookAt(0, -3.9, 0);
      this.coreFeed = this._feed(tiles.filter((_, i) => i % 4 === 1 || i % 4 === 2), coreCam, 1024, 864, true);
      const hallCam = new THREE.PerspectiveCamera(66, 1, 0.1, 40);   // high in the south-east corner
      hallCam.position.set(8.3, 5.0, 5.3);
      hallCam.lookAt(0, 0.6, -0.6);
      this.hallFeed = this._feed([tiles[7]], hallCam, 512, 288, false);
    }
    // Underwater look for the core camera: blue haze and a lamp in the pool, used only while
    // that view renders (intensity, not visibility, so the shaders keep the same light count).
    this.underFog = new THREE.FogExp2(0x0e5c96, 0.3);
    this.underBg = new THREE.Color(0x072a40);
    this.water = this.root.getObjectByName("fx_PoolWater");

    this.renderer.setAnimationLoop(() => this._frame());
  }

  _feed(tiles, cam, w, h, under) {
    // A live camera picture spread across one or more wall tiles, with an on-screen display
    // drawn on a transparent overlay just in front.
    const rt = new THREE.WebGLRenderTarget(w, h);
    cam.aspect = 1;
    const meshes = tiles.map((t) => (t.isMesh ? t : t.getObjectByProperty("isMesh", true)));
    const world = meshes.map((m) => {
      const p = m.geometry.attributes.position, v = new THREE.Vector3(), pts = [];
      for (let i = 0; i < p.count; i++) pts.push(v.fromBufferAttribute(p, i).applyMatrix4(m.matrixWorld).clone());
      return pts;
    });
    const all = world.flat();
    const z0 = Math.min(...all.map((q) => q.z)), z1 = Math.max(...all.map((q) => q.z));
    const y0 = Math.min(...all.map((q) => q.y)), y1 = Math.max(...all.map((q) => q.y));
    const xf = Math.min(...all.map((q) => q.x));
    cam.aspect = (z1 - z0) / (y1 - y0);
    cam.updateProjectionMatrix();
    const mat = new THREE.MeshBasicMaterial({ map: rt.texture });
    meshes.forEach((m, k) => {
      const g = m.geometry.clone();
      const uv = new Float32Array(g.attributes.position.count * 2);
      world[k].forEach((q, i) => {
        uv[2 * i] = (q.z - z0) / (z1 - z0);
        uv[2 * i + 1] = (q.y - y0) / (y1 - y0);
      });
      g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
      m.geometry = g;
      m.material = mat;
    });
    const cv = document.createElement("canvas");
    cv.width = w;
    cv.height = h;
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    const osd = new THREE.Mesh(new THREE.PlaneGeometry(z1 - z0, y1 - y0),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthWrite: false }));
    osd.rotation.y = -Math.PI / 2;
    osd.position.set(xf - 0.004, (y0 + y1) / 2, (z0 + z1) / 2);
    this.scene.add(osd);
    return { rt, cam, meshes, osd, under, sc: { cv, ctx: cv.getContext("2d"), tex }, last: 0 };
  }

  _renderFeeds() {
    const now = performance.now();
    const due = [[this.coreFeed, this.feedEvery[0]], [this.hallFeed, this.feedEvery[1]]].filter(([f, every]) => f && now - f.last >= every);
    if (!due.length) return;
    const sc = this.scene, fog = sc.fog, bgc = sc.background;
    const hide = [this.coreFeed, this.hallFeed].flatMap((f) => (f ? [...f.meshes, f.osd] : []));
    hide.forEach((m) => { m.visible = false; });
    for (const [f] of due) {
      f.last = now;
      if (f.under) {
        sc.fog = this.underFog;
        sc.background = this.underBg;
        this.poolLamp.intensity = 5;
        if (this.water) this.water.visible = false;
      }
      this.renderer.setRenderTarget(f.rt);
      this.renderer.render(sc, f.cam);
      this.renderer.setRenderTarget(null);
      sc.fog = fog;
      sc.background = bgc;
      this.poolLamp.intensity = 0;
      if (this.water) this.water.visible = true;
    }
    hide.forEach((m) => { m.visible = true; });
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
      // In the Mac app a key the page leaves unhandled travels up the Cocoa responder chain:
      // macOS beeps for every walk key, and Esc (cancelOperation:) takes the window out of full
      // screen. Claiming the key here stops both. Cmd/Ctrl shortcuts still reach the app.
      if (!e.metaKey && !e.ctrlKey && !(e.target.closest?.("button") && (e.key === "Enter" || e.key === " "))) {
        e.preventDefault();
      }
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
      if (this.locked) this._lockPending = false;
      if (!this.locked) this._release();
      this.hooks.lockChange?.(this.locked);
    });
    document.addEventListener("pointerlockerror", () => {
      this.dragLook = true;
      this.hooks.lockChange?.(false, true);
    });

    let down = null;
    c.addEventListener("contextmenu", (e) => e.preventDefault());
    c.addEventListener("dragstart", (e) => e.preventDefault());
    c.addEventListener("mousedown", (e) => {
      e.preventDefault();       // no text selection or drag image while looking around
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
    if (this.active) this._renderFeeds();
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
    // Knee, hip (so desks and benches block), chest and head.
    for (const h of [STEP_UP + 0.03, 0.72, 1.1, 1.75]) {
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
    if (this.screens.center) drawMimicScreen(this.screens.center, s);
    for (const r of ["SS1", "SS2", "RR"]) {
      const sc = this.screens[`ro_${r}`];
      if (sc) drawSegment(sc, `${r} ${s.rods[r] ? s.rods[r].position_cm.toFixed(1) : "--.-"}`, "#ffb020");
    }
    if (this.screens.ro_NS) drawSegment(this.screens.ro_NS, s.source_inserted ? "NS IN" : "NS OUT", "#30d158");
    if (this.screens.ro_FC) drawSegment(this.screens.ro_FC, "FC --", "#5b6573");
    this.wall.forEach((sc, i) => sc && WALL[i] && WALL[i](sc, s, trend));
    const feeds = [];
    if (this.coreFeed) {
      feedOsd(this.coreFeed.sc, "CAM 1  CORE", `POWER ${fmtW(s.channels.ch3_power_w)}   POOL ${s.process.pool_temp_c.toFixed(1)} °C`);
      feeds.push(this.coreFeed.sc);
    }
    if (this.hallFeed) {
      feedOsd(this.hallFeed.sc, "CAM 3  REACTOR HALL");
      feeds.push(this.hallFeed.sc);
    }
    for (const sc of Object.values(this.screens).concat(this.wall, feeds)) if (sc) sc.tex.needsUpdate = true;
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

function bg(sc, title, accent = "#0a246a") {
  // The workstation look: grey window chrome, a navy title bar and a light panel, like the
  // operator displays of the late 1990s (see the HMI theme in app.css).
  const { ctx: g, cv } = sc;
  const h = cv.height / 9;
  g.fillStyle = "#e8e6df";
  g.fillRect(0, 0, cv.width, cv.height);
  const grad = g.createLinearGradient(0, 0, cv.width, 0);
  grad.addColorStop(0, accent === "#ff6b6b" ? "#a00000" : "#0a246a");
  grad.addColorStop(1, accent === "#ff6b6b" ? "#f08080" : "#a6caf0");
  g.fillStyle = grad;
  g.fillRect(0, 0, cv.width, h * 0.8);
  g.fillStyle = "#ffffff";
  g.font = `bold ${h * 0.42}px ${SANS}`;
  g.textBaseline = "middle";
  g.fillText(title, h * 0.3, h * 0.4);
  // window buttons
  for (let k = 0; k < 3; k++) {
    const x = cv.width - h * (0.75 + k * 0.7), y = h * 0.12;
    g.fillStyle = "#d4d0c8"; g.fillRect(x, y, h * 0.6, h * 0.56);
    g.strokeStyle = "#404040"; g.lineWidth = 2; g.strokeRect(x, y, h * 0.6, h * 0.56);
  }
  // status bar
  g.fillStyle = "#d4d0c8";
  g.fillRect(0, cv.height - h * 0.6, cv.width, h * 0.6);
  g.strokeStyle = "#808080"; g.lineWidth = 2;
  g.strokeRect(4, cv.height - h * 0.55, cv.width * 0.7, h * 0.5);
  g.lineWidth = 1;
  return h;
}

function drawReactorScreen(sc, s) {
  const { ctx: g, cv } = sc;
  const h = bg(sc, "PUR-1 REACTOR CONTROL", s.scrammed ? "#ff6b6b" : "#0030c0");
  const W = cv.width;
  g.textBaseline = "alphabetic";
  g.fillStyle = "#303030";
  g.font = `${h * 0.4}px ${SANS}`;
  g.fillText("POWER (CH2 LOG)", 40, h * 1.9);
  g.fillStyle = "#000000";
  g.font = `${h * 1.25}px ${MONO}`;
  g.fillText(`${fmt(s.channels.ch2_percent)} %`, 40, h * 3.3);
  g.font = `${h * 0.5}px ${MONO}`;
  g.fillStyle = "#303030";
  g.fillText(`Period ${fmtP(s.channels.ch2_period_s)}`, 40, h * 4.1);
  g.fillText(`Linear ${fmtW(s.channels.ch3_power_w)}   Safety ${s.channels.ch4_percent.toFixed(1)} %`, 40, h * 4.8);
  // rods
  const names = Object.keys(s.rods);
  names.forEach((n, i) => {
    const r = s.rods[n];
    const x = W * 0.58 + i * W * 0.13, top = h * 1.5, bh = h * 4.6, bw = W * 0.06;
    g.strokeStyle = "#808080";
    g.strokeRect(x, top, bw, bh);
    g.fillStyle = n === s.regulating_rod ? "#7a3fb0" : "#606870";
    const f = r.position_cm / r.travel_cm;
    g.fillRect(x + 4, top + bh * (1 - f), bw - 8, bh * f);
    g.fillStyle = "#000000";
    g.font = `${h * 0.42}px ${MONO}`;
    g.fillText(n, x, top + bh + h * 0.6);
    g.fillText(r.position_cm.toFixed(1), x, top + bh + h * 1.15);
  });
  // status line
  const y = h * 8.2;
  g.font = `600 ${h * 0.55}px ${SANS}`;
  if (s.scrammed) {
    g.fillStyle = "#e00000";
    g.fillRect(0, h * 7.4, W, h * 1.6);
    g.fillStyle = "#fff";
    g.fillText("SCRAM  " + s.scram_causes.join("; ").slice(0, 60), 40, y);
  } else {
    g.fillStyle = s.servo.enabled ? "#008000" : "#303030";
    g.fillText(s.servo.enabled ? `SERVO ON  ${fmtW(s.servo.setpoint_w)}` : "SERVO OFF", 40, y);
    g.fillStyle = "#0030c0";
    g.fillText("Click to use", W - 260, y);
  }
}

function drawMimicScreen(sc, s) {
  // The RTP 3000 operator display: a plan-view mimic of the 4 x 4 core with the rod positions,
  // the power and period, and the protection-system status. Read only; the controls are on the
  // left workstation and the hard-wired panel.
  const { ctx: g, cv } = sc;
  const h = bg(sc, "RTP 3000 · OPERATOR DISPLAY", s.scrammed ? "#ff6b6b" : "#0a246a");
  const W = cv.width;
  const cell = h * 1.35, gx = 60, gy = h * 1.6;
  const rods = { SS1: [3, 3], SS2: [0, 0], RR: [0, 3] };
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 4; c++) {
      g.fillStyle = "#ffffff";
      g.fillRect(gx + c * cell, gy + r * cell, cell - 6, cell - 6);
      g.fillStyle = s.true.power_w > 1 ? "#4a78c8" : "#b8c4d8";
      g.fillRect(gx + c * cell + 8, gy + r * cell + 8, cell - 22, cell - 22);
    }
  }
  g.textBaseline = "middle";
  g.font = `600 ${h * 0.38}px ${SANS}`;
  for (const [n, [r, c]] of Object.entries(rods)) {
    const rod = s.rods[n];
    const f = rod ? rod.position_cm / rod.travel_cm : 0;
    g.fillStyle = n === s.regulating_rod ? "#7a3fb0" : "#303030";
    g.fillRect(gx + c * cell + 8, gy + r * cell + 8 + (cell - 22) * f, cell - 22, (cell - 22) * (1 - f));
    g.fillStyle = "#ffffff";
    g.fillText(n, gx + c * cell + 14, gy + r * cell + cell / 2 - 3);
  }
  g.textBaseline = "alphabetic";
  g.fillStyle = "#303030";
  g.font = `${h * 0.36}px ${SANS}`;
  g.fillText("CORE PLAN · rods shown as inserted fraction", gx, gy + 4 * cell + h * 0.5);
  const x = W * 0.52;
  const row = (label, value, y, color = "#000000") => {
    g.fillStyle = "#303030";
    g.font = `${h * 0.38}px ${SANS}`;
    g.fillText(label, x, y);
    g.fillStyle = color;
    g.font = `${h * 0.7}px ${MONO}`;
    g.fillText(value, x, y + h * 0.75);
  };
  row("POWER", fmtW(s.true.power_w), h * 1.8);
  row("PERIOD", fmtP(s.channels.ch2_period_s), h * 3.2);
  row("POOL", `${s.process.pool_temp_c.toFixed(1)} °C  ${s.process.pool_level_m.toFixed(2)} m`, h * 4.6);
  const rps = s.protection && s.protection.enabled === false ? "RPS OUT OF SERVICE" : "RPS IN SERVICE";
  row("PROTECTION", s.scrammed ? "SCRAM" : rps, h * 6.0, s.scrammed ? "#e00000" : "#008000");
  g.fillStyle = "#303030";
  g.font = `${h * 0.36}px ${SANS}`;
  g.fillText("Read only: use the left workstation to operate", x, h * 8.3);
}

function drawPlantScreen(sc, s, trend) {
  const { ctx: g, cv } = sc;
  const h = bg(sc, "PLANT DATA", "#b06000");
  const W = cv.width;
  // mini power trend, last 10 minutes, log 1 mW to 100 kW
  const x0 = 40, y0 = h * 1.4, pw = W * 0.6, ph = h * 4.4;
  g.strokeStyle = "#c8c8c8";
  for (let e = -3; e <= 5; e++) {
    const yy = y0 + ph * (1 - (e + 3) / 8);
    g.beginPath(); g.moveTo(x0, yy); g.lineTo(x0 + pw, yy); g.stroke();
  }
  const t1 = s.time_s, t0 = t1 - 600;
  g.strokeStyle = "#0030c0";
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
  g.fillStyle = "#303030";
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
    g.fillStyle = "#303030";
    g.font = `${h * 0.38}px ${SANS}`;
    g.fillText(k, rx, y0 + h * (0.4 + i * 1.1));
    g.fillStyle = "#000000";
    g.font = `${h * 0.55}px ${MONO}`;
    g.fillText(v, rx, y0 + h * (0.95 + i * 1.1));
  });
  // alarms
  g.font = `${h * 0.42}px ${SANS}`;
  const alarms = s.alarms.length ? s.alarms : ["No active alarms"];
  alarms.slice(0, 2).forEach((a, i) => {
    g.fillStyle = s.alarms.length ? "#b06000" : "#008000";
    g.fillText(a.slice(0, 64), 40, h * (7.4 + i * 0.7));
  });
  g.fillStyle = "#b06000";
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


// ------------------------------------------------------------------ the video wall
//
// Laid out like the real PUR-1 wall: trend plots down the left (black, green traces, red title
// bars) over a white plant schematic, the live underwater core camera across the middle two
// columns, and status, a hall camera and the radiation monitors down the right.

function wallHeader(g, W, H, title, color = "#b00000") {
  const hh = H * 0.13;
  g.fillStyle = color;
  g.fillRect(0, 0, W, hh);
  g.fillStyle = "#ffffff";
  g.font = `bold ${hh * 0.62}px ${SANS}`;
  g.textBaseline = "middle";
  g.fillText(title, 12, hh * 0.52);
  const t = new Date().toLocaleTimeString([], { hour12: false });
  g.textAlign = "right";
  g.font = `${hh * 0.55}px ${MONO}`;
  g.fillText(t, W - 12, hh * 0.52);
  g.textAlign = "left";
  g.textBaseline = "alphabetic";
  return hh;
}

function trendTile(sc, s, trend, title, series, { log = false, lo, hi, unit = "" } = {}) {
  // series: [{ pick(p) -> value, color, label }]; 10 minutes of history.
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#000000";
  g.fillRect(0, 0, W, H);
  const hh = wallHeader(g, W, H, title);
  const x0 = 64, x1 = W - 14, y0 = hh + 14, y1 = H - 34;
  const t1 = s.time_s, t0 = t1 - 600;
  const pts = trend.filter((p) => p[0] >= t0);
  const val = (v) => (log ? Math.log10(Math.max(v, 1e-12)) : v);
  if (lo === undefined || hi === undefined) {
    const vs = pts.flatMap((p) => series.map((c) => val(c.pick(p)))).filter(isFinite);
    lo = vs.length ? Math.min(...vs) : 0;
    hi = vs.length ? Math.max(...vs) : 1;
    const pad = Math.max((hi - lo) * 0.15, log ? 0.5 : 0.5);
    lo -= pad; hi += pad;
  }
  // grid
  g.strokeStyle = "#1f3a1f";
  g.lineWidth = 1;
  g.fillStyle = "#8fbf8f";
  g.font = `${H * 0.065}px ${MONO}`;
  for (let k = 0; k <= 4; k++) {
    const yy = y1 - ((y1 - y0) * k) / 4;
    g.beginPath(); g.moveTo(x0, yy); g.lineTo(x1, yy); g.stroke();
    const v = lo + ((hi - lo) * k) / 4;
    g.fillText(log ? `1e${v.toFixed(0)}` : v.toFixed(1), 6, yy + 6);
  }
  for (let k = 0; k <= 10; k += 2) {
    const xx = x0 + ((x1 - x0) * k) / 10;
    g.beginPath(); g.moveTo(xx, y0); g.lineTo(xx, y1); g.stroke();
  }
  g.fillText("-10 min", x0, H - 10);
  g.textAlign = "right";
  g.fillText("now", x1, H - 10);
  g.textAlign = "left";
  // traces
  series.forEach((c, j) => {
    g.strokeStyle = c.color;
    g.lineWidth = 3;
    g.beginPath();
    let first = true;
    for (const p of pts) {
      const v = val(c.pick(p));
      if (!isFinite(v)) continue;
      const xx = x0 + ((p[0] - t0) / 600) * (x1 - x0);
      const yy = y1 - ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * (y1 - y0);
      first ? g.moveTo(xx, yy) : g.lineTo(xx, yy);
      first = false;
    }
    g.stroke();
    const last = pts.length ? c.pick(pts[pts.length - 1]) : NaN;
    g.fillStyle = c.color;
    g.font = `bold ${H * 0.075}px ${MONO}`;
    g.fillText(`${c.label} ${c.fmt ? c.fmt(last) : fmt(last)}${unit}`, x0 + 8 + j * (W * 0.42), y0 + H * 0.09);
  });
  g.lineWidth = 1;
}

function schematicTile(sc, s) {
  // White plant schematic of the purification and cooling loop, like the one on the real wall.
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#ffffff";
  g.fillRect(0, 0, W, H);
  const hh = wallHeader(g, W, H, "PRIMARY WATER SYSTEM", "#0a246a");
  const run = s.process.chiller_available;
  const flow = run ? "#00a000" : "#909090";
  const yPipe = hh + (H - hh) * 0.42, yRet = H - 40;
  // pool
  const px = 70, pr = 46;
  g.strokeStyle = "#000"; g.lineWidth = 3;
  g.fillStyle = "#cfe6ff";
  g.fillRect(px - pr, yPipe - 20, pr * 2, yRet - yPipe + 30);
  g.strokeRect(px - pr, yPipe - 20, pr * 2, yRet - yPipe + 30);
  const lvl = Math.max(0, Math.min(1, s.process.pool_level_m / 5.2));
  g.fillStyle = "#4a90d9";
  const top = yRet + 10 - (yRet - yPipe + 30) * lvl;
  g.fillRect(px - pr + 3, top, pr * 2 - 6, yRet + 10 - top - 2);
  g.fillStyle = "#000";
  g.font = `bold ${H * 0.07}px ${SANS}`;
  g.textAlign = "center";
  g.fillText("POOL", px, yPipe - 28);
  // components along the loop
  const comps = [["PUMP", 0.30, true], ["FILTER", 0.47], ["IX", 0.63], ["CHILLER", 0.82]];
  g.strokeStyle = flow; g.lineWidth = 6;
  g.beginPath(); g.moveTo(px + pr, yPipe); g.lineTo(W * 0.92, yPipe); g.lineTo(W * 0.92, yRet); g.lineTo(px + pr, yRet); g.stroke();
  // flow arrows
  g.fillStyle = flow;
  for (const fx of [0.38, 0.55, 0.72]) {
    const ax = W * fx;
    g.beginPath(); g.moveTo(ax + 9, yPipe); g.lineTo(ax - 7, yPipe - 9); g.lineTo(ax - 7, yPipe + 9); g.fill();
  }
  for (const fx of [0.6, 0.3]) {
    const ax = W * fx;
    g.beginPath(); g.moveTo(ax - 9, yRet); g.lineTo(ax + 7, yRet - 9); g.lineTo(ax + 7, yRet + 9); g.fill();
  }
  g.lineWidth = 2.5;
  for (const [name, fx, round] of comps) {
    const cx = W * fx, w = 64, h = 46;
    g.fillStyle = name === "CHILLER" && !run ? "#ffd0d0" : "#e8e6df";
    g.strokeStyle = "#000";
    if (round) {
      g.beginPath(); g.arc(cx, yPipe, 24, 0, Math.PI * 2); g.fill(); g.stroke();
    } else {
      g.fillRect(cx - w / 2, yPipe - h / 2, w, h); g.strokeRect(cx - w / 2, yPipe - h / 2, w, h);
    }
    g.fillStyle = "#000";
    g.font = `${H * 0.058}px ${SANS}`;
    g.fillText(name, cx, yPipe + 46);
  }
  // values
  g.textAlign = "left";
  g.font = `${H * 0.065}px ${MONO}`;
  g.fillStyle = "#000";
  g.fillText(`T ${s.process.pool_temp_c.toFixed(2)} °C`, W * 0.25, yRet - 16);
  g.fillText(`LVL ${s.process.pool_level_m.toFixed(2)} m`, W * 0.56, yRet - 16);
  g.fillStyle = run ? "#008000" : "#c00000";
  g.fillText(run ? "CHILLER RUN" : "CHILLER TRIP", W * 0.66, hh + 26);
  g.lineWidth = 1;
}

function statusTile(sc, s) {
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#000000";
  g.fillRect(0, 0, W, H);
  const hh = wallHeader(g, W, H, "PUR-1 REACTOR STATUS");
  const mode = s.scrammed ? "SCRAM" : s.setback ? "SETBACK" : s.true.power_w > 1 ? "AT POWER" : "SHUTDOWN";
  g.fillStyle = s.scrammed ? "#ff3030" : s.setback ? "#ffb020" : "#30e030";
  g.font = `bold ${H * 0.17}px ${MONO}`;
  g.fillText(mode, 14, hh + H * 0.2);
  g.font = `${H * 0.075}px ${MONO}`;
  g.fillStyle = "#30e030";
  const rows = [
    ["POWER", fmtW(s.channels.ch3_power_w)],
    ["LOG PWR", `${fmt(s.channels.ch2_percent)} %`],
    ["PERIOD", fmtP(s.channels.ch2_period_s)],
    ["SERVO", s.servo.enabled ? `AUTO ${fmtW(s.servo.setpoint_w)}` : "MANUAL"],
  ];
  rows.forEach(([k, v], i) => {
    const y = hh + H * (0.34 + i * 0.1);
    g.fillStyle = "#8fbf8f"; g.fillText(k, 14, y);
    g.fillStyle = "#e0ffe0"; g.fillText(v, 150, y);
  });
  // rod bars
  Object.entries(s.rods).forEach(([n, r], i) => {
    const x = W * 0.62 + i * W * 0.12, top = hh + 20, bh = H * 0.62, bw = W * 0.07;
    g.strokeStyle = "#3a5a3a"; g.strokeRect(x, top, bw, bh);
    const f = r.position_cm / r.travel_cm;
    g.fillStyle = n === s.regulating_rod ? "#c084fc" : "#30e030";
    g.fillRect(x + 3, top + bh * (1 - f), bw - 6, bh * f);
    g.fillStyle = "#e0ffe0";
    g.font = `${H * 0.06}px ${MONO}`;
    g.fillText(n, x, top + bh + H * 0.08);
    g.fillText(r.position_cm.toFixed(1), x, top + bh + H * 0.15);
  });
}

function radiationTile(sc, s) {
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.fillStyle = "#000000";
  g.fillRect(0, 0, W, H);
  const hh = wallHeader(g, W, H, "RADIATION MONITORS");
  const r = s.radiation_mr_h;
  const rows = [["RAM POOL TOP", r.pool_top, 50], ["RAM CONSOLE", r.console, 5], ["RAM WATER", r.water, 50], ["CAM AIR", r.air, 5]];
  g.font = `${H * 0.08}px ${MONO}`;
  rows.forEach(([k, v, lim], i) => {
    const y = hh + H * (0.13 + i * 0.12);
    g.fillStyle = "#8fbf8f"; g.fillText(k, 14, y);
    g.fillStyle = v >= lim ? "#ff3030" : "#e0ffe0";
    g.fillText(`${fmt(v)} mR/h`, W * 0.52, y);
  });
  const alarms = s.scrammed ? s.scram_causes : s.alarms;
  g.fillStyle = alarms.length ? "#ffb020" : "#30e030";
  g.font = `${H * 0.07}px ${MONO}`;
  (alarms.length ? alarms : ["NO ACTIVE ALARMS"]).slice(0, 2).forEach((a, i) => g.fillText(a.slice(0, 40), 14, hh + H * (0.66 + i * 0.1)));
}

function feedOsd(sc, label, sub) {
  // On-screen display over a camera feed: camera name, a recording dot and the time.
  const { ctx: g, cv } = sc;
  const W = cv.width, H = cv.height;
  g.clearRect(0, 0, W, H);
  const fs = Math.max(16, H * 0.045);
  g.font = `bold ${fs}px ${MONO}`;
  g.textBaseline = "top";
  g.fillStyle = "rgba(0,0,0,0.45)";
  g.fillRect(10, 10, g.measureText(label).width + fs * 2.2, fs * 1.5);
  g.fillStyle = "#ffffff";
  g.fillText(label, 14 + fs * 1.4, 14);
  g.fillStyle = Math.floor(performance.now() / 700) % 2 ? "#ff2020" : "#600000";
  g.beginPath(); g.arc(14 + fs * 0.6, 14 + fs * 0.55, fs * 0.38, 0, Math.PI * 2); g.fill();
  const t = new Date().toLocaleTimeString([], { hour12: false });
  g.textAlign = "right";
  g.fillStyle = "#ffffff";
  g.fillText(t, W - 14, 14);
  if (sub) {
    g.textBaseline = "bottom";
    g.fillText(sub, W - 14, H - 12);
  }
  g.textAlign = "left";
  g.textBaseline = "alphabetic";
}

// Index = row * 4 + column, rows top to bottom and columns left to right as the operator sees them.
// Columns 1 and 2 carry the core camera and are not drawn here.
const WALL = {
  0: (sc, s, trend) => trendTile(sc, s, trend, "REACTOR POWER (LOG)", [
    { pick: (p) => p[1], color: "#30ff30", label: "P", fmt: fmtW },
  ], { log: true, lo: -3, hi: 5 }),
  4: (sc, s, trend) => trendTile(sc, s, trend, "FUEL / POOL TEMPERATURE", [
    { pick: (p) => p[4], color: "#30ff30", label: "FUEL", fmt: (v) => `${isFinite(v) ? v.toFixed(1) : "--"} °C` },
    { pick: (p) => p[5], color: "#ffe030", label: "POOL", fmt: (v) => `${isFinite(v) ? v.toFixed(2) : "--"} °C` },
  ]),
  8: (sc, s) => schematicTile(sc, s),
  3: (sc, s) => statusTile(sc, s),
  11: (sc, s) => radiationTile(sc, s),
};
