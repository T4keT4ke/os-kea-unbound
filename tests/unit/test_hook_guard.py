import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "src/opnsense/scripts/keaunbound/hook-guard.py"

from test_config_sync import GSS as _GSS, load_injector  # noqa: E402

GSS = dict(_GSS, reverse_zones_text="10.in-addr.arpa = 10.0.0.1, 10.0.0.2 gss",
           gss_servers_text="10.0.0.1 = dc01.ad.example.com")


def load_guard():
    spec = importlib.util.spec_from_file_location("hg", GUARD)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def setup(tmp_path, check, settings=GSS, hook_in_config=True):
    m = load_injector(tmp_path)
    hook = tmp_path / "libddns_gss_tsig.so"
    hook.write_text("x")
    m.HOOK = str(hook)
    m.D2 = str(tmp_path / "d2.json")
    m.KEA4 = str(tmp_path / "k4.json")
    m.KEA6 = str(tmp_path / "k6.json")
    m.KRB5_CONF = str(tmp_path / "krb5.conf")
    m._d2_check = lambda cfg: check["ok"]
    m.load_settings = lambda: dict(settings) if settings else None
    m._collect_suffixes = lambda sfx: [sfx]
    # the injector has already put the hook into the config (state before the update)
    saved = m._d2_check
    m._d2_check = lambda cfg: True
    json.dump({"DhcpDdns": {}}, open(m.D2, "w"))
    json.dump({"Dhcp4": {}}, open(m.KEA4, "w"))
    json.dump({"Dhcp6": {}}, open(m.KEA6, "w"))
    if hook_in_config:
        m.run()
    m._d2_check = saved
    return m


def libs(m):
    return [h["library"] for h in json.load(open(m.D2))["DhcpDdns"].get("hooks-libraries", [])]


def test_incompatible_hook_is_dropped_and_kea_restarted(tmp_path):
    check = {"ok": True}
    m = setup(tmp_path, check)
    assert libs(m) == [m.HOOK]
    check["ok"] = False                       # Kea updated, hook no longer loads
    calls = []
    out = load_guard().guard(m, restart=lambda: calls.append(1))
    assert libs(m) == []
    assert calls == [1] and "restarting Kea" in out
    assert "rejected" in open(m.LOG).read()


def test_compatible_hook_left_alone(tmp_path):
    check = {"ok": True}
    m = setup(tmp_path, check)
    calls = []
    out = load_guard().guard(m, restart=lambda: calls.append(1))
    assert libs(m) == [m.HOOK] and calls == [] and out == "ok, no change"


def test_hook_comes_back_when_it_loads_again(tmp_path):
    check = {"ok": False}
    m = setup(tmp_path, check, hook_in_config=False)
    g = load_guard()
    g.guard(m, restart=lambda: None)
    assert libs(m) == []
    check["ok"] = True                        # matching package installed
    calls = []
    g.guard(m, restart=lambda: calls.append(1))
    assert libs(m) == [m.HOOK] and calls == [1]


def test_disabled_plugin_does_nothing(tmp_path):
    m = setup(tmp_path, {"ok": False}, settings=None)
    calls = []
    out = load_guard().guard(m, restart=lambda: calls.append(1))
    assert calls == [] and "disabled" in out


def test_restart_failure_is_reported_not_raised(tmp_path):
    check = {"ok": True}
    m = setup(tmp_path, check)
    check["ok"] = False

    def boom():
        raise OSError("no configctl")
    out = load_guard().guard(m, restart=boom)
    assert "restart failed" in out
