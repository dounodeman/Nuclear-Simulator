// Background sound of the main control room, synthesised with Web Audio (no sound files):
//  - the air handling: a low rumble of supply air through the ceiling diffusers, with a slow
//    swell, and the hiss of air through the perforated luminous ceiling;
//  - the electrical hum of the ballasts and panel transformers at 60 Hz and its harmonics;
//  - the cooling fans of the plant process computer and recorder cabinets, a steady whir
//    with a faint blade tone;
//  - now and then a relay clicking in the back panels and a burst of the alarm typer.
// Browsers only start audio after a click, so start() is called from the "Enter" button.

function noiseBuffer(ctx, seconds, colour) {
  const n = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(1, n, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let last = 0, b0 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < n; i++) {
    const w = Math.random() * 2 - 1;
    if (colour === "brown") { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
    else if (colour === "pink") {
      b0 = 0.99765 * b0 + w * 0.0990460; b1 = 0.96300 * b1 + w * 0.2965164; b2 = 0.57000 * b2 + w * 1.0526913;
      d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.2;
    } else d[i] = w;
  }
  // fade the loop ends into each other so the loop point does not click
  const f = Math.min(Math.floor(ctx.sampleRate * 0.05), Math.floor(n / 4));
  for (let i = 0; i < f; i++) { const k = i / f; d[n - f + i] = d[n - f + i] * (1 - k) + d[i] * k; }
  return buf;
}

export class RoomSound {
  constructor() {
    this.ctx = null;
    this.volume = 0.5;
    this.enabled = true;
    this.timer = null;
  }

  start() {
    if (this.ctx) { this.ctx.resume?.(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    const ctx = (this.ctx = new AC());
    this.master = ctx.createGain();
    this.master.gain.value = this.enabled ? this.volume : 0;
    this.master.connect(ctx.destination);
    const loop = (colour, seconds = 6) => {
      const s = ctx.createBufferSource();
      s.buffer = noiseBuffer(ctx, seconds, colour);
      s.loop = true;
      s.start(ctx.currentTime + Math.random() * 0.1);
      return s;
    };
    const chain = (src, ...nodes) => { let a = src; for (const n of nodes) { a.connect(n); a = n; } a.connect(this.master); return nodes[nodes.length - 1]; };
    const filt = (type, f, q = 0.7) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; };
    const gain = (v) => { const g = ctx.createGain(); g.gain.value = v; return g; };
    const lfo = (target, rate, depth) => {
      const o = ctx.createOscillator(); o.frequency.value = rate;
      const d = gain(depth); o.connect(d); d.connect(target); o.start();
    };

    // air handling: rumble and a swelling hiss
    const rumble = chain(loop("brown"), filt("lowpass", 220), gain(0.55));
    lfo(rumble.gain, 0.07, 0.08);
    const hiss = chain(loop("pink"), filt("bandpass", 950, 0.45), filt("lowpass", 3200), gain(0.10));
    lfo(hiss.gain, 0.045, 0.025);

    // 60 Hz electrical hum and its harmonics (ballasts, panel transformers)
    for (const [f, v] of [[60, 0.010], [120, 0.022], [180, 0.006], [240, 0.004], [360, 0.002]]) {
      const o = ctx.createOscillator(); o.frequency.value = f; o.type = "sine";
      chain(o, gain(v)); o.start();
    }

    // computer and cabinet fans: a whir with a slightly wandering blade tone
    chain(loop("white", 4), filt("bandpass", 2300, 1.1), gain(0.018));
    const blade = ctx.createOscillator(); blade.type = "triangle"; blade.frequency.value = 236;
    lfo(blade.frequency, 0.13, 1.8);
    chain(blade, filt("lowpass", 700), gain(0.006)); blade.start();
    const blade2 = ctx.createOscillator(); blade2.type = "triangle"; blade2.frequency.value = 311;
    lfo(blade2.frequency, 0.09, 2.5);
    chain(blade2, filt("lowpass", 900), gain(0.003)); blade2.start();

    this.clickBuf = noiseBuffer(ctx, 0.03, "white");
    this._schedule();
  }

  // relay clicks and the odd burst of the alarm typer, at random intervals
  _schedule() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      if (this.ctx && this.enabled && this.volume > 0) {
        if (Math.random() < 0.75) this._click(1 + Math.floor(Math.random() * 2), 0.09);
        else this._typer();
      }
      this._schedule();
    }, 6000 + Math.random() * 18000);
  }

  _click(count, level, at = 0) {
    const ctx = this.ctx;
    for (let i = 0; i < count; i++) {
      const s = ctx.createBufferSource(); s.buffer = this.clickBuf;
      const hp = ctx.createBiquadFilter(); hp.type = "highpass"; hp.frequency.value = 1800;
      const g = ctx.createGain();
      const t = ctx.currentTime + at + i * (0.03 + Math.random() * 0.05);
      g.gain.setValueAtTime(level, t); g.gain.exponentialRampToValueAtTime(0.0005, t + 0.025);
      s.connect(hp); hp.connect(g); g.connect(this.master);
      s.start(t); s.stop(t + 0.03);
    }
  }

  _typer() {
    const chars = 12 + Math.floor(Math.random() * 30);
    for (let i = 0; i < chars; i++) this._click(1, 0.035, i * (0.07 + Math.random() * 0.03));
  }

  setVolume(v) {
    this.volume = v;
    if (this.master) this.master.gain.setTargetAtTime(this.enabled ? v : 0, this.ctx.currentTime, 0.1);
  }

  setEnabled(on) {
    this.enabled = on;
    this.setVolume(this.volume);
  }

  suspend() { this.ctx?.suspend?.(); }
  resume() { this.ctx?.resume?.(); }
}
