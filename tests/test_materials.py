"""Materials lab: activation, gamma counting, analysis, and the workstation commands."""

import json

import numpy as np
import pytest

from reactorsim.app.session import CommandError, SimSession
from reactorsim.experiments import EXPERIMENTS
from reactorsim.materials import POSITIONS, REACTIONS, MaterialsLab


def _lab(seed=1):
    return MaterialsLab(flux_per_watt=2.2e7, beta=0.0075, rng=np.random.default_rng(seed), unknown_seed=seed)


def _run(lab, seconds, power_w, t0=0.0, step=1.0):
    t = t0
    while t < t0 + seconds - 1e-9:
        lab.advance(step, power_w, t)
        t += step
    return t


def test_activation_builds_up_and_decays_exactly():
    lab = _lab()
    s = lab.prepare("gold_foil")
    lab.insert(s.id, "core_center", 0.0)
    t = _run(lab, 600, 1000.0, step=10.0)
    lab.remove(s.id, t)
    a0 = s.activities()["Au-198"]
    r = REACTIONS["Au-198"][1]
    th, epi, _ = lab.flux("core_center", 1000.0)
    rate = s.target_atoms("Au", r) * 1e-24 * (th * r.sigma_b + epi * r.ri_b)
    assert a0 == pytest.approx(rate * (1 - np.exp(-r.lam * 600)), rel=0.1)
    _run(lab, 86400, 0.0, t0=t, step=3600.0)
    assert s.activities()["Au-198"] == pytest.approx(a0 * np.exp(-r.lam * 86400), rel=1e-3)


def test_samples_add_negative_reactivity_and_positions_fill():
    lab = _lab()
    ids = [lab.prepare("aluminium").id for _ in range(POSITIONS["core_center"].capacity + 1)]
    for i in ids[:-1]:
        assert lab.insert(i, "core_center", 0.0) <= 0
    with pytest.raises(ValueError):
        lab.insert(ids[-1], "core_center", 0.0)
    cd = lab.prepare("gold_foil", cadmium=True)
    assert lab.insert(cd.id, "core_edge", 0.0) < 0


def test_count_finds_gold_and_dead_time_is_reported():
    lab = _lab()
    s = lab.prepare("gold_foil")
    lab.insert(s.id, "core_center", 0.0)
    t = _run(lab, 900, 1000.0, step=10.0)
    lab.remove(s.id, t)
    lab.start_count(s.id, 120.0, 25.0, t)
    t = _run(lab, 400, 0.0, t0=t)
    res = s.counts[-1]
    assert {p["nuclide"] for p in res["peaks"]} == {"Au-198"}
    assert 0 <= res["dead_time"] < 0.5
    assert res["live_s"] == pytest.approx(120.0)


@pytest.mark.parametrize("name", ["foil_activation", "half_life", "silicon_doping"])
def test_materials_experiments_match_truth(name):
    _, res = EXPERIMENTS[name].run(seed=1)
    err = res["error"]
    key = next(iter(err))
    assert abs(err[key]) < 3.0, res


@pytest.mark.slow
@pytest.mark.parametrize("name", ["activation_analysis", "radiation_damage"])
def test_slow_materials_experiments(name):
    _, res = EXPERIMENTS[name].run(seed=1)
    if name == "activation_analysis":
        assert {"Al", "Na", "K", "Cl", "Mn"} <= set(res["measured"]["elements_found"])
        assert res["measured"]["worst_error_percent"] < 10
    else:
        assert abs(res["error"]["fast_flux_percent"]) < 5


def test_lab_commands_through_the_session():
    s = SimSession("power_10kw", seed=1)
    sid = s.command("lab_prepare", material="gold_foil")["sample"]
    s.command("lab_insert", sample=sid, position="core_center")
    s.advance(120.0)
    st = s.state(lab_spectrum=True)
    json.dumps(st)  # strict JSON for the page
    smp = next(x for x in st["lab"]["samples"] if x["id"] == sid)
    assert smp["location"] == "core_center" and smp["worth_dollars"] < 0
    with pytest.raises(CommandError):
        s.command("lab_count", sample=sid, live_s=60, shelf_cm=25)  # still in the core
    s.command("lab_remove", sample=sid)
    s.command("lab_count", sample=sid, live_s=30, shelf_cm=25)
    s.advance(60.0)
    st = s.state(lab_spectrum=True)
    assert st["lab"]["detector"]["done"] and len(st["lab"]["detector"]["spectrum"]) == 1024
    with pytest.raises(CommandError):
        s.command("lab_prepare", material="kryptonite")
    s.command("lab_discard", sample=sid)
    assert all(x["id"] != sid for x in s.state()["lab"]["samples"])


def test_every_experiment_is_registered_with_an_objective():
    for key in ["foil_activation", "activation_analysis", "half_life", "silicon_doping", "radiation_damage"]:
        assert EXPERIMENTS[key].objective
