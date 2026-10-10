// Surface detail for the hall, made in the page rather than shipped as image files.
//
// The glTF models carry flat colours. Here each material that should look like a real surface
// (painted block walls, the epoxy floor, carpet and chair fabric, brushed stainless, acoustic
// ceiling tiles, ...) gets a small grey canvas texture that multiplies its colour, and for the
// rougher ones a bump map from the same canvas. The meshes are given box-projected UVs in world
// metres, so the pattern keeps its real size and runs on across neighbouring objects.
import * as THREE from "three";

const SIZE = 512;

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function canvas(fill) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = SIZE;
  const g = cv.getContext("2d");
  g.fillStyle = fill;
  g.fillRect(0, 0, SIZE, SIZE);
  return [cv, g];
}

function noise(g, n, size, lo, hi, alpha, seed) {
  const r = rng(seed);
  for (let i = 0; i < n; i++) {
    const v = Math.round(lo + (hi - lo) * r());
    g.fillStyle = `rgba(${v},${v},${v},${alpha})`;
    const s = size * (0.5 + r());
    g.fillRect(r() * SIZE, r() * SIZE, s, s);
  }
}

// Each pattern: draw(g) on a SIZE x SIZE canvas; metres = world size of one repeat.
const PATTERNS = {
  block(g) {
    // Painted concrete block, 16 x 8 in units in running bond: two blocks by four courses per tile.
    noise(g, 9000, 2, 200, 255, 0.25, 11);
    g.strokeStyle = "rgba(150,146,138,0.75)";
    g.lineWidth = 5;
    const bh = SIZE / 4;
    for (let row = 0; row < 4; row++) {
      const y = row * bh;
      g.beginPath(); g.moveTo(0, y); g.lineTo(SIZE, y); g.stroke();
      for (const x of row % 2 ? [SIZE / 4, (3 * SIZE) / 4] : [0, SIZE / 2]) {
        g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + bh); g.stroke();
      }
    }
  },
  speckle(g) {
    noise(g, 26000, 1.6, 150, 255, 0.35, 23);
    noise(g, 900, 2.5, 90, 130, 0.5, 29);
  },
  concrete(g) {
    noise(g, 30000, 2.2, 140, 255, 0.3, 31);
    noise(g, 300, 30, 170, 235, 0.08, 37);
  },
  fabric(g) {
    // A tight weave: alternating light and dark threads both ways.
    for (let i = 0; i < SIZE; i += 4) {
      g.fillStyle = `rgba(${i % 8 ? 210 : 255},${i % 8 ? 210 : 255},${i % 8 ? 210 : 255},0.55)`;
      g.fillRect(0, i, SIZE, 2);
      g.fillRect(i, 0, 2, SIZE);
    }
    noise(g, 6000, 1.5, 170, 255, 0.4, 43);
  },
  carpet(g) {
    noise(g, 40000, 2, 120, 255, 0.45, 53);
    noise(g, 2500, 3, 60, 110, 0.35, 59);
  },
  brushed(g) {
    // Fine streaks along v (up a vertical drive tube, along the length of a rail).
    const r = rng(61);
    for (let i = 0; i < 1400; i++) {
      const v = Math.round(185 + 70 * r());
      g.strokeStyle = `rgba(${v},${v},${v},0.35)`;
      g.lineWidth = 0.6 + r();
      const x = r() * SIZE;
      g.beginPath(); g.moveTo(x, 0); g.lineTo(x + (r() - 0.5) * 4, SIZE); g.stroke();
    }
  },
  stipple(g) {
    // Orange-peel painted steel, laminate and powder coat.
    noise(g, 16000, 2.4, 205, 255, 0.3, 71);
  },
  ceiling(g) {
    // 2 x 2 ft acoustic tiles in a white T-bar grid, with fissures and pinholes.
    noise(g, 9000, 1.6, 150, 230, 0.5, 79);
    const r = rng(83);
    g.strokeStyle = "rgba(170,170,170,0.5)";
    g.lineWidth = 1;
    for (let i = 0; i < 220; i++) {
      const x = r() * SIZE, y = r() * SIZE;
      g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 22, y + (r() - 0.5) * 22); g.stroke();
    }
    g.fillStyle = "rgba(255,255,255,1)";
    g.fillRect(0, 0, SIZE, 10);
    g.fillRect(0, 0, 10, SIZE);
    g.fillStyle = "rgba(140,140,140,0.8)";
    g.fillRect(0, 10, SIZE, 2);
    g.fillRect(10, 0, 2, SIZE);
  },
  spangle(g) {
    // Hot-dip galvanising: irregular light and dark crystals.
    const r = rng(89);
    for (let i = 0; i < 900; i++) {
      const v = Math.round(205 + 50 * r());
      g.fillStyle = `rgba(${v},${v},${v},0.35)`;
      g.beginPath();
      const x = r() * SIZE, y = r() * SIZE, s = 6 + 18 * r();
      g.moveTo(x, y);
      for (let k = 1; k < 6; k++) g.lineTo(x + Math.cos(k * 1.25 + r()) * s, y + Math.sin(k * 1.25 + r()) * s);
      g.fill();
    }
  },
};

// Material name (from models/pur1/common.py) -> [pattern, metres per repeat, bump scale].
const SURFACES = {
  WallCream: ["block", 0.81, 2.0],
  ConcreteBlock: ["block", 0.81, 2.5],
  FloorEpoxy: ["speckle", 1.2, 0],
  FloorStripeYellow: ["speckle", 1.2, 0],
  Concrete: ["concrete", 1.5, 1.0],
  CarpetMat: ["carpet", 0.6, 1.5],
  ChairBlue: ["fabric", 0.08, 0.6],
  ChairGreen: ["fabric", 0.08, 0.6],
  ChairFabric: ["fabric", 0.08, 0.6],
  Stainless: ["brushed", 0.5, 0],
  Aluminum6061: ["brushed", 0.6, 0],
  AluminumAnodised: ["brushed", 0.6, 0],
  Ceiling: ["ceiling", 0.61, 1.2],
  SteelPainted: ["stipple", 0.4, 0.3],
  DeskBlack: ["stipple", 0.3, 0.2],
  DoorGrey: ["stipple", 0.4, 0.2],
  DoorFrame: ["stipple", 0.4, 0.2],
  TableTopWhite: ["stipple", 0.5, 0],
  TableBlueLegs: ["stipple", 0.3, 0],
  CabinetBlack: ["stipple", 0.4, 0.2],
  PoolWallBlack: ["stipple", 0.6, 0.3],
  PoolLipGrey: ["concrete", 1.0, 0.5],
  GratingGalv: ["spangle", 0.4, 0],
  Duct: ["spangle", 0.8, 0],
  PipeGreen: ["stipple", 0.3, 0],
  PCCase: ["stipple", 0.3, 0],
};

const cache = {};
function texture(pattern) {
  if (!cache[pattern]) {
    const [cv, g] = canvas("#ffffff");
    PATTERNS[pattern](g);
    const t = new THREE.CanvasTexture(cv);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    const b = new THREE.CanvasTexture(cv);
    b.wrapS = b.wrapT = THREE.RepeatWrapping;
    cache[pattern] = [t, b];
  }
  return cache[pattern];
}

function boxUVs(mesh, metres) {
  // Project each vertex onto the world plane its normal faces most: walls get (horizontal, up),
  // floors and ceilings get (x, z).
  const g = mesh.geometry;
  const p = g.attributes.position, n = g.attributes.normal;
  if (!p || !n) return;
  const m = mesh.matrixWorld, nm = new THREE.Matrix3().getNormalMatrix(m);
  const v = new THREE.Vector3(), w = new THREE.Vector3();
  const uv = new Float32Array(p.count * 2);
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i).applyMatrix4(m);
    w.fromBufferAttribute(n, i).applyMatrix3(nm);
    const ax = Math.abs(w.x), ay = Math.abs(w.y), az = Math.abs(w.z);
    let a, b;
    if (ay >= ax && ay >= az) { a = v.x; b = v.z; }
    else if (ax >= az) { a = v.z; b = v.y; }
    else { a = v.x; b = v.y; }
    uv[2 * i] = a / metres;
    uv[2 * i + 1] = b / metres;
  }
  g.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
}

export function applySurfaces(root) {
  root.updateMatrixWorld(true);
  const done = new Set(), geoms = new Set();
  let count = 0;
  root.traverse((o) => {
    if (!o.isMesh || !o.material || Array.isArray(o.material)) return;
    const spec = SURFACES[o.material.name];
    if (!spec || !o.material.isMeshStandardMaterial) return;
    const [pattern, metres, bump] = spec;
    if (o.material.map && !done.has(o.material)) return;   // the model's own texture wins
    if (geoms.has(o.geometry)) o.geometry = o.geometry.clone();   // shared: UVs are per placement
    geoms.add(o.geometry);
    boxUVs(o, metres);
    if (!done.has(o.material)) {
      const [t, b] = texture(pattern);
      o.material.map = t;
      if (bump) {
        o.material.bumpMap = b;
        o.material.bumpScale = bump;
      }
      o.material.needsUpdate = true;
      done.add(o.material);
    }
    count++;
  });
  return count;
}
