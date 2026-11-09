import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load():
    spec = importlib.util.spec_from_file_location(
        "ktab", ROOT / "src/opnsense/scripts/keaunbound/keytab.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_is_keytab():
    m = load()
    assert m.is_keytab(b"\x05\x02" + b"x" * 20) and m.is_keytab(b"\x05\x01rest")
    assert not m.is_keytab(b"") and not m.is_keytab(b"\x05") and not m.is_keytab(b"hello")
    assert not m.is_keytab(b"\x05\x02" + b"x" * m.MAX_SIZE)       # too large


def test_parse_klist():
    m = load()
    out = ("Keytab name: FILE:/usr/local/etc/kea/dhcp.keytab\n"
           "KVNO Principal\n---- ----\n"
           "   3 DHCP/fw.ad.example.com@AD.EXAMPLE.COM\n"
           "   3 DHCP/fw.ad.example.com@AD.EXAMPLE.COM\n")
    assert m.parse_klist(out) == [{"kvno": 3, "principal": "DHCP/fw.ad.example.com@AD.EXAMPLE.COM"}]


def test_destination(tmp_path):
    m = load()
    def cfg(path):
        p = tmp_path / "c.xml"
        p.write_text("<opnsense><OPNsense><KeaUnbound><general><gss_keytab>%s</gss_keytab>"
                     "</general></KeaUnbound></OPNsense></opnsense>" % path)
        return str(p)
    assert m.destination(cfg("/usr/local/etc/kea/my.keytab")) == "/usr/local/etc/kea/my.keytab"
    assert m.destination(cfg("/etc/passwd")) == m.DEFAULT            # outside /usr/local/etc/
    assert m.destination(cfg("/usr/local/etc/../../etc/x")) == m.DEFAULT
    assert m.destination(str(tmp_path / "missing.xml")) == m.DEFAULT


def test_install_rejects_bad_paths_and_content(tmp_path, monkeypatch):
    m = load()
    assert m.install("/etc/passwd")["status"] == "error"             # not an upload path
    up = tmp_path / "keaunbound-keytab-abc123"
    monkeypatch.setattr(m, "UPLOAD_RE", __import__("re").compile(r".*/keaunbound-keytab-[A-Za-z0-9]+$"))
    up.write_bytes(b"not a keytab")
    assert "keytab" in m.install(str(up))["message"] and not up.exists()   # removed anyway
    dest = tmp_path / "kea" / "dhcp.keytab"
    monkeypatch.setattr(m, "destination", lambda *a: str(dest))
    up.write_bytes(b"\x05\x02" + b"k" * 40)
    assert m.install(str(up)) == {"status": "ok", "path": str(dest)}
    assert oct(dest.stat().st_mode & 0o777) == "0o600" and not up.exists()
