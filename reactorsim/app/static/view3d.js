// 3D view of the PUR-1 core or reactor hall, driven by the live plant state.
// The models (models/export/*.glb) carry ui_Rod_* blades, modelled fully inserted, that move up
// by their withdrawn distance, and an fx_CherenkovGlow mesh whose brightness follows power.
import * as THREE from "three";
import { GLTFLoader } from "./vendor/three/loaders/GLTFLoader.js";
import { OrbitControls } from "./vendor/three/controls/OrbitControls.js";

// Camera direction (from the target) and distance in model radii for each model.
const VIEWS = {
  pur1_core: { dir: [1, 0.9, 1.1], dist: 1.6 },
  reactor_hall: { dir: [1, 0.75, 1.2], dist: 1.25 },
};

export class ReactorView {
  constructor(el, base) {
    this.el = el;
    this.base = base;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.innerHTML = "";
    el.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(40, 1, 0.01, 200);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    this.scene.add(new THREE.HemisphereLight(0xdde8ff, 0x1a2230, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(4, 8, 5);
    this.scene.add(sun);
    this.glowLight = new THREE.PointLight(0x4fc3f7, 0, 3, 2);
    this.scene.add(this.glowLight);

    this.loader = new GLTFLoader();
    this.cache = {};
    this.rods = {};
    this.glow = [];
    this.root = null;

    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  async load(name) {
    if (!this.cache[name]) {
      this.cache[name] = await this.loader.loadAsync(`${this.base}${name}.glb`);
    }
    if (this.root) this.scene.remove(this.root);
    this.root = this.cache[name].scene;
    this.scene.add(this.root);
    this.rods = {};
    this.glow = [];
    this.root.traverse((o) => {
      const m = /^ui_Rod_(SS1|SS2|RR)$/.exec(o.name);
      if (m) {
        if (o.userData.baseY === undefined) o.userData.baseY = o.position.y;
        this.rods[m[1]] = o;
      }
      if (o.name.startsWith("fx_CherenkovGlow")) {
        o.traverse((c) => {
          if (c.isMesh) {
            if (!c.userData.ownMaterial) {
              c.material = c.material.clone();
              c.material.transparent = true;
              c.material.depthWrite = false;
              c.userData.ownMaterial = true;
            }
            this.glow.push(c);
          }
        });
        const p = new THREE.Vector3();
        o.getWorldPosition(p);
        this.glowLight.position.copy(p);
      }
    });
    const v = VIEWS[name] || VIEWS.pur1_core;
    const box = new THREE.Box3().setFromObject(this.root);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const dir = new THREE.Vector3(...v.dir).normalize();
    this.camera.position.copy(sphere.center).addScaledVector(dir, sphere.radius * v.dist / Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * 0.6);
    this.camera.near = sphere.radius / 100;
    this.camera.far = sphere.radius * 20;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(sphere.center);
    this.controls.update();
    if (this.lastState) this.update(this.lastState);
  }

  update(s) {
    this.lastState = s;
    for (const [name, obj] of Object.entries(this.rods)) {
      const r = s.rods[name];
      if (r) obj.position.y = obj.userData.baseY + r.position_cm / 100;
    }
    // Cherenkov glow: invisible below ~1 W, full at rated power and brighter above it.
    const p = s.true.power_w;
    const f = Math.max(0, Math.min(1.6, (Math.log10(Math.max(p, 1e-6)) - 0) / 4));
    for (const m of this.glow) {
      m.visible = f > 0.01;
      m.material.opacity = Math.min(0.85, 0.15 + 0.5 * f);
      m.material.emissiveIntensity = 8 * f;
    }
    this.glowLight.intensity = 2.5 * f;
  }
}
