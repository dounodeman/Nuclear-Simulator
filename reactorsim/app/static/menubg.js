// Main menu background: a made-up instrument panel whose gauges drift up and down.
// Decoration only. The panel is generic and is not modelled on PUR-1 or any real plant,
// so none of its labels or ranges carry any meaning.

const FACE = "#dfeadb";        // pale green meter faces
const PANEL = "#d8ccb2";       // beige panel paint
const BEZEL = "#3a3d40";
const BEZEL_HI = "#5a5e62";
const INK = "#1c1f22";
const LABELS = ["FLOW", "PRESSURE", "LEVEL", "TEMP", "SPEED", "LOAD", "VALVE", "SUPPLY", "RETURN", "BYPASS"];

// Small deterministic random generator, so the panel looks the same on every visit.
function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

// A slowly wandering value in 0..1: a few sines with random periods and phases.
function wanderer(r) {
  const parts = [0, 1, 2].map(() => ({ f: 0.03 + r() * 0.12, p: r() * Math.PI * 2, a: 0.3 + r() * 0.7 }));
  const sum = parts.reduce((t, q) => t + q.a, 0);
  const mid = 0.25 + r() * 0.5;
  return (t) => {
    let v = 0;
    for (const q of parts) v += q.a * Math.sin(t * q.f * Math.PI * 2 + q.p);
    return Math.min(1, Math.max(0, mid + (v / sum) * 0.38));
  };
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y);
  g.arcTo(x + w, y, x + w, y + h, r);
  g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r);
  g.arcTo(x, y, x + w, y, r);
  g.closePath();
}

function bezel(g, x, y, w, h) {
  roundRect(g, x, y, w, h, Math.min(w, h) * 0.08);
  g.fillStyle = BEZEL;
  g.fill();
  g.strokeStyle = BEZEL_HI;
  g.lineWidth = 2;
  g.stroke();
}

function plate(g, text, cx, y, w, h) {
  g.fillStyle = "#24272a";
  roundRect(g, cx - w / 2, y, w, h, 3);
  g.fill();
  g.fillStyle = "#e8e8e8";
  g.font = `${Math.round(h * 0.6)}px Tahoma, Verdana, sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(text, cx, y + h / 2 + 1);
}

// ---------------------------------------------------------------- instruments

function dial(g, x, y, w, h, v, label) {
  bezel(g, x, y, w, h);
  const r = Math.min(w, h * 0.82) * 0.42;
  const cx = x + w / 2, cy = y + h * 0.44;
  g.fillStyle = "#c9c9c9";
  g.beginPath(); g.arc(cx, cy, r + 4, 0, Math.PI * 2); g.fill();
  g.fillStyle = FACE;
  g.beginPath(); g.arc(cx, cy, r, 0, Math.PI * 2); g.fill();
  const a0 = Math.PI * 0.75, span = Math.PI * 1.5;
  g.strokeStyle = INK;
  g.fillStyle = INK;
  g.font = `${Math.round(r * 0.16)}px Tahoma, Verdana, sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  for (let i = 0; i <= 50; i++) {
    const a = a0 + span * (i / 50);
    const long = i % 5 === 0;
    g.lineWidth = long ? 2 : 1;
    g.beginPath();
    g.moveTo(cx + Math.cos(a) * r * 0.92, cy + Math.sin(a) * r * 0.92);
    g.lineTo(cx + Math.cos(a) * r * (long ? 0.78 : 0.85), cy + Math.sin(a) * r * (long ? 0.78 : 0.85));
    g.stroke();
    if (i % 10 === 0) g.fillText(String(i * 2), cx + Math.cos(a) * r * 0.63, cy + Math.sin(a) * r * 0.63);
  }
  const a = a0 + span * v;
  g.lineWidth = Math.max(2, r * 0.05);
  g.lineCap = "round";
  g.beginPath();
  g.moveTo(cx - Math.cos(a) * r * 0.12, cy - Math.sin(a) * r * 0.12);
  g.lineTo(cx + Math.cos(a) * r * 0.86, cy + Math.sin(a) * r * 0.86);
  g.stroke();
  g.lineCap = "butt";
  g.beginPath(); g.arc(cx, cy, r * 0.07, 0, Math.PI * 2); g.fill();
  plate(g, label, cx, y + h * 0.84, w * 0.62, h * 0.1);
}

function edgewise(g, x, y, w, h, v, label, zone) {
  bezel(g, x, y, w, h);
  const fx = x + w * 0.05, fy = y + h * 0.14, fw = w * 0.9, fh = h * 0.72;
  g.fillStyle = FACE;
  g.fillRect(fx, fy, fw, fh);
  if (zone) {
    g.fillStyle = "#e0c020"; g.fillRect(fx + fw * 0.78, fy + fh * 0.5, fw * 0.1, fh * 0.16);
    g.fillStyle = "#c82020"; g.fillRect(fx + fw * 0.88, fy + fh * 0.5, fw * 0.1, fh * 0.16);
  }
  g.strokeStyle = INK;
  for (let i = 0; i <= 40; i++) {
    const tx = fx + fw * (0.02 + 0.96 * i / 40);
    g.lineWidth = i % 4 === 0 ? 1.5 : 1;
    g.beginPath(); g.moveTo(tx, fy + fh * 0.5); g.lineTo(tx, fy + fh * (i % 4 === 0 ? 0.22 : 0.34)); g.stroke();
  }
  const px = fx + fw * (0.02 + 0.96 * v);
  g.fillStyle = "#1040c0";
  g.fillRect(px - 2, fy + fh * 0.16, 4, fh * 0.56);
  g.fillStyle = "#333";
  g.font = `${Math.round(fh * 0.13)}px Tahoma, Verdana, sans-serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillText(label, fx + fw / 2, fy + fh * 0.84);
}

function vbar(g, x, y, w, h, v) {
  bezel(g, x, y, w, h);
  const fx = x + w * 0.12, fy = y + h * 0.05, fw = w * 0.76, fh = h * 0.9;
  g.fillStyle = FACE;
  g.fillRect(fx, fy, fw, fh);
  g.fillStyle = "#d8c020"; g.fillRect(fx + fw * 0.62, fy + fh * 0.06, fw * 0.14, fh * 0.3);
  g.fillStyle = "#c82020"; g.fillRect(fx + fw * 0.62, fy + fh * 0.02, fw * 0.14, fh * 0.05);
  g.strokeStyle = INK;
  for (let i = 0; i <= 30; i++) {
    const ty = fy + fh * (0.97 - 0.94 * i / 30);
    g.lineWidth = i % 5 === 0 ? 1.5 : 1;
    g.beginPath(); g.moveTo(fx + fw * 0.6, ty); g.lineTo(fx + fw * (i % 5 === 0 ? 0.3 : 0.42), ty); g.stroke();
  }
  const py = fy + fh * (0.97 - 0.94 * v);
  g.fillStyle = INK;
  g.beginPath(); g.moveTo(fx + fw * 0.62, py); g.lineTo(fx + fw * 0.95, py - 5); g.lineTo(fx + fw * 0.95, py + 5); g.fill();
}

function digits(g, x, y, w, h, v, max) {
  bezel(g, x, y, w, h);
  g.fillStyle = "#120606";
  g.fillRect(x + w * 0.06, y + h * 0.14, w * 0.88, h * 0.72);
  const n = Math.round(v * max);
  const txt = String(n).padStart(String(max).length, " ");
  g.font = `bold ${Math.round(h * 0.56)}px "Courier New", monospace`;
  g.textAlign = "right";
  g.textBaseline = "middle";
  g.fillStyle = "#3a0a0a";
  g.fillText("8".repeat(txt.length), x + w * 0.9, y + h * 0.52);
  g.fillStyle = "#ff3020";
  g.shadowColor = "#ff2010"; g.shadowBlur = 8;
  g.fillText(txt, x + w * 0.9, y + h * 0.52);
  g.shadowBlur = 0;
}

function annunciator(g, x, y, w, h, t, r) {
  bezel(g, x, y, w, h);
  const cols = 4, rows = 3, pad = w * 0.06;
  const cw = (w - pad * 2) / cols, ch = (h - pad * 2) / rows;
  for (let i = 0; i < cols * rows; i++) {
    const c = i % cols, k = Math.floor(i / cols);
    const lit = Math.sin(t * (0.2 + r[i] * 0.6) + r[i] * 9) > 0.55;
    const flash = r[i] > 0.85 && Math.floor(t * 2) % 2 === 0;
    g.fillStyle = lit ? (r[i] > 0.7 ? (flash ? "#601010" : "#e02020") : r[i] > 0.4 ? "#e8b020" : "#f0e0a0") : "#5a2020";
    if (!lit && r[i] < 0.3) g.fillStyle = "#808080";
    g.fillRect(x + pad + c * cw + 2, y + pad + k * ch + 2, cw - 4, ch - 4);
  }
}

function lamps(g, x, y, w, h, t, r) {
  bezel(g, x, y, w, h);
  for (let i = 0; i < 4; i++) {
    const on = Math.sin(t * (0.3 + r[i]) + r[i] * 7) > 0;
    const cx = x + w * (0.2 + i * 0.2), cy = y + h / 2, rad = Math.min(w * 0.07, h * 0.3);
    g.fillStyle = i % 2 ? (on ? "#30e040" : "#104010") : (on ? "#ff3020" : "#401010");
    g.beginPath(); g.arc(cx, cy, rad, 0, Math.PI * 2); g.fill();
  }
}

// ---------------------------------------------------------------- layout

function layout(width, height) {
  const r = rng(1979);
  const unit = Math.max(90, Math.min(130, width / 14));
  const items = [];
  const cols = Math.ceil(width / unit) + 1, rows = Math.ceil(height / unit) + 1;
  const used = new Set();
  const free = (c, k, cw, ck) => {
    for (let i = 0; i < cw; i++) for (let j = 0; j < ck; j++) if (used.has(`${c + i},${k + j}`) || c + i >= cols || k + j >= rows) return false;
    return true;
  };
  const take = (c, k, cw, ck) => { for (let i = 0; i < cw; i++) for (let j = 0; j < ck; j++) used.add(`${c + i},${k + j}`); };
  for (let k = 0; k < rows; k++) {
    for (let c = 0; c < cols; c++) {
      if (used.has(`${c},${k}`)) continue;
      const roll = r();
      let kind, cw = 1, ck = 1;
      if (roll < 0.28 && free(c, k, 2, 2)) { kind = "dial"; cw = 2; ck = 2; }
      else if (roll < 0.45 && free(c, k, 1, 2)) { kind = "vbar"; ck = 2; }
      else if (roll < 0.62 && free(c, k, 2, 1)) { kind = "edgewise"; cw = 2; }
      else if (roll < 0.72 && free(c, k, 2, 1)) { kind = "digits"; cw = 2; }
      else if (roll < 0.82 && free(c, k, 2, 1)) { kind = "annunciator"; cw = 2; }
      else if (roll < 0.9) kind = "lamps";
      else kind = "edgewise";
      take(c, k, cw, ck);
      const it = {
        kind, x: c * unit - unit * 0.3, y: k * unit - unit * 0.2, w: cw * unit, h: ck * unit,
        v: wanderer(r), label: LABELS[Math.floor(r() * LABELS.length)], zone: r() > 0.5,
        max: [999, 1800, 3600, 9999][Math.floor(r() * 4)], r: Array.from({ length: 12 }, r),
      };
      if (kind === "lamps") { it.h = unit * 0.5; it.y += unit * 0.25; }
      if (kind === "edgewise" || kind === "digits") { it.h = unit * 0.7; it.y += unit * 0.15; }
      items.push(it);
    }
  }
  return { items, unit };
}

function drawItem(g, it, t) {
  const m = 8, x = it.x + m, y = it.y + m, w = it.w - 2 * m, h = it.h - 2 * m;
  const v = it.v(t);
  switch (it.kind) {
    case "dial": return dial(g, x, y, w, h, v, it.label);
    case "vbar": return vbar(g, x + w * 0.25, y, w * 0.5, h, v);
    case "edgewise": return edgewise(g, x, y, w, h, v, it.label, it.zone);
    case "digits": return digits(g, x + w * 0.1, y, w * 0.8, h, v, it.max);
    case "annunciator": return annunciator(g, x, y, w, h, t, it.r);
    case "lamps": return lamps(g, x, y, w, h, t, it.r);
  }
}

// Start drawing into `canvas`; returns { stop() }. Redraws at about 30 frames a second.
export function startMenuBackground(canvas) {
  const g = canvas.getContext("2d");
  let plan = null, raf = 0, last = 0, stopped = false;
  const t0 = performance.now();
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(canvas.clientWidth * dpr);
    canvas.height = Math.round(canvas.clientHeight * dpr);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    plan = layout(canvas.clientWidth, canvas.clientHeight);
  };
  const frame = (now) => {
    if (stopped) return;
    raf = requestAnimationFrame(frame);
    if (now - last < 33) return;
    last = now;
    const t = (now - t0) / 1000;
    g.fillStyle = PANEL;
    g.fillRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    for (const it of plan.items) drawItem(g, it, t);
  };
  resize();
  window.addEventListener("resize", resize);
  raf = requestAnimationFrame(frame);
  return {
    stop() {
      stopped = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    },
  };
}
