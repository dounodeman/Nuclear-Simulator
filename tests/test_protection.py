from reactorsim.simulator import Simulator


def test_short_period_scrams():
    sim = Simulator()
    sim.initialize_at_power(100.0)
    sim.insert_reactivity(0.0025)  # about a 5 s period
    sim.run(30, until=lambda s: s.scrammed)
    assert sim.scrammed
    assert any("period" in c for c in sim.scram_causes)


def test_setback_holds_slow_rise_below_scram():
    sim = Simulator()
    sim.initialize_at_power(10_000.0)
    sim.insert_reactivity(0.0008)  # slow rise toward 110%
    sim.run(120)
    assert any(e.kind == "setback" for e in sim.events)
    assert not sim.scrammed
    assert max(s.power for s in sim.history) < 12_000


def test_safety_channel_high_scrams():
    sim = Simulator()
    sim.initialize_at_power(10_000.0)
    sim.set_channel_fault("ch4", "fail_high")
    sim.run(1)
    assert sim.scrammed
    assert any("Ch4" in c for c in sim.scram_causes)


def test_withdrawal_interlock_below_2_cps():
    sim = Simulator()
    sim.withdraw_source()
    sim.run(60)
    assert sim.instruments.readings.ch1_cps < 2
    sim.drive("SS1", "out")
    sim.run(5)
    assert sim.rods["SS1"].position == 0.0


def test_scram_must_be_reset_and_drives_relatched():
    sim = Simulator()
    sim.initialize_at_power(1_000.0)
    sim.scram()
    sim.run(5)
    sim.drive("SS1", "out")
    sim.run(2)
    assert sim.rods["SS1"].position == 0.0
    assert sim.reset_scram()
    sim.drive("SS1", "in")
    sim.run(400)
    assert sim.rods["SS1"].latched


def test_failed_rps_annunciates_but_does_not_trip():
    sim = Simulator()
    sim.initialize_at_power(100.0)
    sim.protection.enabled = False
    sim.insert_reactivity(0.0025)
    sim.run(5)
    assert not sim.scrammed
    assert any("RPS FAILED" in e.message for e in sim.events)
