import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "kdel", ROOT / "src/opnsense/scripts/keaunbound/lease-delete.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_parse_ips():
    m = load()
    assert m.parse_ips("10.0.0.5, 2001:db8::7") == ["10.0.0.5", "2001:db8::7"]
    assert m.parse_ips("10.0.0.5;rm") is None and m.parse_ips("") is None
    assert m.parse_ips("10.0.0.5,bad") is None


def test_delete_leases_asks_kea_to_update_ddns():
    m = load()
    calls = []

    def send(cmd, svc, args):
        calls.append((cmd, svc, args))
        if cmd == "lease6-get-all":
            return {"result": 0, "arguments": {"leases": [
                {"ip-address": "2001:db8::7", "type": "IA_NA"}]}}
        return {"result": 3, "text": "not found"} if args["ip-address"] == "10.0.0.9" \
            else {"result": 0, "text": "ok"}

    out = m.delete_leases(["10.0.0.5", "10.0.0.9", "2001:db8::7"], send)
    assert out == {"removed": ["10.0.0.5", "2001:db8::7"], "failed": ["10.0.0.9: not found"]}
    assert ("lease4-del", "dhcp4", {"ip-address": "10.0.0.5", "update-ddns": True}) in calls
    assert ("lease6-del", "dhcp6", {"ip-address": "2001:db8::7", "update-ddns": True,
                                    "type": "IA_NA"}) in calls
