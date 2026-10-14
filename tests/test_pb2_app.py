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
