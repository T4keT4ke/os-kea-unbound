import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
INJECTOR = ROOT / "src/opnsense/scripts/keaunbound/kea-config-sync.py"

SETTINGS = {
    "port": 53535, "suffix": "home.lan", "tsig": True,
    "tsig_name": "keaunbound", "tsig_secret": "YWJjZA==", "tsig_algo": "HMAC-SHA256",
}


def load_injector(tmp_path):
    spec = importlib.util.spec_from_file_location("kcs", INJECTOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.LOG = str(tmp_path / "keaunbound.log")  # don't write to /var/log in tests
    return m


def test_patch_dhcp_global_and_subnet_override(tmp_path):
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": [
        {"subnet": "10.0.0.0/24", "ddns-send-updates": False},   # Kea default -> strip
        {"subnet": "10.1.0.0/24", "ddns-send-updates": True},    # explicit user -> keep
    ]}}, open(p, "w"))
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is True
    c = json.load(open(p))["Dhcp4"]
    assert c["ddns-send-updates"] is True
    assert c["ddns-qualifying-suffix"] == "home.lan"
    assert c["ddns-replace-client-name"] == "when-not-present"
    subs = c["subnet4"]
    assert "ddns-send-updates" not in subs[0]      # false stripped -> inherits global true
    assert subs[1]["ddns-send-updates"] is True     # explicit true preserved
    # master switch (dhcp-ddns.enable-updates) must be set, pointed at D2's default
    assert c["dhcp-ddns"]["enable-updates"] is True
    assert c["dhcp-ddns"]["server-ip"] == "127.0.0.1"
    assert c["dhcp-ddns"]["server-port"] == 53001
    assert c["ddns-update-on-renew"] is True        # defaults on
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is False  # idempotent


def test_patch_dhcp_strips_subnet_update_on_renew_false(tmp_path):
    # core emits a per-subnet "ddns-update-on-renew": false that overrides our global
    # true; strip it (only when the setting is on), keep an explicit true.
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": [
        {"subnet": "10.0.0.0/24", "ddns-update-on-renew": False},
        {"subnet": "10.1.0.0/24", "ddns-update-on-renew": True},
    ]}}, open(p, "w"))
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is True
    subs = json.load(open(p))["Dhcp4"]["subnet4"]
    assert "ddns-update-on-renew" not in subs[0] and subs[1]["ddns-update-on-renew"] is True
    off = tmp_path / "off.json"
    json.dump({"Dhcp4": {"subnet4": [{"subnet": "10.0.0.0/24", "ddns-update-on-renew": False}]}},
              open(off, "w"))
    m.patch_dhcp(str(off), "Dhcp4", dict(SETTINGS, update_on_renew=False))
    assert json.load(open(off))["Dhcp4"]["subnet4"][0]["ddns-update-on-renew"] is False


def test_patch_dhcp_per_subnet_suffix(tmp_path):
    # issue #17: a subnet with its own domain-name option gets a per-subnet
    # ddns-qualifying-suffix; one matching the global, or with no domain, inherits.
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": [
        {"subnet": "10.0.0.0/24",                                  # own domain -> override
         "option-data": [{"name": "domain-name", "data": "iot.lan"}]},
        {"subnet": "10.1.0.0/24",                                  # == global -> inherit
         "option-data": [{"name": "domain-name", "data": "home.lan"}]},
        {"subnet": "10.2.0.0/24"},                                 # no domain -> inherit
    ]}}, open(p, "w"))
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is True         # SETTINGS suffix=home.lan
    subs = json.load(open(p))["Dhcp4"]["subnet4"]
    assert subs[0]["ddns-qualifying-suffix"] == "iot.lan"          # differs -> set
    assert "ddns-qualifying-suffix" not in subs[1]                 # equals global -> inherit
    assert "ddns-qualifying-suffix" not in subs[2]                 # no domain -> inherit
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is False        # idempotent


def test_patch_dhcp_per_subnet_suffix_in_shared_network(tmp_path):
    # shared-network subnets are covered too.
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": [], "shared-networks": [{"name": "sn", "subnet4": [
        {"subnet": "10.5.0.0/24",
         "option-data": [{"name": "domain-name", "data": "guest.lan"}]}]}]}}, open(p, "w"))
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is True
    sn = json.load(open(p))["Dhcp4"]["shared-networks"][0]["subnet4"][0]
    assert sn["ddns-qualifying-suffix"] == "guest.lan"


def test_patch_d2_multi_suffix(tmp_path):
    # issue #17: one forward zone per distinct suffix in s["suffixes"], all pointed
    # at our listener with our key; "." kept as the harmless fallback.
    m = load_injector(tmp_path)
    p = tmp_path / "d2.json"
    json.dump({"DhcpDdns": {"forward-ddns": {"ddns-domains": []},
                            "reverse-ddns": {"ddns-domains": []}, "tsig-keys": []}}, open(p, "w"))
    s = dict(SETTINGS, suffixes=["home.lan", "iot.lan", "guest.lan"])
    assert m.patch_d2(str(p), s) is True
    fwd = {x["name"]: x for x in json.load(open(p))["DhcpDdns"]["forward-ddns"]["ddns-domains"]}
    for z in ("home.lan.", "iot.lan.", "guest.lan.", "."):
        assert z in fwd
        assert fwd[z]["dns-servers"][0] == {"ip-address": "127.0.0.1", "port": 53535}
        assert fwd[z]["key-name"] == "keaunbound."
    assert m.patch_d2(str(p), s) is False                          # idempotent


def test_collect_suffixes(tmp_path):
    # global first, then per-subnet domains across both families, deduped (ci).
    m = load_injector(tmp_path)
    m.KEA4 = str(tmp_path / "k4.json")
    m.KEA6 = str(tmp_path / "k6.json")
    json.dump({"Dhcp4": {"subnet4": [
        {"option-data": [{"name": "domain-name", "data": "iot.lan"}]},
        {"option-data": [{"name": "domain-name", "data": "Home.LAN"}]},   # dup of global (ci)
    ]}}, open(m.KEA4, "w"))
    json.dump({"Dhcp6": {"subnet6": [
        {"option-data": [{"name": "domain-name", "data": "v6.lan"}]}]}}, open(m.KEA6, "w"))
    out = m._collect_suffixes("home.lan")
    assert out[0] == "home.lan"                       # global first
    assert "iot.lan" in out and "v6.lan" in out
    assert sum(1 for x in out if x.lower() == "home.lan") == 1   # deduped case-insensitively


def test_patch_dhcp_merges_existing_ddns_block(tmp_path):
    # a user's extra dhcp-ddns keys must be preserved, only the connection params
    # we require are forced (non-destructive merge, not a clobber).
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": [], "dhcp-ddns": {
        "enable-updates": False, "max-queue-size": 2048, "sender-ip": "127.0.0.2",
    }}}, open(p, "w"))
    assert m.patch_dhcp(str(p), "Dhcp4", SETTINGS) is True
    block = json.load(open(p))["Dhcp4"]["dhcp-ddns"]
    assert block["enable-updates"] is True            # forced on
    assert block["server-ip"] == "127.0.0.1"          # forced to our D2
    assert block["max-queue-size"] == 2048            # user key preserved
    assert block["sender-ip"] == "127.0.0.2"          # user key preserved


def test_patch_dhcp_update_on_renew_off(tmp_path):
    m = load_injector(tmp_path)
    p = tmp_path / "k4.json"
    json.dump({"Dhcp4": {"subnet4": []}}, open(p, "w"))
    settings = dict(SETTINGS, update_on_renew=False)
    assert m.patch_dhcp(str(p), "Dhcp4", settings) is True
    c = json.load(open(p))["Dhcp4"]
    assert c["ddns-update-on-renew"] is False
    assert c["dhcp-ddns"]["enable-updates"] is True   # master switch unaffected


def test_patch_d2_preserves_user_config(tmp_path):
    m = load_injector(tmp_path)
    p = tmp_path / "d2.json"
    json.dump({"DhcpDdns": {
        "forward-ddns": {"ddns-domains": [
            {"name": "corp.example.com.", "dns-servers": [{"ip-address": "10.0.0.53"}], "key-name": "corpkey."}]},
        "reverse-ddns": {"ddns-domains": []},
        "tsig-keys": [{"name": "corpkey.", "algorithm": "HMAC-SHA256", "secret": "Y29ycA=="}],
    }}, open(p, "w"))
    assert m.patch_d2(str(p), SETTINGS) is True
    d = json.load(open(p))["DhcpDdns"]
    fwd = [x["name"] for x in d["forward-ddns"]["ddns-domains"]]
    assert "corp.example.com." in fwd and "." in fwd          # user preserved + catch-all added
    assert [x["name"] for x in d["reverse-ddns"]["ddns-domains"]] == ["in-addr.arpa.", "ip6.arpa."]
    keys = [x["name"] for x in d["tsig-keys"]]
    assert "corpkey." in keys and "keaunbound." in keys        # user key preserved + ours added
    catchall = next(x for x in d["forward-ddns"]["ddns-domains"] if x["name"] == ".")
    assert catchall["dns-servers"][0] == {"ip-address": "127.0.0.1", "port": 53535}
    assert catchall["key-name"] == "keaunbound."
    assert m.patch_d2(str(p), SETTINGS) is False               # idempotent


def test_patch_d2_reverse_zones(tmp_path):
    # configured reverse zones go straight to the given servers (no TSIG key, longest
    # match beats our in-addr.arpa. catch-all); a user domain with the same name is
    # replaced by ours, other user domains survive.
    m = load_injector(tmp_path)
    p = tmp_path / "d2.json"
    json.dump({"DhcpDdns": {"reverse-ddns": {"ddns-domains": [
        {"name": "124.10.in-addr.arpa.", "dns-servers": [{"ip-address": "1.1.1.1"}]},
        {"name": "5.5.5.in-addr.arpa.", "dns-servers": [{"ip-address": "10.0.0.53"}]}]}}},
        open(p, "w"))
    s = dict(SETTINGS, reverse_zones=[("124.10.in-addr.arpa.", ["10.124.1.14", "10.124.0.8"], False)])
    assert m.patch_d2(str(p), s) is True
    rev = json.load(open(p))["DhcpDdns"]["reverse-ddns"]["ddns-domains"]
    assert [d["name"] for d in rev] == ["5.5.5.in-addr.arpa.", "124.10.in-addr.arpa.",
                                         "in-addr.arpa.", "ip6.arpa."]
    ours = rev[1]
    assert ours["dns-servers"] == [{"ip-address": "10.124.1.14", "port": 53},
                                   {"ip-address": "10.124.0.8", "port": 53}]
    assert "key-name" not in ours
    assert m.patch_d2(str(p), s) is False                      # idempotent


GSS = dict(SETTINGS, gss_enabled=True, gss_rekey="90", gss_lifetime="180", gss_realm="AD.EXAMPLE.COM",
           gss_client_principal="DHCP/fw.ad.example.com@AD.EXAMPLE.COM",
           gss_keytab="/usr/local/etc/kea/dhcp.keytab", gss_replay=False,
           gss_servers={"10.0.0.1": "dc01.ad.example.com"},
           reverse_zones=[("10.in-addr.arpa.", ["10.0.0.1", "10.0.0.2"], True),
                          ("11.in-addr.arpa.", ["10.0.0.3"], False)])


def _gss_d2(tmp_path, m, check=True, hook_present=True):
    hook = tmp_path / "libddns_gss_tsig.so"
    if hook_present:
        hook.write_text("x")
    m.HOOK = str(hook)
    m._d2_check = lambda cfg: check
    p = tmp_path / "d2.json"
    json.dump({"DhcpDdns": {"hooks-libraries": [{"library": "/other.so"}]}}, open(p, "w"))
    return p


def test_patch_d2_gss_hook(tmp_path):
    m = load_injector(tmp_path)
    p = _gss_d2(tmp_path, m)
    assert m.patch_d2(str(p), GSS) is True
    hooks = json.load(open(p))["DhcpDdns"]["hooks-libraries"]
    assert [h["library"] for h in hooks] == ["/other.so", m.HOOK]          # other hook kept
    par = hooks[1]["parameters"]
    assert par["client-principal"] == "DHCP/fw.ad.example.com@AD.EXAMPLE.COM"
    assert par["client-keytab"] == "FILE:/usr/local/etc/kea/dhcp.keytab"
    assert par["gss-replay-flag"] is False
    assert (par["tkey-lifetime"], par["rekey-interval"], par["retry-interval"]) == (180, 90, 30)
    # only servers of `gss` zones that have a name in the GSS server list
    assert par["servers"] == [{"id": "dns-10.0.0.1", "ip-address": "10.0.0.1", "port": 53,
                               "server-principal": "DNS/dc01.ad.example.com@AD.EXAMPLE.COM"}]
    assert m.patch_d2(str(p), GSS) is False                                # idempotent


def test_patch_d2_gss_falls_back_when_hook_unusable(tmp_path):
    # hook file missing, or kea-dhcp-ddns -t rejects it: D2 config stays without our
    # hook (other hooks untouched) instead of risking D2 failing to start.
    for kw in ({"hook_present": False}, {"check": False}):
        m = load_injector(tmp_path)
        p = _gss_d2(tmp_path, m, **kw)
        m.patch_d2(str(p), GSS)
        hooks = json.load(open(p))["DhcpDdns"]["hooks-libraries"]
        assert [h["library"] for h in hooks] == ["/other.so"]
    m = load_injector(tmp_path)
    p = _gss_d2(tmp_path, m)
    m.patch_d2(str(p), dict(GSS, gss_enabled=False))                       # disabled -> none
    assert [h["library"] for h in json.load(open(p))["DhcpDdns"]["hooks-libraries"]] == ["/other.so"]


def test_gss_key_times(tmp_path):
    m = load_injector(tmp_path)
    assert m.gss_key_times({"gss_rekey": "60", "gss_lifetime": "300"}) == (300, 60, 30)
    assert m.gss_key_times({"gss_rekey": "31", "gss_lifetime": "900"}) == (900, 31, 30)
    for bad in ({"gss_rekey": "900", "gss_lifetime": "600"},     # renewal >= lifetime
                {"gss_rekey": "10", "gss_lifetime": "600"},      # below minimum
                {"gss_rekey": "x", "gss_lifetime": "600"}):
        assert m.gss_key_times(bad) == (180, 90, 30)


def test_write_krb5_conf(tmp_path):
    m = load_injector(tmp_path)
    p = tmp_path / "krb5.conf"
    s = dict(GSS, gss_kdc="10.0.0.1, 10.0.0.2", gss_domain="AD.Example.com.")
    assert m.write_krb5_conf(s, str(p)) is True
    t = p.read_text()
    assert "default_realm = AD.EXAMPLE.COM" in t and "kdc = 10.0.0.2" in t
    assert ".ad.example.com = AD.EXAMPLE.COM" in t and "rdns = false" in t
    assert m.write_krb5_conf(s, str(p)) is False                       # unchanged
    assert m.write_krb5_conf(dict(s, gss_kdc="10.0.0.9"), str(p)) is True   # ours -> update
    p.write_text("[libdefaults]\n  default_realm = HAND.MADE\n")        # user's own file
    assert m.write_krb5_conf(s, str(p)) is False
    assert "HAND.MADE" in p.read_text()
    assert m.write_krb5_conf(dict(s, gss_kdc=""), str(tmp_path / "x")) is False   # no KDC: hands off


def test_patch_dhcp_authoritative(tmp_path):
    m = load_injector(tmp_path)
    for key, want in (("Dhcp4", True), ("Dhcp6", False)):
        p = tmp_path / (key + ".json")
        json.dump({key: {}}, open(p, "w"))
        m.patch_dhcp(str(p), key, dict(SETTINGS, authoritative=True))
        assert ("authoritative" in json.load(open(p))[key]) is want   # v4 only
    json.dump({"Dhcp4": {}}, open(p, "w"))
    m.patch_dhcp(str(p), "Dhcp4", SETTINGS)                    # option off -> key absent
    assert "authoritative" not in json.load(open(p))["Dhcp4"]


def test_disabled_plugin_yields_no_settings(tmp_path):
    m = load_injector(tmp_path)
    cfg = tmp_path / "config.xml"
    cfg.write_text("<opnsense><system><domain>x</domain></system></opnsense>")
    m.CONFIG = str(cfg)
    assert m.load_settings() is None


def test_qualifying_suffix_defaults_to_domain(tmp_path):
    m = load_injector(tmp_path)
    cfg = tmp_path / "config.xml"
    cfg.write_text(
        "<opnsense><system><domain>box.lan</domain></system>"
        "<OPNsense><KeaUnbound><general>"
        "<enabled>1</enabled><qualifying_suffix></qualifying_suffix>"
        "<tsig_enabled>1</tsig_enabled><tsig_key_secret>YWJjZA==</tsig_key_secret>"
        "</general></KeaUnbound></OPNsense></opnsense>"
    )
    m.CONFIG = str(cfg)
    s = m.load_settings()
    assert s is not None and s["suffix"] == "box.lan"
