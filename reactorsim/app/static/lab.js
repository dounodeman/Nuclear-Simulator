// Materials lab workstation: prepare samples, irradiate them in the core, count them on the
// HPGe gamma spectrometer and work through the guided materials science experiments.
// The physics and the analysis software run in the simulator (reactorsim/materials.py);
// this page sends lab_* commands and draws what comes back in state.lab.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

let cmd = null;
let built = false;
let lastSampleIds = "";
let lastPositions = "";
let lastAnalysisKey = "";
let lastGuideKey = "";
let openGuide = "flux";

function fmt(v, digits = 3) {
  if (v === null || v === undefined || !isFinite(v)) return "-";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-2) return v.toExponential(digits - 1).replace("e+", "e");
  return v.toPrecision(digits).replace(/\.0+$|(\.\d*?)0+$/, "$1");
}
function fmtDur(s) {
  if (s === null || s === undefined || !isFinite(s)) return "-";
  if (s < 120) return `${s.toFixed(0)} s`;
  if (s < 7200) return `${(s / 60).toFixed(1)} min`;
  if (s < 3 * 86400) return `${(s / 3600).toFixed(2)} h`;
  if (s < 2 * 365 * 86400) return `${(s / 86400).toFixed(1)} d`;
  return `${(s / 3.156e7).toFixed(2)} y`;
}
function fmtMass(g) {
  if (g >= 1) return `${fmt(g)} g`;
  if (g >= 1e-3) return `${fmt(g * 1e3)} mg`;
  return `${fmt(g * 1e6)} µg`;
}
function fmtBq(a) {
  if (!isFinite(a)) return "-";
  if (a >= 3.7e7) return `${fmt(a / 3.7e10)} Ci`;
  if (a >= 3.7e4) return `${fmt(a / 3.7e7)} mCi`;
  return `${fmt(a / 3.7e4)} µCi`;
}
const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ------------------------------------------------------------------ guided experiments

// Each guide lists the steps; check(lab) marks a step done from the lab state.
const samplesOf = (lab, material, f = () => true) => lab.samples.filter((s) => s.material === material && f(s));
const irradiated = (s) => s.irradiation_s > 0;
const counted = (s) => s.counts > 0;
const fluxAt = (lab, pos) => lab.results.flux[pos];
const anyFlux = (lab) => Object.keys(lab.results.flux).length > 0;
const posOf = (lab, s) => lab.positions.find((p) => p.samples.includes(s.id))?.key;

const GUIDES = [
  {
    key: "flux", title: "1. Neutron flux and cadmium ratio",
    intro: "Gold foils are the standard flux monitor. A bare foil captures thermal and epithermal neutrons; " +
      "a foil inside a cadmium box (which stops neutrons below 0.5 eV) captures only epithermal ones. " +
      "Their Au-198 activities give the thermal flux, the epithermal flux and the cadmium ratio at a position.",
    steps: [
      ["Prepare a bare gold foil (10 mg)", (l) => samplesOf(l, "gold_foil", (s) => !s.cadmium).length > 0],
      ["Prepare a gold foil with the cadmium cover", (l) => samplesOf(l, "gold_foil", (s) => s.cadmium).length > 0],
      ["Load both into the same position and run at steady power for at least 10 min (1 kW is plenty)",
        (l) => samplesOf(l, "gold_foil", (s) => s.irradiation_s >= 600).length >= 2],
      ["Take them out and count each one (411.8 keV), keeping dead time under 10%",
        (l) => samplesOf(l, "gold_foil", counted).length >= 2],
    ],
    result(l) {
      const rows = Object.entries(l.results.flux).map(([k, f]) => {
        const pos = l.positions.find((p) => p.key === k);
        const tru = pos ? `<span class="truth"> (true ${fmt(pos.true_thermal_flux / Math.max(l._power_kw, 1e-9))})</span>` : "";
        return `<tr><td>${esc(f.label)}</td><td>${fmt(f.thermal_per_kw)}${tru}</td><td>${fmt(f.epithermal_per_kw)}</td><td>${fmt(f.cadmium_ratio)}</td></tr>`;
      }).join("");
      return rows ? `<table class="lab-table"><tr><th>Position</th><th>Thermal flux per kW</th><th>Epithermal per kW</th><th>Cd ratio</th></tr>${rows}</table>
        <p class="hint">Flux in n/cm²·s per kW of reactor power, from the bare and cadmium-covered foils.</p>` : "";
    },
  },
  {
    key: "naa", title: "2. Neutron activation analysis of an unknown",
    intro: "Every activated element gives off gamma rays at its own energies. Irradiate an unknown sample where " +
      "you have measured the flux, count it, and the analysis software identifies the elements from the peaks " +
      "and works out how much of each is there (the absolute method).",
    steps: [
      ["Measure the flux at a position (experiment 1)", anyFlux],
      ["Prepare an unknown sample (geological sample or alloy shaving)",
        (l) => l.samples.some((s) => s.material.startsWith("unknown"))],
      ["Irradiate it at that position (30 min at 10 kW suits short- and long-lived products)",
        (l) => l.samples.some((s) => s.material.startsWith("unknown") && irradiated(s))],
      ["Count it soon after for the short-lived products, and again hours later for the long-lived ones",
        (l) => l.samples.some((s) => s.material.startsWith("unknown") && counted(s))],
    ],
    result(l) {
      const out = [];
      for (const s of l.samples.filter((x) => x.material.startsWith("unknown"))) {
        const a = l.results.analyses[s.id];
        if (!a) continue;
        if (!a.element_masses_g) {
          out.push(`<p class="hint">Sample ${s.id}: measure the flux at ${esc(a.needs_flux || "its position")} to quantify.</p>`);
          continue;
        }
        const comp = s.true?.composition || {};
        const rows = Object.entries(a.element_masses_g).sort((x, y) => y[1] - x[1]).map(([el, m]) => {
          const frac = m / s.mass_g;
          const tru = comp[el] !== undefined ? `<span class="truth"> (true ${fmtFrac(comp[el])})</span>` : "";
          return `<tr><td>${el}</td><td>${fmtMass(m)}</td><td>${fmtFrac(frac)}${tru}</td></tr>`;
        }).join("");
        out.push(`<h4>Sample ${s.id}: ${esc(s.name)}</h4><table class="lab-table"><tr><th>Element</th><th>Mass</th><th>Concentration</th></tr>${rows}</table>`);
      }
      return out.join("");
    },
  },
  {
    key: "halflife", title: "3. Half-life measurement",
    intro: "Count a short-lived product several times as it decays and fit the activities: the slope gives the " +
      "half-life. Aluminium (Al-28, 2.24 min) or indium (In-116m, 54 min) work well. Watch the dead time: " +
      "a hot sample at the start biases the fit.",
    steps: [
      ["Prepare an aluminium coupon (50 mg) or an indium foil",
        (l) => l.samples.some((s) => ["aluminium", "indium_foil"].includes(s.material))],
      ["Irradiate it briefly (Al: 2 min at 1 kW; In: 10 min at 1 kW)",
        (l) => l.samples.some((s) => ["aluminium", "indium_foil"].includes(s.material) && irradiated(s))],
      ["Count it at least three times in a row (Al: 60 s counts; In: 5 min counts)",
        (l) => Object.keys(l.results.half_lives).length > 0],
    ],
    result(l) {
      const rows = Object.values(l.results.half_lives).map((h) =>
        `<tr><td>${h.sample}</td><td>${h.nuclide}</td><td>${fmtDur(h.half_life_s)}</td><td>${fmtDur(h.library_s)}</td><td>${h.points}</td></tr>`).join("");
      return rows ? `<table class="lab-table"><tr><th>Sample</th><th>Nuclide</th><th>Measured</th><th>Library</th><th>Counts</th></tr>${rows}</table>` : "";
    },
  },
  {
    key: "ntd", title: "4. Silicon neutron transmutation doping",
    intro: "Thermal neutrons turn a few Si-30 atoms into Si-31, which decays to phosphorus: a donor spread " +
      "perfectly evenly through the crystal. This is how detector-grade and power-device silicon is doped. " +
      "Goal: take a 5000 Ω·cm float-zone wafer down to 2000 Ω·cm (within 10%).",
    steps: [
      ["Measure the flux at a position (experiment 1)", anyFlux],
      ["Load a silicon wafer at that position", (l) => samplesOf(l, "silicon_wafer", irradiated).length > 0 ||
        samplesOf(l, "silicon_wafer", (s) => posOf(l, s)).length > 0],
      ["Irradiate until the predicted resistivity reaches 2000 Ω·cm, then take it out",
        (l) => Object.entries(l.results.ntd).some(([id, n]) => Math.abs(n.resistivity_ohm_cm - 2000) <= 200 &&
          samplesOf(l, "silicon_wafer", (s) => String(s.id) === id && !posOf(l, s)).length)],
    ],
    result(l) {
      const rows = Object.entries(l.results.ntd).map(([id, n]) => {
        const ok = Math.abs(n.resistivity_ohm_cm - 2000) <= 200;
        return `<tr><td>${id}</td><td>${fmt(n.phosphorus_per_cm3)}</td><td class="${ok ? "ok" : ""}">${fmt(n.resistivity_ohm_cm, 4)} Ω·cm</td></tr>`;
      }).join("");
      return rows ? `<table class="lab-table"><tr><th>Wafer</th><th>P donors per cm³</th><th>Resistivity</th></tr>${rows}</table>
        <p class="hint">Predicted from the thermal fluence (measured flux × time at power). About 10 h at 10 kW in the centre position.</p>` : "";
    },
  },
  {
    key: "damage", title: "5. Radiation damage and activation of steel",
    intro: "Fast neutrons knock atoms out of the lattice (displacements per atom, dpa), which hardens and " +
      "embrittles reactor steels. The Ni-58(n,p)Co-58 threshold reaction in the steel itself measures the fast " +
      "flux. The same irradiation activates the steel: note the Co-60 from a 0.1% cobalt impurity.",
    steps: [
      ["Prepare a stainless steel 304 coupon", (l) => samplesOf(l, "steel_304").length > 0],
      ["Irradiate it in the core (the longer, the better the Co-58 statistics; try 1 h at 10 kW)",
        (l) => samplesOf(l, "steel_304", irradiated).length > 0],
      ["Let the Mn-56 decay for a few hours, then count it for at least 30 min",
        (l) => Object.keys(l.results.damage).length > 0],
    ],
    result(l) {
      const rows = Object.entries(l.results.damage).map(([id, d]) =>
        `<tr><td>${id}</td><td>${fmt(d.fast_flux)}</td><td>${fmt(d.fast_fluence)}</td><td>${fmt(d.dpa)}</td><td>${fmt(d.hardening_mpa)} MPa</td></tr>`).join("");
      return rows ? `<table class="lab-table"><tr><th>Coupon</th><th>Fast flux</th><th>Fluence</th><th>dpa</th><th>Hardening</th></tr>${rows}</table>
        <p class="hint">A power-reactor pressure vessel sees about 0.1 dpa over its life and core internals 1–100 dpa; PUR-1's 10 kW gives millionths.</p>` : "";
    },
  },
];

function fmtFrac(f) {
  if (f >= 0.01) return `${(f * 100).toPrecision(3)} %`;
  return `${fmt(f * 1e6)} ppm`;
}

// ------------------------------------------------------------------ build

export function initLab(command) {
  cmd = command;
}

function build(lab) {
  built = true;
  $("#labMaterial").innerHTML = lab.materials.map((m) =>
    `<option value="${m.key}" data-mass="${m.mass_g}">${esc(m.name)}</option>`).join("");
  const setMass = () => {
    const opt = $("#labMaterial").selectedOptions[0];
    $("#labMass").value = +(opt.dataset.mass * 1000).toPrecision(4);
  };
  $("#labMaterial").addEventListener("change", setMass);
  setMass();
  $("#labPrepare").addEventListener("click", () => cmd("lab_prepare", {
    material: $("#labMaterial").value, mass_g: +$("#labMass").value / 1000, cadmium: $("#labCadmium").checked,
  }));
  $("#labShelf").innerHTML = lab.shelves_cm.map((c) => `<option value="${c}" ${c === 10 ? "selected" : ""}>${c} cm</option>`).join("");
  $("#labStart").addEventListener("click", () => {
    const sid = $("#labCountSample").value;
    if (!sid) return;
    cmd("lab_count", { sample: +sid, live_s: +$("#labLive").value, shelf_cm: +$("#labShelf").value });
  });
  $("#labStop").addEventListener("click", () => cmd("lab_stop"));
  $("#labSamples").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-act]");
    if (!b) return;
    const sid = +b.closest("tr").dataset.id;
    const act = b.dataset.act;
    if (act === "load") cmd("lab_insert", { sample: sid, position: $("select", b.closest("tr")).value });
    else if (act === "remove") cmd("lab_remove", { sample: sid });
    else if (act === "count") { $("#labCountSample").value = sid; $("#labStart").click(); }
    else if (act === "waste") cmd("lab_discard", { sample: sid });
  });
  $("#labGuides").addEventListener("click", (e) => {
    const h = e.target.closest("[data-guide]");
    if (!h) return;
    openGuide = openGuide === h.dataset.guide ? null : h.dataset.guide;
    lastGuideKey = "";
  });
}

// ------------------------------------------------------------------ render

export function renderLab(s, visible) {
  const lab = s.lab;
  if (!lab) return;
  if (!built) build(lab);
  if (!visible) return;
  lab._power_kw = s.true.power_w / 1000;

  // Sample table: rebuild rows when the set of samples changes, update cells every poll.
  const positionsOpts = lab.positions.map((p) => `<option value="${p.key}">${esc(p.label)}</option>`).join("");
  const ids = lab.samples.map((x) => `${x.id}:${x.location}`).join(",");
  if (ids !== lastSampleIds) {
    lastSampleIds = ids;
    const chosen = Object.fromEntries($$("#labSamples tr[data-id]").map((tr) => [tr.dataset.id, $("select", tr)?.value]));
    $("#labSamples").innerHTML = lab.samples.length ? lab.samples.map((x) => {
      const inCore = lab.positions.some((p) => p.key === x.location);
      const actions = inCore ? `<button data-act="remove">Remove</button>`
        : x.location === "detector" ? `<span class="hint">on detector</span>`
          : `<select aria-label="Position">${positionsOpts}</select><button data-act="load">Load</button>
             <button data-act="count">Count</button><button data-act="waste" title="Send to radioactive waste">Waste</button>`;
      return `<tr data-id="${x.id}"><td>${x.id}</td><td>${esc(x.name)}${x.cadmium ? " <b>(Cd)</b>" : ""}</td>
        <td>${fmtMass(x.mass_g)}</td><td data-c="loc"></td><td data-c="time"></td><td data-c="dose" class="num"></td>
        <td data-c="true" class="truth num"></td><td class="acts">${actions}</td></tr>`;
    }).join("") : `<tr><td colspan="8" class="hint">No samples yet. Pick a material and press Prepare.</td></tr>`;
    // Keep each sample's chosen position, defaulting to the centre.
    $$("#labSamples tr[data-id] select").forEach((sel) => { sel.value = chosen[sel.closest("tr").dataset.id] || "core_center"; });
    const bench = lab.samples.filter((x) => x.location === "bench" || x.location === "detector");
    const cur = $("#labCountSample").value;
    $("#labCountSample").innerHTML = bench.map((x) => `<option value="${x.id}">${x.id}: ${esc(x.name)}</option>`).join("");
    if (bench.some((x) => String(x.id) === cur)) $("#labCountSample").value = cur;
  }
  for (const x of lab.samples) {
    const tr = $(`#labSamples tr[data-id="${x.id}"]`);
    if (!tr) continue;
    $("[data-c=loc]", tr).textContent = x.location_label;
    $("[data-c=time]", tr).textContent = x.in_core_s !== null ? `in ${fmtDur(x.in_core_s)}`
      : x.since_eoi_s !== null ? `out ${fmtDur(x.since_eoi_s)}` : "not irradiated";
    const dose = $("[data-c=dose]", tr);
    dose.textContent = lab.positions.some((p) => p.key === x.location) ? "in core" : `${fmt(x.dose_mr_h_30cm)} mR/h`;
    dose.classList.toggle("hot", x.dose_mr_h_30cm > 5);
    $("[data-c=true]", tr).textContent = x.true ? fmtBq(x.true.activity_bq) : "";
  }

  // Irradiation positions
  const posKey = lab.positions.map((p) => p.samples.join("+")).join("|");
  if (posKey !== lastPositions) {
    lastPositions = posKey;
    $("#labPositions").innerHTML = lab.positions.map((p) => `
      <div class="lab-pos" data-pos="${p.key}">
        <div class="lab-pos-name">${esc(p.label)}</div>
        <div class="lab-pos-slots">${Array.from({ length: p.capacity }, (_, i) => {
          const sid = p.samples[i];
          return `<span class="slot ${sid ? "full" : ""}">${sid ?? ""}</span>`;
        }).join("")}</div>
        <div class="truth lab-pos-flux" data-flux></div>
      </div>`).join("");
  }
  for (const p of lab.positions) {
    const el = $(`.lab-pos[data-pos="${p.key}"] [data-flux]`);
    if (el) el.textContent = `φth ${fmt(p.true_thermal_flux)} · φfast ${fmt(p.true_fast_flux)} n/cm²s`;
  }
  const worth = lab.samples.reduce((t, x) => t + (x.worth_dollars || 0), 0);
  $("#labWorth").textContent = `${worth >= 0 ? "+" : "−"}${Math.abs(worth * 100).toFixed(2)} ¢`;
  $("#labPower").textContent = s.channels.ch3_power_w >= 1000 ? `${fmt(s.channels.ch3_power_w / 1000)} kW` : `${fmt(s.channels.ch3_power_w)} W`;

  // Detector
  const d = lab.detector;
  const running = d && !d.done;
  $("#labStart").disabled = !!running || !$("#labCountSample").value;
  $("#labStop").disabled = !running;
  $("#labLiveRead").textContent = d ? `${d.live_s.toFixed(0)} / ${d.preset_live_s.toFixed(0)} s` : "-";
  $("#labRealRead").textContent = d ? `${d.real_s.toFixed(0)} s` : "-";
  const dt = d ? d.dead_time * 100 : 0;
  $("#labDeadRead").textContent = d ? `${dt.toFixed(1)} %` : "-";
  $("#labDeadRead").classList.toggle("hot", dt > 10);
  $("#labDeadRead").classList.toggle("alarm", dt > 40);
  $("#labRateRead").textContent = d ? `${fmt(d.input_cps)} cps` : "-";
  $("#labDetSample").textContent = d ? `Sample ${d.sample_id}${running ? " (counting)" : " (done)"}` : "No count yet";
  const analysis = d ? lab.results.analyses[d.sample_id] : null;
  drawSpectrum(d, d && d.done ? analysis : null);

  const akey = d ? `${d.sample_id}:${analysis?.count}:${d.done}` : "";
  if (akey !== lastAnalysisKey) {
    lastAnalysisKey = akey;
    $("#labPeaks").innerHTML = analysis && d.done ? (analysis.peaks.length ? `<table class="lab-table">
      <tr><th>Energy</th><th>Nuclide</th><th>Net counts</th><th>±</th><th>Activity at count</th><th>At end of irradiation</th></tr>
      ${analysis.peaks.map((p) => `<tr><td>${p.energy_kev.toFixed(1)} keV</td><td>${p.nuclide} <span class="hint">(${p.element}, ${fmtDur(p.half_life_s)})</span></td>
        <td class="num">${fmt(p.net, 4)}</td><td class="num">${(100 * p.sigma / p.net).toFixed(1)}%</td>
        <td class="num">${fmtBq(p.activity_start_bq)}</td><td class="num">${p.activity_eoi_bq === null ? "-" : fmtBq(p.activity_eoi_bq)}</td></tr>`).join("")}
      </table>` : `<p class="hint">No peaks above the detection limit.</p>`) : `<p class="hint">Peak analysis appears when a count finishes.</p>`;
  }

  // Guides
  const gkey = JSON.stringify([openGuide, lab.samples.map((x) => [x.id, x.location, x.counts, Math.floor(x.irradiation_s / 60)]),
    lab.results, document.body.classList.contains("truth")]);
  if (gkey !== lastGuideKey) {
    lastGuideKey = gkey;
    $("#labGuides").innerHTML = GUIDES.map((g) => {
      const done = g.steps.map(([, check]) => !!check(lab));
      const all = done.every(Boolean);
      const open = openGuide === g.key;
      return `<div class="guide ${open ? "open" : ""}">
        <button class="guide-head" data-guide="${g.key}" aria-expanded="${open}">
          <span>${g.title}</span><span class="guide-prog ${all ? "ok" : ""}">${done.filter(Boolean).length}/${done.length}</span></button>
        ${open ? `<div class="guide-body"><p>${g.intro}</p>
          <ol class="steps">${g.steps.map(([t], i) => `<li class="${done[i] ? "done" : ""}">${t}</li>`).join("")}</ol>
          <div class="guide-result">${g.result(lab)}</div></div>` : ""}
      </div>`;
    }).join("");
  }
}

// ------------------------------------------------------------------ spectrum display

function drawSpectrum(d, analysis) {
  const cv = $("#labSpectrum");
  const r = cv.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  if (cv.width !== Math.round(r.width * dpr) || cv.height !== Math.round(r.height * dpr)) {
    cv.width = Math.round(r.width * dpr);
    cv.height = Math.round(r.height * dpr);
  }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = r.width, H = r.height;
  g.fillStyle = "#ffffff";
  g.fillRect(0, 0, W, H);
  const L = 46, R = 8, T = 8, B = 22;
  const pw = W - L - R, ph = H - T - B;
  const spec = d?.spectrum;
  const emax = 3000;
  const kpb = d?.kev_per_bin || 3;
  const peakMax = spec ? Math.max(10, ...spec) : 10;
  const top = Math.ceil(Math.log10(peakMax));
  const x = (e) => L + (e / emax) * pw;
  const y = (c) => T + ph * (1 - Math.log10(Math.max(c, 0.5) / 0.5) / (top - Math.log10(0.5)));
  g.font = "10px Tahoma, Verdana, sans-serif";
  g.strokeStyle = "#d8d8d8"; g.fillStyle = "#404040"; g.lineWidth = 1;
  for (let e = 0; e <= top; e++) {
    const yy = Math.round(y(10 ** e)) + 0.5;
    g.beginPath(); g.moveTo(L, yy); g.lineTo(L + pw, yy); g.stroke();
    g.textAlign = "right"; g.fillText(e === 0 ? "1" : `1e${e}`, L - 4, yy + 3);
  }
  g.textAlign = "center";
  for (let e = 0; e <= emax; e += 500) {
    const xx = Math.round(x(e)) + 0.5;
    g.beginPath(); g.moveTo(xx, T); g.lineTo(xx, T + ph); g.stroke();
    g.fillText(`${e}`, xx, H - 8);
  }
  g.textAlign = "left";
  g.fillText("keV", L + 4, T + 10);
  if (!spec) {
    g.fillStyle = "#808080"; g.textAlign = "center";
    g.fillText("No spectrum", L + pw / 2, T + ph / 2);
    g.textAlign = "left";
    return;
  }
  g.strokeStyle = "#0030c0"; g.lineWidth = 1;
  g.beginPath();
  spec.forEach((c, i) => {
    const e = (i + 0.5) * kpb;
    if (e > emax) return;
    const xx = x(e), yy = y(c);
    i ? g.lineTo(xx, yy) : g.moveTo(xx, yy);
  });
  g.stroke();
  if (analysis) {
    g.fillStyle = "#c00000"; g.strokeStyle = "rgba(192,0,0,.5)";
    const used = [];
    for (const p of analysis.peaks) {
      const xx = x(p.energy_kev);
      const c = spec[Math.floor(p.energy_kev / kpb)] || 1;
      const yy = Math.max(T + 10, y(c) - 6);
      g.beginPath(); g.moveTo(xx, yy); g.lineTo(xx, yy - 8); g.stroke();
      const label = `${p.nuclide} ${p.energy_kev.toFixed(0)}`;
      let ly = yy - 11;
      while (used.some(([ux, uy]) => Math.abs(ux - xx) < 70 && Math.abs(uy - ly) < 11)) ly -= 11;
      used.push([xx, ly]);
      g.fillText(label, Math.min(xx + 2, L + pw - 70), Math.max(ly, T + 8));
    }
  }
}
