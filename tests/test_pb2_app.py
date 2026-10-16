"""The Peach Bottom 2 control-room session: panel readings, switches and annunciators."""

import json

import pytest

from reactorsim.app.bwr_session import BWRSession, INITIAL_STATES
from reactorsim.app.session import CommandError


def test_state_is_strict_json_with_panel_readings():
    s = BWRSession("full_power", seed=1)
    s.advance(2.0)
    st = s.state()
    json.dumps(st, allow_nan=False)
    r = st["readings"]
    assert r["aprm"] == pytest.approx(100.0, abs=0.5)
    assert r["pressure"] == pytest.approx(1020.0, abs=2.0)
    assert r["level"] == pytest.approx(35.0, abs=0.5)
    assert r["core_flow"] == pytest.approx(102.5, rel=0.01)   # Mlb/h
    assert r["steam_flow"] == pytest.approx(13.3, rel=0.03)   # Mlb/h
    assert 1000 < r["gen_mw"] < 1100
    assert st["lamps"]["recirc_a_run"] and st["lamps"]["msiv_open"] and not st["lamps"]["srv_1"]
    assert all(r[f"srv_{i}_sw"] == 1 for i in range(1, 12))  # every SRV switch in AUTO
    assert st["annunciators"] == {}


def test_scram_buttons_light_the_windows_until_acknowledged_and_reset():
    s = BWRSession("full_power", seed=1)
    s.command("scram")
    s.advance(5.0)
    st = s.state()
    assert st["scrammed"] and st["annunciators"]["scram"] == "flash"
    assert st["lamps"]["scram"] and not st["lamps"]["rod_out_permit"]
    assert st["readings"]["aprm"] < 5.0 and st["readings"]["time_since_scram"] > 4.0
    s.command("ann_ack")
    assert s.state()["annunciators"]["scram"] == "on"
    with pytest.raises(CommandError):
        s.command("rod_drive", direction="out")  # rod block while scrammed
    s.command("ann_reset")
    assert s.state()["annunciators"]["scram"] == "on"  # the condition still holds


def test_rod_pushbuttons_move_the_bank_and_the_core_display_follows():
    s = BWRSession("full_power", seed=1)
    n0 = s.state()["readings"]["rod_notch"]
    s.command("rod_drive", direction="in")
    s.advance(2.0)
    s.command("rod_drive", direction="stop")
    s.advance(3.0)
    st = s.state()
    assert st["readings"]["rod_notch"] < n0 - 0.5
    assert st["readings"]["aprm"] < 97.0
    s.command("rod_select", rod="30-31")
    assert s.state()["readings"]["rod_selected"] == "30-31"


def test_srv_switch_cycles_close_auto_open():
    s = BWRSession("full_power", seed=1)
    s.command("srv", valve=3)
    s.advance(1.0)
    st = s.state()
    assert st["readings"]["srv_3_sw"] == 2 and st["lamps"]["srv_3"] and st["annunciators"]["srv_open"] == "flash"
    s.command("srv", valve=3)
    s.advance(1.0)
    assert s.state()["readings"]["srv_3_sw"] == 0 and not s.state()["lamps"]["srv_3"]
    s.command("srv", valve=3)
    assert s.state()["readings"]["srv_3_sw"] == 1


def test_turbine_trip_switch_and_loss_of_feedwater_reach_the_boards():
    s = BWRSession("full_power", seed=1)
    s.command("turbine_trip")
    s.advance(20.0)
    st = s.state()
    assert st["scrammed"] and st["lamps"]["turbine_tripped"] and st["lamps"]["tsv_closed"]
    assert st["readings"]["turbine_speed"] < 1800 and st["readings"]["gen_mw"] == 0.0
    assert st["annunciators"]["turbine_trip"] == "flash"
    s = BWRSession("full_power", seed=2)
    s.command("feed_pump")
    s.advance(60.0)
    st = s.state()
    assert st["lamps"]["feed_stopped"] and st["annunciators"]["level_low_l3"] == "flash"
    assert st["readings"]["level"] < 1.0


def test_every_initial_state_starts_steady():
    for key in INITIAL_STATES:
        s = BWRSession(key, seed=3)
        s.advance(30.0)
        st = s.state()
        assert not st["scrammed"] and st["annunciators"] == {}, key


# --------------------------------------------------------------------------- auxiliary benchboards

def test_feedwater_heater_string_out_cools_the_feed_and_raises_power():
    s = BWRSession("full_power", seed=1)
    s.command("aux", equip="heater", unit="a")
    s.advance(600.0)
    st = s.state()
    r = st["readings"]
    assert r["feed_temp"] < 350.0 and r["fw_string_a"] < 150.0
    assert r["aprm"] > 103.0   # colder feed, more subcooling, more power
    assert st["annunciators"]["fw_heater_out"] == "flash" and st["lamps"]["heater_a_stopped"]


def test_losing_circulating_water_trips_the_turbine_then_isolates_the_condenser():
    s = BWRSession("full_power", seed=1)
    for u in "abc":
        s.command("aux", equip="circ_pump", unit=u)
    s.advance(90.0)
    st = s.state()
    assert st["lamps"]["turbine_tripped"] and st["scrammed"]
    assert st["readings"]["vacuum"] < 22.5 and st["annunciators"]["vacuum_low"] == "flash"
    s.advance(240.0)
    st = s.state()
    assert st["readings"]["vacuum"] < 7.0 and not st["lamps"]["condenser_avail"] and st["lamps"]["msiv_closed"]


def test_standby_air_compressor_starts_and_losing_all_air_scrams_the_reactor():
    s = BWRSession("full_power", seed=1)
    s.command("aux", equip="air_comp", unit="a")
    s.command("aux", equip="air_comp", unit="b")
    s.advance(90.0)
    st = s.state()
    assert st["lamps"]["air_comp_c_run"] and not st["scrammed"]     # standby auto-start on low pressure
    s.command("aux", equip="air_comp", unit="c")                     # stopped by hand: stays off
    s.advance(120.0)
    assert not s.state()["scrammed"] and s.state()["annunciators"]["air_low"] == "flash"
    s.advance(80.0)
    st = s.state()
    assert st["scrammed"] and "instrument air" in st["scram_causes"][0]


def test_diesels_restore_low_pressure_ecc_and_torus_cooling_after_a_blackout():
    s = BWRSession("full_power", seed=1)
    s.command("station_blackout")
    s.advance(20.0)
    st = s.state()
    assert st["lamps"]["station_blackout"] and st["lamps"]["lpci_unavail"] and st["readings"]["e_bus_1"] == 0.0
    with pytest.raises(CommandError):
        s.command("aux", equip="hpsw_pump", unit="a")   # no power on its bus
    with pytest.raises(CommandError):
        s.command("aux", equip="cond_pump", unit="a")   # non-safety bus: needs offsite power
    s.command("aux", equip="diesel", unit="1")
    s.advance(15.0)
    st = s.state()
    assert st["lamps"]["diesel_1_run"] and st["readings"]["e_bus_1"] == pytest.approx(4.16)
    assert not st["lamps"]["lpci_unavail"] and not st["lamps"]["station_blackout"]
    s.command("aux", equip="hpsw_pump", unit="a")
    s.command("aux", equip="torus_cool", unit="a")
    s.advance(5.0)
    assert s.state()["readings"]["rhr_hx"] > 0 and s.state()["lamps"]["torus_cooling"]


def test_torus_cooling_takes_heat_out_of_the_torus():
    s = BWRSession("full_power", seed=1)
    s.sim.torus_temp = 60.0
    s.command("aux", equip="hpsw_pump", unit="a")
    s.command("aux", equip="torus_cool", unit="a")
    s.advance(600.0)
    assert s.sim.torus_temp < 59.0


def test_crd_condensate_and_cleanup_interlocks():
    s = BWRSession("full_power", seed=1)
    s.command("aux", equip="crd_pump", unit="a")
    with pytest.raises(CommandError):
        s.command("rod_drive", direction="in")          # no drive water
    s.advance(120.0)
    assert s.state()["annunciators"]["crd_accum"] == "flash"
    s = BWRSession("full_power", seed=1)
    for u in "abc":
        s.command("aux", equip="cond_pump", unit=u)
    s.advance(5.0)
    assert s.state()["lamps"]["feed_stopped"]
    with pytest.raises(CommandError):
        s.command("feed_pump")                           # no suction
    s = BWRSession("full_power", seed=1)
    s.command("slc")
    s.advance(2.0)
    st = s.state()
    assert st["lamps"]["rwcu_isolated"] and st["readings"]["rwcu_flow"] == 0.0
    with pytest.raises(CommandError):
        s.command("aux", equip="rwcu_pump", unit="a")   # SLC still injecting


def test_one_feed_pump_trip_runs_the_recirculation_back_without_a_scram():
    s = BWRSession("full_power", seed=1)
    s.command("feed_pump", pump="a")
    s.advance(120.0)
    st = s.state()
    assert st["lamps"]["feed_a_stopped"] and st["lamps"]["feed_b_run"] and st["lamps"]["runback"]
    assert not st["scrammed"] and 50.0 < st["readings"]["aprm"] < 80.0
    assert st["readings"]["recirc_demand"] == pytest.approx(45.0, abs=0.5)
    assert st["readings"]["level"] == pytest.approx(35.0, abs=3.0)
    s.command("feed_pump", pump="a")
    s.advance(2.0)
    assert not s.state()["lamps"]["runback"]


def test_loss_of_offsite_power_starts_the_diesels_and_restores_the_ecc():
    s = BWRSession("full_power", seed=1)
    s.command("loss_of_offsite_power")
    s.advance(3.0)
    st = s.state()
    assert st["scrammed"]
    assert st["lamps"]["lpci_unavail"] and st["annunciators"]["loop"] == "flash"
    s.advance(15.0)
    st = s.state()
    assert all(st["lamps"][f"diesel_{i}_run"] for i in range(1, 5))
    assert not st["lamps"]["lpci_unavail"] and st["lamps"]["crd_pump_a_run"]   # load sequencer
    s.command("loss_of_offsite_power")                                          # restore
    s.advance(2.0)
    assert s.state()["lamps"]["offsite_power"] and s.state()["lamps"]["cond_pump_a_run"]


def test_diesels_start_on_a_loca_signal_and_run_unloaded():
    s = BWRSession("full_power", seed=1)
    s.command("ads_manual")
    s.advance(15.0)
    r = s.state()["readings"]
    assert all(s.state()["lamps"][f"diesel_{i}_run"] for i in range(1, 5))
    assert r["diesel_kw_1"] == 0.0 and r["bus_4kv"] == pytest.approx(4.16)


def test_mode_switch_turns_one_detent_at_a_time_and_shutdown_scrams():
    s = BWRSession("full_power", seed=1)
    s.command("mode_switch")
    assert s.state()["readings"]["mode"] == 2 and not s.state()["scrammed"]   # STARTUP
    s.command("mode_switch")
    assert s.state()["readings"]["mode"] == 1                                  # REFUEL
    s.command("mode_switch")
    st = s.state()
    assert st["readings"]["mode"] == 0 and st["scrammed"] and "SHUTDOWN" in st["scram_causes"][0]
    s.command("mode_switch")
    assert s.state()["readings"]["mode"] == 1                                  # back toward RUN
