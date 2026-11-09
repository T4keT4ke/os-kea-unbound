import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "kaddr", ROOT / "src/opnsense/scripts/keaunbound/addresses.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_reservation_rows_global_and_subnet():
    m = load()
    cfg = {"Dhcp4": {"reservations": [{"ip-address": "10.0.0.2", "hostname": "g"}],
                     "subnet4": [{"id": 3, "reservations": [
                         {"ip-address": "10.0.0.9", "hostname": "p", "hw-address": "aa:bb"}]}]}}
    assert m.reservation_rows(cfg, "4") == [("10.0.0.2", "g", "", ""),
                                            ("10.0.0.9", "p", "aa:bb", "3")]
    assert m.reservation_rows(None, "4") == []


def test_build_rows_merges_static_and_dynamic():
    m = load()
    resv = [("10.0.0.9", "printer", "aa:bb", "3"), ("10.0.0.2", "offline", "cc:dd", "3")]
    leases = [("10.0.0.9", "printer-lease", "aa:bb", "3", 500),
              ("10.0.0.50", "laptop", "ee:ff", "3", 900)]
    rows = {r["address"]: r for r in m.build_rows(resv, leases)}
    assert rows["10.0.0.9"]["type"] == "static" and rows["10.0.0.9"]["status"] == "active"
    assert rows["10.0.0.9"]["hostname"] == "printer" and rows["10.0.0.9"]["expires"] == 500
    assert rows["10.0.0.2"]["status"] == "reserved"          # offline reservation still listed
    assert rows["10.0.0.50"]["type"] == "dynamic"
    assert [r["address"] for r in m.build_rows(resv, leases)] == ["10.0.0.2", "10.0.0.9", "10.0.0.50"]
