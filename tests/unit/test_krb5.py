from lib import krb5


def test_parse_kdcs():
    assert krb5.parse_kdcs("10.0.0.1, dc02.example.com;10.0.0.1 bad/host") == [
        "10.0.0.1", "dc02.example.com"]
    assert krb5.parse_kdcs(None) == []


def test_render_krb5_conf():
    t = krb5.render_krb5_conf("AD.EXAMPLE.COM", ["10.0.0.1"], "ad.example.com")
    assert t.startswith(krb5.MARKER) and "dns_lookup_kdc = false" in t
    assert "kdc = 10.0.0.1" in t and "[domain_realm]" in t
    assert "[domain_realm]" not in krb5.render_krb5_conf("R", ["k"], "")
