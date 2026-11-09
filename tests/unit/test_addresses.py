import importlib.util
import ipaddress
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "kaddr", ROOT / "src/opnsense/scripts/keaunbound/addresses.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_reservations_global_and_subnet():
    m = load()
    cfg = {"Dhcp4": {"reservations": [{"ip-address": "10.0.0.2", "hostname": "g"}],
                     "subnet4": [{"id": 3, "reservations": [
                         {"ip-address": "10.0.0.9", "hostname": "p", "hw-address": "aa:bb",
                          "client-id": "01:aa"}]}]}}
    r = m.reservations(cfg, "4")
    assert [(x["ip"], x["hostname"], x["subnet"]) for x in r] == [
        ("10.0.0.2", "g", ""), ("10.0.0.9", "p", "3")]
    assert r[1]["client_id"] == "01aa"            # colons stripped, like core
    assert m.reservations(None, "4") == []


def test_build_records_merges_static_dynamic_and_offline():
    m = load()
    ranges = {ipaddress.ip_network("10.0.0.0/24"): "vlan10"}
    resvs = [{"ip": "10.0.0.9", "hostname": "printer", "hwaddr": "aa:bb", "client_id": "",
              "duid": "", "subnet": "3"},
             {"ip": "10.0.0.2", "hostname": "offline", "hwaddr": "cc:dd", "client_id": "01cc",
              "duid": "", "subnet": "3"}]
    leases = [{"ip-address": "10.0.0.9", "hw-address": "aa:bb", "hostname": "printer",
               "state": 0, "cltt": 100, "valid-lft": 400, "subnet-id": 3},
              {"ip-address": "10.0.0.50", "hw-address": "ee:ff", "hostname": "laptop",
               "state": 0, "cltt": 200, "valid-lft": 700}]
    rows = {r["address"]: r for r in m.build_records("4", resvs, leases, ranges)}
    assert rows["10.0.0.9"]["is_reserved"] == ["hwaddr"] and rows["10.0.0.9"]["state"] == 0
    assert rows["10.0.0.9"]["expire"] == 500 and rows["10.0.0.9"]["if"] == "vlan10"
    assert rows["10.0.0.2"]["state"] == m.NO_LEASE      # offline reservation still listed
    assert rows["10.0.0.2"]["is_reserved"] == ["hwaddr", "client_id"]
    assert rows["10.0.0.50"]["is_reserved"] == [] and rows["10.0.0.50"]["if"] == "vlan10"
    assert len(rows) == 3
